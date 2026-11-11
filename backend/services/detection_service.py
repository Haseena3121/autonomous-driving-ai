"""Single-image detection with the real trained model + OpenCV annotation."""

import base64
import logging
from collections import Counter

import cv2
import numpy as np

from services.model_service import get_model_service

logger = logging.getLogger(__name__)

# BGR palette, cycled by class id.
PALETTE = [
    (248, 189, 56), (113, 113, 248), (36, 191, 251), (113, 113, 248), (250, 139, 167),
    (212, 234, 94), (21, 204, 250), (182, 114, 244), (250, 165, 96), (128, 222, 74),
    (60, 146, 251), (248, 140, 129),
]


def class_color(class_id: int) -> tuple:
    return PALETTE[class_id % len(PALETTE)]


def draw_detections(image, detections, draw_track_ids: bool = True):
    """Draw boxes + labels on a copy-safe BGR image (mutates and returns it)."""
    height, width = image.shape[:2]
    scale = max(height, width) / 1000.0
    thickness = max(1, round(2 * scale))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.45, 0.6 * scale)
    font_thickness = max(1, thickness - 1)

    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        color = class_color(det["class_id"])
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

        label = det["class_name"]
        if det.get("confidence") is not None:
            label += f" {det['confidence'] * 100:.0f}%"
        if draw_track_ids and det.get("track_id") is not None:
            label += f" #{det['track_id']}"

        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)
        top = y1 - text_h - baseline - 6
        if top < 0:  # box touches the top edge -> draw the label inside
            top = y1 + 4
            bottom = top + text_h + baseline + 4
            org = (x1 + 4, bottom - baseline - 2)
        else:
            bottom = y1
            org = (x1 + 4, y1 - baseline - 4)
        cv2.rectangle(image, (x1, top), (x1 + text_w + 8, bottom), color, -1)
        cv2.putText(image, label, org, font, font_scale, (16, 20, 26), font_thickness, cv2.LINE_AA)
    return image


def encode_jpeg(image, quality: int = 90) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buffer.tobytes()


def to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")


def decode_image_bytes(data: bytes):
    """Decode uploaded bytes into a BGR image, or None if invalid."""
    array = np.frombuffer(data, np.uint8)
    if array.size == 0:
        return None
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def detect_image(image_bgr, conf: float = 0.25, iou: float = 0.45, imgsz: int = 640) -> dict:
    """Run the actual trained model on one image and annotate it."""
    service = get_model_service()
    service.require_model()

    result, elapsed_ms = service.predict(image_bgr, conf=conf, iou=iou, imgsz=imgsz)
    detections = service.parse_boxes(result)
    annotated = draw_detections(image_bgr.copy(), detections)

    per_class = Counter(d["class_name"] for d in detections)
    confidences = [d["confidence"] for d in detections]
    height, width = image_bgr.shape[:2]

    return {
        "detections": detections,
        "annotated": annotated,
        "inference_ms": round(elapsed_ms, 1),
        "stats": {
            "total": len(detections),
            "per_class": dict(sorted(per_class.items(), key=lambda kv: -kv[1])),
            "class_count": len(per_class),
            "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        },
        "image_size": {"width": width, "height": height},
        "device": service.device,
        "model_status": service.status,
    }
