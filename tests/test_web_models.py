"""Model manager endpoints: component validation, sources, download channel."""
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


def test_download_installed_component_conflicts(server):
    installed = next(c["id"] for c in server.MODEL_COMPONENTS
                     if all((ROOT / "models" / rel).exists() for rel in c["paths"]))
    with pytest.raises(HTTPException) as err:
        server.models_download(server.ModelDownload(component=installed))
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


def test_download_start_rejects_when_busy(server, monkeypatch, tmp_path):
    comp = {"id": "fake", "platform": None, "paths": ["nope/model.safetensors"], "mode": "core"}
    manager = server.DownloadManager()

    class FakeProc:
        def poll(self):
            return None

    manager.current = {"component": "fake", "mode": "core", "source": "mirror",
                       "proc": FakeProc(), "error": None, "cancelled": False,
                       "started": 0, "log_tail": []}
    with pytest.raises(HTTPException) as err:
        manager.start(comp, "mirror")
    assert err.value.status_code == 409
    # a dead entry does not block a retry
    manager.current["proc"] = None
    assert manager.snapshot() is not None


def test_download_source_setting_validation(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(download_source="ftp"))
    assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(download_source="huggingface"))
    assert store.get("download_source") == "huggingface"
    assert server.state()["download_source"] == "huggingface"


def test_default_lora_validation(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(default_lora="ghost-lora"))
    assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(default_lora=None))
    assert store.get("default_lora") is None
