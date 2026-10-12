"""Example payload shape: ABC scores + lyric examples for the create helpers."""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("yue2_web_server_examples", ROOT / "web" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_examples_payload_has_scores_and_lyrics(server):
    payload = server.examples()
    assert {"melody.abc", "score.abc"} <= set(payload["scores"])
    assert payload["lyrics"], "at least one lyric example is expected"
    for item in payload["lyrics"]:
        assert item["name"] and item["lyrics"].strip()


def test_examples_lyrics_include_chinese(server):
    payload = server.examples()
    assert any(re.search(r"[\u4e00-\u9fff]", item["lyrics"]) for item in payload["lyrics"]), \
        "the lyric pool must contain a Chinese example"
