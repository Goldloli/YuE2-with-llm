"""Self-contained one-click bundle: build helpers, launchers and smoke checks."""
from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))

import build_package as bp  # noqa: E402
import smoke_package as sp  # noqa: E402


def _load_start():
    spec = importlib.util.spec_from_file_location("yue2_start", ROOT / "tools" / "start.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_portable_runtime_is_pinned():
    assert bp.PBS_VERSION and bp.PBS_TAG
    assert bp.PBS_TRIPLES == {
        "macos": "aarch64-apple-darwin",
        "win-x64": "x86_64-pc-windows-msvc",
    }
    url = bp.PBS_URL.format(tag=bp.PBS_TAG, version=bp.PBS_VERSION,
                            triple=bp.PBS_TRIPLES["macos"])
    assert url.startswith("https://github.com/astral-sh/python-build-standalone/releases/download/")
    assert "install_only_stripped" in url


def test_bundle_requirements_track_pyproject():
    requirements = bp.bundle_requirements()
    torch_pin = next((req for req in requirements if req.startswith("torch==")), None)
    assert torch_pin, "torch must stay pinned in pyproject.toml"
    assert "torchaudio" + torch_pin[len("torch"):] in requirements
    assert any(req.startswith("fastapi") for req in requirements)  # [web] extra


def test_runtime_python_paths(tmp_path):
    assert bp.runtime_python(tmp_path, "macos").as_posix().endswith("runtime/bin/python3")
    assert bp.runtime_python(tmp_path, "win-x64").as_posix().endswith("runtime/python.exe")


def test_launchers_prefer_bundled_runtime():
    mac = (ROOT / "packaging/launchers/start.command").read_text(encoding="utf-8")
    win = (ROOT / "packaging/launchers/start.bat").read_text(encoding="utf-8")
    assert "runtime/bin/python3" in mac and "--bundled" in mac
    assert "runtime\\python.exe" in win and "--bundled" in win
    # the legacy fallbacks must stay for source checkouts
    assert ".venv/bin/python" in mac
    assert ".venv\\Scripts\\python.exe" in win


def test_start_bundled_ready(tmp_path, monkeypatch):
    start = _load_start()
    monkeypatch.setattr(start, "ROOT", tmp_path)
    monkeypatch.setattr(start, "BUNDLED_RUNTIME", tmp_path / "runtime/bin/python3")
    monkeypatch.setattr(start, "BUNDLED_WEB_ENV", tmp_path / "envs/web")
    assert not start.bundled_ready()
    (tmp_path / "envs/web").mkdir(parents=True)
    assert not start.bundled_ready()
    start.BUNDLED_RUNTIME.parent.mkdir(parents=True)
    start.BUNDLED_RUNTIME.write_text("#!/bin/sh\n", encoding="utf-8")
    assert start.bundled_ready()


def _entry_info(name: str, mode: int = 0o644):
    info = zipfile.ZipInfo(name)
    info.external_attr = mode << 16
    return info


def _bundle_zip(tmp_path: Path, platform: str = "macos", bundled: bool = True) -> Path:
    path = tmp_path / f"yue2-studio-oneclick-20261027-{platform}.zip"
    launcher = sp.LAUNCHERS[platform]
    with zipfile.ZipFile(path, "w") as zf:
        for entry in sp.REQUIRED:
            zf.writestr(entry, "x")
        zf.writestr(_entry_info(f"{sp.ROOT_NAME}/{launcher}", 0o755), "#!/bin/bash\n")
        if bundled:
            zf.writestr(_entry_info(f"{sp.ROOT_NAME}/{sp.RUNTIME_PYTHONS[platform]}", 0o755), "#")
            for marker in sp.BUNDLE_MARKERS[platform]:
                zf.writestr(f"{sp.ROOT_NAME}/{marker}", "x")
    return path


def test_smoke_requires_runtime_for_release(tmp_path):
    path = _bundle_zip(tmp_path, bundled=False)
    with pytest.raises(SystemExit):
        sp.check(path)
    sp.check(path, allow_slim=True)
    assert path.with_name(path.name + ".sha256").exists()


def test_smoke_accepts_self_contained_bundle(tmp_path):
    path = _bundle_zip(tmp_path)
    sp.check(path)
    sidecar = path.with_name(path.name + ".sha256")
    assert sidecar.read_bytes().endswith(b"\n")


def test_smoke_rejects_other_launcher_and_missing_markers(tmp_path):
    path = _bundle_zip(tmp_path)
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr(f"{sp.ROOT_NAME}/{sp.OTHER_LAUNCHERS['macos']}", "x")
    with pytest.raises(SystemExit):
        sp.check(path)
