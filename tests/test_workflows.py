"""Guard rails for GitHub Actions workflow scripts.

macOS runners execute ``/bin/bash`` 3.2, which folds trailing UTF-8 bytes into a
variable name when ``$VAR`` is immediately followed by a multi-byte character:
``echo "已上传到 $REL：..."`` read as ``${REL：}`` and ``set -u`` aborted the step
on run 40487484848 (Windows git-bash 5 accepted it, so the bug only showed on
macOS). Always brace the variable and keep the delimiter ASCII.
"""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
HAZARD = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]")


def test_no_variable_glued_to_multibyte_text():
    offenders = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for match in HAZARD.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.name}:{line}: {match.group()!r}")
    assert not offenders, (
        "workflow 里 $VAR 后面紧跟非 ASCII 字符（macOS bash 3.2 会把它并进变量名）；"
        "改成 ${VAR} 并用 ASCII 分隔符：" + "; ".join(offenders)
    )
