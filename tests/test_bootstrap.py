"""Environment bootstrap: models are downloaded by the app, channel choice persists."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bootstrap  # noqa: E402
import start  # noqa: E402


class FakeStdin(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(start, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "VENV", tmp_path / ".venv")
    monkeypatch.setattr(start, "VENV", tmp_path / ".venv")
    monkeypatch.setattr(bootstrap, "SHEETSAGE_VENV", tmp_path / ".venv-sheetsage2")
    monkeypatch.setattr(bootstrap, "MLX_VENV", tmp_path / ".venv-mlx")
    (tmp_path / "models").mkdir()
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: None)
    monkeypatch.setattr(bootstrap, "ensure_venv", lambda: tmp_path / ".venv/bin/python")
    monkeypatch.setattr(bootstrap, "install_deps", lambda py: None)
    monkeypatch.setattr(bootstrap, "ensure_mlx_runtime", lambda: None)
    monkeypatch.setattr(bootstrap, "run", lambda cmd, **kw: None)
    monkeypatch.setattr(sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(bootstrap, "download", lambda mode, channel=None: calls.append((mode, channel)))
    monkeypatch.setattr(sys, "argv", ["bootstrap.py", "--yes"])
    return tmp_path, calls


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_default_run_downloads_no_models(env):
    root, calls = env
    bootstrap.main()
    assert calls == []
    assert not (root / "web" / "data" / "settings.json").exists()


def test_models_flag_downloads_core_from_mirror(env):
    _, calls = env
    sys.argv = ["bootstrap.py", "--yes", "--models"]  # noqa: F841 - monkeypatched sys
    bootstrap.main()
    assert calls[0] == ("core", "mirror")
    assert {channel for _, channel in calls} == {"mirror"}


def test_download_source_flag_is_forwarded(env):
    _, calls = env
    sys.argv = ["bootstrap.py", "--yes", "--models", "--download-source", "huggingface"]  # noqa: F841
    bootstrap.main()
    assert calls[0] == ("core", "huggingface")
    assert {channel for _, channel in calls} == {"huggingface"}


def test_mlx_flag_fetches_mlx_weights(env):
    _, calls = env
    sys.argv = ["bootstrap.py", "--yes", "--models", "--mlx"]  # noqa: F841
    bootstrap.main()
    assert ("mlx", "mirror") in calls


def test_interactive_choice_is_persisted(env, monkeypatch):
    root, _ = env
    monkeypatch.setattr(sys, "stdin", FakeStdin("2\n"))
    assert bootstrap.choose_channel(assume_yes=False) == "huggingface"
    saved = json.loads((root / "web" / "data" / "settings.json").read_text(encoding="utf-8"))
    assert saved["download_source"] == "huggingface"
    # a second call reuses the saved channel without prompting
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))  # would raise if prompted
    assert bootstrap.choose_channel(assume_yes=False) == "huggingface"


def test_fixed_source_skips_prompt(env, monkeypatch):
    root, _ = env
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))  # would raise if prompted
    assert bootstrap.choose_channel(assume_yes=False, fixed="mirror") == "mirror"
    assert not (root / "web" / "data" / "settings.json").exists()


def test_save_channel_keeps_other_settings(env):
    root, _ = env
    path = root / "web" / "data" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"decoder": "legacy"}), encoding="utf-8")
    bootstrap.save_channel("huggingface")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == {"decoder": "legacy", "download_source": "huggingface"}


def test_any_engine_ready_accepts_mlx_only(env):
    root, _ = env
    assert not bootstrap.any_engine_ready()
    _touch(root / "models" / "YuE2-3B-MLX" / "8bit" / "model.safetensors")
    assert bootstrap.any_engine_ready()


def test_start_models_ready_accepts_mlx_only(env):
    root, _ = env
    assert not start.models_ready()
    _touch(root / "models" / "YuE2-3B-MLX" / "4bit" / "model.safetensors")
    assert start.models_ready()


def test_start_env_ready_requires_deps_marker(env):
    root, _ = env
    assert not start.env_ready()
    _touch(root / ".venv" / "bin" / "python")
    assert not start.env_ready()
    _touch(root / ".venv" / ".deps-installed")
    assert start.env_ready()
