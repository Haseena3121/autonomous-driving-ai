#!/usr/bin/env python3
"""Export the trained model to ONNX / TensorRT (required tech stack).

Usage:
    python export_model.py --weights backend/models/best.pt --format onnx
    python export_model.py --weights backend/models/best.pt --format engine  # TensorRT, GPU only
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=Path("backend/models/best.pt"))
    parser.add_argument("--format", choices=["onnx", "engine", "torchscript"], default="onnx")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--half", action="store_true", help="FP16 (engine/onnx with GPU)")
    args = parser.parse_args()

    if not args.weights.exists():
        print(f"Weights not found: {args.weights}\nTrain first (see model_training/README.md).")
        return 1

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print(f"Missing ultralytics: {exc}\npip install ultralytics")
        return 1

    model = YOLO(str(args.weights))
    path = model.export(format=args.format, imgsz=args.imgsz, half=args.half)
    print(f"\nExported: {path}")

    if args.format == "onnx":
        print("Benchmark it inside the app: YOLO('best.onnx') — pip install onnxruntime-gpu (or onnxruntime)")
    if args.format == "engine":
        print("TensorRT engine ready — works only on the machine/GPU where it was built.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
