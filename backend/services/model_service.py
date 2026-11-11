"""Loads and serves the user-trained Ultralytics YOLO model (``best.pt``).

Design rules enforced here:

* The model is loaded **exactly once** when Flask starts (``ModelService`` is a
  thread-safe singleton; ``load()`` is idempotent).
* If ``backend/models/best.pt`` is missing, the status becomes ``missing`` and
  the message explains how to fix it. **No placeholder or fake model is ever
  substituted** — inference endpoints raise :class:`ModelNotLoadedError` and
  the REST layer turns that into HTTP 503.
* GPU (CUDA) is used automatically when available, with CPU as the fallback.
* Class names, task type and training metadata come from the real checkpoint.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when inference is requested but no trained model is loaded."""


class ModelService:
    """Thread-safe singleton wrapper around the trained YOLO model."""

    _instance: "ModelService | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "ModelService":
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialised = False
                cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        self._inference_lock = threading.RLock()  # serialise GPU/CPU inference
        self._load_lock = threading.Lock()

        self.model = None
        self.device: str | None = None
        self.device_name: str | None = None
        self.cuda_available = False
        self.status = "not_loaded"  # not_loaded | loading | loaded | missing | error
        self.message = "Model has not been loaded yet."
        self.model_path: Path | None = None
        self.loaded_at: str | None = None
        self.load_time_ms: int | None = None

        self.classes: list[dict] = []  # [{"id": 0, "name": "person"}, ...]
        self.task: str | None = None
        self.imgsz: int | None = None
        self.parameters_million: float | None = None
        self.gflops: float | None = None
        self.training_metadata: dict | None = None
        self.ultralytics_version: str | None = None
        self.torch_version: str | None = None

    # ------------------------------------------------------------- loading --
    def load(self, model_path, force: bool = False) -> dict:
        """Load the trained model. Idempotent unless ``force=True``."""
        with self._load_lock:
            if self.status == "loaded" and not force:
                return self.info()

            self.model_path = Path(model_path)
            if not self.model_path.exists():
                self.status = "missing"
                self.model = None
                self.message = (
                    f"Trained model not found at '{self.model_path}'. "
                    "Place your Google-Colab-trained best.pt into backend/models/ and restart the server "
                    "(or press 'Reload model' on the Model Information page). "
                    "No fake or placeholder model is used."
                )
                logger.error(self.message)
                return self.info()

            self.status = "loading"
            self.message = "Loading model..."
            started = time.perf_counter()
            try:
                import torch
                from ultralytics import YOLO
            except ImportError as exc:
                self.status = "error"
                self.message = (
                    f"AI dependencies are missing ({exc}). Install the backend requirements with "
                    "'pip install -r requirements.txt' (see README for the CUDA torch wheel)."
                )
                logger.exception("Failed to import AI dependencies")
                return self.info()

            try:
                self.cuda_available = torch.cuda.is_available()
                self.device = "cuda:0" if self.cuda_available else "cpu"
                if self.cuda_available:
                    try:
                        self.device_name = torch.cuda.get_device_name(0)
                    except Exception:  # pragma: no cover - driver quirks
                        self.device_name = "CUDA GPU"
                self.torch_version = torch.__version__

                model = YOLO(str(self.model_path))
                model.to(self.device)
                self.model = model

                try:
                    import ultralytics

                    self.ultralytics_version = ultralytics.__version__
                except Exception:  # pragma: no cover
                    pass

                names = getattr(model, "names", None) or {}
                self.classes = [{"id": int(k), "name": str(v)} for k, v in sorted(names.items())]
                self.task = getattr(model, "task", "detect")
                overrides = getattr(model, "overrides", {}) or {}
                self.imgsz = overrides.get("imgsz", 640)

                self.parameters_million, self.gflops = self._model_facts(model)
                self.training_metadata = self._extract_training_metadata(model)

                self.load_time_ms = int((time.perf_counter() - started) * 1000)
                self.loaded_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self.status = "loaded"
                self.message = (
                    f"Model loaded on {self.device.upper()} in {self.load_time_ms} ms — "
                    f"{len(self.classes)} classes, task '{self.task}'."
                )
                logger.info(self.message)
            except Exception as exc:
                self.status = "error"
                self.model = None
                self.message = f"Failed to load the trained model: {exc}"
                logger.exception("Model loading failed")
            return self.info()

    @staticmethod
    def _model_facts(model) -> tuple[float | None, float | None]:
        """Return (parameters in millions, GFLOPs) as reported by Ultralytics."""
        try:
            info = model.info(verbose=False)
            if isinstance(info, (tuple, list)) and len(info) >= 4:
                params = float(info[1])
                flops = float(info[3])
                return round(params / 1e6, 2), round(flops / 1e9, 1)
        except Exception:
            logger.debug("model.info() unavailable", exc_info=True)
        return None, None

    @staticmethod
    def _extract_training_metadata(model) -> dict | None:
        """Pull the training arguments Ultralytics embeds inside best.pt."""
        ckpt = getattr(model, "ckpt", None)
        if not isinstance(ckpt, dict):
            return None
        args = ckpt.get("train_args")
        if args is None:
            return None
        if not isinstance(args, dict):
            try:
                args = vars(args)
            except TypeError:
                return None
        keys = ("data", "epochs", "imgsz", "batch", "optimizer", "lr0", "patience", "device", "model", "seed", "time")
        meta = {k: args[k] for k in keys if args.get(k) is not None}
        return meta or None

    # -------------------------------------------------------------- status --
    @property
    def is_loaded(self) -> bool:
        return self.status == "loaded"

    def require_model(self) -> None:
        if not self.is_loaded:
            raise ModelNotLoadedError(self.message)

    def info(self) -> dict:
        path = self.model_path
        exists = bool(path and path.exists())
        size_mb = round(path.stat().st_size / (1024 * 1024), 2) if exists else None
        return {
            "status": self.status,
            "message": self.message,
            "model_path": str(path) if path else None,
            "model_exists": exists,
            "file_size_mb": size_mb,
            "model_type": self.task,
            "framework": "Ultralytics YOLO",
            "ultralytics_version": self.ultralytics_version,
            "torch_version": self.torch_version,
            "cuda_available": self.cuda_available,
            "device": self.device,
            "device_name": self.device_name,
            "class_count": len(self.classes),
            "classes": self.classes,
            "imgsz": self.imgsz,
            "parameters_million": self.parameters_million,
            "gflops": self.gflops,
            "training_metadata": self.training_metadata,
            "loaded_at": self.loaded_at,
            "load_time_ms": self.load_time_ms,
        }

    # ------------------------------------------------------------ inference --
    def predict(
        self,
        image_bgr,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 640,
        tracker: str | None = None,
        persist: bool = False,
    ):
        """Run real inference on a BGR numpy image.

        Returns ``(ultralytics Results, inference_ms)``. Raises
        :class:`ModelNotLoadedError` when no model is available.
        """
        self.require_model()
        kwargs = {
            "source": image_bgr,
            "conf": float(conf),
            "iou": float(iou),
            "imgsz": int(imgsz),
            "device": self.device,
            "verbose": False,
            "persist": persist,
        }
        if tracker:
            kwargs["tracker"] = tracker
        with self._inference_lock:
            started = time.perf_counter()
            results = self.model.predict(**kwargs)
            elapsed_ms = (time.perf_counter() - started) * 1000
        return results[0], elapsed_ms

    def parse_boxes(self, result) -> list[dict]:
        """Convert an Ultralytics Results object into plain JSON-safe rows."""
        boxes = []
        names = getattr(result, "names", None) or {}
        for box in getattr(result, "boxes", None) or []:
            track_id = None
            raw_id = getattr(box, "id", None)
            if raw_id is not None:
                track_id = int(raw_id.item())
            cls_id = int(box.cls.item())
            boxes.append(
                {
                    "class_id": cls_id,
                    "class_name": str(names.get(cls_id, str(cls_id))),
                    "confidence": round(float(box.conf.item()), 4),
                    "bbox": [round(float(v), 1) for v in box.xyxy[0].tolist()],
                    "track_id": track_id,
                }
            )
        return boxes


def get_model_service() -> ModelService:
    """Return the process-wide singleton."""
    return ModelService()
