#!/usr/bin/env python3
"""Train the ENet lane-segmentation comparison model used by the website.

Dataset: a folder of road images + a folder of same-name binary masks
(white = lane pixels, black = background). Works with BDD100K lane maps or
TuSimple-converted masks.

The checkpoint is written to backend/models/lane_seg_enet.pth with metadata;
the Lane Detection page then labels the deep comparison as "trained by me".

Usage:
    python train_lane_enet.py --images dataset/lane/images --masks dataset/lane/masks --epochs 40
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.deep_lane_service import ENet, INPUT_HEIGHT, INPUT_WIDTH  # noqa: E402


def build_pairs(images_dir: Path, masks_dir: Path):
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    pairs = []
    for image_path in sorted(images_dir.iterdir()):
        if image_path.suffix.lower() not in exts:
            continue
        mask_path = None
        for candidate in (masks_dir / f"{image_path.stem}.png", masks_dir / image_path.name,
                          masks_dir / f"{image_path.stem}_mask.png"):
            if candidate.exists():
                mask_path = candidate
                break
        if mask_path is not None:
            pairs.append((image_path, mask_path))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--masks", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--val-split", type=float, default=0.1)
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "models" / "lane_seg_enet.pth")
    parser.add_argument("--device", default=None, help="'cuda' or 'cpu' (auto by default)")
    args = parser.parse_args()

    try:
        import cv2
        import numpy as np
        import torch
        import torch.nn.functional as F
    except ImportError as exc:
        print(f"Missing dependency: {exc}\nInstall backend/requirements.txt first.")
        return 1

    if not args.images.is_dir() or not args.masks.is_dir():
        print(f"Dataset folders not found: {args.images} / {args.masks}")
        return 1

    pairs = build_pairs(args.images, args.masks)
    if len(pairs) < 8:
        print(f"Need at least 8 image/mask pairs, found {len(pairs)}.")
        return 1

    rng = np.random.default_rng(0)
    indices = rng.permutation(len(pairs))
    val_count = max(2, int(len(pairs) * args.val_split))
    val_pairs = [pairs[i] for i in indices[:val_count]]
    train_pairs = [pairs[i] for i in indices[val_count:]]
    print(f"Dataset: {len(train_pairs)} train / {len(val_pairs)} val pairs "
          f"({INPUT_WIDTH}x{INPUT_HEIGHT} input)")

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    net = ENet(num_classes=1).to(device)
    optimiser = torch.optim.Adam(net.parameters(), lr=args.lr)
    criterion = torch.nn.BCEWithLogitsLoss()

    def load_batch(batch_pairs):
        images, masks = [], []
        for image_path, mask_path in batch_pairs:
            image = cv2.imread(str(image_path))
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if image is None or mask is None:
                continue
            image = cv2.resize(image, (INPUT_WIDTH, INPUT_HEIGHT))
            mask = cv2.resize(mask, (INPUT_WIDTH, INPUT_HEIGHT), interpolation=cv2.INTER_NEAREST)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            image = (image - mean) / std
            images.append(torch.from_numpy(image.transpose(2, 0, 1)))
            masks.append(torch.from_numpy((mask > 127).astype(np.float32)))
        return (torch.stack(images).to(device), torch.stack(masks).unsqueeze(1).to(device))

    best_loss = float("inf")
    for epoch in range(1, args.epochs + 1):
        net.train()
        order = rng.permutation(len(train_pairs))
        epoch_loss, batches = 0.0, 0
        for start in range(0, len(order), args.batch):
            batch = [train_pairs[i] for i in order[start : start + args.batch]]
            images, masks = load_batch(batch)
            if images.shape[0] == 0:
                continue
            optimiser.zero_grad()
            logits = net(images)
            loss = criterion(logits, masks)
            loss.backward()
            optimiser.step()
            epoch_loss += float(loss.item())
            batches += 1

        net.eval()
        val_loss, val_iou, val_n = 0.0, 0.0, 0
        with torch.no_grad():
            for start in range(0, len(val_pairs), args.batch):
                batch = val_pairs[start : start + args.batch]
                images, masks = load_batch(batch)
                if images.shape[0] == 0:
                    continue
                probs = torch.sigmoid(net(images))
                val_loss += float(criterion(probs, masks).item())
                preds = (probs > 0.5).float()
                inter = float((preds * masks).sum())
                union = float(((preds + masks) > 0).float().sum())
                if union > 0:
                    val_iou += inter / union
                val_n += 1

        msg = (f"epoch {epoch:3d}/{args.epochs} | train loss {epoch_loss / max(batches, 1):.4f} | "
               f"val loss {val_loss / max(val_n, 1):.4f} | val IoU {val_iou / max(val_n, 1):.4f}")
        if val_loss / max(val_n, 1) < best_loss:
            best_loss = val_loss / max(val_n, 1)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            torch.save(
                {
                    "state_dict": net.state_dict(),
                    "num_classes": 1,
                    "meta": {
                        "trained_by": "me (this project)",
                        "epochs": args.epochs,
                        "dataset": str(args.images),
                        "val_iou": round(val_iou / max(val_n, 1), 4),
                        "date": time.strftime("%Y-%m-%d %H:%M"),
                    },
                },
                str(args.out),
            )
            msg += "  ✓ saved"
        print(msg)

    print(f"\nCheckpoint written to {args.out}")
    print("The Lane Detection page now labels the deep comparison as 'trained by me'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
