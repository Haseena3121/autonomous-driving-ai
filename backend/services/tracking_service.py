"""ByteTrack multi-object tracking helpers.

Tracking itself is performed by Ultralytics' built-in ByteTrack implementation
(``model.predict(..., tracker="bytetrack.yaml", persist=True)``) applied to the
*actual* detections of the user-trained YOLO model. This module only adds the
visualisation (trajectory trails) and per-track summaries on top of those real
results — nothing here simulates detections or IDs.
"""

import logging

import cv2

logger = logging.getLogger(__name__)

BYTETRACK_NOTE = (
    'Tracking uses Ultralytics ByteTrack (tracker="bytetrack.yaml", persist=True) '
    "on the detections of the actual trained YOLO model."
)
TRAJECTORY_MAX_POINTS = 90


def draw_trajectories(image, trajectories: dict, active_ids, color=(56, 189, 248)):
    """Draw fading motion trails for the tracks visible in the current frame."""
    active = set(active_ids)
    for track_id, points in trajectories.items():
        if track_id not in active or len(points) < 2:
            continue
        pts = [(int(x), int(y)) for x, y in points]
        for i in range(1, len(pts)):
            ratio = i / len(pts)  # recent segments are drawn brighter
            faded = tuple(int(c * (0.3 + 0.7 * ratio)) for c in color)
            cv2.line(image, pts[i - 1], pts[i], faded, 2, cv2.LINE_AA)
        cv2.circle(image, pts[-1], 4, color, -1, cv2.LINE_AA)
    return image


def summarize_tracks(track_registry: dict) -> list[dict]:
    """Aggregate per-track statistics collected while processing the video."""
    rows = []
    for track in track_registry.values():
        frames = max(track["frames"], 1)
        rows.append(
            {
                "track_id": track["track_id"],
                "class_name": track["class_name"],
                "frames": track["frames"],
                "avg_confidence": round(track["conf_sum"] / frames, 4),
            }
        )
    rows.sort(key=lambda row: (-row["frames"], row["track_id"]))
    return rows
