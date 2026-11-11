"""Core REST endpoints: health, model info/reload, performance, results, outputs."""

import time

from flask import Blueprint, jsonify, request, send_from_directory

import config
from services import performance_service
from services.model_service import get_model_service
from services.video_service import job_store

api = Blueprint("core", __name__)
START_TIME = time.time()


@api.get("/health")
def health():
    service = get_model_service()
    return jsonify(
        {
            "success": True,
            "data": {
                "status": "ok",
                "service": "autonomous-driving-api",
                "version": config.API_VERSION,
                "uptime_s": round(time.time() - START_TIME, 1),
                "model": {
                    "status": service.status,
                    "device": service.device,
                    "class_count": len(service.classes),
                    "message": service.message,
                },
            },
        }
    )


@api.get("/model/info")
def model_info():
    return jsonify({"success": True, "data": get_model_service().info()})


@api.post("/model/reload")
def model_reload():
    """Reload best.pt (e.g. after the user adds/replaces the weights file)."""
    service = get_model_service()
    service.load(config.MODEL_PATH, force=True)
    return jsonify({"success": True, "data": service.info()})


@api.get("/performance")
def performance():
    service = get_model_service()
    metrics = performance_service.get_training_metrics(service)
    data = {
        "training_metrics": metrics,
        "training_config": performance_service.parse_args_yaml(config.TRAIN_ARGS_PATH),
        "model": {
            "path": str(config.MODEL_PATH),
            "exists": config.MODEL_PATH.exists(),
            "size_mb": performance_service.model_file_size_mb(),
            "type": service.task,
        },
        "device": service.device,
        "device_name": service.device_name,
        "cuda_available": service.cuda_available,
        "ultralytics_version": service.ultralytics_version,
        "torch_version": service.torch_version,
        "imgsz": service.imgsz,
        "benchmark": None,
        "metrics_note": (
            None
            if metrics
            else "No training metrics available. Copy results.csv (and optionally args.yaml) from your "
            "Google Colab training run into backend/models/ next to best.pt, then reload. "
            "Values are never invented."
        ),
    }
    return jsonify({"success": True, "data": data})


@api.post("/performance/benchmark")
def performance_benchmark():
    service = get_model_service()
    if not service.is_loaded:
        return (
            jsonify({"success": False, "error": {"code": "MODEL_NOT_LOADED", "message": service.message}}),
            503,
        )
    body = request.get_json(silent=True) or {}
    runs = int(body.get("runs", config.BENCHMARK_TIMED_RUNS))
    imgsz = int(body.get("imgsz", config.DEFAULT_IMGSZ))
    result = performance_service.benchmark(service, runs=runs, imgsz=imgsz)
    return jsonify({"success": True, "data": result})


@api.get("/results")
def results_list():
    limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    kind = request.args.get("kind") or None
    status = request.args.get("status") or None
    jobs = job_store.list(limit=limit, kind=kind, status=status)
    return jsonify({"success": True, "data": {"jobs": [job.to_dict() for job in jobs]}})


@api.get("/results/<job_id>")
def results_detail(job_id):
    job = job_store.get(job_id)
    if job is None:
        return jsonify({"success": False, "error": {"code": "JOB_NOT_FOUND", "message": f"Unknown job '{job_id}'."}}), 404
    return jsonify({"success": True, "data": job.to_dict()})


@api.get("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(
        config.OUTPUT_DIR,
        filename,
        as_attachment=request.args.get("download") == "1",
    )
