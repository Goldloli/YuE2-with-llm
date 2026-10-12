"""LLM provider endpoints: config, model discovery, chat playground."""
import asyncio
import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("yue2_web_server_llm", ROOT / "web" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    for name in ("YUE2_STYLE_LLM_BASE_URL", "YUE2_STYLE_LLM_API_KEY",
                 "YUE2_STYLE_LLM_MODEL", "YUE2_STYLE_LLM_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def store_fixture(server, tmp_path, monkeypatch):
    store = server.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(server, "settings", store)
    monkeypatch.setattr(server, "chats", server.ChatStore(tmp_path / "llm_chats.json"))
    return store


@pytest.fixture
def configured(server, store_fixture):
    store_fixture.update(
        llm_providers=[{"id": "p-test", "name": "Mock", "preset": "custom",
                        "base_url": "http://llm.test/v1", "api_key": "sk-mock",
                        "default_model": "mock-model", "enabled": True}],
        llm_active_provider="p-test", llm_timeout=5.0, llm_enhance_output="zh")
    return store_fixture


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self, *args):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeStream:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") if isinstance(line, str) else line
                      for line in lines]

    def __iter__(self):
        return iter(self.lines)

    def close(self):
        pass


def fake_urlopen(payload=None, error=None, stream_lines=None):
    calls = []

    def open_(request, timeout=None):
        calls.append((request, timeout))
        if error is not None:
            raise error
        if stream_lines is not None:
            return FakeStream(stream_lines)
        return FakeResponse(payload)

    return open_, calls


def drain_body(response) -> str:
    """Consume a StreamingResponse (async body_iterator) into a single string."""
    async def run():
        parts = []
        async for chunk in response.body_iterator:
            parts.append(chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk)
        return "".join(parts)
    return asyncio.run(run())


def drain_first_then_close(response) -> str:
    """Read one chunk then close (mimics the client stopping the stream)."""
    async def run():
        agen = response.body_iterator
        first = await agen.__anext__()
        await agen.aclose()
        return first
    chunk = asyncio.run(run())
    return chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk


# ---------------------------------------------------------------------------
# Provider config

def test_presets_cover_documented_platforms(server):
    ids = {p["id"] for p in server.llm_presets()["items"]}
    assert {"deepseek", "qwen", "glm", "kimi", "minimax", "openai", "ollama",
            "custom"} <= ids


@pytest.mark.parametrize("url,ok", [
    ("https://api.deepseek.com", True),
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:8877/v1", True),
    ("ftp://x.test/v1", False),
    ("http://remote.example.com/v1", False),
    ("https://user:pass@api.test/v1", False),
    ("https://api.test/v1?q=1", False),
    ("", False),
])
def test_validate_base_url_rules(server, url, ok):
    assert (server.validate_base_url(url) is None) is ok


def test_provider_crud_masking_and_active(server, store_fixture):
    res = server.llm_provider_create(server.LlmProviderPayload(
        name="A", preset="deepseek", base_url="https://api.deepseek.com",
        api_key="sk-abcdefgh1234", default_model="deepseek-chat"))
    items = res["items"]
    assert len(items) == 1
    pid = items[0]["id"]
    assert items[0]["api_key_masked"] == "••••1234"
    assert "api_key" not in items[0]
    # update without the key field keeps it
    res = server.llm_provider_update(pid, server.LlmProviderPayload(
        default_model="deepseek-reasoner"))
    assert res["items"][0]["api_key_masked"] == "••••1234"
    assert res["items"][0]["default_model"] == "deepseek-reasoner"
    # an explicit empty string clears it
    res = server.llm_provider_update(pid, server.LlmProviderPayload(api_key=""))
    assert res["items"][0]["api_key_masked"] == ""
    # selecting and deleting the active entry clears the selection
    res = server.llm_set_active(server.LlmActivePayload(provider_id=pid))
    assert res["active"] == pid
    res = server.llm_provider_delete(pid)
    assert res["items"] == [] and res["active"] is None


