"""hf_download.download_small writes atomically (no half-written targets)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_hf():
    spec = importlib.util.spec_from_file_location("yue2_hf_download_atomic",
                                                  ROOT / "tools" / "hf_download.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_small_download_does_not_leave_partial_target(tmp_path, monkeypatch):
    hf = _load_hf()
    monkeypatch.setattr(hf, "head_size", lambda repo, name: 10)
    monkeypatch.setattr(hf.time, "sleep", lambda *_args, **_kwargs: None)

    def failing_curl(url, out, start=None, end=None, retries=4):
        out.write_bytes(b"12345")  # partial body before the connection dies
        raise RuntimeError("network down")

    monkeypatch.setattr(hf, "curl_download", failing_curl)
    out = tmp_path / "model.safetensors"

    assert hf.download_small("m-a-p/X", "model.safetensors", out, retries=2) is False
    assert not out.exists()
    assert not list(tmp_path.glob(".*.tmp-*"))


def test_small_download_replaces_target_only_when_complete(tmp_path, monkeypatch):
    hf = _load_hf()
    monkeypatch.setattr(hf, "head_size", lambda repo, name: 5)

    def good_curl(url, out, start=None, end=None, retries=4):
        out.write_bytes(b"hello")
        return True

    monkeypatch.setattr(hf, "curl_download", good_curl)
    out = tmp_path / "cfg.json"
    out.write_bytes(b"old")  # different size -> must be replaced

    assert hf.download_small("m-a-p/X", "cfg.json", out) is True
    assert out.read_bytes() == b"hello"
    assert not list(tmp_path.glob(".*.tmp-*"))
