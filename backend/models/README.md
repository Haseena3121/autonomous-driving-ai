# Trained model location

Place your Google-Colab-trained weights here:

```
backend/models/best.pt      <- REQUIRED  (your BDD100K YOLO model)
backend/models/results.csv  <- optional  (real training metrics for the Performance page)
backend/models/args.yaml    <- optional  (training hyper-parameters for the Model Info page)
backend/models/lane_seg_enet.pth <- optional (YOUR ENet lane segmentation checkpoint)
```

The server never ships or downloads a substitute model. While `best.pt` is
missing:

* `/api/health` reports `model.status = "missing"`,
* `/api/model/info` shows the exact expected path,
* every inference endpoint returns **HTTP 503** with setup instructions,
* the website shows the model setup guide on the dashboard.

After copying the file, restart the backend (or press **Reload model** on the
Model Information page). The full Colab training workflow is documented in
[`model_training/README.md`](../../model_training/README.md).
