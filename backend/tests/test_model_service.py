"""Model service tests.

The first test always runs (it proves the missing-model behaviour is honest).
Tests that require the real best.pt skip automatically when it is absent.
"""

from pathlib import Path

import numpy as np
import pytest

from services.model_service import ModelNotLoadedError, get_model_service

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "best.pt"

requires_model = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="backend/models/best.pt is not present (user-trained weights are not committed)",
)


def test_missing_model_reports_missing(tmp_path):
    service = get_model_service()
    info = service.load(tmp_path / "definitely-missing.pt", force=True)
    assert info["status"] == "missing"
    assert info["model_exists"] is False
    assert info["classes"] == []
    assert "best.pt" in info["message"]
    with pytest.raises(ModelNotLoadedError):
        service.predict(np.zeros((32, 32, 3), np.uint8))


@requires_model
def test_real_model_loads_and_predicts():
    service = get_model_service()
    info = service.load(MODEL_PATH, force=True)
    assert info["status"] == "loaded"
    assert info["class_count"] > 0
    assert info["classes"][0]["name"]
    assert info["model_type"] in {"detect", "segment", "classify", "pose", "obb"}
    result, elapsed_ms = service.predict(np.full((480, 640, 3), 90, np.uint8))
    assert elapsed_ms > 0
    boxes = service.parse_boxes(result)
    assert isinstance(boxes, list)