def test_provider_validation_rejects_bad_input(server, store_fixture):
    with pytest.raises(HTTPException) as err:
        server.llm_provider_create(server.LlmProviderPayload(name="", preset="custom"))
    assert err.value.status_code == 422
    with pytest.raises(HTTPException):
        server.llm_provider_create(server.LlmProviderPayload(name="A", preset="nope"))
    with pytest.raises(HTTPException):
        server.llm_provider_create(server.LlmProviderPayload(
            name="A", preset="custom", base_url="ftp://x.test"))
    with pytest.raises(HTTPException):
        server.llm_set_active(server.LlmActivePayload(provider_id="missing"))
    with pytest.raises(HTTPException) as err:
        server.llm_provider_update("missing", server.LlmProviderPayload(name="x"))
    assert err.value.status_code == 404


def test_legacy_config_is_synthesized_and_materialized(server, store_fixture):
    store_fixture.update(llm_base_url="http://legacy.test/v1", llm_model="legacy-model",
                         llm_api_key="k12345678")
    items, active = server.providers_snapshot()
    assert active == "legacy"
    assert items[0]["id"] == "legacy" and items[0]["api_key_masked"] == "••••5678"
    # any mutation materializes it into a real entry and clears the old fields
    res = server.llm_provider_update("legacy", server.LlmProviderPayload(name="旧配置"))
    real = res["items"][0]
    assert real["id"] != "legacy" and real["name"] == "旧配置"
    assert res["active"] == real["id"]
    assert store_fixture.get("llm_base_url") == ""
    assert store_fixture.get("llm_model") == ""
    assert store_fixture.get("llm_api_key") == ""


def test_state_summary_has_no_key_material(server, configured):
    summary = server._llm_active_summary()
    assert summary["id"] == "p-test" and summary["model"] == "mock-model"
    assert "sk-mock" not in str(server.state())


# ---------------------------------------------------------------------------
# Model discovery

def test_fetch_models_success_dedup_and_sort(server, store_fixture, monkeypatch):
    open_, calls = fake_urlopen(payload={"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}]})
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1"))
    assert res["ok"] is True and res["items"] == ["a", "b"]
    assert calls[0][0].full_url == "https://x.test/v1/models"


def test_fetch_models_error_taxonomy(server, store_fixture, monkeypatch):
    res = server.llm_fetch_models(server.LlmModelsRequest(preset="custom", base_url="ftp://x"))
    assert res["error_code"] == "invalid_url"
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="deepseek", base_url="https://api.deepseek.com"))
    assert res["error_code"] == "auth_failed"
    open_, _ = fake_urlopen(error=urllib.error.HTTPError("u", 401, "unauth", {}, None))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1", api_key="k"))
    assert res["error_code"] == "auth_failed"
    open_, _ = fake_urlopen(error=urllib.error.HTTPError("u", 429, "slow", {}, None))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1", api_key="k"))
    assert res["error_code"] == "rate_limited"
    open_, _ = fake_urlopen(error=urllib.error.URLError(TimeoutError("timed out")))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1", api_key="k"))
    assert res["error_code"] == "timeout"
    open_, _ = fake_urlopen(error=urllib.error.URLError("connection refused"))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1", api_key="k"))
    assert res["error_code"] == "connect_failed"


def test_fetch_models_borrows_provider_key(server, configured, monkeypatch):
    open_, calls = fake_urlopen(payload={"data": [{"id": "mock-model"}]})
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://llm.test/v1", provider_id="p-test"))
    assert res["ok"] is True
    assert calls[0][0].headers["Authorization"] == "Bearer sk-mock"


def test_fetch_models_ollama_fallback(server, store_fixture, monkeypatch):
    responses = [urllib.error.HTTPError("u", 404, "nf", {}, None),
                 {"models": [{"name": "llama3"}, {"name": "qwen2"}]}]
    calls = []

    def open_(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="ollama", base_url="http://localhost:11434/v1"))
    assert res["ok"] is True
    assert res["items"] == ["llama3", "qwen2"]
    assert "原生协议" in res["message"]
    assert calls[0].endswith("/v1/models") and calls[1].endswith("/api/tags")


def test_fetch_models_oversized_response(server, store_fixture, monkeypatch):
    class BigResponse:
        def read(self, *args):
            return b"x" * (server.MODELS_MAX_RESPONSE + 10)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BigResponse())
    res = server.llm_fetch_models(server.LlmModelsRequest(
        preset="custom", base_url="https://x.test/v1"))
    assert res["error_code"] == "too_large"


