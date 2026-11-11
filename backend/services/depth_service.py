"""MiDaS monocular depth estimation (torch.hub).

Produces RELATIVE (inverse) depth maps: higher values = closer to the camera.
The values are explicitly NOT metric distances in metres — every API response
carries the disclaimer string below and the UI displays it.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "MiDaS estimates RELATIVE (inverse) depth. Values are normalised scores where "
    "higher = closer to the camera. They are NOT exact distances in metres."
)
HUB_REPOS = ("isl-org/MiDaS", "intel-isl/MiDaS")


class DepthUnavailableError(RuntimeError):
    """Raised when MiDaS cannot be loaded (missing torch or first-run download)."""


class DepthService:
    """Lazy-loads MiDaS on first use (keeps Flask startup fast)."""

    def __init__(self, model_type: str | None = None):
        self.model_type = model_type or config.MIDAS_MODEL_TYPE
        self._lock = threading.Lock()
        self.model = None
        self.transform = None
        self.device: str | None = None
        self.device_name: str | None = None
        self.load_error: str | None = None
        self.load_time_s: float | None = None

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        torch_installed = True
        try:
            import torch  # noqa: F401
        except ImportError:
            torch_installed = False
        cached = any((Path(config.MIDAS_CACHE_DIR) / repo.split("/")[-1]).exists() for repo in HUB_REPOS)
        return {
            "available": self.model is not None,
            "torch_installed": torch_installed,
            "model_type": self.model_type,
            "device": self.device,
            "device_name": self.device_name,
            "cache_dir": str(config.MIDAS_CACHE_DIR),
            "weights_cached": cached,
            "load_error": self.load_error,
            "load_time_s": round(self.load_time_s, 1) if self.load_time_s else None,
            "message": self._message(torch_installed, cached),
            "disclaimer": DISCLAIMER,
        }

    def _message(self, torch_installed: bool, cached: bool) -> str:
        if self.model is not None:
            return f"MiDaS ({self.model_type}) loaded on {self.device}."
        if not torch_installed:
            return "PyTorch is not installed — install backend/requirements.txt first."
        if self.load_error:
            return f"MiDaS could not be loaded: {self.load_error}"
        return (
            f"MiDaS ({self.model_type}) will be downloaded on first use (~70 MB for MiDaS_small) "
            f"into {config.MIDAS_CACHE_DIR}. Internet access is required for the first run."
            + (" Weights appear cached already." if cached else "")
        )

    # ------------------------------------------------------------------ load
    def ensure_loaded(self, model_type: str | None = None) -> None:
        if model_type and model_type != self.model_type:
            self.model = None
            self.model_type = model_type
        if self.model is not None:
            return
        with self._lock:
            if self.model is not None:
                return
            started = time.perf_counter()
            try:
                import torch

                torch.hub.set_dir(str(config.MIDAS_CACHE_DIR))
                model, transform, repo_used = None, None, None
                last_error: Exception | None = None
                for repo in HUB_REPOS:
                    try:
                        model = torch.hub.load(repo, self.model_type)
                        transforms = torch.hub.load(repo, "transforms")
                        transform = (
                            transforms.small_transform
                            if self.model_type == "MiDaS_small"
                            else transforms.dpt_transform
                        )
                        repo_used = repo
                        break
                    except Exception as exc:  # try the mirror repo next
                        last_error = exc
                        logger.warning("MiDaS load from %s failed: %s", repo, exc)
                if model is None or transform is None:
                    raise DepthUnavailableError(
                        f"Could not download MiDaS from torch.hub ({last_error}). "
                        "An internet connection is required for the first run."
                    )
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
                if self.device != "cpu":
                    try:
                        self.device_name = torch.cuda.get_device_name(0)
                    except Exception:  # pragma: no cover
                        self.device_name = "CUDA GPU"
                model.to(self.device).eval()
                self.model = model
                self.transform = transform
                self.load_time_s = time.perf_counter() - started
                logger.info("MiDaS %s loaded from %s on %s in %.1fs", self.model_type, repo_used, self.device, self.load_time_s)
            except DepthUnavailableError:
                raise
            except ImportError as exc:
                self.load_error = str(exc)
                raise DepthUnavailableError(
                    "PyTorch is required for depth estimation. Install backend/requirements.txt first."
                ) from exc
            except Exception as exc:  # noqa: BLE001
                self.load_error = str(exc)
                raise DepthUnavailableError(f"MiDaS failed to load: {exc}") from exc

    # ------------------------------------------------------------------ infer
    def estimate(self, image_bgr, detections: list | None = None) -> dict:
        """Return depth map stats for one BGR image.

        ``detections`` (from the real YOLO model, optional) enables
        object-level relative depth read-outs.
        """
        import torch  # guaranteed available after ensure_loaded

        self.ensure_loaded()
        started = time.perf_counter()

        height, width = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        input_batch = self.transform(rgb)
        if isinstance(input_batch, (list, tuple)):
            input_batch = input_batch[0]
        if input_batch.dim() == 3:
            input_batch = input_batch.unsqueeze(0)

        with torch.no_grad():
            prediction = self.model(input_batch.to(self.device))
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=(height, width), mode="bicubic", align_corners=False
            ).squeeze()

        depth = prediction.cpu().numpy().astype(np.float32)
        depth_min, depth_max = float(depth.min()), float(depth.max())
        if depth_max > depth_min:
            depth_norm = (depth - depth_min) / (depth_max - depth_min)
        else:
            depth_norm = np.zeros_like(depth)
        elapsed_ms = (time.perf_counter() - started) * 1000

        colored = cv2.applyColorMap((depth_norm * 255).astype(np.uint8), cv2.COLORMAP_MAGMA)

        objects = []
        for det in detections or []:
            x1, y1, x2, y2 = (int(v) for v in det["bbox"])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                continue
            region = depth_norm[y1:y2, x1:x2]
            relative = float(np.median(region))
            objects.append(
                {
                    "class_name": det["class_name"],
                    "confidence": det["confidence"],
                    "track_id": det.get("track_id"),
                    "relative_depth": round(relative, 3),
                }
            )
        objects.sort(key=lambda o: -o["relative_depth"])

        return {
            "depth": depth_norm,
            "colored": colored,
            "objects": objects,
            "depth_range": {"min": round(depth_min, 4), "max": round(depth_max, 4)},
            "inference_ms": round(elapsed_ms, 1),
            "model_type": self.model_type,
            "device": self.device,
            "disclaimer": DISCLAIMER,
        }


def get_depth_service() -> DepthService:
    global _depth_service
    if _depth_service is None:
        _depth_service = DepthService()
    return _depth_service


_depth_service: DepthService | None = None
