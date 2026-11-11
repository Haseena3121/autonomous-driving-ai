"""CARLA simulator bridge + ROS2 module status endpoints."""

from flask import Blueprint, Response, jsonify, request

from services.simulation_service import get_simulation_service

api = Blueprint("simulation", __name__)


@api.get("/simulation/status")
def simulation_status():
    return jsonify({"success": True, "data": get_simulation_service().status()})


@api.post("/simulation/connect")
def simulation_connect():
    body = request.get_json(silent=True) or {}
    host = str(body.get("host", "127.0.0.1")) or "127.0.0.1"
    try:
        port = int(body.get("port", 2000))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": {"code": "INVALID_PARAM", "message": "port must be an integer."}}), 400

    service = get_simulation_service()
    try:
        service.connect(host, port)
    except Exception as exc:  # noqa: BLE001 - honest failure report to the UI
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "CARLA_UNAVAILABLE",
                        "message": f"Could not connect to CARLA at {host}:{port}: {exc}",
                        "instructions": service.status()["instructions"],
                    },
                }
            ),
            503,
        )
    return jsonify({"success": True, "data": service.status()})


@api.post("/simulation/disconnect")
def simulation_disconnect():
    service = get_simulation_service()
    service.disconnect()
    return jsonify({"success": True, "data": service.status()})


@api.get("/simulation/frame")
def simulation_frame():
    """Latest annotated camera frame from the CARLA perception loop (JPEG)."""
    service = get_simulation_service()
    jpeg, meta = service.get_frame()
    if jpeg is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {"code": "NO_FRAME", "message": "No live frame available. Connect to a running CARLA server first."},
                }
            ),
            503,
        )
    response = Response(jpeg, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-ADAS-Meta"] = str(meta)
    return response


@api.get("/ros2/status")
def ros2_status():
    """Report whether the separate ROS2 perception module can run here."""
    node_path = "simulation/ros2/perception_node.py"
    ros2_installed = False
    try:
        import rclpy  # noqa: F401

        ros2_installed = True
    except ImportError:
        pass
    message = (
        "ROS2 (rclpy) detected — run the perception node with: "
        "python3 simulation/ros2/perception_node.py --ros-args -p model_path:=backend/models/best.pt"
        if ros2_installed
        else "ROS2 is not installed in this environment. Install ROS 2 (e.g. Humble) plus "
        "ros-humble-cv-bridge and ros-humble-vision-msgs, then run simulation/ros2/perception_node.py "
        "(see simulation/ros2/README.md). The website will report the module status either way."
    )
    return jsonify(
        {
            "success": True,
            "data": {
                "ros2_installed": ros2_installed,
                "node_path": node_path,
                "message": message,
            },
        }
    )
