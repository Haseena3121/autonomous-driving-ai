# AI-Based Autonomous Driving System — Project Documentation

This document contains the complete system architecture, installation guide, API reference, perception modules, and troubleshooting guide for the AI-Based Autonomous Driving System.

---

## 1. System Overview & Architecture

The system is a production-grade autonomous driving perception stack and dashboard composed of:
* **Frontend:** React 18, Vite 5, React Router 6, Recharts, Dark/Blue Automotive HUD styling.
* **Backend:** Python 3, Flask REST API, Flask-CORS, OpenCV, NumPy.
* **AI & Computer Vision Engines:**
  * **Object Detection:** Ultralytics YOLO (`backend/models/best.pt`), trained on BDD100K.
  * **Multi-Object Tracking:** ByteTrack (`tracker="bytetrack.yaml"`, `persist=True`) with motion trajectory history.
  * **Lane Detection:** Classical OpenCV pipeline (Grayscale → Gaussian Blur → Canny Edge → Region of Interest (ROI) Mask → Probabilistic Hough Transform → Lane Polynomial Fit & Steering Offset) and optional deep segmentation (ENet).
  * **Depth Estimation:** MiDaS relative monocular depth estimation via `torch.hub`, overlaid with bounding box depth scoring.
  * **Simulation:** CARLA simulator Python API bridge with live camera feed streaming + ROS 2 perception node.

### Directory Structure

```
autonomous-driving-ai/
├── frontend/                     # React + Vite web dashboard
│   ├── src/
│   │   ├── components/           # Reusable UI widgets (Layout, Sidebar, TopBar, Dropzone, Tables)
│   │   ├── pages/                # Dashboard perception modules and chatbox
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ObjectDetection.jsx
│   │   │   ├── VideoAnalysis.jsx
│   │   │   ├── ObjectTracking.jsx
│   │   │   ├── LaneDetection.jsx
│   │   │   ├── DepthEstimation.jsx
│   │   │   ├── DrivingSimulation.jsx
│   │   │   ├── ModelPerformance.jsx
│   │   │   └── DoubtsChatbox.jsx
│   │   └── services/api.js       # REST client
│   ├── package.json
│   └── vite.config.js
├── backend/                      # Flask REST API
│   ├── app.py                    # Application factory & startup model loading
│   ├── config.py                 # Paths, limits, thresholds, CORS
│   ├── requirements.txt          # Python packages (torch, ultralytics, opencv, flask...)
│   ├── models/                   # Place your trained best.pt here
│   ├── routes/                   # REST blueprints (/api/*)
│   │   ├── core_routes.py
│   │   ├── detection_routes.py
│   │   ├── tracking_routes.py
│   │   ├── lane_routes.py
│   │   ├── depth_routes.py
│   │   ├── simulation_routes.py
│   │   └── chat_routes.py
│   └── services/                 # Computer vision & model inference logic
├── model_training/               # Colab notebook, BDD100K converter, YAML configs
├── simulation/                   # CARLA autonomous agent & ROS 2 node
├── docs/                         # Project & Model documentation
│   ├── PROJECT_DOCUMENTATION.md
│   ├── MODEL_INFORMATION.md
│   ├── API.md
│   └── architecture.md
├── start.bat                     # Windows one-click launcher
└── README.md
```

---

## 2. Installation & Quick Start

### Prerequisites
* **Python:** 3.10 - 3.13
* **Node.js:** v18+ (v20+ recommended)
* **OS:** Windows 10/11, Ubuntu 20.04+, or macOS

### Starting on Windows
Run `start.bat` from the project root or execute manually:

```powershell
# 1. Backend
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python app.py     # Runs on http://localhost:5000

# 2. Frontend (in a new terminal)
cd frontend
npm install
npm run dev       # Runs on http://localhost:5173
```

---

## 3. Complete REST API Reference

All backend responses use a structured JSON envelope:
* **Success:** `{"success": true, "data": { ... }}`
* **Error:** `{"success": false, "error": {"code": "ERROR_CODE", "message": "Details"}}`

