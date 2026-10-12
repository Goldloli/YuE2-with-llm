"""Chinese style prompt localization: detect CJK text and translate to English tags.

The checkpoint's native protocol (yue2-native-v1) is trained on English [Tags]
labels. A Chinese style is translated before the request is built, so the model
input distribution stays unchanged. Providers are tried in order: an optional
OpenAI-compatible LLM endpoint (env-configured), then the bundled offline
term dictionary; if neither can translate, the style passes through unchanged
with a warning. Lyrics are never touched.
"""
from __future__ import annotations
import json
import logging
import os
import re
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

STYLE_LANGUAGES = ("auto", "en", "off")
TERMS_FILE = Path(__file__).parent / "data" / "zh_style_terms.json"
CJK_RE = re.compile(r"[㐀-䶿一-鿿]")

LLM_TIMEOUT_SECONDS = 10.0
LLM_TIMEOUT_MAX = 60.0
LLM_SYSTEM_PROMPT = (
    "Translate the user's music style description into English comma-separated tags "
    "for a music generation model. Cover genre, instruments, mood, vocals, tempo and "
    "language. Keep any existing English tags unchanged. Answer with the tags only."
)


def contains_cjk(text):
    return bool(CJK_RE.search(text))


class DictionaryProvider:
    """Offline Chinese term dictionary; fragments without an entry stay unchanged."""
    name = "dictionary"

    def __init__(self, terms):
        self.terms = dict(terms)
        self._keys = sorted(self.terms, key=len, reverse=True)

    @classmethod
    def load(cls, path=TERMS_FILE):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def translate(self, text):
        tokens, buffer = [], []

        def flush():
            fragment = re.sub(r"\s+", " ", "".join(buffer)).strip()
            buffer.clear()
            if fragment:
                tokens.append(fragment)

        i = 0
        while i < len(text):
            if text[i] in "，、,;；/|\n\r":
                flush()
                i += 1
                continue
            key = next((k for k in self._keys if text.startswith(k, i)), None)
            if key is None:
                buffer.append(text[i])
                i += 1
            else:
                flush()
                tokens.append(self.terms[key])
                i += len(key)
        flush()
        seen, unique = set(), []
        for token in tokens:
            if token.lower() not in seen:
                seen.add(token.lower())
                unique.append(token)
        return ", ".join(unique) or None


class HybridProvider:
    """Dictionary-first policy: full dictionary coverage wins, the LLM covers the rest.

    A dictionary result without CJK leftovers is deterministic and free, so it
    short-circuits before any network call; anything the dictionary cannot fully
    cover goes to the LLM when one is configured.
    """
    name = "hybrid"

    def __init__(self, dictionary, llm=None):
        self.dictionary = dictionary
        self.llm = llm

    def translate(self, text):
        partial = self.dictionary.translate(text)
        if partial and not contains_cjk(partial):
            return partial
        if self.llm is not None:
            try:
                result = self.llm.translate(text)
            except Exception as exc:  # noqa: BLE001 - fall back to the partial result
                log.warning("Style translation via %s failed: %s", self.llm.name, exc)
                result = None
            if result:
                return result
        return partial


class LlmProvider:
    """OpenAI-compatible chat-completions endpoint (web settings or environment)."""
    name = "llm"

    def __init__(self, base_url, model, api_key=None, timeout=LLM_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.url = self.base_url + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = max(1.0, min(float(timeout), LLM_TIMEOUT_MAX))

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        base_url = (env.get("YUE2_STYLE_LLM_BASE_URL") or "").strip()
        model = (env.get("YUE2_STYLE_LLM_MODEL") or "").strip()
        if not base_url or not model:
            return None
        try:
            timeout = float(env.get("YUE2_STYLE_LLM_TIMEOUT") or LLM_TIMEOUT_SECONDS)
        except ValueError:
            timeout = LLM_TIMEOUT_SECONDS
        return cls(base_url, model, env.get("YUE2_STYLE_LLM_API_KEY"), timeout)

    def chat(self, system, user):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "temperature": 0, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}]}
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"),
                                         headers=headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return (content or "").strip() or None

    def translate(self, text):
        return self.chat(LLM_SYSTEM_PROMPT, text)


def active_provider(values):
    """The provider selected as active (or the legacy single-endpoint config), else None.

    Entries without base_url + default_model, or disabled entries, are not usable.
    The legacy fields only apply while the stored list is empty.
    """
    values = values or {}
    providers = values.get("llm_providers") or []
    active_id = values.get("llm_active_provider")
    entry = None
    if active_id:
        entry = next((e for e in providers
                      if isinstance(e, dict) and e.get("id") == active_id), None)
        if entry is not None and not entry.get("enabled", True):
            return None
    if entry is None:
        if providers:
            return None
        base_url = (values.get("llm_base_url") or "").strip()
        model = (values.get("llm_model") or "").strip()
        if not base_url or not model:
            return None
        return {"id": "legacy", "name": model, "preset": "custom", "base_url": base_url,
                "default_model": model, "api_key": values.get("llm_api_key") or ""}
    base_url = (entry.get("base_url") or "").strip()
    model = (entry.get("default_model") or "").strip()
    if not base_url or not model:
        return None
    return {"id": entry.get("id"), "name": entry.get("name") or "",
            "preset": entry.get("preset") or "custom", "base_url": base_url,
            "default_model": model, "api_key": entry.get("api_key") or ""}