# ---------------------------------------------------------------------------
# Connectivity & enhancement (active provider resolution)

def test_llm_test_borrows_provider_key(server, configured, monkeypatch):
    open_, calls = fake_urlopen({"choices": [{"message": {"content": "OK"}}]})
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_test(server.LlmTestRequest(provider_id="p-test"))
    assert res["ok"] is True
    assert calls[0][0].headers["Authorization"] == "Bearer sk-mock"


def test_llm_test_reports_failure(server, configured, monkeypatch):
    open_, _ = fake_urlopen(error=urllib.error.URLError("boom"))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_test(server.LlmTestRequest(provider_id="p-test"))
    assert res["ok"] is False and "boom" in res["error"]


def test_enhance_uses_active_provider(server, configured, monkeypatch):
    open_, calls = fake_urlopen(
        {"choices": [{"message": {"content": "```\n说唱, 嘻哈\n```"}}]})
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    res = server.llm_enhance(server.EnhanceRequest(style="黑人说唱"))
    assert res == {"style": "说唱, 嘻哈"}
    assert calls[0][0].full_url == "http://llm.test/v1/chat/completions"


def test_enhance_rejected_when_not_configured(server, store_fixture):
    with pytest.raises(HTTPException) as err:
        server.llm_enhance(server.EnhanceRequest(style="黑人说唱"))
    assert err.value.status_code == 409


def test_sanitize_enhanced_style_handles_fences_quotes_and_caps():
    from yue2.style_localization import sanitize_enhanced_style
    assert sanitize_enhanced_style('"hip hop", `rap`, •male vocals') == "hip hop, rap, male vocals"
    assert sanitize_enhanced_style("标签：说唱，嘻哈，说唱") == "说唱, 嘻哈"
    assert sanitize_enhanced_style("") is None
    assert sanitize_enhanced_style("   ") is None
    many = ", ".join(f"tag{i}" for i in range(20))
    assert len(sanitize_enhanced_style(many).split(", ")) == 12


# ---------------------------------------------------------------------------
# Chat playground

def test_conversation_crud_and_auto_title(server, store_fixture):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    cid = conv["id"]
    assert server.chat_conversations()["items"][0]["id"] == cid
    server.chats.append_message(cid, "user", "你好世界，这是第一句话")
    detail = server.chat_conversation_get(cid)
    assert detail["messages"][0]["content"] == "你好世界，这是第一句话"
    assert detail["conversation"]["title"] == "你好世界，这是第一句话"[:24]
    meta = server.chat_conversation_update(
        cid, server.ChatUpdate(model="m1", provider_id="p-test"))["conversation"]
    assert meta["model"] == "m1" and meta["provider_id"] == "p-test"
    server.chat_conversation_update(cid, server.ChatUpdate(title="改名了"))
    assert server.chats.get(cid)["conversation"]["title"] == "改名了"
    assert server.chat_conversation_delete(cid) == {"ok": True}
    with pytest.raises(HTTPException) as err:
        server.chat_conversation_get(cid)
    assert err.value.status_code == 404


def test_chat_store_caps_and_persistence(server, tmp_path):
    store = server.ChatStore(tmp_path / "c.json")
    conv = store.create()["id"]
    for i in range(server.CHAT_MAX_MESSAGES + 5):
        store.append_message(conv, "user", f"m{i}")
    assert len(store.conversations[0]["messages"]) == server.CHAT_MAX_MESSAGES
    for _ in range(server.CHAT_MAX_CONVERSATIONS + 3):
        store.create()
    assert len(store.conversations) == server.CHAT_MAX_CONVERSATIONS
    reloaded = server.ChatStore(tmp_path / "c.json")
    assert len(reloaded.conversations) == server.CHAT_MAX_CONVERSATIONS


def test_chat_stream_turn_streams_and_persists(server, configured, monkeypatch):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    lines = ['data: {"choices": [{"delta": {"content": "你"}}]}',
             'data: {"choices": [{"delta": {"content": "好"}}]}',
             "data: [DONE]"]
    open_, calls = fake_urlopen(stream_lines=lines)
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    response = server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="打个招呼"))
    assert response.media_type == "text/event-stream"
    body = drain_body(response)
    assert '"delta": "你"' in body and '"delta": "好"' in body
    assert body.rstrip().endswith("[DONE]")
    payload = json.loads(calls[0][0].data.decode("utf-8"))
    assert payload["stream"] is True
    assert payload["messages"][-1] == {"role": "user", "content": "打个招呼"}
    detail = server.chats.get(conv["id"])
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "你好"
    assert detail["conversation"]["provider_id"] == "p-test"
    assert detail["conversation"]["model"] == "mock-model"


