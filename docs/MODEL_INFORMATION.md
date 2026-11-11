# AI-Based Autonomous Driving System — Model Information & Specifications

This document outlines the architecture, training methodology, dataset specifications, input/output formats, and hardware benchmarks for the deep learning models powering the ADAS system.

---

## 1. Object Detection & Tracking Model

### Model Architecture
* **Backbone:** Ultralytics YOLOv8 (CSPDarknet with C2f feature extraction modules).
* **Neck:** Path Aggregation Network (PANet) with Feature Pyramid Network (FPN) for multi-scale feature fusion.
* **Head:** Anchor-free decoupled detection head separating objectness, classification, and bounding box regression branches.
* **Loss Functions:**
  * Box Loss: Complete IoU (CIoU) + Distribution Focal Loss (DFL).
  * Classification Loss: Binary Cross-Entropy (BCE).

### Expected Weights File
* **Filename:** `best.pt`
* **Target Location:** `backend/models/best.pt`
* **Format:** PyTorch serialized checkpoint (`.pt`), containing model weights, class names dictionary, and training hyperparameters.
* **Default Resolution:** $640 \times 640$ pixels (auto-letterboxed during inference).

---

## 2. Dataset Specification (BDD100K)

The model is trained on the Berkeley DeepDrive 100K (BDD100K) dataset, the benchmark autonomous driving dataset featuring diverse weather, day/night lighting, and urban/highway scenarios.

### Classes (10 Detection Categories)
| Class ID | Class Name | Autonomous Driving Role |
|---|---|---|
| `0` | `pedestrian` | Vulnerable road user (VRU), triggers emergency brake |
| `1` | `rider` | Cyclists & motorcyclists with erratic movement vectors |
| `2` | `car` | Standard passenger vehicles, distance keeping |
| `3` | `truck` | Heavy commercial vehicles, wide blind-spot monitoring |
| `4` | `bus` | Transit vehicles, frequent stops and pedestrian discharge |
| `5` | `train` | Railway crossing hazards |
| `6` | `motorcycle` | Two-wheeler fast dynamics tracking |
| `7` | `bicycle` | Non-motorized vehicle lane sharing |
| `8` | `traffic light` | Signal state classification (Red/Yellow/Green) |
| `9` | `traffic sign` | Speed limit, stop sign, regulatory compliance |

---

## 3. Training Workflow (Google Colab)

The scripts in `model_training/` allow end-to-end training:

1. **Dataset Preparation:**
   ```bash
   python model_training/convert_bdd100k_to_yolo.py \
       --labels path/to/bdd100k_labels_images_train.json \
       --output path/to/yolo_dataset
   ```
2. **Training Command:**
   ```bash
   yolo detect train \
       data=model_training/bdd100k.yaml \
       model=yolov8n.pt \
       epochs=50 \
       imgsz=640 \
       batch=16 \
       device=0 \
       project=runs/train \
       name=adas_bdd100k
   ```
3. **Artifact Deployment:**
   * Download `runs/train/adas_bdd100k/weights/best.pt` from Google Colab.
   * Copy `best.pt` to `backend/models/best.pt`.
   * (Optional) Copy `results.csv` and `args.yaml` into `backend/models/` to populate training curves and hyperparameter inspection in the Model Performance module.

---

## 4. Evaluation Metrics & Benchmarks

The system evaluates detection quality across standard COCO-style metrics:

* **Precision ($P$):** Fraction of detections that were correct ($\frac{TP}{TP + FP}$).
* **Recall ($R$):** Fraction of ground truth road objects successfully detected ($\frac{TP}{TP + FN}$).
* **mAP@50:** Mean Average Precision at an Intersection-over-Union (IoU) threshold of 0.50.
* **mAP@50-95:** Strict Average Precision averaged across IoU thresholds from 0.50 to 0.95 with steps of 0.05.

### Typical Latency & Hardware Expectations

| Hardware Platform | Precision / Mode | Average Latency (ms) | Throughput (FPS) |
|---|---|---|---|
| Intel Core i7 / AMD Ryzen (CPU) | FP32 (CPU Fallback) | 45 - 90 ms | 11 - 22 FPS |
| NVIDIA GeForce RTX 3060 (Laptop) | FP16 (CUDA) | 8 - 14 ms | 70 - 120 FPS |
| NVIDIA GeForce RTX 4080 / 4090 | FP16 (CUDA) | 3 - 6 ms | 160 - 300+ FPS |
| NVIDIA Tesla T4 (Google Colab Free) | FP16 (CUDA) | 12 - 18 ms | 55 - 80 FPS |
| Jetson Orin Nano / NX | INT8 / FP16 (TensorRT) | 10 - 20 ms | 50 - 100 FPS |

---

## 5. Secondary Perception Models

### 1. Monocular Relative Depth (MiDaS)
* **Architecture:** Vision Transformer (DPT) / EfficientNet-based monocular depth estimation.
* **Weights Source:** Auto-cached from PyTorch Hub (`intel-isl/MiDaS`, `MiDaS_small`).
* **Output:** Normalized relative disparity inverse depth map ($H \times W \times 1$).

### 2. Deep Lane Segmentation (ENet / SCNN Comparison)
* **Architecture:** Compact encoder-decoder CNN designed for real-time semantic segmentation on embedded processors.
* **Location:** `backend/models/enet_lane.pt` (optional user-trained checkpoint).
* **Output:** Binary/multiclass lane line pixel mask.

---

## 6. Model Lifecycle & Hot Reloading

The Flask server loads `backend/models/best.pt` during initialization into a singleton service (`ModelService`).
* **Hot Reloading:** When a new `best.pt` is saved to `backend/models/`, calling `POST /api/model/reload` reloads the weights in-memory without dropping active client connections or restarting the server.
* **Thread Safety:** Inference is thread-safe using re-entrant execution locks (`threading.RLock`) to prevent memory corruption during concurrent requests.
