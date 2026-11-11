#!/usr/bin/env python3
"""ROS 2 perception node for the ADAS project (separate module, not part of
the Flask server).

Subscribes to a camera topic, runs the trained YOLO model on every frame and
publishes detections + an annotated image. ByteTrack can be enabled with a
parameter.

    ros2 topics:
        subscribe : /adas/image_raw         (sensor_msgs/Image)
        publish   : /adas/detections        (vision_msgs/Detection2DArray)
        publish   : /adas/annotated_image   (sensor_msgs/Image)

    run:
        python3 perception_node.py --ros-args \
            -p model_path:=backend/models/best.pt -p conf:=0.35 -p use_tracking:=true

Requires: ROS 2 (Humble or newer) with ros-humble-cv-bridge and
ros-humble-vision-msgs, plus the backend requirements (ultralytics, torch,
opencv). The website's Simulation page reports whether rclpy is importable in
its own environment — running the node itself is intentionally independent.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.detection_service import draw_detections  # noqa: E402


class AdasPerceptionNode(Node):
    def __init__(self):
        super().__init__("adas_perception")

        self.declare_parameter("model_path", str(BACKEND_DIR / "models" / "best.pt"))
        self.declare_parameter("conf", 0.35)
        self.declare_parameter("iou", 0.45)
        self.declare_parameter("imgsz", 640)
        self.declare_parameter("use_tracking", False)
        self.declare_parameter("image_topic", "/adas/image_raw")

        model_path = Path(self.get_parameter("model_path").value)
        conf = float(self.get_parameter("conf").value)
        iou = float(self.get_parameter("iou").value)
        imgsz = int(self.get_parameter("imgsz").value)
        use_tracking = bool(self.get_parameter("use_tracking").value)
        image_topic = str(self.get_parameter("image_topic").value)

        self._params = {"conf": conf, "iou": iou, "imgsz": imgsz,
                        "tracker": "bytetrack.yaml" if use_tracking else None,
                        "persist": use_tracking}

        from services.model_service import ModelService

        self._model_service = ModelService()
        self._model_service.load(model_path)
        if not self._model_service.is_loaded:
            self.get_logger().error(f"Model not loaded: {self._model_service.message}")
            raise SystemExit(1)

        self._bridge = CvBridge()
        self._detection_pub = self.create_publisher(Detection2DArray, "/adas/detections", 10)
        self._image_pub = self.create_publisher(Image, "/adas/annotated_image", 10)
        qos = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._sub = self.create_subscription(Image, image_topic, self._on_image, qos)
        self.get_logger().info(
            f"ADAS perception ready — model={model_path} conf={conf} tracking={use_tracking} "
            f"topic={image_topic}"
        )

    def _on_image(self, msg: Image) -> None:
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"cv_bridge conversion failed: {exc}")
            return

        try:
            result, elapsed_ms = self._model_service.predict(frame, **self._params)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"inference failed: {exc}")
            return

        detections = self._model_service.parse_boxes(result)
        annotated = draw_detections(frame.copy(), detections)

        detection_array = Detection2DArray()
        detection_array.header = msg.header
        for det in detections:
            detection = Detection2D()
            detection.bbox.center.position.x = float((det["bbox"][0] + det["bbox"][2]) / 2.0)
            detection.bbox.center.position.y = float((det["bbox"][1] + det["bbox"][3]) / 2.0)
            detection.bbox.size_x = float(det["bbox"][2] - det["bbox"][0])
            detection.bbox.size_y = float(det["bbox"][3] - det["bbox"][1])
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = det["class_id"]
            hypothesis.hypothesis.score = det["confidence"]
            detection.results.append(hypothesis)
            detection_array.detections.append(detection)
        self._detection_pub.publish(detection_array)

        try:
            annotated_msg = self._bridge.cv2_to_imgmsg(annotated, encoding="bgr8")
            annotated_msg.header = msg.header
            self._image_pub.publish(annotated_msg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"annotated image publish failed: {exc}")

        self.get_logger().info(f"{len(detections)} objects in {elapsed_ms:.1f} ms", throttle_duration_sec=2.0)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = AdasPerceptionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
