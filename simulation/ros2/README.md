# ROS 2 integration (separate module)

`perception_node.py` is a **standalone rclpy node** — it reuses the backend's
model/drawing services but does NOT run inside the Flask server. The website's
Simulation page only *reports* whether `rclpy` is importable in its own
environment; running the node is fully independent.

## Requirements

```bash
# ROS 2 Humble or newer (Ubuntu 22.04 example)
sudo apt install ros-humble-ros-base ros-humble-cv-bridge ros-humble-vision-msgs
pip install -r backend/requirements.txt     # ultralytics, torch, opencv
```

## Run

```bash
# 1) camera publisher — CARLA's ros2 bridge, a Gazebo camera, or any sensor_msgs/Image:
ros2 run image_tools cam2image --ros-args -p reliability:=best_effort -p frequency:=15.0

# 2) the perception node (remap the camera topic if needed):
python3 simulation/ros2/perception_node.py --ros-args \
    -p model_path:=backend/models/best.pt \
    -p conf:=0.35 \
    -p use_tracking:=true \
    -r image_raw:=/adas/image_raw
```

## Topics

| Direction | Topic | Type |
| --- | --- | --- |
| subscribe | `/adas/image_raw` (parameter `image_topic`) | `sensor_msgs/Image` |
| publish | `/adas/detections` | `vision_msgs/Detection2DArray` |
| publish | `/adas/annotated_image` | `sensor_msgs/Image` |

## Inspect the output

```bash
ros2 topic echo /adas/detections --once
ros2 run rqt_image_view rqt_image_view /adas/annotated_image
```

## Parameters

| Parameter | Default | Meaning |
| --- | --- | --- |
| `model_path` | `backend/models/best.pt` | your trained YOLO weights |
| `conf` | 0.35 | detection confidence threshold |
| `iou` | 0.45 | NMS IoU |
| `imgsz` | 640 | inference size |
| `use_tracking` | false | enable ByteTrack (`persist=True`) |
| `image_topic` | `/adas/image_raw` | camera topic to subscribe |
