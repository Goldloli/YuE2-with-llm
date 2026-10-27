"""Model manager endpoints: component validation, sources, download channel."""
import sys
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("yue2_web_server_models", ROOT / "web" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_models_payload_shape(server):
    payload = server._models_payload()
    ids = {c["id"] for c in payload["components"]}
    assert {"core", "decoders", "realaudio", "transcribe"} <= ids
    assert {"lora-deathmetal-v1", "lora-jpop-t4", "lora-instrumental-v3abc"} <= ids
    for c in payload["components"]:
        assert c["bytes"] > 0
        assert "installed" in c and "downloaded_bytes" in c


def test_download_unknown_component(server):
    with pytest.raises(HTTPException) as err:
        server.models_download(server.ModelDownload(component="nope"))
    assert err.value.status_code == 422


def test_download_installed_component_conflicts(server, monkeypatch, tmp_path):
    (tmp_path / "models" / "probe").mkdir(parents=True)
    (tmp_path / "models" / "probe" / "model.safetensors").write_bytes(b"x")
    comp = {"id": "probe", "platform": None, "paths": ["probe/model.safetensors"],
            "mode": "core"}
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setitem(server.MODEL_COMPONENTS_BY_ID, "probe", comp)
    with pytest.raises(HTTPException) as err:
        server.models_download(server.ModelDownload(component="probe"))
    assert err.value.status_code == 409


def test_download_bad_source(server, monkeypatch):
    missing = next((c["id"] for c in server.MODEL_COMPONENTS
                    if not all((ROOT / "models" / rel).exists() for rel in c["paths"])), None)
    if missing is None:
        pytest.skip("every component is installed; nothing to probe")
    with pytest.raises(HTTPException) as err:
        server.models_download(server.ModelDownload(component=missing, source="ftp"))
    assert err.value.status_code == 422


def test_cancel_without_download(server):
    with pytest.raises(HTTPException) as err:
        server.models_cancel(server.ModelCancel(component="core"))
    assert err.value.status_code == 404


class _FakeProc:
    def __init__(self):
        self.terminated = False

    @property
    def stdout(self):
        return []

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def _fake_manager(server, monkeypatch, max_concurrent=None):
    """DownloadManager with a fake child process and a no-op watcher thread."""
    monkeypatch.setattr(server.DownloadManager, "_watch", lambda self, cid, proc: None)
    procs = []

    class FakePopen(_FakeProc):
        def __init__(self, *args, **kwargs):
            super().__init__()
            procs.append(self)

    monkeypatch.setattr(server.subprocess, "Popen", FakePopen)
    if max_concurrent is None:
        max_concurrent = server.MAX_CONCURRENT_DOWNLOADS
    return server.DownloadManager(max_concurrent=max_concurrent), procs


def _comp(component_id, *paths):
    return {"id": component_id, "mode": "core", "paths": list(paths)}


def test_download_allows_multiple_components_concurrently(server, monkeypatch):
    manager, procs = _fake_manager(server, monkeypatch)
    manager.start(_comp("fake-a", "a/model.safetensors"), "mirror")
    manager.start(_comp("fake-b", "b/model.safetensors"), "mirror")
    snapshot = manager.snapshot()
    assert [job["component"] for job in snapshot] == ["fake-a", "fake-b"]
    assert all(job["running"] for job in snapshot)
    assert len(procs) == 2


def test_download_same_component_rejected_while_running(server, monkeypatch):
    manager, _ = _fake_manager(server, monkeypatch)
    manager.start(_comp("fake-a", "a/model.safetensors"), "mirror")
    with pytest.raises(HTTPException) as err:
        manager.start(_comp("fake-a", "a/model.safetensors"), "mirror")
    assert err.value.status_code == 409
    assert "already running" in str(err.value.detail)


def test_download_respects_concurrency_limit(server, monkeypatch):
    manager, _ = _fake_manager(server, monkeypatch, max_concurrent=2)
    manager.start(_comp("fake-a", "a/x"), "mirror")
    manager.start(_comp("fake-b", "b/x"), "mirror")
    with pytest.raises(HTTPException) as err:
        manager.start(_comp("fake-c", "c/x"), "mirror")
    assert err.value.status_code == 409
    assert "Up to 2" in str(err.value.detail)
    assert len(manager.snapshot()) == 2


def test_download_rejects_overlapping_targets(server, monkeypatch):
    manager, _ = _fake_manager(server, monkeypatch)
    manager.start(_comp("fake-a", "shared/model.safetensors"), "mirror")
    with pytest.raises(HTTPException) as err:
        manager.start(_comp("fake-b", "shared/model.safetensors"), "mirror")
    assert err.value.status_code == 409
    assert "shares files" in str(err.value.detail)


def test_cancel_stops_only_target_component(server, monkeypatch):
    manager, procs = _fake_manager(server, monkeypatch)
    manager.start(_comp("fake-a", "a/x"), "mirror")
    manager.start(_comp("fake-b", "b/x"), "mirror")
    manager.cancel("fake-a")
    assert procs[0].terminated is True
    assert procs[1].terminated is False
    assert [job["component"] for job in manager.snapshot()] == ["fake-b"]
    with pytest.raises(HTTPException) as err:
        manager.cancel("fake-a")
    assert err.value.status_code == 404


def test_models_payload_marks_each_active_download(server, monkeypatch):
    manager, _ = _fake_manager(server, monkeypatch)
    comps = {c["id"]: c for c in server.MODEL_COMPONENTS}
    manager.start(comps["core"], "mirror")
    manager.start(comps["decoders"], "mirror")
    monkeypatch.setattr(server, "downloads", manager)
    payload = server._models_payload()
    by_id = {c["id"]: c for c in payload["components"]}
    assert by_id["core"]["downloading"] is True
    assert by_id["decoders"]["downloading"] is True
    assert {job["component"] for job in payload["downloads"]} == {"core", "decoders"}


def test_download_source_setting_validation(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(download_source="ftp"))
    assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(download_source="huggingface"))
    assert store.get("download_source") == "huggingface"
    assert server.state()["download_source"] == "huggingface"


def test_state_reports_core_installed(server):
    """The UI uses /api/state to decide whether to land on the Models page first."""
    assert isinstance(server.state()["core_installed"], bool)


def test_default_lora_validation(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(default_lora="ghost-lora"))
    assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(default_lora=None))
    assert store.get("default_lora") is None


def test_cuda_kit_entry_only_for_windows(server, monkeypatch):
    """The CUDA kit row shows up in the model page only on Windows."""
    fake_status = {"supported": True, "gpu_detected": True, "installed": False,
                   "invalidated": False, "enabled": False, "reason": None,
                   "kit": None, "job": None}

    class FakeKit:
        def status(self):
            return dict(fake_status)

        def size_bytes(self):
            return 0

    monkeypatch.setattr(server, "cuda_kit", FakeKit())
    monkeypatch.setattr(sys, "platform", "win32")
    entry = next(c for c in server._models_payload()["components"] if c["id"] == "cuda-kit")
    assert entry["group"] == "cuda" and entry["cuda"]["supported"] is True
    assert entry["installed"] is False
    monkeypatch.setattr(sys, "platform", "darwin")
    assert all(c["id"] != "cuda-kit" for c in server._models_payload()["components"])
