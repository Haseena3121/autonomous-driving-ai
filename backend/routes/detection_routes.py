"""Detection endpoints: single image inference + asynchronous video jobs."""

import uuid

from flask import Blueprint, jsonify

import config
from services import detection_service
from services.detection_service import decode_image_bytes, encode_jpeg, to_data_url
from services.model_service import ModelNotLoadedError
from services.validation import (
    ApiValidationError,
    get_uploaded_file,
    parse_float,
    parse_int,
    save_upload,
    validate_extension,
)
from services.video_service import job_store, video_processor

api = Blueprint("detection", __name__)


@api.post("/detect/image")
def detect_image():
    try:
        storage = get_uploaded_file("image")
        ext = validate_extension(storage.filename, config.ALLOWED_IMAGE_EXT, "image")
        conf = parse_float("conf", config.DEFAULT_CONF, 0.05, 0.95)
        iou = parse_float("iou", config.DEFAULT_IOU, 0.1, 0.9)
        imgsz = parse_int("imgsz", config.DEFAULT_IMGSZ, 320, 1536)

        image = decode_image_bytes(storage.read())
        if image is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "INVALID_IMAGE", "message": "Could not decode the uploaded image."},
                    }
                ),
                400,
            )
    except ApiValidationError as exc:
        return jsonify({"success": False, "error": {"code": exc.code, "message": str(exc)}}), 400

    try:
        result = detection_service.detect_image(image, conf=conf, iou=iou, imgsz=imgsz)
    except ModelNotLoadedError as exc:
        return jsonify({"success": False, "error": {"code": "MODEL_NOT_LOADED", "message": str(exc)}}), 503

    annotated_bytes = encode_jpeg(result["annotated"])
    output_name = f"{uuid.uuid4().hex}.jpg"
    (config.OUTPUT_DIR / output_name).write_bytes(annotated_bytes)

    data = {
        "detections": result["detections"],
        "total": result["stats"]["total"],
        "stats": result["stats"],
        "inference_ms": result["inference_ms"],
        "device": result["device"],
        "image": result["image_size"],
        "original_image": to_data_url(encode_jpeg(image)),
        "annotated_image": to_data_url(annotated_bytes),
        "annotated_url": f"/api/outputs/{output_name}",
    }
    return jsonify({"success": True, "data": data})


@api.post("/detect/video")
def detect_video():
    return _start_video_job(kind="detect")


@api.get("/detect/video/status/<job_id>")
def detect_video_status(job_id):
    return _job_status(job_id)


def _start_video_job(kind: str):
    field = "video"
    try:
        storage = get_uploaded_file(field)
        ext = validate_extension(storage.filename, config.ALLOWED_VIDEO_EXT, "video")
        conf = parse_float("conf", config.DEFAULT_CONF, 0.05, 0.95)
        iou = parse_float("iou", config.DEFAULT_IOU, 0.1, 0.9)
        imgsz = parse_int("imgsz", config.DEFAULT_IMGSZ, 320, 1536)
    except ApiValidationError as exc:
        return jsonify({"success": False, "error": {"code": exc.code, "message": str(exc)}}), 400

    params = {"conf": conf, "iou": iou, "imgsz": imgsz}
    upload_path = save_upload(storage, ext)
    job = job_store.create(kind, storage.filename, params)
    video_processor.submit(job, upload_path)
    return jsonify({"success": True, "data": job.to_dict()}), 202


def _job_status(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        return jsonify({"success": False, "error": {"code": "JOB_NOT_FOUND", "message": f"Unknown job '{job_id}'."}}), 404
    return jsonify({"success": True, "data": job.to_dict()})
