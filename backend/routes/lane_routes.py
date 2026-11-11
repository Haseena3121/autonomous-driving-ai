"""Lane detection endpoints: classical OpenCV pipeline + deep ENet comparison."""

import uuid

from flask import Blueprint, jsonify

import config
from services.detection_service import encode_jpeg, to_data_url
from services.lane_service import LaneDetectionService
from services.validation import (
    ApiValidationError,
    get_uploaded_file,
    parse_bool,
    parse_float,
    parse_int,
    validate_extension,
)
from services.deep_lane_service import LaneModelUnavailable, get_deep_lane_service

api = Blueprint("lane", __name__)

_lane_service = LaneDetectionService()


@api.post("/lane/detect")
def lane_detect():
    try:
        storage = get_uploaded_file("image")
        ext = validate_extension(storage.filename, config.ALLOWED_IMAGE_EXT, "image")
        canny_low = parse_int("canny_low", 50, 1, 500)
        canny_high = parse_int("canny_high", 150, 1, 800)
        steps = parse_bool("steps", False)
    except ApiValidationError as exc:
        return jsonify({"success": False, "error": {"code": exc.code, "message": str(exc)}}), 400

    from services.detection_service import decode_image_bytes

    image = decode_image_bytes(storage.read())
    if image is None:
        return (
            jsonify({"success": False, "error": {"code": "INVALID_IMAGE", "message": "Could not decode the uploaded image."}}),
            400,
        )

    annotated, step_images, meta = _lane_service.detect(
        image, canny_low=canny_low, canny_high=canny_high, return_steps=steps
    )
    annotated_bytes = encode_jpeg(annotated)
    output_name = f"{uuid.uuid4().hex}.jpg"
    (config.OUTPUT_DIR / output_name).write_bytes(annotated_bytes)

    data = {
        "meta": meta,
        "annotated_image": to_data_url(annotated_bytes),
        "annotated_url": f"/api/outputs/{output_name}",
        "steps": None,
    }
    if step_images:
        data["steps"] = {name: to_data_url(encode_jpeg(img)) for name, img in step_images.items()}
    return jsonify({"success": True, "data": data})


@api.post("/lane/deep")
def lane_deep():
    """Deep-learning lane segmentation comparison (user-trained ENet)."""
    try:
        storage = get_uploaded_file("image")
        ext = validate_extension(storage.filename, config.ALLOWED_IMAGE_EXT, "image")
        threshold = parse_float("threshold", 0.5, 0.05, 0.95)
    except ApiValidationError as exc:
        return jsonify({"success": False, "error": {"code": exc.code, "message": str(exc)}}), 400

    from services.detection_service import decode_image_bytes

    image = decode_image_bytes(storage.read())
    if image is None:
        return (
            jsonify({"success": False, "error": {"code": "INVALID_IMAGE", "message": "Could not decode the uploaded image."}}),
            400,
        )

    deep = get_deep_lane_service()
    try:
        annotated, meta = deep.infer(image, threshold=threshold)
    except LaneModelUnavailable as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "LANE_MODEL_UNAVAILABLE",
                        "message": str(exc),
                        "instructions": [
                            "Train the ENet lane segmentation model with: python model_training/train_lane_enet.py "
                            "--images <folder> --masks <folder>",
                            "The trained checkpoint is saved to backend/models/lane_seg_enet.pth and this page "
                            "will then label it as 'trained by me'.",
                            "No pretrained substitute is used, so the comparison stays honest.",
                        ],
                    },
                }
            ),
            503,
        )

    annotated_bytes = encode_jpeg(annotated)
    output_name = f"{uuid.uuid4().hex}.jpg"
    (config.OUTPUT_DIR / output_name).write_bytes(annotated_bytes)

    data = {
        "status": deep.status(),
        "meta": meta,
        "annotated_image": to_data_url(annotated_bytes),
        "annotated_url": f"/api/outputs/{output_name}",
    }
    return jsonify({"success": True, "data": data})
