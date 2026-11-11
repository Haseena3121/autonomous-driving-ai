"""Depth estimation endpoint (MiDaS) with optional object-level read-outs."""

import uuid

from flask import Blueprint, jsonify

import config
from services.detection_service import decode_image_bytes, encode_jpeg, to_data_url
from services.depth_service import DepthUnavailableError, get_depth_service
from services.model_service import get_model_service
from services.validation import (
    ApiValidationError,
    get_uploaded_file,
    parse_bool,
    validate_extension,
)

api = Blueprint("depth", __name__)


@api.post("/depth/estimate")
def depth_estimate():
    try:
        storage = get_uploaded_file("image")
        ext = validate_extension(storage.filename, config.ALLOWED_IMAGE_EXT, "image")
        with_objects = parse_bool("with_objects", True)
    except ApiValidationError as exc:
        return jsonify({"success": False, "error": {"code": exc.code, "message": str(exc)}}), 400

    image = decode_image_bytes(storage.read())
    if image is None:
        return (
            jsonify({"success": False, "error": {"code": "INVALID_IMAGE", "message": "Could not decode the uploaded image."}}),
            400,
        )

    detections, detection_note = [], None
    if with_objects:
        model_service = get_model_service()
        if model_service.is_loaded:
            try:
                result, _ = model_service.predict(image, conf=config.DEFAULT_CONF, iou=config.DEFAULT_IOU)
                detections = model_service.parse_boxes(result)
            except Exception as exc:  # noqa: BLE001 - depth still works without objects
                detection_note = f"Object depth skipped (detection failed: {exc})"
        else:
            detection_note = (
                "Object-level depth skipped: the trained YOLO model is not loaded. "
                "Place best.pt in backend/models/ to enable it."
            )

    depth = get_depth_service()
    try:
        result = depth.estimate(image, detections=detections)
    except DepthUnavailableError as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "DEPTH_MODEL_UNAVAILABLE",
                        "message": str(exc),
                        "status": depth.status(),
                    },
                }
            ),
            503,
        )

    colored_bytes = encode_jpeg(result["colored"])
    output_name = f"{uuid.uuid4().hex}.jpg"
    (config.OUTPUT_DIR / output_name).write_bytes(colored_bytes)

    data = {
        "status": depth.status(),
        "depth_image": to_data_url(colored_bytes),
        "depth_url": f"/api/outputs/{output_name}",
        "original_image": to_data_url(encode_jpeg(image)),
        "objects": result["objects"],
        "depth_range": result["depth_range"],
        "inference_ms": result["inference_ms"],
        "disclaimer": result["disclaimer"],
        "detection_note": detection_note,
    }
    return jsonify({"success": True, "data": data})


@api.get("/depth/status")
def depth_status():
    return jsonify({"success": True, "data": get_depth_service().status()})
