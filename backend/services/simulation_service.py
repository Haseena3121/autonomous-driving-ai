"""Optional CARLA simulator bridge used by the Simulation page.

When a CARLA server (e.g. ``./CarlaUE4.sh``) is running and the ``carla``
Python package is installed, ``connect()`` spawns an ego vehicle with an RGB
camera and runs the real perception stack (trained YOLO + OpenCV lanes) on the
live feed inside a background thread. The latest annotated JPEG is served to
the website through ``/api/simulation/frame``.

If CARLA is not installed or the server is offline, every call reports the
honest reason — the website never fabricates simulation frames.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

import cv2
import numpy as np

import config
from services.detection_service import draw_detections, encode_jpeg
from services.lane_service import LaneDetectionService
from services.model_service import get_model_service

logger = logging.getLogger(__name__)

INSTRUCTIONS = [
    "1. Install the CARLA simulator (0.9.15 recommended): https://carla.org — extract the package.",
    '2. Start the server in a terminal:  ./CarlaUE4.sh   (Linux)  or  CarlaUE4.exe  (Windows).',
    "3. Install the Python client matching your CARLA version:  pip install carla==0.9.15",
    "4. Start this Flask backend, then press 'Connect' here (host 127.0.0.1, port 2000).",
    "Note: the first frames can take a few seconds while the vehicle and camera spawn.",
]


class CarlaPerceptionService:
    """Bridges a live CARLA camera into the perception pipeline."""

    def __init__(self):
        self._lock = threading.Lock()
        self.connected = False
        self.host: str | None = None
        self.port: int | None = None
        self.server_version: str | None = None
        self.vehicle_id: str | None = None
        self.camera_active = False
        self.perception_fps = 0.0
        self.last_meta: dict = {}
        self.last_error: str | None = None

        self._client = None
        self._vehicle = None
        self._sensor = None
        self._frames: queue.Queue = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._latest_jpeg: bytes | None = None
        self.lane_service = LaneDetectionService()

        try:
            import carla  # noqa: F401

            self.carla_installed = True
        except ImportError:
            self.carla_installed = False

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        return {
            "carla_installed": self.carla_installed,
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "server_version": self.server_version,
            "vehicle_id": self.vehicle_id,
            "camera_active": self.camera_active,
            "perception_fps": round(self.perception_fps, 1),
            "last_meta": self.last_meta,
            "last_error": self.last_error,
            "model_loaded": get_model_service().is_loaded,
            "message": self._message(),
            "instructions": INSTRUCTIONS,
        }

    def _message(self) -> str:
        if self.connected:
            return (
                f"Connected to CARLA {self.server_version} at {self.host}:{self.port}. "
                "Live perception feed is streaming below."
            )
        if not self.carla_installed:
            return 'The "carla" Python package is not installed in this environment. Follow the steps below to enable the live simulation.'
        if self.last_error:
            return f"Last connection attempt failed: {self.last_error}"
        return "CARLA client available but not connected. Start a CARLA server and press Connect."

    # ---------------------------------------------------------------- connect
    def connect(self, host: str = "127.0.0.1", port: int = 2000) -> dict:
        if not self.carla_installed:
            raise RuntimeError(
                'The "carla" Python package is not installed. Run: pip install carla==0.9.15 '
                "(version must match your CARLA simulator)."
            )
        import carla

        with self._lock:
            if self.connected:
                return self.status()
            self.last_error = None
            try:
                client = carla.Client(host, port)
                client.set_timeout(10.0)
                self.server_version = client.get_server_version()  # raises if server offline
                world = client.get_world()

                blueprint_library = world.get_blueprint_library()
                vehicle_bp = blueprint_library.find("vehicle.tesla.model3")
                spawn_points = world.get_map().get_spawn_points()
                if not spawn_points:
                    raise RuntimeError("The CARLA map has no spawn points.")
                vehicle = None
                for spawn_point in spawn_points[:10]:
                    try:
                        vehicle = world.spawn_actor(vehicle_bp, spawn_point)
                        break
                    except RuntimeError:
                        continue
                if vehicle is None:
                    raise RuntimeError("Could not spawn the ego vehicle (all spawn points blocked).")
                vehicle.set_autopilot(True)

                camera_bp = blueprint_library.find("sensor.camera.rgb")
                camera_bp.set_attribute("image_size_x", "960")
                camera_bp.set_attribute("image_size_y", "540")
                camera_bp.set_attribute("fov", "90")
                camera_transform = carla.Transform(carla.Location(x=1.6, z=2.4))
                sensor = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)
                sensor.listen(self._on_frame)

                self._client = client
                self._vehicle = vehicle
                self._sensor = sensor
                self.vehicle_id = vehicle.id
                self.host, self.port = host, port
                self.camera_active = True
                self.connected = True
                self._stop.clear()
                self._worker = threading.Thread(target=self._loop, daemon=True, name="carla-perception")
                self._worker.start()
                logger.info("CARLA connected: server=%s vehicle=%s", self.server_version, vehicle.id)
            except Exception as exc:  # noqa: BLE001 - surface the real reason to the UI
                self.last_error = str(exc)
                self._teardown()
                raise
            return self.status()

    def disconnect(self) -> None:
        with self._lock:
            self._teardown()
        logger.info("CARLA disconnected")

    def _teardown(self) -> None:
        self._stop.set()
        if self._sensor is not None:
            try:
                self._sensor.stop()
                self._sensor.destroy()
            except Exception:  # pragma: no cover
                pass
        if self._vehicle is not None:
            try:
                self._vehicle.destroy()
            except Exception:  # pragma: no cover
                pass
        self._sensor = None
        self._vehicle = None
        self._client = None
        self.connected = False
        self.camera_active = False
        self.vehicle_id = None
        self._latest_jpeg = None
        self.last_meta = {}

    # ------------------------------------------------------------- camera cb
    def _on_frame(self, sensor_image) -> None:
        """CARLA camera callback: BGRA buffer -> BGR numpy frame."""
        array = np.frombuffer(sensor_image.raw_data, dtype=np.uint8)
        array = array.reshape((sensor_image.height, sensor_image.width, 4))[:, :, :3][:, :, ::-1]
        frame = np.ascontiguousarray(array)
        try:
            self._frames.put_nowait(frame)
        except queue.Full:
            try:
                self._frames.get_nowait()
                self._frames.put_nowait(frame)
            except queue.Empty:
                pass

    # ------------------------------------------------------------ perception
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                frame = self._frames.get(timeout=0.5)
            except queue.Empty:
                continue
            started = time.perf_counter()
            annotated, meta = self._perceive(frame)
            self._latest_jpeg = encode_jpeg(annotated, quality=82)
            elapsed = time.perf_counter() - started
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            self.perception_fps = self.perception_fps * 0.8 + fps * 0.2 if self.perception_fps else fps
            self.last_meta = meta

    def _perceive(self, frame):
        """Run the real trained YOLO + lane detection on one live frame."""
        model_service = get_model_service()
        meta = {"model_loaded": model_service.is_loaded, "detections": 0, "inference_ms": None, "lane_offset_px": None}
        annotated, _, lane_meta = self.lane_service.detect(frame)
        meta["lane_offset_px"] = lane_meta.get("offset_px")
        if model_service.is_loaded:
            try:
                result, elapsed_ms = model_service.predict(frame, conf=config.DEFAULT_CONF, iou=config.DEFAULT_IOU)
                detections = model_service.parse_boxes(result)
                annotated = draw_detections(annotated, detections)
                meta["detections"] = len(detections)
                meta["inference_ms"] = round(elapsed_ms, 1)
                meta["classes"] = sorted({d["class_name"] for d in detections})
            except Exception as exc:  # noqa: BLE001
                meta["detection_error"] = str(exc)
        return annotated, meta

    # ----------------------------------------------------------------- frame
    def get_frame(self):
        with self._lock:
            return self._latest_jpeg, dict(self.last_meta)


def get_simulation_service() -> CarlaPerceptionService:
    global _simulation_service
    if _simulation_service is None:
        _simulation_service = CarlaPerceptionService()
    return _simulation_service


_simulation_service: CarlaPerceptionService | None = None
