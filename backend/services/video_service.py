"""Frame-by-frame video processing for detection and ByteTrack tracking jobs.

Videos are streamed with ``cv2.VideoCapture`` — only the current frame is in
memory at any time, never the whole file. Each job runs in a background
thread; the frontend polls ``GET /api/results/<job_id>`` for progress.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2

import config
from services.detection_service import draw_detections
from services.model_service import ModelNotLoadedError, get_model_service
from services.tracking_service import (
    TRAJECTORY_MAX_POINTS,
    BYTETRACK_NOTE,
    draw_trajectories,
    summarize_tracks,
)

logger = logging.getLogger(__name__)


@dataclass
class VideoJob:
    job_id: str
    kind: str  # "detect" | "track"
    filename: str
    params: dict
    status: str = "queued"  # queued | processing | completed | failed
    progress: float | None = None
    frames_processed: int = 0
    total_frames: int | None = None
    error: str | None = None
    output_filename: str | None = None
    stats: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict:
        output = None
        if self.output_filename:
            output = {"filename": self.output_filename, "url": f"/api/outputs/{self.output_filename}"}
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "filename": self.filename,
            "params": self.params,
            "status": self.status,
            "progress": self.progress,
            "frames_processed": self.frames_processed,
            "total_frames": self.total_frames,
            "error": self.error,
            "output": output,
            "stats": self.stats,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class JobStore:
    """In-memory job registry (thread-safe)."""

    def __init__(self):
        self._jobs: dict[str, VideoJob] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, filename: str, params: dict) -> VideoJob:
        job = VideoJob(job_id=uuid.uuid4().hex[:12], kind=kind, filename=filename, params=params)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> VideoJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 20, kind: str | None = None, status: str | None = None) -> list[VideoJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[: max(1, min(limit, 100))]


job_store = JobStore()


class VideoProcessor:
    """Runs video jobs on worker threads."""

    def submit(self, job: VideoJob, input_path: Path) -> None:
        thread = threading.Thread(target=self._run, args=(job, input_path), daemon=True, name=f"video-{job.job_id}")
        thread.start()

    def _run(self, job: VideoJob, input_path: Path) -> None:
        try:
            self._process(job, input_path)
        except ModelNotLoadedError as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = time.time()
        except Exception as exc:  # noqa: BLE001 - report the real error to the UI
            logger.exception("Video job %s failed", job.job_id)
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = time.time()

    # ------------------------------------------------------------------
    def _process(self, job: VideoJob, input_path: Path) -> None:
        service = get_model_service()
        service.require_model()

        job.status = "processing"
        track = job.kind == "track"
        conf = job.params.get("conf", config.DEFAULT_CONF)
        iou = job.params.get("iou", config.DEFAULT_IOU)
        imgsz = job.params.get("imgsz", config.DEFAULT_IMGSZ)

        capture = cv2.VideoCapture(str(input_path))
        if not capture.isOpened():
            raise ValueError(
                "Could not open the video file — the codec may be unsupported by OpenCV on this machine. "
                "Re-encode to MP4 (H.264) and try again."
            )
        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or None
            if width <= 0 or height <= 0:
                ok, frame = capture.read()
                if not ok:
                    raise ValueError("The video contains no readable frames.")
                height, width = frame.shape[:2]
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            job.total_frames = total

            raw_path = config.OUTPUT_DIR / f"{job.job_id}_raw.mp4"
            writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            if not writer.isOpened():
                raise ValueError("OpenCV could not create the output video writer (mp4v codec).")

            per_class: Counter = Counter()
            track_registry: dict = {}
            trajectories = defaultdict(lambda: deque(maxlen=TRAJECTORY_MAX_POINTS))
            unique_ids: set = set()
            started = time.perf_counter()
            inference_ms_total = 0.0
            frame_index = 0

            try:
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    if track:
                        result, elapsed = service.predict(
                            frame, conf=conf, iou=iou, imgsz=imgsz, tracker="bytetrack.yaml", persist=True
                        )
                    else:
                        result, elapsed = service.predict(frame, conf=conf, iou=iou, imgsz=imgsz)
                    inference_ms_total += elapsed

                    detections = service.parse_boxes(result)
                    active_ids = []
                    for det in detections:
                        per_class[det["class_name"]] += 1
                        tid = det.get("track_id")
                        if tid is not None:
                            unique_ids.add(tid)
                            active_ids.append(tid)
                            entry = track_registry.setdefault(
                                tid,
                                {"track_id": tid, "class_name": det["class_name"], "frames": 0, "conf_sum": 0.0},
                            )
                            entry["frames"] += 1
                            entry["conf_sum"] += det["confidence"]
                            center = (
                                (det["bbox"][0] + det["bbox"][2]) / 2,
                                (det["bbox"][1] + det["bbox"][3]) / 2,
                            )
                            trajectories[tid].append(center)

                    annotated = draw_detections(frame, detections)
                    if track:
                        annotated = draw_trajectories(annotated, trajectories, active_ids)
                    writer.write(annotated)

                    frame_index += 1
                    job.frames_processed = frame_index
                    if total:
                        job.progress = round(100.0 * frame_index / total, 1)
            finally:
                capture.release()
                writer.release()

            if frame_index == 0:
                raise ValueError("No frames could be read from the video.")

            elapsed_total = time.perf_counter() - started
            output_filename = self._finalize_output(raw_path, job.job_id)

            job.output_filename = output_filename
            job.stats = {
                "per_class": dict(sorted(per_class.items(), key=lambda kv: -kv[1])),
                "unique_track_ids": len(unique_ids) if track else None,
                "tracks": summarize_tracks(track_registry) if track else None,
                "trajectories": {
                    str(tid): [[round(x, 1), round(y, 1)] for x, y in pts] for tid, pts in trajectories.items()
                }
                if track
                else None,
                "avg_inference_ms": round(inference_ms_total / frame_index, 1),
                "processing_fps": round(frame_index / elapsed_total, 2) if elapsed_total > 0 else None,
                "video_fps": round(fps, 2),
                "width": width,
                "height": height,
                "bytetrack_note": BYTETRACK_NOTE if track else None,
            }
            job.status = "completed"
            job.progress = 100.0
            job.completed_at = time.time()
            logger.info("Video job %s completed: %d frames in %.1fs", job.job_id, frame_index, elapsed_total)
        finally:
            capture.release()
            try:
                Path(input_path).unlink(missing_ok=True)  # temp upload cleanup
            except OSError:
                pass

    @staticmethod
    def _finalize_output(raw_path: Path, job_id: str) -> str:
        """Re-encode to H.264 for browser playback when ffmpeg is available."""
        final_path = config.OUTPUT_DIR / f"{job_id}.mp4"
        if shutil.which("ffmpeg"):
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(raw_path),
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(final_path),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=1800)
            if result.returncode == 0:
                raw_path.unlink(missing_ok=True)
                return final_path.name
            logger.warning("ffmpeg re-encode failed (rc=%s); serving OpenCV mp4v output", result.returncode)
        raw_path.replace(final_path)
        return final_path.name


video_processor = VideoProcessor()
