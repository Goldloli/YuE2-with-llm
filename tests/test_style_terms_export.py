"""Word glossary export: docs/style-terms.md stays in sync with the dictionary."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "export_style_terms", ROOT / "tools" / "export_style_terms.py")
export_style_terms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_style_terms)


def test_glossary_matches_regeneration():
    terms = export_style_terms.load_terms()
    assert export_style_terms.OUT_FILE.read_text(encoding="utf-8") == \
        export_style_terms.render(terms)


def test_every_term_is_categorized():
    assert export_style_terms.uncategorized(export_style_terms.load_terms()) == []


def test_category_table_has_no_stale_entries():
    assert export_style_terms.stale_groups(export_style_terms.load_terms()) == []


def test_glossary_lists_every_term():
    terms = export_style_terms.load_terms()
    text = export_style_terms.OUT_FILE.read_text(encoding="utf-8")
    assert [key for key in terms if key not in text] == []
