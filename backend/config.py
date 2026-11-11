"""Central configuration for the ADAS backend.

Every value can be overridden with an ``ADAS_*`` environment variable so the
same code runs unchanged on a laptop (CPU) or a CUDA machine (GPU).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# ------------------------------------------------------------------ server --
HOST = os.environ.get("ADAS_HOST", "0.0.0.0")
PORT = int(os.environ.get("ADAS_PORT", "5000"))
DEBUG = os.environ.get("ADAS_DEBUG", "0") == "1"
# Comma-separated origins, or "*" for any origin (fine for local development).
CORS_ORIGINS = os.environ.get("ADAS_CORS_ORIGINS", "*").split(",")

# ----------------------------------------------------------- trained model --
MODELS_DIR = BASE_DIR / "models"
# The user-trained YOLO weights downloaded from Google Colab live here.
MODEL_PATH = Path(os.environ.get("ADAS_MODEL_PATH", str(MODELS_DIR / "best.pt")))
# Files produced by Ultralytics during training (copied out of Colab).
RESULTS_CSV_PATH = Path(os.environ.get("ADAS_RESULTS_CSV", str(MODELS_DIR / "results.csv")))
TRAIN_ARGS_PATH = MODELS_DIR / "args.yaml"
# Optional user-trained ENet checkpoint for the deep lane segmentation comparison.
LANE_SEG_CHECKPOINT = Path(os.environ.get("ADAS_LANE_SEG_CKPT", str(MODELS_DIR / "lane_seg_enet.pth")))
# MiDaS torch.hub download cache.
MIDAS_CACHE_DIR = MODELS_DIR / "midas_cache"
MIDAS_MODEL_TYPE = os.environ.get("ADAS_MIDAS_MODEL", "MiDaS_small")  # or "DPT_Hybrid"

# ------------------------------------------------------- uploads / outputs --
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_FILE = BASE_DIR / "app.log"

# ------------------------------------------------------------------ limits --
MAX_IMAGE_MB = int(os.environ.get("ADAS_MAX_IMAGE_MB", "16"))
MAX_VIDEO_MB = int(os.environ.get("ADAS_MAX_VIDEO_MB", "200"))
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "bmp", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "avi", "mov", "mkv"}

# ------------------------------------------------------------- database ------
MONGO_URI = os.environ.get("ADAS_MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB_NAME = os.environ.get("ADAS_MONGO_DB", "adas_database")

# --------------------------------------------------- inference defaults -----
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.45
DEFAULT_IMGSZ = 640

# -------------------------------------------------------------- benchmark ---
BENCHMARK_WARMUP_RUNS = 3
BENCHMARK_TIMED_RUNS = 10

# ------------------------------------------------------------------ frontend --
# Path to the built React production bundle (frontend/dist).  When this
# directory exists Flask serves the SPA + static assets on the same port as
# the API, removing the need for a separate frontend server.
FRONTEND_DIST = Path(os.environ.get("ADAS_FRONTEND_DIST", str(PROJECT_ROOT / "frontend" / "dist")))

# ------------------------------------------------------ temp-file cleanup ---
CLEANUP_MAX_AGE_HOURS = int(os.environ.get("ADAS_CLEANUP_HOURS", "6"))
CLEANUP_INTERVAL_SECONDS = int(os.environ.get("ADAS_CLEANUP_INTERVAL", "3600"))

API_VERSION = "1.0.0"


def ensure_dirs() -> None:
    """Create runtime directories on first start."""
    for directory in (MODELS_DIR, UPLOAD_DIR, OUTPUT_DIR, MIDAS_CACHE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
