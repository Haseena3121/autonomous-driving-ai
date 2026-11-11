#!/usr/bin/env python3
"""Convert BDD100K detection labels (JSON) to Ultralytics YOLO format.

Produces:
    <out>/images/train  <out>/images/val     (copies of the source images)
    <out>/labels/train  <out>/labels/val     (one .txt per image: cls cx cy w h, normalised)
    <out>/data.yaml     (Ultralytics dataset definition)

Usage (Colab):
    !python bdd100k_to_yolo.py \
        --labels-train bdd100k/labels/bdd100k_labels_images_train.json \
        --labels-val   bdd100k/labels/bdd100k_labels_images_val.json \
        --images-train bdd100k/images/100k/train \
        --images-val   bdd100k/images/100k/val \
        --out datasets/bdd100k
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Canonical BDD100K detection class order (also used by most public mirrors).
BDD_CLASSES = [
    "person",
    "rider",
    "car",
    "bus",
    "truck",
    "bike",
    "motor",
    "traffic light",
    "traffic sign",
    "train",
]
CLASS_TO_ID = {name: idx for idx, name in enumerate(BDD_CLASSES)}


def convert_split(labels_json: Path, images_dir: Path, out_images: Path, out_labels: Path) -> dict:
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    with labels_json.open(encoding="utf-8") as handle:
        frames = json.load(handle)

    stats = {"frames": 0, "with_objects": 0, "boxes": 0, "skipped": 0, "missing_images": 0}
    for frame in frames:
        name = frame.get("name")
        if not name:
            continue
        stats["frames"] += 1

        image_path = images_dir / name
        if not image_path.exists():
            stats["missing_images"] += 1
            continue

        lines = []
        for label in frame.get("labels", []):
            category = label.get("category")
            class_id = CLASS_TO_ID.get(category)
            box2d = label.get("box2d")
            if class_id is None or box2d is None:
                stats["skipped"] += 1
                continue
            x1, y1 = float(box2d["x1"]), float(box2d["y1"])
            x2, y2 = float(box2d["x2"]), float(box2d["y2"])
            width = x2 - x1
            height = y2 - y1
            if width <= 1 or height <= 1:
                stats["skipped"] += 1
                continue

            image_w = float(label.get("width", 1280) or 1280)
            image_h = float(label.get("height", 720) or 720)
            # BDD100K frame entries do not carry size; infer from the image once.
            if image_w == 1280 and image_h == 720:
                image_w, image_h = float(frame.get("img_w", 1280)), float(frame.get("img_h", 720))

            cx = (x1 + x2) / 2.0 / image_w
            cy = (y1 + y2) / 2.0 / image_h
            w = width / image_w
            h = height / image_h
            cx, cy, w, h = (max(0.0, min(1.0, v)) for v in (cx, cy, w, h))
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
            stats["boxes"] += 1

        stem = Path(name).stem
        label_path = out_labels / f"{stem}.txt"
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if lines:
            stats["with_objects"] += 1

        target = out_images / name
        if not target.exists():
            shutil.copy2(image_path, target)

    return stats


def write_data_yaml(out_dir: Path) -> Path:
    yaml_path = out_dir / "data.yaml"
    names_block = "\n".join(f"  {idx}: {name}" for idx, name in enumerate(BDD_CLASSES))
    yaml_path.write_text(
        f"path: {out_dir.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n"
        f"nc: {len(BDD_CLASSES)}\n"
        f"names:\n{names_block}\n",
        encoding="utf-8",
    )
    return yaml_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-train", required=True, type=Path)
    parser.add_argument("--labels-val", required=True, type=Path)
    parser.add_argument("--images-train", required=True, type=Path)
    parser.add_argument("--images-val", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="Output dataset directory")
    args = parser.parse_args()

    out = args.out
    print(f"[1/3] Converting train split -> {out / 'labels' / 'train'}")
    train_stats = convert_split(args.labels_train, args.images_train, out / "images" / "train", out / "labels" / "train")
    print(f"[2/3] Converting val split   -> {out / 'labels' / 'val'}")
    val_stats = convert_split(args.labels_val, args.images_val, out / "images" / "val", out / "labels" / "val")
    yaml_path = write_data_yaml(out)
    print(f"[3/3] Wrote dataset definition {yaml_path}")

    for split, stats in (("train", train_stats), ("val", val_stats)):
        print(
            f"{split}: frames={stats['frames']} with_objects={stats['with_objects']} "
            f"boxes={stats['boxes']} skipped_labels={stats['skipped']} missing_images={stats['missing_images']}"
        )
    print("\nNext step (Colab):")
    print(f"  from ultralytics import YOLO")
    print(f'  YOLO("yolov8s.pt").train(data="{yaml_path}", epochs=50, imgsz=640, batch=16)')
    return 0


if __name__ == "__main__":
    sys.exit(main())
