# Model training — Google Colab workflow (BDD100K → best.pt)

This folder contains everything needed to train the YOLO model in **Google
Colab** and connect it to the website. Nothing here is required to *run* the
web app — only `backend/models/best.pt` is, and it is produced by this
workflow.

```
model_training/
├── README.md             ← this guide (Colab cells, step by step)
├── training_config.yaml  ← the training configuration used
├── bdd100k_to_yolo.py    ← BDD100K labels → Ultralytics YOLO format converter
├── train_yolo.py         ← same training call as the notebook, as a CLI script
├── train_lane_enet.py    ← trains the ENet lane-segmentation comparison model
└── export_model.py       ← ONNX / TensorRT export (required tech stack)
```

---

## 1 · Open the Colab notebook

Runtime → *Change runtime type* → **GPU (T4 is fine)**.

```python
# Cell 1 — install Ultralytics (pre-installed torch/CUDA on Colab is reused)
!pip install -q ultralytics
import ultralytics, torch
print("ultralytics", ultralytics.__version__, "| torch", torch.__version__,
      "| cuda", torch.cuda.is_available())
```

## 2 · Get BDD100K

Option A (recommended): register at the official site and download the
detection labels + 100k images:

* https://bdd-data.berkeley.edu — *BDD100K Images (100k)* and
  *BDD100K Detection Labels 2020*

Option B (no registration): the Kaggle mirror `solesensei/solesensei_bdd100k`:

```python
# Cell 2 — example with the Kaggle API (needs kaggle.json in ~/.kaggle)
!pip -q install kaggle
# !mkdir -p ~/.kaggle && cp /content/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
!kaggle datasets download -d solesensei/solesensei_bdd100k -p /content --unzip -q
```

Option C (bonus, listed in the project brief): record synthetic frames from
CARLA itself with `simulation/carla_perception_agent.py` and add them to the
training set — domain-randomisation style.

After extraction you need this layout:

```
/content/bdd100k/
├── images/100k/{train,val}/…jpg
└── labels/bdd100k_labels_images_{train,val}.json
```

## 3 · Convert BDD100K → YOLO format

```python
# Cell 3
!python bdd100k_to_yolo.py \
    --labels-train /content/bdd100k/labels/bdd100k_labels_images_train.json \
    --labels-val   /content/bdd100k/labels/bdd100k_labels_images_val.json \
    --images-train /content/bdd100k/images/100k/train \
    --images-val   /content/bdd100k/images/100k/val \
    --out /content/datasets/bdd100k
```

The converter writes `images/{train,val}`, `labels/{train,val}` (YOLO txt) and
the dataset definition `/content/datasets/bdd100k/data.yaml` with the 10
BDD100K classes: `person, rider, car, bus, truck, bike, motor, traffic light,
traffic sign, train`.

## 4 · Train

```python
# Cell 4
from ultralytics import YOLO

model = YOLO("yolov8s.pt")          # COCO-pretrained backbone (transfer learning)
results = model.train(
    data="/content/datasets/bdd100k/data.yaml",
    epochs=50, imgsz=640, batch=16,
    optimizer="auto", lr0=0.01, patience=20,
    project="bdd100k_yolo", name="adas_v1",
)
print("Best weights:", model.trainer.best)   # /content/bdd100k_yolo/adas_v1/weights/best.pt
```

`training_config.yaml` documents this configuration; `train_yolo.py` wraps the
same call as a CLI script if you prefer a terminal.

Optional experiment tracking (Weights & Biases, part of the required stack):

```python
!pip -q install wandb
import ultralytics; ultralytics.checks()
# then either:  import wandb; wandb.login()
# or run training with:  yolo train ... project=… name=…
```

## 5 · Copy the outputs out of Colab

```python
# Cell 5 — the three files that power the website
from google.colab import files
run = "/content/bdd100k_yolo/adas_v1"
for f in [f"{run}/weights/best.pt", f"{run}/results.csv", f"{run}/args.yaml"]:
    files.download(f)
```

Place them in the project:

```
backend/models/best.pt      # REQUIRED — used by every inference endpoint
backend/models/results.csv  # real Precision / Recall / mAP per epoch → Performance page
backend/models/args.yaml    # hyper-parameters → Model Info page
```

Restart the backend (or press **Reload model**). The dashboard, class list and
performance page fill with real values — nothing is hard-coded.

## 6 · Validate & measure (optional but recommended for the report)

```python
# Cell 6
metrics = model.val(data="/content/datasets/bdd100k/data.yaml")   # P / R / mAP50 / mAP50-95
speed = model.predict("/content/bdd100k/images/100k/val/000001.jpg", imgsz=640)
```

The website's *Model Performance → Run benchmark* button re-measures latency
and FPS on the machine running the backend, so the numbers in your final
presentation always reflect real hardware.

## 7 · ONNX / TensorRT export (required tech stack)

```python
# Cell 7 — ONNX (portable, ~3× faster on CPU with onnxruntime)
model.export(format="onnx", imgsz=640)

# TensorRT engine (NVIDIA deployment, colabs have no TRT by default:
# use a local CUDA machine for this one)
# model.export(format="engine", imgsz=640, half=True)
```

`export_model.py` in this folder wraps both. Exported engines are drop-in
usable by Ultralytics (`YOLO("best.onnx")`) if you want to benchmark them in
the same app.

---

## Lane segmentation comparison model (ENet)

The Lane Detection page compares the classical OpenCV pipeline with a deep
segmentation model that **you train yourself** (it is clearly labelled
"trained by me" in the UI and API; without a checkpoint the page honestly says
so).

1. Prepare a lane-mask dataset (e.g. BDD100K lane segmentation maps or
   TuSimple): a folder of images and a folder of same-name binary masks
   (white = lane, black = background).
2. Train:

```bash
python model_training/train_lane_enet.py \
    --images dataset/lane/images --masks dataset/lane/masks --epochs 40
```

3. The checkpoint is written to `backend/models/lane_seg_enet.pth` and the
   comparison section activates automatically.

---

## Checklist

- [ ] `backend/models/best.pt` present
- [ ] `backend/models/results.csv` copied (real metrics on the Performance page)
- [ ] `backend/models/args.yaml` copied (training metadata on the Model Info page)
- [ ] Backend restarted → Home Dashboard shows **Loaded** with device + classes
- [ ] Optional: `lane_seg_enet.pth` trained for the deep lane comparison
- [ ] Optional: `best.onnx` / TensorRT engine exported
