"""AI Doubts Assistant REST endpoint.

Provides contextual answers to user questions and doubts regarding:
- YOLOv8 model training on BDD100K (Google Colab, hyperparameters, export)
- Multi-object tracking with ByteTrack (Kalman filters, track IDs, trajectories)
- Classical OpenCV lane detection (Canny edge, Hough transform, steering offset)
- Monocular depth estimation (MiDaS, relative depth vs metric LiDAR)
- CARLA simulation and ROS 2 perception integration
- System setup, PyTorch CUDA GPU acceleration, and troubleshooting
"""

import re
from flask import Blueprint, jsonify, request

api = Blueprint("chat", __name__)

# Comprehensive knowledge base for autonomous driving and project doubts
KNOWLEDGE_BASE = [
    {
        "keywords": ["train", "colab", "google colab", "bdd100k", "dataset", "epochs", "weights"],
        "category": "Model Training",
        "answer": (
            "### 🎓 Training YOLO on Google Colab for BDD100K\n\n"
            "To train your model and generate `best.pt`:\n\n"
            "1. **Open Google Colab:** Choose a GPU runtime (`Runtime > Change runtime type > T4 GPU`).\n"
            "2. **Download BDD100K Dataset:** Get the 100k 10-class images and annotations (`bdd100k_labels_images_train.json`).\n"
            "3. **Convert Labels to YOLO Format:** Run the converter script in `model_training/`:\n"
            "   ```bash\n"
            "   python model_training/convert_bdd100k_to_yolo.py --labels bdd100k_labels_images_train.json --output ./bdd100k_yolo\n"
            "   ```\n"
            "4. **Train with Ultralytics YOLOv8:**\n"
            "   ```python\n"
            "   from ultralytics import YOLO\n"
            "   model = YOLO('yolov8n.pt')  # or yolov8s.pt for higher accuracy\n"
            "   model.train(data='model_training/bdd100k.yaml', epochs=50, imgsz=640, batch=16, device=0)\n"
            "   ```\n"
            "5. **Place Checkpoint in Backend:** Download `best.pt` from Colab (`runs/detect/train/weights/best.pt`) and place it into `backend/models/best.pt`."
        ),
    },
    {
        "keywords": ["best.pt", "missing", "503", "reload", "load model", "not loaded", "where to put"],
        "category": "Model Deployment",
        "answer": (
            "### 📂 How to Add and Load `best.pt`\n\n"
            "* **File path:** Copy your trained checkpoint to:\n"
            "  `backend/models/best.pt`\n\n"
            "* **Why 503 is returned:** By design, the project never outputs fake or placeholder bounding boxes. When `best.pt` is absent, the backend reports `status: missing` and returns HTTP 503 on inference calls.\n\n"
            "* **How to reload:**\n"
            "  1. Paste `best.pt` into `backend/models/`.\n"
            "  2. You can either restart the backend server or send a `POST /api/model/reload` request.\n"
            "  3. Once loaded, the top status pill will turn green: **Model: Loaded (CPU/CUDA)**."
        ),
    },
    {
        "keywords": ["lane", "canny", "hough", "offset", "opencv", "steering", "curvature"],
        "category": "Lane Detection",
        "answer": (
            "### 🛣️ How the OpenCV Lane Detection Pipeline Works\n\n"
            "The lane detection module uses a classical computer vision pipeline without requiring deep learning:\n\n"
            "1. **Grayscale Conversion:** Simplifies pixel data from 3 channels to 1.\n"
            "2. **Gaussian Blur ($5\\times 5$):** Suppresses high-frequency asphalt textures and camera noise.\n"
            "3. **Canny Edge Detection:** Uses gradient thresholding (`low=50`, `high=150`) to locate road markings.\n"
            "4. **Trapezoidal Region of Interest (ROI):** Masks out the sky, trees, and oncoming traffic, focusing exclusively on the drivable triangular wedge in front of the vehicle.\n"
            "5. **Probabilistic Hough Transform (`HoughLinesP`):** Identifies collinear edge pixels as straight line segments.\n"
            "6. **Slope Filtering & Averaging:** Splits lines into left lane ($slope < -0.3$) and right lane ($slope > 0.3$), then fits continuous boundary lines.\n"
            "7. **Lane-Centre & Steering Offset:** Compares the midpoint between left/right lanes against the camera optical centre ($W/2$) to compute deviation (e.g. $-0.18\\text{ m}$ left)."
        ),
    },
    {
        "keywords": ["track", "bytetrack", "tracking", "trajectory", "kalman", "id", "ids"],
        "category": "Object Tracking",
        "answer": (
            "### 🔗 How ByteTrack Multi-Object Tracking Works\n\n"
            "ByteTrack keeps track of vehicle and pedestrian trajectories across successive video frames:\n\n"
            "1. **Standard Trackers Problem:** Older trackers discard low-confidence detections (e.g. occluded cars), losing track continuity.\n"
            "2. **ByteTrack Innovation:** Detections are partitioned into high-confidence ($> 0.6$) and low-confidence ($0.1 - 0.6$) pools.\n"
            "3. **First Association:** High-confidence boxes are matched with existing Kalman-filter predicted tracks using Intersection-over-Union (IoU).\n"
            "4. **Second Association:** Unmatched tracks are matched against low-confidence detections. This maintains tracking even during heavy occlusion.\n"
            "5. **Trajectory History:** The application stores the trailing $(x, y)$ centroids of each track ID to draw motion trails indicating movement direction and speed."
        ),
    },
    {
        "keywords": ["depth", "midas", "metric", "distance", "relative", "metres", "meters", "disparity"],
        "category": "Depth Estimation",
        "answer": (
            "### 🕳️ Why Depth Estimation is Relative (Not Metres)\n\n"
            "* **Monocular Scale Ambiguity:** A single standard camera image does not capture true scale. For example, a small toy car close to the camera projects the same retinal image size as a full-size truck far away.\n"
            "* **MiDaS Architecture:** Uses a Vision Transformer / CNN trained on mixed multi-dataset relative depth (disparity). It predicts **relative proximity**:\n"
            "  * High values / warm colors (yellow/red) = **Near the ego-vehicle**.\n"
            "  * Low values / cool colors (blue/purple) = **Distant background**.\n"
            "* **Object-Level Scoring:** The backend maps each YOLO bounding box to the MiDaS depth map and calculates median proximity, allowing the obstacle avoidance logic to prioritize closer hazards without needing a physical \$10,000 LiDAR sensor."
        ),
    },
    {
        "keywords": ["carla", "simulation", "simulator", "ros", "ros2", "spawn", "town"],
        "category": "Simulation & CARLA",
        "answer": (
            "### 🚗 CARLA Simulation & ROS 2 Integration\n\n"
            "* **CARLA Bridge:** The backend communicates with a running CARLA server (`localhost:2000`) using the official Python client library.\n"
            "* **Sensors:** It spawns an ego-vehicle (`vehicle.tesla.model3` or Lincoln MKZ) with a forward-facing RGB camera sensor ($800 \\times 600$, 90° FOV).\n"
            "* **Live Stream:** As CARLA renders frames, the backend processes them through the YOLO detection pipeline and streams annotated JPEG frames to the dashboard.\n"
            "* **ROS 2 Perception Node:** Located in `simulation/ros2_perception_node.py`. Subscribes to `/camera/image_raw`, runs inference, and publishes detections to `/perception/detections` with bounding box 3D coordinates."
        ),
    },
    {
        "keywords": ["cuda", "gpu", "cpu", "torch", "nvidia", "slow", "fps"],
        "category": "Hardware & Performance",
        "answer": (
            "### ⚡ Enabling CUDA GPU Acceleration\n\n"
            "If your inference runs on CPU and you have an NVIDIA GPU:\n\n"
            "1. **Check GPU Detection:**\n"
            "   ```powershell\n"
            "   python -c \"import torch; print('CUDA available:', torch.cuda.is_available())\"\n"
            "   ```\n"
            "2. **Install PyTorch with CUDA 12.1:**\n"
            "   ```powershell\n"
            "   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --force-reinstall\n"
            "   ```\n"
            "3. **Performance Difference:**\n"
            "   * **CPU (Core i7 / Ryzen):** ~12 - 20 FPS (50 - 80 ms per frame)\n"
            "   * **GPU (RTX 3060 / 4060):** ~80 - 150 FPS (6 - 12 ms per frame)\n"
            "   The system automatically runs on GPU whenever PyTorch CUDA is available."
        ),
    },
    {
        "keywords": ["doc", "docs", "documentation", "model information", "architecture", "files"],
        "category": "Documentation",
        "answer": (
            "### 📄 Project & Model Documentation Location\n\n"
            "As requested, project documentation and model information are organized in clean, comprehensive markdown files inside the `docs/` directory:\n\n"
            "* **[docs/PROJECT_DOCUMENTATION.md](file:///c:/Vechile/autonomous-driving-ai/docs/PROJECT_DOCUMENTATION.md):** Architecture, setup guide, full REST API reference, perception pipelines, and troubleshooting.\n"
            "* **[docs/MODEL_INFORMATION.md](file:///c:/Vechile/autonomous-driving-ai/docs/MODEL_INFORMATION.md):** YOLOv8 model architecture, BDD100K 10 classes, Colab training workflow, evaluation metrics (mAP50, Precision, Recall), and hardware benchmarks.\n"
            "* **[docs/API.md](file:///c:/Vechile/autonomous-driving-ai/docs/API.md):** Request/response JSON schemas.\n"
            "* **[docs/architecture.md](file:///c:/Vechile/autonomous-driving-ai/docs/architecture.md):** Low-level module dataflows."
        ),
    },
]

