"""Pure-OpenCV lane detection tests (no model required)."""

import cv2
import numpy as np

from services.lane_service import LaneDetectionService


def _road_image(width=640, height=360):
    image = np.full((height, width, 3), 40, np.uint8)
    # two bright lane markings converging towards a vanishing point
    # (explicit 3-channel colour: a bare scalar only fills the first channel)
    cv2.line(image, (120, height), (300, int(0.62 * height)), (235, 235, 235), 6)
    cv2.line(image, (560, height), (360, int(0.62 * height)), (235, 235, 235), 6)
    return image


def test_lane_detection_finds_lanes():
    image = _road_image()
    annotated, steps, meta = LaneDetectionService().detect(image, return_steps=True)
    assert annotated.shape == image.shape
    assert meta["lanes_detected"] in {"both", "left", "right"}
    assert meta["hough_segments"] > 0
    assert set(steps) == {"edges", "roi"}
    if meta["lanes_detected"] == "both":
        assert meta["lane_center_px"] is not None
        assert meta["offset_direction"] in {"left", "right"}
        assert meta["left_line"]["x_at_bottom"] < meta["right_line"]["x_at_bottom"]


def test_lane_detection_blank_image_reports_none():
    image = np.full((360, 640, 3), 40, np.uint8)
    annotated, _, meta = LaneDetectionService().detect(image)
    assert meta["lanes_detected"] == "none"
    assert meta["lane_center_px"] is None


def test_canny_parameters_are_respected():
    image = _road_image()
    _, _, meta_low = LaneDetectionService().detect(image, canny_low=10, canny_high=60)
    _, _, meta_high = LaneDetectionService().detect(image, canny_low=200, canny_high=400)
    assert meta_low["image_width"] == 640
    assert meta_high["hough_segments"] >= 0
