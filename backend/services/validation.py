"""Request validation helpers shared by all API routes.

Every endpoint validates the uploaded file (presence + extension), clamps
numeric parameters into safe ranges and raises :class:`ApiValidationError`
which the route layer converts into a 400 JSON error.
"""

import uuid
from pathlib import Path

from flask import request as flask_request
from werkzeug.utils import secure_filename

import config


class ApiValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def get_uploaded_file(field: str = "image"):
    """Return the uploaded FileStorage or raise a validation error."""
    storage = flask_request.files.get(field)
    if storage is None and flask_request.files:
        storage = next(iter(flask_request.files.values()))
    if storage is None or not storage.filename:
        raise ApiValidationError("NO_FILE", f"Multipart field '{field}' containing a file is required.")
    return storage


def validate_extension(filename: str, allowed: set[str], kind: str) -> str:
    if "." not in filename:
        raise ApiValidationError("INVALID_FILE_TYPE", f"File name has no extension. Allowed {kind}: {sorted(allowed)}.")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed:
        raise ApiValidationError(
            "INVALID_FILE_TYPE",
            f"Unsupported {kind} extension '.{ext}'. Allowed: {', '.join(sorted(allowed))}.",
        )
    return ext


def save_upload(storage, ext: str) -> Path:
    """Persist the upload under backend/uploads/ with a random safe name."""
    name = f"{uuid.uuid4().hex}.{ext}"
    path = config.UPLOAD_DIR / secure_filename(name)
    storage.save(str(path))
    return path


def parse_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = flask_request.form.get(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiValidationError("INVALID_PARAM", f"Parameter '{name}' must be a number.")
    return min(max(value, lo), hi)


def parse_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = flask_request.form.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        raise ApiValidationError("INVALID_PARAM", f"Parameter '{name}' must be an integer.")
    return min(max(value, lo), hi)


def parse_bool(name: str, default: bool = False) -> bool:
    raw = flask_request.form.get(name)
    if raw in (None, ""):
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")