def test_chat_turn_rejects_unconfigured_and_missing(server, store_fixture):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    with pytest.raises(HTTPException) as err:
        server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="hi"))
    assert err.value.status_code == 409
    with pytest.raises(HTTPException) as err:
        server.llm_chat(server.ChatTurn(conversation_id="nope", text="hi"))
    assert err.value.status_code == 404
    with pytest.raises(HTTPException) as err:
        server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="   "))
    assert err.value.status_code == 422


def test_chat_turn_first_byte_failure_is_json(server, configured, monkeypatch):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    open_, _ = fake_urlopen(error=urllib.error.HTTPError("u", 401, "unauth", {}, None))
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    with pytest.raises(HTTPException) as err:
        server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="hi"))
    assert err.value.status_code == 502


def test_chat_stream_mid_failure_keeps_partial(server, configured, monkeypatch):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]

    class BoomStream:
        def __iter__(self):
            yield 'data: {"choices": [{"delta": {"content": "部分"}}]}'.encode("utf-8")
            raise ConnectionError("upstream dropped")

        def close(self):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BoomStream())
    response = server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="hi"))
    body = drain_body(response)
    assert '"delta": "部分"' in body and '"error"' in body
    detail = server.chats.get(conv["id"])
    assert detail["messages"][-1]["role"] == "assistant"
    assert detail["messages"][-1]["content"] == "部分"


def test_chat_stream_client_stop_persists_partial(server, configured, monkeypatch):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    lines = ['data: {"choices": [{"delta": {"content": "A"}}]}',
             'data: {"choices": [{"delta": {"content": "B"}}]}',
             "data: [DONE]"]
    open_, _ = fake_urlopen(stream_lines=lines)
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    response = server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="hi"))
    first = drain_first_then_close(response)  # the client stops the stream
    assert '"delta": "A"' in first
    detail = server.chats.get(conv["id"])
    assert detail["messages"][-1]["role"] == "assistant"
    assert detail["messages"][-1]["content"] == "A"


def test_chat_turn_truncates_history(server, configured, monkeypatch):
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    cid = conv["id"]
    for i in range(20):
        server.chats.append_message(cid, "user", f"q{i}")
        server.chats.append_message(cid, "assistant", f"a{i}")
    open_, calls = fake_urlopen(stream_lines=["data: [DONE]"])
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    response = server.llm_chat(server.ChatTurn(conversation_id=cid, text="final"))
    drain_body(response)
    payload = json.loads(calls[0][0].data.decode("utf-8"))
    sent = payload["messages"]
    assert sent[-1] == {"role": "user", "content": "final"}
    assert len(sent) <= server.CHAT_CONTEXT_MESSAGES + 1
    assert all(m["content"] != "q0" for m in sent)


def test_chat_stream_partial_persists_without_close(server, configured, monkeypatch):
    """Starlette never closes the sync iterator on client disconnect, so the
    incremental persist must leave the partial content on disk without a finally."""
    conv = server.chat_conversation_create(server.ChatCreate())["conversation"]
    lines = ['data: {"choices": [{"delta": {"content": "A"}}]}',
             'data: {"choices": [{"delta": {"content": "B"}}]}',
             "data: [DONE]"]
    open_, _ = fake_urlopen(stream_lines=lines)
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    response = server.llm_chat(server.ChatTurn(conversation_id=conv["id"], text="hi"))

    async def one_chunk_then_abandon():
        agen = response.body_iterator
        return await agen.__anext__()  # no aclose: simulates the disconnect path

    first = asyncio.run(one_chunk_then_abandon())
    text = first.decode("utf-8") if isinstance(first, bytes) else first
    assert '"delta": "A"' in text
    detail = server.chats.get(conv["id"])
    assert detail["messages"][-1]["role"] == "assistant"
    assert detail["messages"][-1]["content"] == "A"
