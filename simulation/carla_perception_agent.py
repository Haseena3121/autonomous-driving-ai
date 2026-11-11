#!/usr/bin/env python3
"""Standalone CARLA perception agent (desktop version of the website bridge).

Connects to a running CARLA simulator, spawns an ego vehicle with an RGB
camera and runs the SAME perception stack as the website: your trained YOLO
model + ByteTrack + the OpenCV lane pipeline. Annotated frames are shown in an
OpenCV window and written to backend/outputs/.

Usage:
    # 1) start the simulator first, e.g.:  ./CarlaUE4.sh
    # 2) install the matching client:      pip install carla==0.9.15
    python carla_perception_agent.py --host 127.0.0.1 --port 2000 \
        --model ../backend/models/best.pt
"""

import argparse
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import cv2  # noqa: E402
import numpy as np  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--model", type=Path, default=BACKEND_DIR / "models" / "best.pt")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--no-track", action="store_true", help="disable ByteTrack trails")
    parser.add_argument("--record", type=Path, default=None, help="write annotated MP4 here (default: backend/outputs/carla_perception.mp4)")
    parser.add_argument("--max-frames", type=int, default=1800, help="recording length cap")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import carla
    except ImportError as exc:
        print(f'The "carla" client package is not installed ({exc}).')
        print("Install the version matching your simulator: pip install carla==0.9.15")
        return 1

    from services.detection_service import draw_detections
    from services.lane_service import LaneDetectionService
    from services.model_service import ModelService
    from services.tracking_service import TRAJECTORY_MAX_POINTS, draw_trajectories

    if not args.model.exists():
        print(f"Weights not found: {args.model}\nPlace your trained best.pt there first (see model_training/README.md).")
        return 1

    print(f"Connecting to CARLA at {args.host}:{args.port} …")
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    print(f"Server version: {client.get_server_version()}")
    world = client.get_world()

    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.find("vehicle.tesla.model3")
    vehicle = None
    for spawn_point in world.get_map().get_spawn_points()[:10]:
        try:
            vehicle = world.spawn_actor(vehicle_bp, spawn_point)
            break
        except RuntimeError:
            continue
    if vehicle is None:
        print("Could not spawn a vehicle — all spawn points blocked. Retry in a new map/episode.")
        return 1
    vehicle.set_autopilot(True)

    camera_bp = blueprint_library.find("sensor.camera.rgb")
    camera_bp.set_attribute("image_size_x", "960")
    camera_bp.set_attribute("image_size_y", "540")
    camera_bp.set_attribute("fov", "90")
    camera = world.spawn_actor(
        camera_bp, carla.Transform(carla.Location(x=1.6, z=2.4)), attach_to=vehicle
    )

    model_service = ModelService()
    print(f"Loading weights {args.model} …")
    model_service.load(args.model)
    if not model_service.is_loaded:
        print(model_service.message)
        camera.destroy()
        vehicle.destroy()
        return 1

    lane_service = LaneDetectionService()
    trajectories = defaultdict(lambda: deque(maxlen=TRAJECTORY_MAX_POINTS))

    frame_q = []

    def on_frame(sensor_image):
        array = np.frombuffer(sensor_image.raw_data, dtype=np.uint8)
        array = array.reshape((sensor_image.height, sensor_image.width, 4))[:, :, :3][:, :, ::-1]
        frame_q.append(np.ascontiguousarray(array))
        if len(frame_q) > 2:  # keep only the freshest frames
            frame_q.pop(0)

    camera.listen(on_frame)

    record_path = args.record or (BACKEND_DIR / "outputs" / "carla_perception.mp4")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    saved = 0
    print("\nPerception loop running — press Q in the preview window (or Ctrl+C) to stop.\n")

    try:
        while True:
            if not frame_q:
                time.sleep(0.01)
                continue
            frame = frame_q.pop(0)
            annotated, _, lane_meta = lane_service.detect(frame)

            if args.no_track:
                result, _ = model_service.predict(frame, conf=args.conf)
                detections = model_service.parse_boxes(result)
                active_ids = []
            else:
                result, _ = model_service.predict(
                    frame, conf=args.conf, tracker="bytetrack.yaml", persist=True
                )
                detections = model_service.parse_boxes(result)
                active_ids = []
                for det in detections:
                    tid = det.get("track_id")
                    if tid is None:
                        continue
                    active_ids.append(tid)
                    center = ((det["bbox"][0] + det["bbox"][2]) / 2, (det["bbox"][1] + det["bbox"][3]) / 2)
                    trajectories[tid].append(center)

            annotated = draw_detections(annotated, detections)
            if active_ids:
                annotated = draw_trajectories(annotated, trajectories, active_ids)

            if writer is None:
                writer = cv2.VideoWriter(str(record_path), cv2.VideoWriter_fourcc(*"mp4v"), 20.0, (annotated.shape[1], annotated.shape[0]))
            if saved < args.max_frames:
                writer.write(annotated)
                saved += 1

            offset = lane_meta.get("offset_px")
            hud = f"objects: {len(detections)} | lane offset: {offset if offset is not None else '—'} px"
            cv2.putText(annotated, hud, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow("ADAS perception (Q to quit)", annotated)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if writer is not None:
            writer.release()
        camera.stop()
        camera.destroy()
        vehicle.destroy()
        print(f"\nSaved {saved} annotated frames to {record_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
