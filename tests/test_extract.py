"""Extraction unit tests. Run: python3 -m pytest tests/ -q"""
import sys

sys.path.insert(0, ".")

from scrapeforge.extract import extract_items

HTML = """
<html><body>
<table>
  <tr class="athing"><td><span class="titleline"><a href="/a">Alpha</a></span></td></tr>
  <tr class="score"><td><span class="score">10 points</span></td></tr>
  <tr class="athing"><td><span class="titleline"><a href="/b">Beta</a></span></td></tr>
  <tr class="score"><td><span class="score">20 points</span></td></tr>
</table>
</body></html>
"""


def test_item_and_global_scope():
    rows = extract_items(HTML, "tr.athing", {
        "title": {"selector": "span.titleline a", "attr": "text"},
        "url": {"selector": "span.titleline a", "attr": "href"},
        "score": {"selector": "span.score", "attr": "text", "scope": "global"},
    })
    assert len(rows) == 2
    assert rows[0]["title"] == "Alpha" and rows[0]["url"] == "/a"
    assert rows[0]["score"] == "10 points"
    assert rows[1]["title"] == "Beta" and rows[1]["score"] == "20 points"


def test_missing_element_is_empty_string():
    rows = extract_items("<html><body><div class='i'></div></body></html>",
                         "div.i", {"x": {"selector": "a", "attr": "text"}})
    assert rows == [{"x": ""}]
