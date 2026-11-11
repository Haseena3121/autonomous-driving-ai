"""Deep lane segmentation (ENet) tests — skip when PyTorch is not installed."""

import pytest

torch = pytest.importorskip("torch")

from services.deep_lane_service import ENet  # noqa: E402


def test_enet_output_shape():
    net = ENet(num_classes=1)
    net.eval()
    with torch.no_grad():
        out = net(torch.randn(1, 3, 288, 512))
    assert out.shape == (1, 1, 288, 512)


def test_enet_odd_size_input_is_supported():
    net = ENet(num_classes=1)
    net.eval()
    with torch.no_grad():
        out = net(torch.randn(1, 3, 304, 544))
    assert out.shape == (1, 1, 304, 544)


def test_enet_state_dict_roundtrip(tmp_path):
    net = ENet(num_classes=1)
    torch.save({"state_dict": net.state_dict(), "num_classes": 1, "meta": {"epochs": 1}}, tmp_path / "ckpt.pth")
    loaded = torch.load(tmp_path / "ckpt.pth", map_location="cpu", weights_only=False)
    other = ENet(num_classes=loaded["num_classes"])
    other.load_state_dict(loaded["state_dict"], strict=True)