| Method | Endpoint | Description | Key Parameters |
|---|---|---|---|
| `GET` | `/api/health` | Service health, uptime, and loaded model status | None |
| `GET` | `/api/model/info` | Checkpoint metadata, classes, framework & device | None |
| `POST` | `/api/model/reload` | Reloads `best.pt` without restarting Flask | None |
| `POST` | `/api/detect/image` | Runs YOLO object detection on an image | `image` (file), `conf`, `iou`, `imgsz` |
| `POST` | `/api/detect/video` | Queues async frame-by-frame video detection | `video` (file), `conf`, `iou`, `imgsz` |
| `POST` | `/api/track/video` | Queues ByteTrack object tracking on a video | `video` (file), `conf`, `iou`, `imgsz` |
| `GET` | `/api/results` | Lists recent video processing jobs | `limit` (default: 10) |
| `GET` | `/api/results/<id>` | Polls status and results of a video job | `job_id` |
| `POST` | `/api/lane/detect` | OpenCV Canny + Hough lane detection | `image` (file), `canny_low`, `canny_high`, `steps` |
| `POST` | `/api/lane/deep` | ENet deep learning lane segmentation | `image` (file), `threshold` |
| `POST` | `/api/depth/estimate`| Monocular depth map using MiDaS | `image` (file), `with_objects` |
| `GET` | `/api/depth/status` | Reports MiDaS model download/cache state | None |
| `GET` | `/api/simulation/status`| CARLA simulator connection status | None |
| `POST`| `/api/simulation/connect`| Connects to CARLA server | `host`, `port` |
| `POST`| `/api/simulation/disconnect`| Disconnects from CARLA server | None |
| `GET` | `/api/simulation/frame`| Retrieves latest camera frame from CARLA | None |
| `GET` | `/api/ros2/status` | Checks ROS 2 perception node status | None |
| `GET` | `/api/performance` | Training metrics (mAP50, loss) from results.csv | None |
| `POST`| `/api/performance/benchmark`| On-device FPS and latency benchmark | `runs`, `imgsz` |
| `POST`| `/api/chat` | AI Doubts Assistant for questions | `message` (string), `history` (list) |

---

## 4. Perception Modules & Workflow

### 1. Object Detection (YOLOv8)
* **Model:** Ultralytics YOLOv8 trained on BDD100K 10 classes (`pedestrian`, `rider`, `car`, `truck`, `bus`, `train`, `motorcycle`, `bicycle`, `traffic light`, `traffic sign`).
* **Input:** RGB image or video frame.
* **Output:** Bounding boxes $[x_1, y_1, x_2, y_2]$, class prediction, confidence score $[0.0 - 1.0]$, and latency.

### 2. Multi-Object Tracking (ByteTrack)
* Uses ByteTrack association algorithm.
* Matches high and low confidence detection boxes between consecutive frames using Kalman filter motion estimation and IoU matching.
* Generates persistent `track_id` values and draws motion trajectory trails.

### 3. Lane Detection (OpenCV Pipeline)
1. **Grayscale conversion:** Removes color complexity.
2. **Gaussian Blur ($5\times 5$):** Reduces high-frequency noise.
3. **Canny Edge Detection:** Detects sharp intensity gradients.
4. **Trapezoidal ROI Masking:** Restricts focus to the drivable lane region directly ahead of the vehicle.
5. **Probabilistic Hough Transform (`HoughLinesP`):** Identifies straight line segments.
6. **Lane Fit & Offset:** Groups line segments into left and right boundaries using slope filtering, fits polynomial lines, calculates lane centre and vehicle offset in metres/pixels.

### 4. Monocular Relative Depth Estimation (MiDaS)
* Generates relative inverse depth maps using Intel ISL's MiDaS via PyTorch Hub.
* Warmer colors (red/yellow) indicate objects closer to the camera; cooler colors (blue/purple) indicate distant background.
* Maps detected bounding boxes to the depth map to calculate per-object proximity scores.

### 5. Autonomous Driving Simulation (CARLA & ROS 2)
* Interacts with CARLA simulator via Python API (`carla`).
* Spawns ego vehicle (e.g., `vehicle.tesla.model3`) with an attached RGB camera sensor.
* Streams annotated frames to the dashboard in real-time.
* Fully compatible with ROS 2 perception topics (`/camera/image_raw`, `/perception/bounding_boxes`).

---

## 5. Troubleshooting & Frequently Asked Questions

### Q: Why do inference endpoints return HTTP 503 "Model status: Missing"?
**Answer:** The app uses real models by design with zero fake data. The weights file `backend/models/best.pt` has not been provided yet.
1. Download `best.pt` from your training run.
2. Place it in `backend/models/best.pt`.
3. The server will detect it or you can restart the backend.

### Q: How do I enable GPU acceleration with CUDA?
**Answer:** Check if PyTorch detects your GPU:
```python
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
If false, install the CUDA PyTorch wheel matching your driver (e.g., CUDA 12.1):
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Q: Why is depth estimation called "relative" and not metric?
**Answer:** Single-camera (monocular) imagery suffers from scale ambiguity. Without LiDAR, stereo cameras, or calibrated ground plane geometry, depth maps output relative proximity values (0 to 1), not absolute metric distances.

### Q: Can I run without CARLA installed?
**Answer:** Yes. The simulation page detects CARLA availability automatically and displays connection instructions when CARLA is offline. All other perception modules (detection, tracking, lanes, depth) operate completely independently.
