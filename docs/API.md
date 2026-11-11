# REST API reference

Base URL: `http://localhost:5000`

All responses use one envelope:

```json
{ "success": true,  "data": { ... } }
{ "success": false, "error": { "code": "...", "message": "...", "instructions": ["..."] } }
```

Errors: `400` invalid input/file · `404` unknown resource · `413` upload too
large · `503` model/module genuinely unavailable (missing `best.pt`, MiDaS not
downloadable, CARLA offline) — the app never returns fake data instead of an
error.

---

## GET /api/health

Liveness plus a compact model summary.

```json
{
  "success": true,
  "data": {
    "status": "ok", "service": "autonomous-driving-api", "version": "1.0.0",
    "uptime_s": 128.4,
    "model": { "status": "loaded", "device": "cuda:0", "class_count": 10, "message": "..." }
  }
}
```

## GET /api/model/info

Full checkpoint report: `status`, `model_path`, `model_exists`, `file_size_mb`,
`model_type` (task), `framework`, `ultralytics_version`, `torch_version`,
`cuda_available`, `device`, `device_name`, `class_count`, `classes`
(`[{id, name}]`), `imgsz`, `parameters_million`, `gflops`,
`training_metadata` (embedded train args), `loaded_at`, `load_time_ms`.

## POST /api/model/reload

Re-reads `backend/models/best.pt` (force reload). Returns the same payload as
`/api/model/info`. Use after adding/replacing weights without restarting.

## POST /api/detect/image

`multipart/form-data`: `image` (png/jpg/jpeg/bmp/webp ≤16 MB), optional
`conf` (0.05–0.95, default 0.25), `iou` (0.1–0.9, default 0.45), `imgsz`
(320–1536, default 640).

```json
{
  "success": true,
  "data": {
    "total": 7,
    "detections": [
      { "class_id": 2, "class_name": "car", "confidence": 0.9123,
        "bbox": [412.5, 233.0, 733.2, 415.8], "track_id": null }
    ],
    "stats": { "total": 7, "per_class": {"car": 5, "person": 2}, "class_count": 2, "avg_confidence": 0.7718 },
    "inference_ms": 24.6,
    "device": "cuda:0",
    "image": { "width": 1280, "height": 720 },
    "original_image": "data:image/jpeg;base64,…",
    "annotated_image": "data:image/jpeg;base64,…",
    "annotated_url": "/api/outputs/9f2c….jpg"
  }
}
```

## POST /api/detect/video — start job

`multipart/form-data`: `video` (mp4/avi/mov/mkv ≤200 MB), `conf`, `iou`,
`imgsz`. Returns **202** with a job object; processing runs on a background
thread (frame-by-frame, constant memory).

```json
{ "success": true, "data": { "job_id": "6f1a9c0d2e4b", "kind": "detect", "status": "queued", "progress": null, "output": null, "stats": {} } }
```

## POST /api/track/video — start job

Same fields as above; runs YOLO + ByteTrack (`persist=True`). Job `kind` is
`"track"` and the final stats include `unique_track_ids`, `tracks`
(`[{track_id, class_name, frames, avg_confidence}]`) and `trajectories`.

## GET /api/results?limit=20&kind=&status=

List recent jobs (newest first). `kind`: `detect|track`, `status`:
`queued|processing|completed|failed`.

## GET /api/results/{job_id}

Poll one job. `status` transitions: `queued → processing → completed | failed`.

```json
{
  "success": true,
  "data": {
    "job_id": "6f1a9c0d2e4b", "kind": "track", "status": "completed",
    "progress": 100.0, "frames_processed": 812, "total_frames": 812,
    "output": { "filename": "6f1a9c0d2e4b.mp4", "url": "/api/outputs/6f1a9c0d2e4b.mp4" },
    "stats": {
      "per_class": {"car": 2140, "person": 388},
      "unique_track_ids": 9,
      "tracks": [{ "track_id": 1, "class_name": "car", "frames": 640, "avg_confidence": 0.86 }],
      "avg_inference_ms": 21.3, "processing_fps": 31.7, "video_fps": 30.0,
      "width": 1280, "height": 720
    },
    "error": null, "created_at": 1730000000.1, "completed_at": 1730000031.4
  }
}
```

