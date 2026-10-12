"""Style prompt localization: CJK detection, translation providers, persistence."""
import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import urllib.request

import numpy as np
import pytest

from yue2.cli import request_kwargs
from yue2.pipeline import SemanticResult, SongResult, SymbolicPlan, YuE2Pipeline
from yue2.protocol import SongRequest
from yue2.storage import identity
from yue2.style_localization import (TERMS_FILE, DictionaryProvider, LlmProvider,
                                     contains_cjk, default_chain, llm_provider,
                                     localize_style)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    for name in ("YUE2_STYLE_LLM_BASE_URL", "YUE2_STYLE_LLM_API_KEY",
                 "YUE2_STYLE_LLM_MODEL", "YUE2_STYLE_LLM_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)


class SpyProvider:
    name = "spy"

    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result
        self.error = error

    def translate(self, text):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.result


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(payload=None, error=None):
    calls = []

    def open_(request, timeout=None):
        calls.append((request, timeout))
        if error is not None:
            raise error
        return FakeResponse(payload)

    return open_, calls


def bare_pipeline():
    return YuE2Pipeline.__new__(YuE2Pipeline)


# ---------------------------------------------------------------------------
# Detection (Unicode ranges only)

@pytest.mark.parametrize("text,expected", [
    ("雷鬼，小调合唱", True),
    ("Mandarin, 温暖钢琴, acoustic pop", True),
    ("reggae, minor choir, woodwinds, electro pop", False),
    ("80 bpm, fast, female vocals!", False),
    ("", False),
])
def test_cjk_detection(text, expected):
    assert contains_cjk(text) is expected


def test_pure_english_style_never_calls_a_provider():
    spy = SpyProvider(result="translated")
    style = "reggae, minor choir, woodwinds, electro pop"
    assert localize_style(style, "auto", provider_chain=[spy]) == (style, None, False)
    assert spy.calls == []


# ---------------------------------------------------------------------------
# Dictionary provider

@pytest.mark.parametrize("zh,en", [
    ("雷鬼", "reggae"),
    ("木吉他", "acoustic guitar"),
    ("忧郁", "melancholy"),
    ("女声", "female vocals"),
    ("慢板", "adagio"),
    ("国语", "Mandarin"),
])
def test_dictionary_covers_each_term_category(zh, en):
    assert DictionaryProvider.load().translate(zh) == en


def test_dictionary_translates_spec_sentence():
    provider = DictionaryProvider.load()
    assert provider.translate("雷鬼，小调合唱，木管，流行电子") == \
        "reggae, minor, choir, woodwinds, electro pop"


def test_mixed_style_preserves_existing_english_tags():
    provider = DictionaryProvider.load()
    assert provider.translate("Mandarin, 温暖钢琴, acoustic pop") == \
        "Mandarin, warm piano, acoustic pop"


def test_dictionary_keeps_unmatched_fragments_and_dedupes():
    provider = DictionaryProvider.load()
    assert provider.translate("雷鬼，稀有自定义词") == "reggae, 稀有自定义词"
    assert provider.translate("中文，国语") == "Mandarin"


def test_dictionary_covers_terms_observed_in_field_tests():
    provider = DictionaryProvider.load()
    assert provider.translate("中国风，古筝，五声音阶，抒情慢板，70 BPM") == \
        "Chinese style, guzheng, pentatonic scale, slow ballad, 70 BPM"
    assert provider.translate("雷鬼，慢速75 BPM，反拍木吉他，慵懒氛围，男声") == \
        "reggae, slow tempo, 75 BPM, offbeat, acoustic guitar, laid-back, ambient, male vocals"


def test_dictionary_covers_expanded_term_groups():
    provider = DictionaryProvider.load()
    assert provider.translate("洞箫，笙，埙，大号，木琴") == \
        "xiao, sheng, xun, tuba, xylophone"
    assert provider.translate("交响乐，迷幻，硬核，碎拍，巴洛克") == \
        "symphony, psychedelic, hardcore, breakbeat, baroque"
    assert provider.translate("伤感，失恋，优雅，阳光") == \
        "sentimental, heartbroken, elegant, sunny"
    assert provider.translate("混响，失真，80年代，独奏") == \
        "reverb, distortion, 80s, solo"
    assert provider.translate("禅意，仙侠，敦煌，国潮") == \
        "zen, xianxia, Dunhuang, modern Chinese style"
    assert provider.translate("俄语，德语，意大利语，广东话") == \
        "Russian, German, Italian, Cantonese"


def test_dictionary_longest_match_survives_expansion():
    provider = DictionaryProvider.load()
    assert provider.translate("回响贝斯，回响") == "dubstep, dub"
    assert provider.translate("洞箫") == "xiao"
    assert provider.translate("锣，鼓") == "gong, drums"
    assert provider.translate("手鼓") == "hand drums"


def test_dictionary_corrected_mappings():
    provider = DictionaryProvider.load()
    assert provider.translate("慢板") == "adagio"
    assert provider.translate("抒情慢板") == "slow ballad"
    assert provider.translate("阅读背景") == "background music"


def test_bundled_dictionary_is_sized_and_english_valued():
    terms = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
    assert 250 <= len(terms) <= 350
    assert all(contains_cjk(key) for key in terms)
    assert all(value and not contains_cjk(value) for value in terms.values())


# ---------------------------------------------------------------------------
# LLM provider (stdlib HTTP against an OpenAI-compatible endpoint)

def test_llm_provider_from_env_requires_base_url_and_model():
    assert LlmProvider.from_env({}) is None
    assert LlmProvider.from_env({"YUE2_STYLE_LLM_BASE_URL": "http://llm.test"}) is None
    provider = LlmProvider.from_env({"YUE2_STYLE_LLM_BASE_URL": "http://llm.test/v1/",
                                     "YUE2_STYLE_LLM_MODEL": "tagger",
                                     "YUE2_STYLE_LLM_API_KEY": "k",
                                     "YUE2_STYLE_LLM_TIMEOUT": "3"})
    assert provider.url == "http://llm.test/v1/chat/completions"
    assert provider.api_key == "k"
    assert provider.timeout == 3.0
    assert LlmProvider("http://llm.test", "tagger", timeout=99).timeout == 60.0
    assert LlmProvider.from_env({"YUE2_STYLE_LLM_BASE_URL": "http://x",
                                 "YUE2_STYLE_LLM_MODEL": "m",
                                 "YUE2_STYLE_LLM_TIMEOUT": "junk"}).timeout == 10.0


def test_llm_provider_translates_via_chat_completions(monkeypatch):
    open_, calls = fake_urlopen({"choices": [{"message": {"content": "reggae, female vocals"}}]})
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    provider = LlmProvider("http://llm.test/v1", "tagger", api_key="secret")
    assert provider.translate("雷鬼，女声") == "reggae, female vocals"
    request, timeout = calls[0]
    assert request.full_url == "http://llm.test/v1/chat/completions"
    assert timeout == 10.0
    assert request.headers["Authorization"] == "Bearer secret"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "tagger"
    assert payload["messages"][-1] == {"role": "user", "content": "雷鬼，女声"}


@pytest.mark.parametrize("error", [TimeoutError("timed out"),
                                   urllib.error.URLError("connection refused")])
def test_llm_timeout_or_error_falls_back_to_dictionary(monkeypatch, error):
    open_, calls = fake_urlopen(error=error)
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    llm = LlmProvider("http://llm.test", "tagger")
    final, original, translated = localize_style("雷鬼", "auto",
                                                 provider_chain=[llm, DictionaryProvider.load()])
    assert (final, original, translated) == ("reggae", "雷鬼", True)
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{"choices": []}, {"unexpected": True},
                                     {"choices": [{"message": {"content": " "}}]}])
