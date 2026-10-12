"""Settings validation and storage endpoints of the web server."""
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("yue2_web_server_settings", ROOT / "web" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def settings_store(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    return store


def test_default_backend_validation(server, settings_store):
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(default_backend="cuda"))
    assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(default_backend="torch"))
    assert settings_store.get("default_backend") == "torch"


def test_mlx_variant_must_be_installed(server, settings_store):
    installed = server.mlx_variants()
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(mlx_variant="2bit"))
    assert err.value.status_code == 422
    if installed:
        server.update_settings(server.SettingsUpdate(mlx_variant=installed[0]))
        assert settings_store.get("mlx_variant") == installed[0]


def test_poll_interval_and_numeric_bounds(server, settings_store):
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(poll_interval=2))
    server.update_settings(server.SettingsUpdate(poll_interval=5))
    assert settings_store.get("poll_interval") == 5.0
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(default_max_seconds=400))
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(default_cfg=21))
    server.update_settings(server.SettingsUpdate(default_max_seconds=60, default_cfg=3.5))
    assert settings_store.get("default_max_seconds") == 60
    assert settings_store.get("default_cfg") == 3.5


def test_choice_fields_validation(server, settings_store):
    for field, bad in (("default_mode", "fancy"), ("start_view", "detail"), ("default_sort", "random")):
        with pytest.raises(HTTPException) as err:
            server.update_settings(server.SettingsUpdate(**{field: bad}))
        assert err.value.status_code == 422
    server.update_settings(server.SettingsUpdate(default_mode="advanced", start_view="library",
                                                 default_sort="title"))
    assert settings_store.get("default_mode") == "advanced"


def test_bool_fields_and_reset(server, settings_store):
    server.update_settings(server.SettingsUpdate(autoplay_on_complete=True, notify_on_complete=True,
                                                 reduce_motion=True))
    assert settings_store.get("autoplay_on_complete") is True
    assert settings_store.get("reduce_motion") is True
    server.update_settings(server.SettingsUpdate(reset_defaults=True))
    assert settings_store.get("autoplay_on_complete") is False
    assert settings_store.get("default_max_seconds") is None


def test_decoder_three_tier_availability(server, settings_store):
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(decoder="fancy"))
    assert err.value.status_code == 422
    for name in ("legacy", "merge"):
        installed = (server.VAE_LEGACY_DIR if name == "legacy" else server.VAE_MERGE_DIR) / "model.safetensors"
        if installed.exists():
            server.update_settings(server.SettingsUpdate(decoder=name))
            assert settings_store.get("decoder") == name
            assert server.decoder_vae_path(name) is not None
        else:
            with pytest.raises(HTTPException) as err:
                server.update_settings(server.SettingsUpdate(decoder=name))
            assert err.value.status_code == 422


def test_dir_stats_and_cleanup(server, tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    (out / "a").mkdir(parents=True)
    (out / "a" / "latent.npy").write_bytes(b"x" * 100)
    (out / "a" / "audio.flac").write_bytes(b"y" * 10)
    (out / "b").mkdir()
    (out / "b" / "latent.npy").write_bytes(b"z" * 50)
    stats = server._dir_stats(out)
    assert stats["bytes"] == 160 and stats["files"] == 3
    assert stats["latent_bytes"] == 150 and stats["latent_files"] == 2

    monkeypatch.setattr(server, "OUTPUTS", out)
    monkeypatch.setattr(server.runner, "current_id", None)
    freed = server.storage_cleanup()
    assert freed == {"freed_bytes": 150, "removed": 2}
    assert (out / "a" / "audio.flac").exists()
    assert not (out / "a" / "latent.npy").exists()


def test_llm_settings_validation_masking_and_clear(server, settings_store):
    with pytest.raises(HTTPException) as err:
        server.update_settings(server.SettingsUpdate(llm_base_url="ftp://x"))
    assert err.value.status_code == 422
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(llm_timeout=0))
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(llm_timeout=61))
    with pytest.raises(HTTPException):
        server.update_settings(server.SettingsUpdate(llm_enhance_output="fr"))
    server.update_settings(server.SettingsUpdate(
        llm_base_url="https://api.test/v1", llm_model="tagger",
        llm_api_key="sk-abcdefgh1234", llm_timeout=20, llm_enhance_output="en"))
    assert settings_store.get("llm_base_url") == "https://api.test/v1"
    assert settings_store.get("llm_enhance_output") == "en"
    assert server.mask_key("sk-abcdefgh1234") == "••••1234"
    state = server.state()
    assert "sk-abcdefgh1234" not in str(state)
    # the legacy single-endpoint config surfaces as a synthesized masked entry
    assert state["llm_providers"][0]["id"] == "legacy"
    assert state["llm_providers"][0]["api_key_masked"] == "••••1234"
    assert state["llm_active_provider"] == "legacy"
    assert state["llm_active"]["id"] == "legacy"
    # a payload without the key field keeps the stored value
    server.update_settings(server.SettingsUpdate(llm_model="tagger2"))
    assert settings_store.get("llm_api_key") == "sk-abcdefgh1234"
    # an explicit empty string clears it
    server.update_settings(server.SettingsUpdate(llm_api_key=""))
    assert settings_store.get("llm_api_key") == ""
    assert server.mask_key("") == ""
