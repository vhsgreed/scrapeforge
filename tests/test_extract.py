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


# HN shape: a job post has no score in its companion row.
HN_WITH_JOB = """
<html><body><table>
  <tr class="athing"><td><span class="titleline"><a href="/a">Alpha</a></span></td></tr>
  <tr><td class="subtext"><span class="score">10 points</span></td></tr>
  <tr class="athing"><td><span class="titleline"><a href="/job">Job</a></span></td></tr>
  <tr><td class="subtext"><span class="age">1 hour ago</span></td></tr>
  <tr class="athing"><td><span class="titleline"><a href="/b">Beta</a></span></td></tr>
  <tr><td class="subtext"><span class="score">20 points</span></td></tr>
</table></body></html>
"""


def test_next_scope_stays_aligned_when_a_row_lacks_the_field():
    rows = extract_items(HN_WITH_JOB, "tr.athing", {
        "title": {"selector": "span.titleline a", "attr": "text"},
        "score": {"selector": "span.score", "attr": "text", "scope": "next"},
    })
    assert [(r["title"], r["score"]) for r in rows] == [
        ("Alpha", "10 points"), ("Job", ""), ("Beta", "20 points")]


def test_global_scope_misaligns_when_a_row_lacks_the_field():
    # Documents why the HN example uses scope: next, not scope: global.
    rows = extract_items(HN_WITH_JOB, "tr.athing", {
        "score": {"selector": "span.score", "attr": "text", "scope": "global"},
    })
    assert rows[1]["score"] == "20 points"  # Beta's score landed on Job
