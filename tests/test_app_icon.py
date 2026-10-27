"""Application icon assets and their integration points."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _png_size(path: Path) -> tuple[int, int]:
    import struct

    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    return struct.unpack(">II", head[16:24])


def test_app_icon_assets_are_square_png():
    for rel in ("assets/app-icon.png", "assets/app-icon-256.png",
                "web/static/app-icon.png", "web/static/apple-touch-icon.png"):
        path = ROOT / rel
        assert path.is_file(), rel
        width, height = _png_size(path)
        assert width == height, rel


def test_index_uses_new_favicon():
    html = (ROOT / "web/static/index.html").read_text(encoding="utf-8")
    assert 'rel="icon"' in html and "/static/app-icon.png" in html
    assert "/static/apple-touch-icon.png" in html
    assert 'rel="icon" href="/static/aura.jpg"' not in html


def test_readme_shows_icon():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "assets/app-icon.png" in readme
    assert '<img src="assets/app-icon.png"' in readme
