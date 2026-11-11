# Simulation modules

Two independent ways to run the perception stack against a live simulator —
neither is required for the website, and the website never fakes their output
(it reports their real status).

## 1 · CARLA

| Entry point | What it does |
| --- | --- |
| `backend/services/simulation_service.py` (via the Simulation page) | In-process bridge: spawns an ego vehicle + camera in a **running** CARLA server, streams frames through your trained YOLO + lanes, serves the latest annotated JPEG to the dashboard at `GET /api/simulation/frame`. |
| `simulation/carla_perception_agent.py` | The same loop as a desktop app with an OpenCV window; records an annotated MP4 into `backend/outputs/`. ByteTrack trajectories included. |

Setup:

```bash
# 1) CARLA simulator (0.9.15 recommended): https://carla.org  →  ./CarlaUE4.sh
# 2) matching Python client:
pip install carla==0.9.15
# 3) standalone agent:
python simulation/carla_perception_agent.py --model backend/models/best.pt
#    or start the backend and press "Connect" on the Simulation page.
```

The camera frames, detections and lane offsets all come from the real
simulator and the real model. If CARLA is not installed/running, every
endpoint returns 503 with setup instructions instead of pretending.

Bonus for training (per the project brief): the agent can record synthetic
driving frames (`--record`) to mix into your BDD100K training set.

## 2 · ROS 2

`ros2/perception_node.py` — rclpy node subscribing to `sensor_msgs/Image`,
publishing `vision_msgs/Detection2DArray` + annotated image. See
[`ros2/README.md`](ros2/README.md) for requirements, run commands and topics.
