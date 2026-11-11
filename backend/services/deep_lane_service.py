"""Deep-learning lane segmentation comparison module (ENet, PyTorch).

IMPORTANT — honest labelling: this module runs **one** model and reports what
it is:

* ``backend/models/lane_seg_enet.pth`` exists  -> the ENet checkpoint YOU
  trained with ``model_training/train_lane_enet.py`` (labelled
  "trained_by_me" in every API response and in the UI).
* the checkpoint is missing -> the module reports ``not_available`` with
  training instructions. **No pretrained network is silently substituted**, so
  the comparison is never misleading.

The ENet architecture below is the exact model used by the training script
(they import this same class), so checkpoints always match.
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

INPUT_WIDTH = 512   # both divisible by 16 as ENet requires
INPUT_HEIGHT = 288


# --------------------------------------------------------------------------- #
# ENet architecture (torch imported lazily: the rest of the backend must      #
# keep working on machines where PyTorch is not installed)                    #
# --------------------------------------------------------------------------- #
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on CPU-only minimal setups
    torch = nn = F = None
    TORCH_AVAILABLE = False

if TORCH_AVAILABLE:

    class ConvBNAct(nn.Sequential):
        def __init__(self, in_ch: int, out_ch: int, kernel: int, stride: int = 1, dilation: int = 1):
            padding = dilation * (kernel // 2)
            super().__init__(
                nn.Conv2d(in_ch, out_ch, kernel, stride=stride, padding=padding, dilation=dilation, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.PReLU(out_ch),
            )

    class InitialBlock(nn.Module):
        """ENet initial block: 3x3 conv (stride 2) pooled with the raw input."""

        def __init__(self, in_ch: int = 3, out_ch: int = 13):
            super().__init__()
            self.conv = nn.Conv2d(in_ch, out_ch, 3, stride=2, padding=1, bias=False)
            self.bn = nn.BatchNorm2d(out_ch)
            self.act = nn.PReLU(out_ch)
            self.pool = nn.MaxPool2d(2, 2)

        def forward(self, x):
            return torch.cat([self.act(self.bn(self.conv(x))), self.pool(x)], dim=1)

    class Bottleneck(nn.Module):
        """ENet bottleneck (regular / downsampling / dilated / asymmetric)."""

        def __init__(self, in_ch: int, out_ch: int, dilation: int = 1, downsample: bool = False, asymmetric: bool = False):
            super().__init__()
            mid = out_ch // 4
            self.reduce = ConvBNAct(in_ch, mid, 1)

            if asymmetric:
                # 5x1 followed by 1x5 (asymmetric convolution from the ENet paper)
                self.main = nn.Sequential(
                    nn.Conv2d(mid, mid, (5, 1), padding=(2, 0), bias=False),
                    nn.BatchNorm2d(mid),
                    nn.PReLU(mid),
                    nn.Conv2d(mid, mid, (1, 5), padding=(0, 2), bias=False),
                    nn.BatchNorm2d(mid),
                    nn.PReLU(mid),
                )
            else:
                self.main = ConvBNAct(mid, mid, 3, stride=2 if downsample else 1, dilation=dilation)

            self.expand = nn.Sequential(nn.Conv2d(mid, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch))
            self.act = nn.PReLU(out_ch)

            if downsample:
                self.shortcut = nn.Sequential(
                    nn.MaxPool2d(2, 2),
                    nn.Conv2d(in_ch, out_ch, 1, bias=False),
                    nn.BatchNorm2d(out_ch),
                )
            elif in_ch != out_ch:
                self.shortcut = nn.Sequential(nn.Conv2d(in_ch, out_ch, 1, bias=False), nn.BatchNorm2d(out_ch))
            else:
                self.shortcut = nn.Identity()

        def forward(self, x):
            main = self.expand(self.main(self.reduce(x)))
            return self.act(main + self.shortcut(x))

    class ENet(nn.Module):
        """Compact ENet-style encoder/decoder for binary lane segmentation."""

        def __init__(self, num_classes: int = 1):
            super().__init__()
            self.initial = InitialBlock(3, 13)  # output 16 channels

            self.stage1 = nn.ModuleList(
                [Bottleneck(16, 64, downsample=True)]
                + [Bottleneck(64, 64) for _ in range(3)]
                + [Bottleneck(64, 64, dilation=2)]
            )
            self.stage2 = nn.ModuleList(
                [Bottleneck(64, 128, downsample=True)]
                + [Bottleneck(128, 128) for _ in range(2)]
                + [Bottleneck(128, 128, dilation=4), Bottleneck(128, 128, asymmetric=True),
                   Bottleneck(128, 128, dilation=8), Bottleneck(128, 128, asymmetric=True),
                   Bottleneck(128, 128, dilation=16)]
            )
            self.stage3 = nn.ModuleList(
                [Bottleneck(128, 128) for _ in range(2)]
                + [Bottleneck(128, 128, dilation=4), Bottleneck(128, 128, asymmetric=True),
                   Bottleneck(128, 128, dilation=8), Bottleneck(128, 128, asymmetric=True),
                   Bottleneck(128, 128, dilation=16)]
            )
            self.stage4 = nn.ModuleList(
                [Bottleneck(128, 128, dilation=2), Bottleneck(128, 128, asymmetric=True), Bottleneck(128, 128, dilation=4)]
            )
            self.stage5 = nn.ModuleList(
                [Bottleneck(128, 128, dilation=2), Bottleneck(128, 128, asymmetric=True), Bottleneck(128, 128, dilation=4)]
            )
            self.head = nn.Conv2d(128, num_classes, 1)

        def forward(self, x):
            input_size = x.shape[-2:]
            x = self.initial(x)
            for block in self.stage1:
                x = block(x)
            for block in self.stage2:
                x = block(x)
            for block in self.stage3:
                x = block(x)
            for block in self.stage4:
                x = block(x)
            for block in self.stage5:
                x = block(x)
            logits = self.head(x)
            return F.interpolate(logits, size=input_size, mode="bilinear", align_corners=False)


# --------------------------------------------------------------------------- #
# Service wrapper                                                             #
# --------------------------------------------------------------------------- #
class LaneModelUnavailable(RuntimeError):
    """Raised when the user-trained segmentation checkpoint is missing."""


class DeepLaneSegmentation:
    """Loads and runs the user-trained ENet checkpoint (mode: trained_by_me)."""

    def __init__(self, checkpoint_path: Path | None = None):
        self.checkpoint_path = Path(checkpoint_path or config.LANE_SEG_CHECKPOINT)
        self._lock = threading.Lock()
        self.net: "ENet | None" = None
        self.device: str | None = None
        self.mode: str | None = None  # "trained_by_me" once a checkpoint loads
        self.trained_info: dict | None = None
        self.load_error: str | None = None

    # ------------------------------------------------------------------
    def checkpoint_available(self) -> bool:
        return self.checkpoint_path.exists()

    def status(self) -> dict:
        return {
            "available": self.net is not None,
            "checkpoint_available": self.checkpoint_available(),
            "torch_installed": TORCH_AVAILABLE,
            "mode": self.mode,
            "checkpoint_path": str(self.checkpoint_path),
            "trained_info": self.trained_info,
            "message": self._status_message(TORCH_AVAILABLE),
        }

    def _status_message(self, torch_installed: bool) -> str:
        if self.net is not None:
            return (
                "User-trained ENet checkpoint loaded — this deep lane segmentation model was TRAINED BY YOU "
                f"({self.trained_info or 'custom checkpoint'})."
            )
        if not torch_installed:
            return "PyTorch is not installed, so the deep lane comparison cannot run."
        if not self.checkpoint_available():
            return (
                f"No lane segmentation checkpoint at '{self.checkpoint_path}'. Train one with "
                "model_training/train_lane_enet.py (BDD100K / TuSimple lane masks) — the UI will then "
                "label it as 'trained by me'. No pretrained substitute is used."
            )
        return f"Checkpoint exists but failed to load: {self.load_error}"

    def ensure_loaded(self) -> None:
        if self.net is not None:
            return
        with self._lock:
            if self.net is not None:
                return
            if not TORCH_AVAILABLE:
                raise LaneModelUnavailable(
                    "PyTorch is not installed, so the deep lane comparison cannot run. "
                    "Install backend/requirements.txt first."
                )
            try:
                if not self.checkpoint_available():
                    raise LaneModelUnavailable(self._status_message(True))
                started = time.perf_counter()
                ckpt = torch.load(str(self.checkpoint_path), map_location="cpu", weights_only=False)
                state_dict = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
                num_classes = 1
                if isinstance(ckpt, dict) and ckpt.get("num_classes"):
                    num_classes = int(ckpt["num_classes"])
                net = ENet(num_classes=num_classes)
                net.load_state_dict(state_dict, strict=True)
                net.eval()
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
                net.to(self.device)
                self.net = net
                self.mode = "trained_by_me"
                if isinstance(ckpt, dict):
                    self.trained_info = ckpt.get("meta")
                logger.info(
                    "Deep lane segmentation checkpoint loaded in %.0f ms (device=%s)",
                    (time.perf_counter() - started) * 1000,
                    self.device,
                )
            except LaneModelUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001
                self.load_error = str(exc)
                self.net = None
                raise LaneModelUnavailable(f"Could not load lane segmentation checkpoint: {exc}") from exc

    # ------------------------------------------------------------------
    def infer(self, image_bgr, threshold: float = 0.5) -> tuple:
        """Return (annotated_bgr, meta) for the deep segmentation result."""
        self.ensure_loaded()
        import torch  # local import keeps module importable without torch

        original_height, original_width = image_bgr.shape[:2]
        started = time.perf_counter()

        resized = cv2.resize(image_bgr, (INPUT_WIDTH, INPUT_HEIGHT), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = torch.from_numpy(((rgb - mean) / std).transpose(2, 0, 1)).unsqueeze(0)

        with torch.no_grad():
            logits = self.net(tensor.to(self.device))
            probs = torch.sigmoid(logits)[0, 0].cpu().numpy()

        elapsed_ms = (time.perf_counter() - started) * 1000
        mask_small = (probs > float(threshold)).astype(np.uint8)
        mask = cv2.resize(mask_small, (original_width, original_height), interpolation=cv2.INTER_NEAREST)

        annotated = image_bgr.copy()
        green = annotated.copy()
        green[mask == 1] = (60, 210, 90)
        annotated = cv2.addWeighted(green, 0.45, annotated, 0.55, 0)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(annotated, contours, -1, (120, 255, 140), 2)

        coverage_pct = float(mask.mean() * 100.0)
        meta = {
            "coverage_pct": round(coverage_pct, 2),
            "threshold": float(threshold),
            "input_size": [INPUT_WIDTH, INPUT_HEIGHT],
            "device": self.device,
            "inference_ms": round(elapsed_ms, 1),
        }
        return annotated, meta


def get_deep_lane_service() -> DeepLaneSegmentation:
    global _deep_lane_service
    if _deep_lane_service is None:
        _deep_lane_service = DeepLaneSegmentation()
    return _deep_lane_service


_deep_lane_service: DeepLaneSegmentation | None = None
