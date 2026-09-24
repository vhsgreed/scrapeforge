"""Embedded JSON tests. Run: python3 -m pytest tests/ -q"""
import json
import sys

sys.path.insert(0, ".")

from scrapeforge.embedded import discover, get_path, items_from_json
from scrapeforge.extract import extract_page

LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "Product", "name": "Lamp", "offers": {"price": "19.90"}},
    {"@type": "BreadcrumbList", "name": "crumbs"},
    {"@type": "Product", "name": "Desk", "offers": {"price": "120"}},
]}
NEXT = {"props": {"pageProps": {"products": [
    {"title": "A", "price": {"amount": 5}, "tags": ["x", "y"]},
    {"title": "B", "price": {"amount": 7}, "tags": []},
]}}}
PAGE = f"""<html><head>
<script type="application/ld+json">{json.dumps(LD)}</script>
<script type="application/ld+json">not json at all</script>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(NEXT)}</script>
<script>window.__INITIAL_STATE__ = {{"cart": {{"items": [{{"sku": 1}}, {{"sku": 2}}]}}}};
var other = 1;</script>
</head><body><div id="root"></div></body></html>"""


def test_get_path_fans_out_and_skips_missing():
    doc = {"a": [{"b": 1}, {"b": 2}, {"c": 3}]}
    assert get_path(doc, "a.*.b") == [1, 2]
    assert get_path(doc, "a.1.b") == [2]
    assert get_path(doc, "a.-1.c") == [3]
    assert get_path(doc, "nope.x") == []


def test_ld_json_graph_with_type_filter():
    items = items_from_json(PAGE, {"json": "ld+json",
                                   "where": {"@type": "Product"}})
    assert [i["name"] for i in items] == ["Lamp", "Desk"]


def test_next_data_path_to_list():
    cfg = {"items": {"json": "next_data", "path": "props.pageProps.products"},
           "fields": {"title": {"path": "title"},
                      "price": {"path": "price.amount", "type": "float"},
                      "tags": {"path": "tags.*", "all": True},
                      "missing": {"path": "nope"}}}
    assert extract_page(PAGE, cfg) == [
        {"title": "A", "price": 5.0, "tags": "x, y", "missing": ""},
        {"title": "B", "price": 7.0, "tags": "", "missing": ""}]


def test_window_var_assignment():
    items = items_from_json(PAGE, {"json": "var:__INITIAL_STATE__",
                                   "path": "cart.items"})
    assert items == [{"sku": 1}, {"sku": 2}]


def test_json_parse_string_assignment():
    html = r'<script>window.__DATA__ = JSON.parse("{\"rows\":[{\"n\":1}]}");</script>'
    assert items_from_json(html, {"json": "var:__DATA__", "path": "rows"}) == [{"n": 1}]


def test_css_selector_source():
    html = '<script id="data" type="application/json">[{"k": "v"}]</script>'
    assert items_from_json(html, {"json": "script#data"}) == [{"k": "v"}]


def test_discover_summarises_sources():
    found = {f["source"]: f for f in discover(PAGE)}
    assert found["ld+json"]["types"] == {"Product": 2, "BreadcrumbList": 1}
    assert ("props.pageProps.products", 2) in found["next_data"]["lists"]
    assert ("cart.items", 2) in found["var:__INITIAL_STATE__"]["lists"]


def test_no_embedded_json():
    assert discover("<html><body>plain</body></html>") == []
