"""Training-metrics parsers must return REAL numbers from REAL files."""

import pytest

from services.performance_service import parse_args_yaml, parse_results_csv

CSV_CONTENT = (
    "epoch,time,train/box_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)\n"
    "1,12.3,1.2,0.710,0.620,0.680,0.470\n"
    "2,24.6,1.1,0.750,0.660,0.720,0.510\n"
)


def test_parse_results_csv_picks_best_epoch(tmp_path):
    path = tmp_path / "results.csv"
    path.write_text(CSV_CONTENT, encoding="utf-8")
    metrics = parse_results_csv(path)
    assert metrics["epoch"] == 2
    assert metrics["total_epochs"] == 2
    assert metrics["precision"] == pytest.approx(0.75)
    assert metrics["recall"] == pytest.approx(0.66)
    assert metrics["map50"] == pytest.approx(0.72)
    assert metrics["map50_95"] == pytest.approx(0.51)
    assert "results.csv" in metrics["source"]


def test_parse_results_csv_missing_file(tmp_path):
    assert parse_results_csv(tmp_path / "nope.csv") is None


def test_parse_results_csv_garbage_file(tmp_path):
    path = tmp_path / "results.csv"
    path.write_text("not,a,real,csv\n1,2,3,4\n", encoding="utf-8")
    assert parse_results_csv(path) is None


def test_parse_args_yaml(tmp_path):
    path = tmp_path / "args.yaml"
    path.write_text("epochs: 50\nimgsz: 640\nbatch: 16\ndata: bdd100k.yaml\n", encoding="utf-8")
    parsed = parse_args_yaml(path)
    assert parsed["epochs"] == 50
    assert parsed["imgsz"] == 640
    assert parsed["batch"] == 16
