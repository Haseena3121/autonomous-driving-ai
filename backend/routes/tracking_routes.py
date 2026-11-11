"""ByteTrack video tracking endpoints (uses the real trained YOLO detections)."""

from flask import Blueprint, jsonify

from routes.detection_routes import _job_status, _start_video_job  # shared job helpers
from services.tracking_service import BYTETRACK_NOTE

api = Blueprint("tracking", __name__)


@api.post("/track/video")
def track_video():
    response, status = _start_video_job(kind="track")
    return response, status


@api.get("/track/status/<job_id>")
def track_status(job_id):
    return _job_status(job_id)


@api.get("/track/info")
def track_info():
    return jsonify({"success": True, "data": {"tracker": "ByteTrack (Ultralytics)", "note": BYTETRACK_NOTE}})
