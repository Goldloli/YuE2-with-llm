"""Local port configuration: ``--port`` > ``YUE2_PORT`` > default 9086."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_MODULES = {}


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _modules():
    if not _MODULES:
        _MODULES["server"] = _load("web/server.py", "yue_server_port")
        _MODULES["start"] = _load("tools/start.py", "yue_start_port")
    return _MODULES["server"], _MODULES["start"]


def test_default_port_is_9086(monkeypatch):
    monkeypatch.delenv("YUE2_PORT", raising=False)
    server, start = _modules()
    assert server.DEFAULT_PORT == 9086
    assert start.DEFAULT_PORT == 9086
    assert server._resolve_port([]) == 9086
    assert start.resolve_port([]) == 9086


def test_env_override(monkeypatch):
    monkeypatch.setenv("YUE2_PORT", "9222")
    server, start = _modules()
    assert server._resolve_port([]) == 9222
    assert start.resolve_port([]) == 9222


def test_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("YUE2_PORT", "9222")
    server, start = _modules()
    assert server._resolve_port(["--port", "9333"]) == 9333
    assert server._resolve_port(["--port=9444"]) == 9444
    assert start.resolve_port(["--port", "9333"]) == 9333
    assert start.resolve_port(["--port=9444"]) == 9444


def test_invalid_port_falls_back_to_default(monkeypatch, capsys):
    monkeypatch.setenv("YUE2_PORT", "abc")
    server, start = _modules()
    assert server._resolve_port([]) == 9086
    assert start.resolve_port([]) == 9086
    assert server._resolve_port(["--port", "70000"]) == 9086
    assert start.resolve_port(["--port", "0"]) == 9086
    assert "using default port 9086" in capsys.readouterr().err


def test_start_url_and_child_env_follow_resolved_port(monkeypatch):
    monkeypatch.delenv("YUE2_PORT", raising=False)
    _, start = _modules()
    try:
        start.set_port(9333)
        assert start.PORT == 9333
        assert start.URL == "http://127.0.0.1:9333"
        env = start.server_process_env({"PYTHONPATH": "x"})
        assert env["YUE2_PORT"] == "9333"
        assert env["PYTHONPATH"] == "x"
    finally:
        start.set_port(start.DEFAULT_PORT)


def test_launchers_pass_extra_arguments():
    mac = (ROOT / "packaging/launchers/start.command").read_text(encoding="utf-8")
    win = (ROOT / "packaging/launchers/start.bat").read_text(encoding="utf-8")
    assert 'tools/start.py --bundled "$@"' in mac
    assert "tools\\start.py --bundled %*" in win
