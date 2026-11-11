# AI-Based Autonomous Driving System

A complete, professional web application for **object detection, object
tracking, lane detection, depth estimation and obstacle avoidance** — built
around **your own trained YOLO model** (`best.pt`, trained on BDD100K in
Google Colab).

> **Honesty by design:** every bounding box, track ID, lane fit, depth score
> and performance number in this app is produced by the actual model or
> pipeline on your machine. There are **no mock detections, no placeholder
> boxes, no hard-coded accuracy values** — and no fake substitute model when
> `best.pt` is missing. Unavailable features report *why* and how to fix them.

| Layer | Technology |
| --- | --- |
| Frontend | React 18 · Vite 5 · JavaScript · CSS3 (dark/blue dashboard) · Recharts |
| Backend | Python 3 · Flask REST API · Flask-CORS · OpenCV · NumPy |
| AI | Ultralytics YOLO (`best.pt`) · ByteTrack · OpenCV lane pipeline · ENet (user-trained comparison) · MiDaS (torch.hub) · PyTorch |
| Simulation | CARLA bridge (in-process + standalone agent) · ROS 2 perception node |
| Deployment extras | ONNX / TensorRT export scripts · Weights & Biases notes |

---

## 1 · Dashboard pages

1. **Home Dashboard** — live model status (loaded / missing + device), class count, uptime, module cards, recent job history.
2. **Object Detection** — image upload → real YOLO inference → original vs annotated side-by-side, per-detection table (class, confidence, bbox), latency, download.
3. **Video Analysis** — video upload → frame-by-frame processing with live upload/processing progress bars → annotated MP4 player + download + detections-per-class chart.
4. **Object Tracking** — ByteTrack (`tracker="bytetrack.yaml"`, `persist=True`) over the real detections → IDs drawn on boxes, motion-trajectory trails, unique-track count, per-track summary table.
5. **Lane Detection** — OpenCV pipeline (grayscale → blur → Canny → ROI → probabilistic Hough → lane fit) with lane-centre offset estimation, intermediate step visualisations, and the separate deep-learning ENet comparison clearly labelled *“trained by me”* or *“not available”*.
6. **Depth Estimation** — MiDaS relative depth map, object-level depth scores (via the trained detector), and a prominent disclaimer: **relative depth, not metres**.
7. **Autonomous Driving Simulation** — connects the website to a running CARLA server, spawns a camera vehicle and streams live annotated perception frames; ROS 2 node status; honest setup instructions when CARLA is offline.
8. **Model Performance** — Precision / Recall / mAP50 / mAP50-95 read from your real training files (checkpoint or `results.csv`), plus a live on-device latency/FPS benchmark with a per-run chart. Missing metrics show **“Not available”** — never invented values.
9. **Model Information** — weights path, size, task, class list, framework versions, CUDA/GPU info, embedded training metadata, and a **Reload model** button.
10. **Project Documentation** — setup, API reference, structure and troubleshooting, in-app.

## 2 · Quick start

### One command (recommended)

```bash
./start.sh        # Linux / macOS
```

On Windows, double-click **`start.bat`** instead. The launcher starts both
servers — the Flask API on `http://localhost:5000` and the React dashboard on
`http://localhost:5173` — and creates `backend/venv` and installs all
dependencies automatically on the first run (Ctrl+C stops both on Linux/macOS;
on Windows close the two server windows).

### Backend (Flask + your trained model)

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
# → put your trained best.pt into backend/models/ (section 3)
python app.py                     # serves http://localhost:5000
```

For a CUDA GPU also install the matching torch wheel, e.g.:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

CPU inference works everywhere and is the automatic fallback — the API always
reports which device it is actually using.

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev                       # serves http://localhost:5173 (proxies /api → :5000)
```

Open **http://localhost:5173**. The dashboard immediately shows whether the
model is loaded. The production build also works: `npm run build` → `dist/`
(set `VITE_API_URL` if the backend is not on port 5000).

## 3 · Connect your Google-Colab-trained model

1. Train on BDD100K following **`model_training/README.md`** (dataset options,
   converter, training cell, optional W&B logging). Colab’s GPU runtimes have
   CUDA torch pre-installed — no extra setup there.
2. Download from the run folder and place into the project:

```
backend/models/best.pt      # REQUIRED — used by every inference endpoint
backend/models/results.csv  # optional — real Precision/Recall/mAP for the Performance page
backend/models/args.yaml    # optional — training hyper-parameters for Model Info
```

3. Restart the backend, or press **Reload model** on the Model Information page.
4. The Home Dashboard now shows **Loaded** with the device, the true class list
   (read from the checkpoint — never hard-coded) and the file size.

While `best.pt` is missing, the server still starts: `/api/health` reports
`model.status = "missing"`, every inference endpoint returns **HTTP 503** with
instructions, and the dashboard shows the setup guide. **No placeholder model
is ever loaded.**

Optional (required tech stack): `model_training/export_model.py` exports
`best.onnx` or a TensorRT engine; `model_training/train_lane_enet.py` trains
the ENet lane-segmentation comparison model.

