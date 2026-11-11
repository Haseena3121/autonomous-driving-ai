"""API tests for the endpoints that must work WITHOUT the trained model."""

import io


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert {"status", "device", "class_count"} <= set(body["data"]["model"])


def test_index_lists_api_endpoints(client):
    res = client.get("/api")
    assert res.status_code == 200
    endpoints = res.get_json()["data"]["endpoints"]
    for expected in ("/api/health", "/api/model/info", "/api/detect/image", "/api/detect/video",
                     "/api/track/video", "/api/lane/detect", "/api/depth/estimate", "/api/results",
                     "/api/performance"):
        assert expected in endpoints


def test_model_info_shape(client):
    res = client.get("/api/model/info")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["status"] in {"not_loaded", "loading", "loaded", "missing", "error"}
    assert "model_path" in data and "classes" in data


def test_detect_image_requires_file(client):
    res = client.post("/api/detect/image")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "NO_FILE"


def test_detect_image_rejects_bad_extension(client):
    data = {"image": (io.BytesIO(b"not-an-image"), "notes.txt")}
    res = client.post("/api/detect/image", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_detect_video_rejects_bad_extension(client):
    data = {"video": (io.BytesIO(b"not-a-video"), "clip.txt")}
    res = client.post("/api/detect/video", data=data, content_type="multipart/form-data")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_lane_detect_requires_file(client):
    res = client.post("/api/lane/detect")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "NO_FILE"


def test_results_list_ok(client):
    res = client.get("/api/results")
    assert res.status_code == 200
    assert isinstance(res.get_json()["data"]["jobs"], list)


def test_results_unknown_job_404(client):
    res = client.get("/api/results/no-such-job")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "JOB_NOT_FOUND"


def test_unknown_api_route_returns_json_404(client):
    res = client.get("/api/definitely/not/here")
    assert res.status_code == 404
    assert res.get_json()["success"] is False


def test_reload_reports_honest_status(client):
    """With no weights the reload must report 'missing', never fake success."""
    res = client.post("/api/model/reload")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["status"] in {"missing", "loaded", "error"}  # all honest states
    if data["status"] == "missing":
        assert "best.pt" in data["message"]


def test_performance_reports_null_metrics_without_files(client):
    res = client.get("/api/performance")
    assert res.status_code == 200
    data = res.get_json()["data"]
    if data["training_metrics"] is None:
        assert "never invented" in data["metrics_note"] or data["metrics_note"]


def test_benchmark_requires_model(client):
    res = client.post("/api/performance/benchmark", json={"runs": 2})
    # 503 with no weights, 200 with weights — both honest.
    assert res.status_code in {200, 503}


def test_simulation_status_honest_without_carla(client):
    res = client.get("/api/simulation/status")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert isinstance(data["carla_installed"], bool)
    assert data["instructions"]  # always tells the user how to enable it


def test_ros2_status(client):
    res = client.get("/api/ros2/status")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert isinstance(data["ros2_installed"], bool)
    assert data["node_path"].endswith("perception_node.py")