def test_llm_malformed_or_empty_answer_falls_back(monkeypatch, payload):
    open_, _ = fake_urlopen(payload)
    monkeypatch.setattr(urllib.request, "urlopen", open_)
    llm = LlmProvider("http://llm.test", "tagger")
    final, _original, translated = localize_style("雷鬼", "auto",
                                                  provider_chain=[llm, DictionaryProvider.load()])
    assert (final, translated) == ("reggae", True)


# ---------------------------------------------------------------------------
# Provider chain orchestration

def test_default_chain_uses_env_endpoint_when_configured(monkeypatch):
    chain = default_chain()
    assert [p.name for p in chain] == ["hybrid"]
    assert chain[0].llm is None
    monkeypatch.setenv("YUE2_STYLE_LLM_BASE_URL", "http://llm.test")
    monkeypatch.setenv("YUE2_STYLE_LLM_MODEL", "tagger")
    chain = default_chain()
    assert [p.name for p in chain] == ["hybrid"]
    assert chain[0].llm.url == "http://llm.test/chat/completions"


def test_hybrid_policy_full_coverage_skips_llm():
    spy = SpyProvider(result="hip hop, rap, male vocals")
    chain = default_chain(llm=spy)
    assert chain[0].translate("雷鬼，木管") == "reggae, woodwinds"
    assert spy.calls == []
    assert chain[0].translate("黑人说唱") == "hip hop, rap, male vocals"
    assert spy.calls == ["黑人说唱"]


