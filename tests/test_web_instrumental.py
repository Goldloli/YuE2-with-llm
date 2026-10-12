"""Web server instrumental transfer: Vocal->Ins via the bundled skill (subprocess)."""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server():
    spec = importlib.util.spec_from_file_location("yue2_web_server", ROOT / "web" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vocal_body(abc_text):
    """Concatenated Vocal voice lines, stripped of chord symbols and comments."""
    lines, current = [], None
    for line in abc_text.splitlines():
        head = line.split("%", 1)[0]
        marker = re.match(r"V:\s*(\w+)", head)
        if marker:
            current = marker.group(1)
            continue
        if current == "Vocal" and head.strip() and not re.match(r"[A-Za-z]:", head):
            lines.append(head)
    return re.sub(r'"[^"]*"', "", "".join(lines))


def test_instrumentalize_score_moves_vocal_notes(server):
    source = (ROOT / "examples" / "score.abc").read_text(encoding="utf-8")
    converted, check = server.instrumentalize_score(source)
    assert check["vocal_notes_before"] > 0
    assert check["vocal_notes_after"] == 0
    assert not re.search(r"[\^_=]*[a-gA-G]", vocal_body(converted))


def test_instrumentalize_score_rejects_garbage(server):
    with pytest.raises(RuntimeError):
        server.instrumentalize_score("not an abc score")
