# Architecture

## 1. System overview

The system is split into a **perception backend** (Python/Flask, all AI work),
a **dashboard frontend** (React/Vite, pure client), and two **optional
simulation front-ends** (CARLA bridge inside the backend, ROS2 node outside
it). Every AI result originates from the user-trained YOLO checkpoint
(`backend/models/best.pt`) or from classical OpenCV/MiDaS pipelines — no
component fabricates detections or metrics.

```
                        ┌────────────────────────────────────────────────┐
                        │                   Browser                      │
                        │   React + Vite dashboard (10 pages, Recharts)  │
                        └───────────────▲────────────────────────────────┘
                                        │  REST / JSON + JPEG (fetch / XHR)
                        ┌───────────────┴────────────────────────────────┐
                        │              Flask backend :5000               │
   uploads ───────────► │  routes/ (blueprints)  →  services/            │
                        │  ┌──────────────────────────────────────────┐  │
                        │  │ model_service      YOLO best.pt (once)   │  │
                        │  │ detection_service  draw / encode         │  │
                        │  │ video_service      frame-loop jobs       │  │
                        │  │ tracking_service   ByteTrack trails      │  │
                        │  │ lane_service       Canny→ROI→Hough       │  │
                        │  │ deep_lane_service  ENet (user-trained)   │  │
                        │  │ depth_service      MiDaS via torch.hub   │  │
                        │  │ performance_service results.csv / bench  │  │
                        │  │ simulation_service CARLA bridge          │  │
                        │  └──────────────────────────────────────────┘  │
                        │  outputs/ (annotated media) · job registry     │
                        └───────┬───────────────────────────▲────────────┘
                                │                           │ camera frames
                     ┌──────────▼─────────┐        ┌────────┴───────────┐
                     │  CARLA simulator   │        │  ROS 2 graph       │
                     │  (server :2000)    │        │  perception_node   │
                     └────────────────────┘        └────────────────────┘
```

## 2. Component responsibilities

| Component | Responsibility | Key files |
| --- | --- | --- |
| Model service | Loads `best.pt` exactly once at startup; GPU/CPU selection; exposes `predict()` with an inference lock; reports honest `missing`/`error` states | `backend/services/model_service.py` |
| Detection service | Decodes uploads, runs inference, draws boxes/labels, JPEG + data-URL encoding | `backend/services/detection_service.py` |
| Video service | Background job threads; streams MP4/AVI/MOV frame-by-frame through YOLO; writes annotated MP4; ffmpeg re-encode for browser playback; progress tracking | `backend/services/video_service.py` |
| Tracking service | ByteTrack visualization: fading trajectory trails, per-ID summaries | `backend/services/tracking_service.py` |
| Lane service | Classical OpenCV pipeline + lane-centre offset estimation | `backend/services/lane_service.py` |
| Deep lane service | ENet segmentation comparison; loads **only** the user-trained checkpoint, labelled `trained_by_me` or `not_available` | `backend/services/deep_lane_service.py` |
| Depth service | MiDaS relative depth (torch.hub, cached in `models/midas_cache`), object-level medians | `backend/services/depth_service.py` |
| Performance service | Reads real metrics from checkpoint `train_metrics` / `results.csv`; measures latency/FPS on this machine | `backend/services/performance_service.py` |
| Simulation service | Spawns CARLA ego vehicle + camera, perception loop → latest annotated JPEG | `backend/services/simulation_service.py` |
| Routes | Request validation, HTTP envelopes, error mapping (503 for unavailable models) | `backend/routes/*.py` |
| Frontend | 10 pages, dropzones, polling progress, Recharts over real job/metric data | `frontend/src/` |

## 3. Data flow — image detection

1. The browser POSTs `multipart/form-data` (`image`, `conf`, `iou`, `imgsz`) to `/api/detect/image`.
2. The route validates extension/size, decodes with OpenCV and calls `detection_service.detect_image`.
3. `model_service.predict()` acquires the inference lock and runs `YOLO.predict(source=frame, device=cuda|cpu)`.
4. Boxes are parsed to plain JSON; annotations are drawn with OpenCV; both original and annotated images are returned as data URLs (plus a downloadable copy in `outputs/`).

## 4. Data flow — video job lifecycle

1. `POST /api/detect/video` (or `/api/track/video`) saves the upload under `backend/uploads/` with a UUID name and creates a `VideoJob` in the in-memory registry (HTTP 202).
2. A daemon thread streams frames via `cv2.VideoCapture` — one frame in memory at a time. For tracking, `predict(tracker="bytetrack.yaml", persist=True)` keeps IDs across frames; trajectories (last 90 centres) are drawn as fading trails.
3. Frames are written with `cv2.VideoWriter`; progress (`frames_processed`, `progress %`) is updated every frame and polled by the frontend via `GET /api/results/<job_id>`.
4. On completion the raw mp4v file is re-encoded to H.264 with ffmpeg (when available) for native browser playback; the upload is deleted. Jobs older than 6 hours are removed by the cleanup daemon.

## 5. CARLA bridge and ROS2 node

* **Backend bridge** (`simulation_service.py`): `POST /api/simulation/connect` spawns a Tesla Model 3 with autopilot + an RGB camera (960×540, FOV 90). Camera callbacks push frames into a 2-slot queue; a perception thread runs YOLO + lanes on each and stores the latest JPEG, served by `GET /api/simulation/frame`. Without the `carla` package or a running server, every endpoint returns 503 with setup instructions — the UI never shows simulated frames.
* **Standalone agent** (`simulation/carla_perception_agent.py`): the same loop as a desktop app with an OpenCV window, writing annotated MP4s.
* **ROS2 node** (`simulation/ros2/perception_node.py`): `rclpy` node subscribing to `sensor_msgs/Image`, publishing `vision_msgs/Detection2DArray` and an annotated image topic; parameters for model path/confidence. Purely separate Python module — the website only reports its availability.

## 6. Design decisions

* **No fake AI.** Missing weights ⇒ `model.status = "missing"` and HTTP 503 from every inference endpoint with instructions; missing metrics ⇒ "Not available"; missing CARLA ⇒ status page with steps. Nothing is simulated.
* **Lazy heavy imports.** `torch`/`ultralytics`/`carla`/`rclpy` are imported inside the functions that need them, so the API server starts (and reports status) even on machines without them.
* **One-shot model load.** A thread-safe singleton prevents double-loading; an RLock serialises GPU access between concurrent HTTP requests and video jobs.
* **Streaming, not buffering.** Videos are processed frame-by-frame; uploads/outputs are auto-cleaned; the job registry is in-memory (restart clears it — results files stay on disk until cleanup).
* **Consistent API envelope.** `{success, data}` / `{success, error:{code, message, instructions?}}` everywhere, so the frontend renders one error component with actionable checklists.
