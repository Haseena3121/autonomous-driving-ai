"""Real performance numbers for the Model Performance page.

Sources, in priority order (all real, never invented):

1. ``train_metrics`` embedded in best.pt by Ultralytics after training.
2. ``backend/models/results.csv`` — the per-epoch CSV Ultralytics writes into
   the Colab training folder (copy it next to best.pt).
3. If neither exists, metrics are reported as ``None`` and the UI shows
   "Not available".

The latency/FPS benchmark runs the actual model on this machine.
"""

from __future__ import annotations

import csv
import logging
import time
from pathlib import Path

import numpy as np

import config

logger = logging.getLogger(__name__)

METRIC_COLUMNS = {
    "precision": ("metrics/precision(B)", "precision"),
    "recall": ("metrics/recall(B)", "recall"),
    "map50": ("metrics/mAP50(B)", "mAP50"),
    "map50_95": ("metrics/mAP50-95(B)", "mAP50-95"),
}


def _col(row: dict, names: tuple) -> float | None:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def parse_results_csv(path) -> dict | None:
    """Parse an Ultralytics results.csv and keep the best epoch (max mAP50-95)."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        logger.warning("Could not read results file %s", path)
        return None
    if not rows:
        return None

    best = max(rows, key=lambda r: _col(r, METRIC_COLUMNS["map50_95"]) or 0.0)
    metrics = {key: _col(best, names) for key, names in METRIC_COLUMNS.items()}
    if all(value is None for value in metrics.values()):
        return None
    try:
        epoch = int(float(best.get("epoch", 0) or 0))
    except (TypeError, ValueError):
        epoch = None
    metrics.update(
        {
            "epoch": epoch,
            "total_epochs": len(rows),
            "source": f"results.csv ({path.name})",
        }
    )
    return metrics


def parse_args_yaml(path) -> dict | None:
    """Read training hyper-parameters from the Ultralytics args.yaml."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, Exception) as exc:  # yaml errors included
        logger.warning("Could not read %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    keys = ("data", "epochs", "imgsz", "batch", "optimizer", "lr0", "patience", "model", "device", "seed", "time")
    parsed = {k: data[k] for k in keys if data.get(k) is not None}
    return parsed or None


def _checkpoint_train_metrics(model_service) -> dict | None:
    ckpt = getattr(model_service.model, "ckpt", None)
    if not isinstance(ckpt, dict):
        return None
    raw = ckpt.get("train_metrics")
    if not isinstance(raw, dict) or not raw:
        return None
    metrics = {}
    for key, names in METRIC_COLUMNS.items():
        for name in names:
            if name in raw and raw[name] is not None:
                try:
                    metrics[key] = round(float(raw[name]), 4)
                except (TypeError, ValueError):
                    pass
                break
    if not metrics:
        return None
    metrics["source"] = "checkpoint (best.pt train_metrics)"
    return metrics


def get_training_metrics(model_service) -> dict | None:
    """Real training metrics or None — never fabricated."""
    if model_service.is_loaded:
        from_checkpoint = _checkpoint_train_metrics(model_service)
        if from_checkpoint:
            return from_checkpoint
    from_csv = parse_results_csv(config.RESULTS_CSV_PATH)
    if from_csv:
        return from_csv
    return None


def model_file_size_mb() -> float | None:
    try:
        return round(config.MODEL_PATH.stat().st_size / (1024 * 1024), 2)
    except OSError:
        return None


def benchmark(model_service, warmup: int | None = None, runs: int | None = None, imgsz: int | None = None) -> dict:
    """Measure real inference latency/FPS of the loaded model on this machine.

    A synthetic 1280x720 frame is used as the timing probe: the *content* does
    not affect latency, and every number reported is measured, not estimated.
    """
    model_service.require_model()
    warmup = warmup or config.BENCHMARK_WARMUP_RUNS
    runs = max(1, min(runs or config.BENCHMARK_TIMED_RUNS, 50))
    imgsz = imgsz or config.DEFAULT_IMGSZ

    probe = np.zeros((720, 1280, 3), dtype=np.uint8)
    probe[:] = (60, 60, 60)
    for i in range(0, 1280, 80):  # pseudo road markings; keeps the probe non-degenerate
        probe[600:640, i : i + 40] = (200, 200, 200)

    for _ in range(warmup):
        model_service.predict(probe, imgsz=imgsz)

    timings = []
    for _ in range(runs):
        _, elapsed_ms = model_service.predict(probe, imgsz=imgsz)
        timings.append(round(elapsed_ms, 1))

    avg_ms = float(np.mean(timings))
    return {
        "device": model_service.device,
        "device_name": model_service.device_name,
        "cuda_available": model_service.cuda_available,
        "imgsz": imgsz,
        "warmup_runs": warmup,
        "timed_runs": runs,
        "runs_ms": timings,
        "avg_ms": round(avg_ms, 1),
        "min_ms": min(timings),
        "max_ms": max(timings),
        "fps": round(1000.0 / avg_ms, 1),
        "model_size_mb": model_file_size_mb(),
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Measured on this machine with a 1280x720 probe frame; results vary by hardware.",
    }