def test_hybrid_policy_falls_back_to_partial_without_llm():
    assert default_chain()[0].translate("黑人说唱") == "黑人, rap"
    failing = SpyProvider(error=RuntimeError("down"))
    assert default_chain(llm=failing)[0].translate("黑人说唱") == "黑人, rap"
    assert failing.calls == ["黑人说唱"]


def test_llm_provider_prefers_active_provider_over_legacy_and_env(monkeypatch):
    monkeypatch.setenv("YUE2_STYLE_LLM_BASE_URL", "http://env.test")
    monkeypatch.setenv("YUE2_STYLE_LLM_MODEL", "env-model")
    values = {"llm_providers": [{"id": "p1", "name": "X", "preset": "custom",
                                 "base_url": "http://settings.test/v1",
                                 "api_key": "secret", "default_model": "set-model",
                                 "enabled": True}],
              "llm_active_provider": "p1", "llm_timeout": 20,
              "llm_base_url": "http://legacy.test/v1", "llm_model": "legacy-model"}
    provider = llm_provider(values)
    assert provider.url == "http://settings.test/v1/chat/completions"
    assert provider.model == "set-model"
    assert provider.api_key == "secret"
    assert provider.timeout == 20.0
    # a disabled active entry is unusable; the non-empty list blocks legacy, env wins
    values["llm_providers"][0]["enabled"] = False
    assert llm_provider(values).url == "http://env.test/chat/completions"
    # legacy fields resolve while the list is empty
    legacy = {"llm_base_url": "http://legacy.test/v1", "llm_model": "legacy-model",
              "llm_api_key": "k"}
    assert llm_provider(legacy).url == "http://legacy.test/v1/chat/completions"
    assert llm_provider({}).url == "http://env.test/chat/completions"
    assert llm_provider({}, env={}) is None


def test_chain_falls_back_in_order_and_logs(caplog):
    first, second = SpyProvider(error=RuntimeError("down")), SpyProvider(result="reggae, choir")
    with caplog.at_level(logging.WARNING, logger="yue2.style_localization"):
        result = localize_style("雷鬼，合唱", "auto", provider_chain=[first, second])
    assert result == ("reggae, choir", "雷鬼，合唱", True)
    assert first.calls == second.calls == ["雷鬼，合唱"]
    assert "spy" in caplog.text


def test_chain_skips_empty_provider_answers():
    empty, fallback = SpyProvider(result=None), SpyProvider(result="reggae")
    assert localize_style("雷鬼", "auto", provider_chain=[empty, fallback]) == ("reggae", "雷鬼", True)


def test_all_providers_unavailable_passes_through_with_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="yue2.style_localization"):
        result = localize_style("雷鬼", "auto", provider_chain=[])
    assert result == ("雷鬼", None, False)
    assert "no translation provider available" in caplog.text


# ---------------------------------------------------------------------------
# Mode switch

def test_en_and_off_modes_pass_chinese_through_untouched():
    spy = SpyProvider(result="translated")
    for mode in ("en", "off"):
        assert localize_style("雷鬼，女声", mode, provider_chain=[spy]) == ("雷鬼，女声", None, False)
    assert spy.calls == []
    pipe = bare_pipeline()
    for mode in ("en", "off"):
        request = pipe._request(style="雷鬼，女声", lyrics="歌词", style_language=mode)
        assert request.style == "雷鬼，女声"
        assert request.style_original is None
        assert "style_original" not in request.to_dict()


def test_invalid_mode_rejected():
    with pytest.raises(ValueError, match="auto, en or off"):
        localize_style("雷鬼", "zh")


# ---------------------------------------------------------------------------
# Pipeline integration, persistence, idempotency

def test_pipeline_request_localizes_and_records_original():
    request = bare_pipeline()._request(style="民谣，木吉他", lyrics="[Verse]\n晚风轻轻吹过窗前")
    assert request.style == "folk, acoustic guitar"
    assert request.style_original == "民谣，木吉他"
    via_alias = bare_pipeline()._request(tags="民谣，木吉他", lyrics="[Verse]\n晚风轻轻吹过窗前")
    assert via_alias == request


