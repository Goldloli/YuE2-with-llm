"""Unit tests for packaging/build_model_bundle.py (tier table + zip splitting)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))

import build_model_bundle as bb  # noqa: E402


def test_tier_modes_are_known():
    for key, spec in bb.TIERS.items():
        for mode in spec["modes"]:
            assert mode in bb.MODE_PATHS, f"{key}: unknown mode {mode}"
        assert spec["required"], f"{key}: no required entries"
        assert spec["est_gb"] > 0 and spec["max_component_gb"] > 0


def test_win_tiers_exclude_mlx():
    for (platform, tier), spec in bb.TIERS.items():
        if platform != "win-x64":
            continue
        assert any(p.startswith("YuE2-3B-MLX") for p in spec["forbidden"]), tier
        assert not any(r.startswith("YuE2-3B-MLX") for r in spec["required"]), tier
        assert not any(m.startswith("mlx") for m in spec["modes"]), tier


def test_mini_tier_excludes_torch_and_transcribe():
    spec = bb.TIERS[("macos", "mini")]
    assert "YuE2-3B/" in spec["forbidden"]
    for blocked in ("MERT-v2-FullSong/", "SheetSage2/", "loras/"):
        assert blocked in spec["forbidden"]
    assert not any(r.startswith("YuE2-3B/") for r in spec["required"])


def test_required_never_under_forbidden_prefix():
    for key, spec in bb.TIERS.items():
        for rel in spec["required"]:
            for prefix in spec["forbidden"]:
                assert not rel.startswith(prefix), f"{key}: {rel} under {prefix}"


def test_split_zip_roundtrip(tmp_path):
    blob = tmp_path / "blob.zip"
    payload = bytes(range(256)) * 40 + b"tail"  # 10244 bytes, deterministic
    blob.write_bytes(payload)
    parts, manifest, zip_sha = bb.split_zip(blob, tmp_path, part_size=1000)

    assert len(parts) == 11  # 10 full parts + 244-byte tail
    names = [n for n, _, _ in parts]
    assert names[:3] == ["blob.zip.part-aa", "blob.zip.part-ab", "blob.zip.part-ac"]
    assert names[-1] == "blob.zip.part-ak"
    assert all(size <= 1000 for _, size, _ in parts)
    assert zip_sha == hashlib.sha256(payload).hexdigest()

    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(parts) + 1  # parts + merged zip line
    for line, (name, _, _) in zip(lines, parts):
        digest, fname = line.split("  ")
        assert fname == name
        assert digest == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    assert lines[-1] == f"{zip_sha}  blob.zip"

    merged = b"".join((tmp_path / n).read_bytes() for n in names)
    assert merged == payload


def test_split_zip_naming_beyond_z(tmp_path):
    blob = tmp_path / "b.zip"
    blob.write_bytes(b"x" * 30)
    parts, _, _ = bb.split_zip(blob, tmp_path, part_size=1)
    assert len(parts) == 30
    assert parts[25][0].endswith(".part-az")
    assert parts[26][0].endswith(".part-ba")


def test_split_zip_small_file_not_split(tmp_path):
    blob = tmp_path / "small.zip"
    payload = b"tiny"
    blob.write_bytes(payload)
    parts, manifest, zip_sha = bb.split_zip(blob, tmp_path, part_size=1000)
    assert parts == []
    assert blob.exists()
    assert manifest.read_text(encoding="utf-8").strip() == f"{zip_sha}  small.zip"


def test_part_size_below_github_limit():
    assert bb.PART_SIZE < 2 * 2 ** 30  # GitHub caps release assets at 2 GiB


def test_disk_need_matches_phases():
    gib = 2 ** 30
    for key, spec in bb.TIERS.items():
        est = int(spec["est_gb"] * gib)
        component = int(spec["max_component_gb"] * gib)
        local = bb.disk_need(spec, local=True)
        ci = bb.disk_need(spec, local=False)
        # splitting always costs 2x the zip; the streaming build can cost more
        # when one component is bigger than the finished zip.
        assert local == 2 * est + bb.MARGIN, key
        assert ci == max(est + component, 2 * est) + bb.MARGIN, key
        assert ci >= local, key


def test_disk_need_budget_for_14gb_runners():
    """14 GB standard runners: mini/standard fit, win-x64 needs a little cleanup."""
    gib = 2 ** 30
    assert round(bb.disk_need(bb.TIERS[("macos", "mini")]) / gib, 1) == 11.2
    assert round(bb.disk_need(bb.TIERS[("macos", "standard")]) / gib, 1) == 12.8
    assert round(bb.disk_need(bb.TIERS[("win-x64", "standard")]) / gib, 1) == 16.8


def test_disk_precheck_fails_fast_when_short(monkeypatch):
    spec = bb.TIERS[("win-x64", "standard")]
    need = bb.disk_need(spec)
    monkeypatch.setattr(bb.shutil, "disk_usage",
                        lambda path: SimpleNamespace(free=need - 1))
    with pytest.raises(SystemExit) as exc:
        bb.disk_precheck(spec, local=False)
    message = str(exc.value)
    assert "磁盘不足" in message and "GiB" in message


def test_disk_precheck_passes_when_enough(monkeypatch, capsys):
    spec = bb.TIERS[("macos", "mini")]
    need = bb.disk_need(spec)
    monkeypatch.setattr(bb.shutil, "disk_usage",
                        lambda path: SimpleNamespace(free=need))
    bb.disk_precheck(spec, local=False)
    assert "disk: need" in capsys.readouterr().out