def llm_provider(values=None, env=None):
    """Resolve the LLM endpoint: active provider (or legacy config), then env."""
    values = values or {}
    try:
        timeout = float(values.get("llm_timeout") or LLM_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        timeout = LLM_TIMEOUT_SECONDS
    active = active_provider(values)
    if active is not None:
        return LlmProvider(active["base_url"], active["default_model"],
                           (active.get("api_key") or "").strip() or None, timeout)
    return LlmProvider.from_env(env)


def default_chain(llm=None):
    """Hybrid policy chain: dictionary-only when fully covered, LLM otherwise.

    `llm` may be supplied by the caller (web settings); when omitted the endpoint
    comes from the environment (CLI usage).
    """
    dictionary = None
    try:
        dictionary = DictionaryProvider.load()
    except (OSError, ValueError) as exc:
        log.warning("Style dictionary unavailable: %s", exc)
    if llm is None:
        llm = LlmProvider.from_env()
    if dictionary is not None:
        return [HybridProvider(dictionary, llm)]
    return [llm] if llm is not None else []


def localize_style(style, mode="auto", provider_chain=None):
    """Return (final_style, style_original, translated) for a style/tags prompt.

    Modes: "auto" translates when the style contains CJK characters; "en" and
    "off" are exact passthroughs. When no provider can translate, the style is
    returned unchanged with translated=False and a warning is logged.
    """
    if mode not in STYLE_LANGUAGES:
        raise ValueError("style language mode must be auto, en or off")
    if mode != "auto" or not contains_cjk(style):
        return style, None, False
    providers = default_chain() if provider_chain is None else provider_chain
    for provider in providers:
        try:
            translated = provider.translate(style)
        except Exception as exc:  # noqa: BLE001 - any provider failure falls through
            log.warning("Style translation via %s failed: %s", provider.name, exc)
            continue
        if translated:
            return translated, style, True
    log.warning("Style left untranslated: no translation provider available")
    return style, None, False


def ensure_instrumental_tag(style):
    """Append the `instrumental` tag unless already present (case-insensitive)."""
    if not isinstance(style, str):
        raise TypeError("style must be a string")
    if re.search(r"\binstrumental\b", style, re.I):
        return style
    stripped = style.strip()
    return f"{stripped}, instrumental" if stripped else "instrumental"


def resolve_style_original(style, style_original, language="auto"):
    """Trust a caller-supplied original over re-localization.

    Returns (style, original). When style_original is provided, the style is
    used as-is and the original is persisted (None when identical); otherwise
    falls back to localize_style with the given language mode.
    """
    if style_original:
        return style, (style_original if style_original != style else None)
    localized, original, _translated = localize_style(style, language)
    return localized, original


# ---------------------------------------------------------------------------
# LLM style enhancement (free-form description -> vocabulary-grounded tags)

ENHANCE_MAX_TAGS = 12
ENHANCE_MAX_CHARS = 200

ENHANCE_INSTRUCTIONS = {
    "zh": (
        "把用户的风格描述理解并改写为逗号分隔的中文风格标签，供音乐生成模型使用。"
        "优先使用下方词表中的中文词（生成时会自动译为英文标签）；仅在词表无法表达意图时补充少量英文标签。"
        "理解用户意图，可补齐合理的流派、乐器、情绪、速度、人声等要素。"
        "只输出标签本身，不要任何解释。"),
    "en": (
        "Rewrite the user's style description into a comma-separated list of English "
        "style tags for a music generation model. Prefer the English tags of the "
        "vocabulary below; add other concise English tags only when needed. Understand "
        "the intent and fill in sensible genre, instrument, mood, tempo and vocal "
        "elements. Output the tags only, without any explanation."),
}


def enhancement_prompt(mode="zh", terms=None):
    """System prompt for LLM style enhancement, grounded in the bundled vocabulary."""
    if mode not in ENHANCE_INSTRUCTIONS:
        raise ValueError("enhance output mode must be zh or en")
    if terms is None:
        terms = DictionaryProvider.load().terms
    vocabulary = "、".join(f"{zh}（{en}）" for zh, en in terms.items())
    return ENHANCE_INSTRUCTIONS[mode] + "\n\n词表（中文（英文））：\n" + vocabulary


def sanitize_enhanced_style(text):
    """Normalize an LLM enhancement reply into a clean comma-separated tag list."""
    if not text:
        return None
    cleaned = re.sub(r"```[A-Za-z0-9_-]*", "", text).strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return None
    if len(lines) > 1:
        # Explanations usually precede the list; the tag line has the most separators.
        best = max(lines, key=lambda line: line.count(",") + line.count("，"))
        cleaned = best if ("," in best or "，" in best) else "、".join(lines)
    else:
        cleaned = lines[0]
    tags, seen = [], set()
    for token in re.split(r"[,，、;；|]+", cleaned):
        tag = token.strip().strip("\"'`“”‘’•*—-").strip()
        tag = re.sub(r"^\d+[.、)]\s*", "", tag)
        tag = re.sub(r"^[^：:]{0,20}[：:]\s*", "", tag).strip("。.!！ ")
        if not tag or len(tag) > 30 or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        tags.append(tag)
        if len(tags) >= ENHANCE_MAX_TAGS:
            break
    if not tags:
        return None
    while len(", ".join(tags)) > ENHANCE_MAX_CHARS:
        tags.pop()
    return ", ".join(tags) or None