## POST /api/lane/detect

`multipart/form-data`: `image`, optional `canny_low` (default 50),
`canny_high` (default 150), `steps` (`1`/`0`, include Canny + ROI previews).

```json
{
  "success": true,
  "data": {
    "meta": {
      "hough_segments": 14, "lanes_detected": "both",
      "left_line":  { "slope_xy": -2.31, "x_at_bottom": 268.4, "x_at_top": 382.1 },
      "right_line": { "slope_xy": 2.05,  "x_at_bottom": 986.7, "x_at_top": 881.3 },
      "lane_center_px": 627.6, "image_center_px": 640.0,
      "offset_px": -12.4, "offset_direction": "left",
      "note": "offset_px > 0 means the estimated lane centre sits right of the image centre."
    },
    "annotated_image": "data:image/jpeg;base64,…",
    "annotated_url": "/api/outputs/….jpg",
    "steps": { "edges": "data:…", "roi": "data:…" }
  }
}
```

## POST /api/lane/deep

`multipart/form-data`: `image`, `threshold` (default 0.5). Runs the ENet
segmentation comparison. Response `status.mode` is `"trained_by_me"` when your
checkpoint (`backend/models/lane_seg_enet.pth`) is loaded; otherwise the
endpoint returns **503** `LANE_MODEL_UNAVAILABLE` with training instructions.

## POST /api/depth/estimate

`multipart/form-data`: `image`, `with_objects` (default `1`). MiDaS relative
depth + YOLO object scores. Response contains `depth_image` (colour-mapped
data URL), `objects: [{class_name, confidence, relative_depth}]` sorted
closest-first, `depth_range`, `inference_ms`, and the standing `disclaimer`
(relative depth ≠ metres). First call downloads MiDaS (~70 MB) into
`backend/models/midas_cache/`.

## GET /api/performance

```json
{
  "success": true,
  "data": {
    "training_metrics": { "precision": 0.7543, "recall": 0.6612, "map50": 0.7205,
                          "map50_95": 0.5120, "epoch": 42, "total_epochs": 50,
                          "source": "results.csv (results.csv)" },
    "training_config": { "data": "bdd100k.yaml", "epochs": 50, "imgsz": 640, "batch": 16 },
    "model": { "path": "…/backend/models/best.pt", "exists": true, "size_mb": 22.5, "type": "detect" },
    "device": "cuda:0", "device_name": "NVIDIA GeForce RTX …",
    "cuda_available": true, "ultralytics_version": "8.3.x", "torch_version": "2.x.x",
    "imgsz": 640, "benchmark": null,
    "metrics_note": null
  }
}
```

`training_metrics` is `null` when no checkpoint metrics and no
`backend/models/results.csv` exist — the UI then shows "Not available". Values
are read from the files, never invented.

## POST /api/performance/benchmark

JSON body `{ "runs": 10, "imgsz": 640 }` (optional). Warms up 3× then measures
each inference on a 1280×720 probe frame **on this machine**:

```json
{ "success": true, "data": { "device": "cuda:0", "runs_ms": [23.4, 22.9], "avg_ms": 23.1,
  "min_ms": 22.6, "max_ms": 24.0, "fps": 43.3, "model_size_mb": 22.5, "note": "Measured on this machine…" } }
```

## GET /api/outputs/{filename}?download=1

Serves annotated results from `backend/outputs/` (`download=1` forces the
browser to save instead of play).

## GET /api/simulation/status · POST /api/simulation/connect · POST /api/simulation/disconnect · GET /api/simulation/frame

CARLA bridge control. `connect` takes JSON `{"host": "127.0.0.1", "port":
2000}`; on failure returns 503 `CARLA_UNAVAILABLE` with step-by-step
`instructions`. `frame` returns the latest annotated JPEG (960×540) or 503
`NO_FRAME`.

## GET /api/ros2/status

Reports whether `rclpy` is importable in the backend environment and where the
separate node lives (`simulation/ros2/perception_node.py`).