## 4 · REST API (summary)

Full reference with request/response examples: **`docs/API.md`**.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | liveness + model status + device |
| GET | `/api/model/info` | checkpoint details, classes, metadata |
| POST | `/api/model/reload` | re-read `best.pt` |
| POST | `/api/detect/image` | YOLO inference on an image |
| POST | `/api/detect/video` | async video detection job |
| POST | `/api/track/video` | async ByteTrack job |
| GET | `/api/results` · `/api/results/{id}` | job list / poll progress |
| POST | `/api/lane/detect` | OpenCV lane pipeline + centre offset |
| POST | `/api/lane/deep` | ENet segmentation comparison |
| POST | `/api/depth/estimate` | MiDaS relative depth + objects |
| GET | `/api/performance` | real training metrics + environment |
| POST | `/api/performance/benchmark` | live latency / FPS measurement |
| GET | `/api/outputs/{file}` | download annotated results |
| GET/POST | `/api/simulation/*` | CARLA status / connect / disconnect / frame |
| GET | `/api/ros2/status` | ROS 2 module availability |

Responses use one envelope: `{success, data}` / `{success, error:{code,
message, instructions?}}`. Validation covers extensions, parameter ranges and
file-size limits (16 MB images / 200 MB videos); uploads and outputs are
auto-cleaned after 6 hours; all requests and errors are logged to
`backend/app.log`.

## 5 · Project structure

```
autonomous-driving-ai/
├── frontend/                     # React + Vite dashboard
│   └── src/{components,pages,services}/
├── backend/
│   ├── app.py                    # app factory: CORS, logging, model load, cleanup
│   ├── config.py                 # paths/limits (ADAS_* env overrides)
│   ├── models/                   # ← best.pt + results.csv + args.yaml (see models/README.md)
│   ├── services/                 # model, detection, video, tracking, lane,
│   │                             # deep_lane, depth, performance, simulation, validation
│   ├── routes/                   # core, detection, tracking, lane, depth, simulation
│   ├── uploads/  outputs/        # runtime files (auto-cleaned)
│   └── tests/                    # pytest suite (25 tests)
├── model_training/               # Colab workflow, BDD100K→YOLO converter,
│                                 # YOLO/ENet trainers, ONNX/TensorRT export
├── simulation/                   # CARLA standalone agent + ROS 2 node
├── docs/                         # architecture.md · API.md
├── README.md  .gitignore
```

## 6 · Tests

```bash
cd backend
python -m pytest tests -v
```

25 tests cover the API contract, validation errors, the lane pipeline,
metrics parsing, the job registry and the ENet architecture. Tests that need
the trained weights are **skipped automatically** when `best.pt` is absent —
the suite is green on a fresh clone and reports honest skip reasons.

## 7 · Troubleshooting

**“Model status: Missing” / 503 from inference endpoints.**
`best.pt` has not been placed yet. `cp best.pt backend/models/` then restart
(or Reload model on the Model Info page). This is intentional — no substitute
model exists.

**CUDA not used (CPU inference).**
`python -c "import torch; print(torch.cuda.is_available())"` must print
`True`. Install the CUDA build:
`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`,
then restart the backend. CPU fallback always works.

**Dependency install failures.**
Use a fresh venv; `requirements.txt` already pins `numpy<3` for NumPy-2
compatibility. On Colab no installation is needed.

**Annotated video does not preview in the browser.**
Browsers play H.264 only; the backend re-encodes automatically when `ffmpeg`
is on PATH (`sudo apt install ffmpeg` / `brew install ffmpeg`). The download
button always works regardless.

**Frontend shows “API offline”.**
Start the backend first (`python app.py`, port 5000), then `npm run dev`.
Custom port → set `VITE_API_URL=http://localhost:PORT` in
`frontend/.env.local`. Port 5000 busy → `ADAS_PORT=5001 python app.py`
(macOS: AirPlay Receiver also uses 5000).

**MiDaS fails on first use.**
The first depth request downloads ~70 MB of weights into
`backend/models/midas_cache/` (internet required once). The error message
always states the real cause.

**CARLA page shows “Client not installed”.**
`pip install carla==0.9.15` (must match your simulator version), start
`./CarlaUE4.sh`, then press Connect. Full steps are rendered on the page.

## 8 · Deliverables map (project brief)

| Deliverable | Where |
| --- | --- |
| Working demo | Run backend + frontend locally (section 2); every page is live |
| Repository + README + setup | This file, `.gitignore`, `docs/` |
| Architecture diagram + API docs | `docs/architecture.md` (diagram + flows) · `docs/API.md` · in-app Documentation page |
| Test results | `backend/tests/` → `python -m pytest tests -v` |
| Performance / accuracy numbers | `backend/models/results.csv` → Model Performance page + on-device benchmark |
| Trained model (YOLO, BDD100K) | Colab workflow → `backend/models/best.pt` |
| TensorRT / ONNX / W&B | `model_training/export_model.py` · `model_training/README.md` §4/§7 |
| CARLA + ROS 2 | `simulation/` (agent + node) · Simulation page |