DEFAULT_FALLBACK = (
    "### 🤖 Autonomous Driving AI Assistant\n\n"
    "I can help clarify doubts regarding:\n"
    "1. **Model Training:** Training YOLOv8 on BDD100K via Google Colab and placing `best.pt`.\n"
    "2. **Object Detection & Tracking:** How YOLOv8 detects 10 road classes and how ByteTrack assigns IDs & trails.\n"
    "3. **Lane Detection:** OpenCV Canny edge, Hough transform, ROI masking, and steering offset calculations.\n"
    "4. **Depth Estimation:** Why MiDaS uses relative monocular depth instead of metric metres.\n"
    "5. **Simulation & CARLA:** Setting up CARLA, spawning vehicles, and ROS 2 perception nodes.\n"
    "6. **Troubleshooting:** Resolving HTTP 503 missing model errors, CUDA GPU acceleration, and video playback.\n\n"
    "Feel free to ask a specific question or choose one of the suggested prompts!"
)


@api.post("/chat")
def chat():
    """Handle chat queries regarding autonomous driving and project doubts."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"success": False, "error": {"code": "EMPTY_MESSAGE", "message": "Message cannot be empty."}}), 400

    query = message.lower()

    # Find the best matching knowledge base entry based on keyword hits
    best_match = None
    best_score = 0

    for entry in KNOWLEDGE_BASE:
        score = sum(1 for kw in entry["keywords"] if re.search(r"\b" + re.escape(kw) + r"\b", query))
        if score > best_score:
            best_score = score
            best_match = entry

    if best_match and best_score > 0:
        reply = best_match["answer"]
        category = best_match["category"]
    else:
        reply = DEFAULT_FALLBACK
        category = "General"

    return jsonify(
        {
            "success": True,
            "data": {
                "reply": reply,
                "category": category,
            },
        }
    )
