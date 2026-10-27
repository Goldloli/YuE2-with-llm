"""Bootstrap skip logic for model-embedded bundles (models/.bundle marker)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import bootstrap  # noqa: E402
import start  # noqa: E402


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "VENV", tmp_path / ".venv")
    monkeypatch.setattr(bootstrap, "MLX_VENV", tmp_path / ".venv-mlx")
    monkeypatch.setattr(bootstrap, "SHEETSAGE_VENV", tmp_path / ".venv-sheetsage2")
    (tmp_path / "models").mkdir()
    monkeypatch.setattr(sys, "argv", ["bootstrap.py", "--yes"])
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: None)
    monkeypatch.setattr(bootstrap, "ensure_venv", lambda: tmp_path / ".venv/bin/python")
    monkeypatch.setattr(bootstrap, "install_deps", lambda py: None)
    monkeypatch.setattr(bootstrap, "run", lambda cmd, **kw: None)
    calls = []
    monkeypatch.setattr(bootstrap, "download", lambda mode: calls.append(mode))
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(bootstrap.platform, "machine", lambda: "arm64")
    return tmp_path, calls


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_slim_package_downloads_everything(fake_root):
    _, calls = fake_root
    bootstrap.main()
    assert calls == ["core", "extras", "mlx", "transcribe"]


def test_mlx_only_bundle_downloads_nothing(fake_root):
    root, calls = fake_root
    _touch(root / "models" / "YuE2-3B-MLX" / "4bit" / "model.safetensors")
    _touch(root / "models" / ".bundle")
    bootstrap.main()
    assert calls == []


def test_torch_bundle_skips_optionals(fake_root, monkeypatch):
    root, calls = fake_root
    _touch(root / "models" / ".bundle")
    monkeypatch.setattr(sys, "platform", "win32")  # torch-only tier 只在 Windows 存在
    monkeypatch.setattr(bootstrap, "core_ready", lambda: True)
    bootstrap.main()
    assert calls == []  # extras/transcribe skipped for bundles; Models page fetches later


def test_bundle_flag_still_downloads_on_request(fake_root):
    root, calls = fake_root
    _touch(root / "models" / ".bundle")
    _touch(root / "models" / "YuE2-3B-MLX" / "8bit" / "model.safetensors")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sys, "argv", ["bootstrap.py", "--yes", "--extras"])
    bootstrap.main()
    assert calls == ["extras"]
    monkeypatch.undo()


def test_start_models_ready_accepts_mlx_only(tmp_path, monkeypatch):
    monkeypatch.setattr(start, "ROOT", tmp_path)
    (tmp_path / "models").mkdir()
    assert not start.models_ready()
    _touch(tmp_path / "models" / "YuE2-3B-MLX" / "8bit" / "model.safetensors")
    assert start.models_ready()
