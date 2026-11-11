#!/usr/bin/env python3
"""Train YOLO on the converted BDD100K dataset (CLI mirror of the Colab cell).

Usage:
    python train_yolo.py --data datasets/bdd100k/data.yaml --epochs 50
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

DEFAULTS = {
    "model": "yolov8s.pt",
    "epochs": 50,
    "imgsz": 640,
    "batch": 16,
    "optimizer": "auto",
    "lr0": 0.01,
    "patience": 20,
    "project": "bdd100k_yolo",
    "name": "adas_v1",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Path to data.yaml (see bdd100k_to_yolo.py)")
    parser.add_argument("--model", default=DEFAULTS["model"])
    parser.add_argument("--epochs", type=int, default=DEFAULTS["epochs"])
    parser.add_argument("--imgsz", type=int, default=DEFAULTS["imgsz"])
    parser.add_argument("--batch", type=int, default=DEFAULTS["batch"])
    parser.add_argument("--device", default=None, help="'0' for GPU, 'cpu' otherwise")
    parser.add_argument("--project", default=DEFAULTS["project"])
    parser.add_argument("--name", default=DEFAULTS["name"])
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
    )
    metrics = model.val()
    best = Path(model.trainer.best).resolve()
    run_dir = best.parent.parent
    print("\nTraining finished.")
    print(f"  best weights : {best}")
    print(f"  run folder   : {run_dir}  (copy results.csv + args.yaml too)")
    if metrics is not None:
        try:
            print(f"  mAP50        : {metrics.box.map50:.4f}")
            print(f"  mAP50-95     : {metrics.box.map:.4f}")
        except AttributeError:
            pass
    print("\nPlace into the website project:")
    print(f"  cp {best} backend/models/best.pt")
    print(f"  cp {run_dir}/results.csv backend/models/results.csv")
    print(f"  cp {run_dir}/args.yaml backend/models/args.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
