"""Platform-specific one-click packaging: build_package.py + smoke_package.py."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))

import build_package as bp  # noqa: E402
import smoke_package as sp  # noqa: E402


def _touch(path: Path, text: str = "x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detect_platform():
    assert bp.detect_platform("darwin", "posix") == "macos"
    assert bp.detect_platform("win32", "nt") == "win-x64"
    assert bp.detect_platform("linux", "posix") is None


def test_launchers_are_platform_specific():
    assert bp.launcher_name("macos") == "start.command"
    assert bp.launcher_name("win-x64") == "start.bat"
    assert bp.other_launcher_name("macos") == "start.bat"
    assert bp.other_launcher_name("win-x64") == "start.command"


def test_zip_name_carries_platform():
    assert bp.package_zip_name("macos", "20261027") == (
        "yue2-studio-oneclick-20261027-macos.zip")
    assert bp.package_zip_name("win-x64", "20261027") == (
        "yue2-studio-oneclick-20261027-win-x64.zip")


def test_smoke_platform_inference():
    assert sp.platform_from_name("yue2-studio-oneclick-20261027-macos.zip") == "macos"
    assert sp.platform_from_name("yue2-studio-oneclick-20261027-win-x64.zip") == "win-x64"
    assert sp.platform_from_name("whatever.zip") is None


def _fake_pkg(tmp_path: Path, platform: str, stray: bool = False) -> Path:
    pkg = tmp_path / "pkg"
    for name in bp.REQUIRED_INSIDE:
        _touch(pkg / name)
    launcher = pkg / bp.launcher_name(platform)
    _touch(launcher, "#!/bin/bash\necho ok\n")
    launcher.chmod(0o755)
    if stray:
        _touch(pkg / bp.other_launcher_name(platform))
    return pkg


def test_self_check_accepts_platform_package(tmp_path):
    bp.self_check(_fake_pkg(tmp_path, "macos"), "macos")
    bp.self_check(_fake_pkg(tmp_path / "win", "win-x64"), "win-x64")


def test_self_check_rejects_stray_launcher(tmp_path):
    with pytest.raises(SystemExit):
        bp.self_check(_fake_pkg(tmp_path, "macos", stray=True), "macos")


def _make_zip(tmp_path: Path, platform: str, other: bool = False,
              exec_bit: bool = True) -> Path:
    path = tmp_path / f"pkg-{platform}.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for entry in sp.REQUIRED:
            zf.writestr(entry, "x")
        info = zipfile.ZipInfo(f"yue2-studio-oneclick/{sp.LAUNCHERS[platform]}")
        info.external_attr = (0o755 if exec_bit else 0o644) << 16
        zf.writestr(info, "#!/bin/bash\n")
        if other:
            zf.writestr(f"yue2-studio-oneclick/{sp.OTHER_LAUNCHERS[platform]}", "x")
    return path


def test_smoke_accepts_matching_launcher(tmp_path):
    path = _make_zip(tmp_path, "macos")
    sp.check(path)
    assert path.with_name(path.name + ".sha256").exists()


def test_smoke_rejects_other_platform_launcher(tmp_path):
    with pytest.raises(SystemExit):
        sp.check(_make_zip(tmp_path, "macos", other=True))


def test_smoke_rejects_missing_exec_bit(tmp_path):
    with pytest.raises(SystemExit):
        sp.check(_make_zip(tmp_path, "macos", exec_bit=False))


def test_smoke_needs_platform_hint_for_unknown_name(tmp_path):
    path = _make_zip(tmp_path, "win-x64").rename(tmp_path / "mystery.zip")
    with pytest.raises(SystemExit):
        sp.check(path)
    sp.check(path, platform="win-x64")
