"""Shared pytest fixtures.

The full test suite runs WITHOUT the trained weights: tests that need
``backend/models/best.pt`` are skipped automatically when the file is absent,
so the suite passes on a fresh clone and reports honest skip reasons.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest

MODEL_PATH = BACKEND_DIR / "models" / "best.pt"

requires_model = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="backend/models/best.pt is not present (user-trained weights are not committed)",
)


@pytest.fixture(scope="session")
def app():
    from app import create_app

    return create_app(testing=True)


@pytest.fixture()
def client(app):
    return app.test_client()
