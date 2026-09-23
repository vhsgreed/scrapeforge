"""Field post-processing tests. Run: python3 -m pytest tests/ -q"""
import sys

sys.path.insert(0, ".")

import pytest

from scrapeforge.extract import clean, extract_items


@pytest.mark.parametrize("raw,spec,want", [
    ("  hi  ", {}, "hi"),
    ("--hi--", {"strip": "-"}, "hi"),
    ("10 points", {"type": "int"}, 10),
    ("£1,299.50", {"type": "float"}, 1299.5),
    ("4.7 out of 5", {"type": "int"}, 4),
    ("id=abc123;", {"regex": r"id=(\w+)"}, "abc123"),
    ("SKU 42 in stock", {"regex": r"SKU \d+", "strip": True}, "SKU 42"),
    ("no number", {"type": "int"}, None),
    ("no number", {"type": "int", "default": 0}, 0),
    (None, {}, ""),
    (None, {"default": "n/a"}, "n/a"),
    ("", {"default": "n/a"}, "n/a"),
    ("x", {"regex": r"\d"}, ""),
    (19.99, {"type": "float"}, 19.99),
    (7, {"type": "str"}, "7"),
])
def test_clean(raw, spec, want):
    assert clean(raw, spec) == want


def test_unknown_type_is_a_config_error():
    with pytest.raises(ValueError):
        clean("1", {"type": "decimal"})


def test_all_joins_every_match_and_types_apply():
    html = """<div class="q"><a class="t">py</a><a class="t">web</a>
              <span class="p">Price: $1,200</span><img src=" /i.png "></div>"""
    rows = extract_items(html, "div.q", {
        "tags": {"selector": "a.t", "all": True},
        "tags_pipe": {"selector": "a.t", "all": True, "join": "|"},
        "price": {"selector": "span.p", "type": "int"},
        "img": {"selector": "img", "attr": "src"},
        "html": {"selector": "span.p", "attr": "html"},
        "missing": {"selector": "b", "type": "float"},
    })
    assert rows == [{"tags": "py, web", "tags_pipe": "py|web", "price": 1200,
                     "img": "/i.png", "html": "Price: $1,200",
                     "missing": None}]
