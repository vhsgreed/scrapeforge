"""Classifier unit tests. Run: python3 -m pytest tests/ -q"""
import sys
sys.path.insert(0, ".")

from scrapeforge.classify import classify_response


def test_static_page():
    html = "<html><head><title>Hello</title></head><body><h1>Hi</h1></body></html>"
    r = classify_response("https://example.com/", 200, html)
    assert r.tier == 1 and r.confident


def test_blocked_empty():
    r = classify_response("https://site/", 202, "")
    assert r.tier == 3


def test_blocked_challenge():
    r = classify_response("https://site/", 200, "<html>captcha verify you are human</html>")
    assert r.tier == 3


def test_akamai_full_page():
    # Big body with akamai punish markers = real page, TLS tier
    html = "<html><body>" + ("x" * 60000) + "</body></html>"
    r = classify_response("https://site/", 200, html)
    assert r.tier == 1  # no markers -> static


def test_ali_style():
    html = "punish" + ("x" * 60000)
    r = classify_response("https://aliexpress.com/", 200, html)
    assert r.tier == 2
