"""Classical OpenCV lane detection.

Pipeline: grayscale -> Gaussian blur -> Canny edges -> trapezoidal region of
interest mask -> probabilistic Hough transform -> left/right lane fitting
(least-squares in x = m*y + b form) -> extrapolated lane overlay + lane-centre
estimation relative to the image centre.

This module uses only OpenCV/NumPy — no learned weights — so it always works
and serves as the classical baseline for the deep-learning comparison in
``deep_lane_service.py``.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class LaneDetectionService:
    """Classic Canny + Hough lane detector with lane-centre estimation."""

    def detect(self, image_bgr, canny_low: int = 50, canny_high: int = 150, return_steps: bool = False):
        height, width = image_bgr.shape[:2]

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, int(canny_low), int(canny_high))
        roi_mask = self._roi_mask(edges)
        masked_edges = cv2.bitwise_and(edges, roi_mask)

        segments = cv2.HoughLinesP(
            masked_edges,
            rho=2,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=max(20, int(width * 0.05)),
            maxLineGap=max(20, int(width * 0.08)),
        )
        segment_count = 0 if segments is None else len(segments)

        left_points, right_points = [], []
        mid_x = width / 2.0
        if segments is not None:
            for line in segments:
                x1, y1, x2, y2 = line[0]
                if x2 == x1:
                    continue
                slope = (y2 - y1) / (x2 - x1)
                length = float(np.hypot(x2 - x1, y2 - y1))
                if abs(slope) < 0.3 or length < 25:
                    continue
                bucket = left_points if slope < 0 else right_points
                bucket.append((x1, y1, length))
                bucket.append((x2, y2, length))

        left_fit = self._fit_line(left_points)
        right_fit = self._fit_line(right_points)

        y_bottom, y_top = height, int(height * 0.62)
        left_line = self._line_meta(left_fit, y_top, y_bottom) if left_fit else None
        right_line = self._line_meta(right_fit, y_top, y_bottom) if right_fit else None

        if left_fit and right_fit:
            lanes_detected = "both"
        elif left_fit:
            lanes_detected = "left"
        elif right_fit:
            lanes_detected = "right"
        else:
            lanes_detected = "none"

        annotated = image_bgr.copy()
        self._draw_segments(annotated, segments, color=(210, 210, 90))
        if left_fit:
            self._draw_lane_line(annotated, left_fit, y_top, y_bottom, color=(90, 220, 90))
        if right_fit:
            self._draw_lane_line(annotated, right_fit, y_top, y_bottom, color=(60, 140, 250))

        lane_center_px = None
        offset_px = None
        offset_direction = None
        if left_fit and right_fit:
            x_left = self._x_at(left_fit, y_bottom)
            x_right = self._x_at(right_fit, y_bottom)
            lane_center_px = (x_left + x_right) / 2.0
            offset_px = lane_center_px - width / 2.0
            offset_direction = "right" if offset_px > 0 else "left"
            self._draw_lane_fill(annotated, left_fit, right_fit, y_top, y_bottom)
            self._draw_center_marker(annotated, lane_center_px, width, y_top, y_bottom, offset_px)

        meta = {
            "image_width": width,
            "image_height": height,
            "hough_segments": segment_count,
            "lanes_detected": lanes_detected,
            "left_line": left_line,
            "right_line": right_line,
            "lane_center_px": round(lane_center_px, 1) if lane_center_px is not None else None,
            "image_center_px": round(width / 2.0, 1),
            "offset_px": round(offset_px, 1) if offset_px is not None else None,
            "offset_direction": offset_direction,
            "note": (
                "offset_px > 0 means the estimated lane centre sits right of the image centre. "
                "Available only when both lane boundaries are detected."
            ),
        }

        steps = None
        if return_steps:
            steps = {
                "edges": self._to_bgr(edges),
                "roi": self._to_bgr(masked_edges),
            }
        return annotated, steps, meta

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _roi_mask(edges):
        height, width = edges.shape[:2]
        mask = np.zeros_like(edges)
        polygon = np.array(
            [
                [
                    (int(0.06 * width), height),
                    (int(0.42 * width), int(0.60 * height)),
                    (int(0.58 * width), int(0.60 * height)),
                    (int(0.94 * width), height),
                ]
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [polygon], 255)
        return mask

    @staticmethod
    def _fit_line(points):
        """Least-squares fit x = m*y + b (stable for near-vertical lanes)."""
        if len(points) < 4:
            return None
        ys = np.array([p[1] for p in points], dtype=np.float64)
        xs = np.array([p[0] for p in points], dtype=np.float64)
        weights = np.array([p[2] for p in points], dtype=np.float64)
        if np.ptp(ys) < 10:  # almost horizontal line cluster -> not a lane
            return None
        try:
            m, b = np.polyfit(ys, xs, 1, w=weights)
        except (np.linalg.LinAlgError, ValueError):
            return None
        if not np.isfinite(m) or not np.isfinite(b):
            return None
        return {"slope": float(m), "intercept": float(b)}

    @staticmethod
    def _x_at(fit: dict, y: float) -> float:
        return fit["slope"] * y + fit["intercept"]

    def _line_meta(self, fit: dict, y_top: int, y_bottom: int) -> dict:
        return {
            "slope_xy": round(fit["slope"], 4),
            "x_at_bottom": round(self._x_at(fit, y_bottom), 1),
            "x_at_top": round(self._x_at(fit, y_top), 1),
        }

    @staticmethod
    def _draw_lane_line(image, fit: dict, y_top: int, y_bottom: int, color) -> None:
        p1 = (int(LaneDetectionService._x_at(fit, y_bottom)), y_bottom)
        p2 = (int(LaneDetectionService._x_at(fit, y_top)), y_top)
        cv2.line(image, p1, p2, color, 6, cv2.LINE_AA)

    @staticmethod
    def _draw_lane_fill(image, left_fit: dict, right_fit: dict, y_top: int, y_bottom: int) -> None:
        overlay = image.copy()
        p1 = (int(LaneDetectionService._x_at(left_fit, y_bottom)), y_bottom)
        p2 = (int(LaneDetectionService._x_at(left_fit, y_top)), y_top)
        p3 = (int(LaneDetectionService._x_at(right_fit, y_top)), y_top)
        p4 = (int(LaneDetectionService._x_at(right_fit, y_bottom)), y_bottom)
        cv2.fillPoly(overlay, [np.array([p1, p2, p3, p4], dtype=np.int32)], (250, 190, 60))
        cv2.addWeighted(overlay, 0.14, image, 0.86, 0, dst=image)

    @staticmethod
    def _draw_center_marker(image, lane_center_px: float, width: int, y_top: int, y_bottom: int, offset_px: float) -> None:
        center = (int(lane_center_px), (y_top + y_bottom) // 2)
        cv2.circle(image, center, 9, (240, 80, 240), 3, cv2.LINE_AA)
        cv2.line(image, (center[0], y_top), (center[0], y_bottom), (240, 80, 240), 2, cv2.LINE_AA)
        image_center = int(width / 2)
        cv2.line(image, (image_center, y_top), (image_center, y_bottom), (200, 200, 200), 1, cv2.LINE_AA)
        label = f"offset {offset_px:+.0f}px"
        cv2.putText(image, label, (12, y_bottom - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 80, 240), 2, cv2.LINE_AA)

    @staticmethod
    def _draw_segments(image, segments, color) -> None:
        if segments is None:
            return
        for line in segments:
            x1, y1, x2, y2 = line[0]
            cv2.line(image, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)

    @staticmethod
    def _to_bgr(gray_image):
        return cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
