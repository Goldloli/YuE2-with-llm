"""Download-channel resolution in tools/hf_download.py (domestic mirror vs HF)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import hf_download  # noqa: E402


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """No env override, no real settings file, and restore the module-level BASE."""
    monkeypatch.delenv("YUE2_HF_ENDPOINT", raising=False)
    settings = tmp_path / "web" / "data" / "settings.json"
    monkeypatch.setattr(hf_download, "SETTINGS_FILE", settings)
    original_base = hf_download.BASE
    yield settings
    hf_download.BASE = original_base


def write_settings(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_defaults_to_domestic_mirror(isolate):
    assert hf_download.resolve_endpoint() == ("https://hf-mirror.com", "mirror")


def test_explicit_source(isolate):
    assert hf_download.resolve_endpoint(source="huggingface") == (
        "https://huggingface.co", "huggingface")


def test_explicit_endpoint_beats_source_and_env(isolate, monkeypatch):
    monkeypatch.setenv("YUE2_HF_ENDPOINT", "https://env.example")
    assert hf_download.resolve_endpoint(endpoint="https://custom.example/", source="mirror") == (
        "https://custom.example", "custom")


def test_source_beats_env_and_env_beats_saved(isolate, monkeypatch):
    write_settings(isolate, {"download_source": "huggingface"})
    monkeypatch.setenv("YUE2_HF_ENDPOINT", "https://env.example")
    assert hf_download.resolve_endpoint()[0] == "https://env.example"
    assert hf_download.resolve_endpoint(source="mirror")[0] == "https://hf-mirror.com"


def test_saved_channel_is_used(isolate):
    write_settings(isolate, {"download_source": "huggingface", "decoder": "legacy"})
    assert hf_download.resolve_endpoint() == ("https://huggingface.co", "huggingface")


def test_invalid_saved_channel_is_ignored(isolate):
    write_settings(isolate, {"download_source": "ftp"})
    assert hf_download.resolve_endpoint()[0] == "https://hf-mirror.com"


def test_set_endpoint_updates_url_builder(isolate):
    hf_download.set_endpoint("https://example.test/")
    assert hf_download.url_for("m-a-p/YuE2-3B", "config.json") == (
        "https://example.test/m-a-p/YuE2-3B/resolve/main/config.json")


def test_unknown_mode_prints_usage(isolate):
    assert hf_download.main(["nope"]) == 2


def test_failure_reports_channel_and_switch_hint(isolate, monkeypatch, capsys):
    def boom(mode):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(hf_download, "run", boom)
    assert hf_download.main(["--source", "huggingface", "core"]) == 1
    err = capsys.readouterr().err
    assert "下载失败" in err and "--source mirror" in err
