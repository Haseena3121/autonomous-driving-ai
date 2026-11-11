"""Detection service test (requires the real trained model)."""

from pathlib import Path

import numpy as np
import pytest

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "best.pt"

requires_model = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="backend/models/best.pt is not present (user-trained weights are not committed)",
)


@requires_model
def test_detect_image_on_synthetic_frame():
    from services.detection_service import detect_image

    image = np.full((360, 640, 3), 80, np.uint8)
    result = detect_image(image, conf=0.25)
    assert result["stats"]["total"] == len(result["detections"])
    assert result["inference_ms"] > 0
    assert result["annotated"].shape == image.shape
    assert result["device"] in {"cpu", "cuda:0"}
    for det in result["detections"]:
        assert {"class_id", "class_name", "confidence", "bbox"} <= set(det)
        assert 0.0 <= det["confidence"] <= 1.0
        assert len(det["bbox"]) == 4


@requires_model
def test_detect_image_runs_on_random_noise():
    """Smoke test: real inference must not crash on any input."""
    from services.detection_service import detect_image

    rng = np.random.default_rng(0)
    image = rng.integers(0, 255, (288, 512, 3), dtype=np.uint8)
    result = detect_image(image)
    assert result["stats"]["total"] >= 0