def test_request_json_persists_translation_and_reruns_identically(tmp_path):
    pipe = bare_pipeline()
    request = pipe._request(style="民谣，木吉他", lyrics="[Verse]\n晚风轻轻吹过窗前")
    plan = SymbolicPlan(request, None, [], [0])
    result = SongResult(np.zeros(480, dtype=np.float32), 48000,
                        SemanticResult(plan, [], {}, False),
                        np.zeros((1, 64, 4), dtype=np.float32), {}, {}, {},
                        identity({"request": request.to_dict()}))
    result.save_artifacts(tmp_path)
    saved = json.loads((tmp_path / "request.json").read_text(encoding="utf-8"))
    assert saved["style"] == "folk, acoustic guitar"
    assert saved["style_original"] == "民谣，木吉他"
    rerun = pipe._request(**request_kwargs(saved))
    assert rerun == request
    assert identity({"request": rerun.to_dict()}) == identity({"request": request.to_dict()})


def test_rerun_with_cjk_leftovers_never_retranslates():
    # Dictionary leftovers (稀有自定义词) keep CJK in the translated style; a rerun
    # must not localize again or clobber the persisted Chinese original.
    pipe = bare_pipeline()
    request = pipe._request(style="中国风，稀有自定义词", lyrics="[Verse]\n月色")
    assert request.style_original == "中国风，稀有自定义词"
    assert "Chinese style" in request.style and "稀有自定义词" in request.style
    rerun = pipe._request(**request_kwargs(request.to_dict()))
    assert rerun == request


def test_english_requests_keep_their_previous_serialization():
    request = bare_pipeline()._request(style="warm piano, acoustic pop", lyrics="line")
    assert request.style_original is None
    assert set(request.to_dict()) == {"style", "lyrics", "cot", "seed", "abc", "cfg_scale", "id"}
    with pytest.raises(TypeError):
        SongRequest("a", "b", style_original=3)


def test_request_kwargs_accepts_persisted_style_original():
    kwargs = request_kwargs({"style": "folk", "lyrics": "x", "style_original": "民谣"})
    assert kwargs["style_original"] == "民谣"


# ---------------------------------------------------------------------------
# MLX entry point (tools/mlx_generate.py) builds requests on translated style

def test_mlx_generate_localizes_before_invoking():
    spec = importlib.util.spec_from_file_location("mlx_generate", ROOT / "tools" / "mlx_generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    zh = SimpleNamespace(style="雷鬼，女声", style_language="auto", style_original=None)
    assert module.localized_style(zh) == ("reggae, female vocals", "雷鬼，女声")
    off = SimpleNamespace(style="雷鬼", style_language="off", style_original=None)
    assert module.localized_style(off) == ("雷鬼", None)
    presolved = SimpleNamespace(style="reggae, female vocals", style_language="auto",
                                style_original="雷鬼，女声")
    assert module.localized_style(presolved) == ("reggae, female vocals", "雷鬼，女声")


def test_resolve_style_original_never_retranslates():
    """A server-supplied original wins even when the style still contains CJK
    leftovers: re-localizing would overwrite the true original with the mixed
    text (the 2-12753 regression)."""
    from yue2.style_localization import resolve_style_original
    mixed = "Chinese style, electronic, 乐, EDM"
    assert resolve_style_original(mixed, "中国风，电子乐") == (mixed, "中国风，电子乐")
    assert resolve_style_original("folk", "folk") == ("folk", None)
    assert resolve_style_original("雷鬼", None) == ("reggae", "雷鬼")
    assert resolve_style_original("雷鬼", "", "off") == ("雷鬼", None)


def test_ensure_instrumental_tag():
    from yue2.style_localization import ensure_instrumental_tag
    assert ensure_instrumental_tag("folk, 70 BPM") == "folk, 70 BPM, instrumental"
    assert ensure_instrumental_tag("dubstep, Instrumental") == "dubstep, Instrumental"
    assert ensure_instrumental_tag("instrumental") == "instrumental"
    assert ensure_instrumental_tag("") == "instrumental"
    assert ensure_instrumental_tag("  ") == "instrumental"
    assert ensure_instrumental_tag("instrumentals") == "instrumentals, instrumental"
    with pytest.raises(TypeError):
        ensure_instrumental_tag(None)
