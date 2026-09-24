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


def test_mid_size_page_with_weak_marker_returns_result():
    # 20-50 KB page mentioning "captcha" used to fall through and return None.
    r = classify_response("https://site/", 200, "a" * 30000 + " captcha")
    assert r is not None
    assert r.tier == 1 and "captcha" in r.markers


def test_large_page_with_generic_word_stays_tier_1():
    r = classify_response("https://site/", 200, "a" * 60000 + " weekly challenge")
    assert r.tier == 1


def test_large_page_with_block_signature_is_tier_2():
    html = "a" * 30000 + '<script src="https://challenges.cloudflare.com/x">'
    r = classify_response("https://site/", 200, html)
    assert r.tier == 2


def test_error_status_is_not_static():
    for status in (404, 500):
        r = classify_response("https://site/", status, "a" * 30000)
        assert r.tier >= 2 and not r.confident


def test_every_branch_returns_a_result():
    bodies = ["", "x", "captcha", "a" * 30000, "a" * 30000 + " captcha",
              "a" * 60000 + " challenge", "punish" + "a" * 60000]
    for status in (0, 200, 202, 301, 403, 404, 429, 500, 503):
        for body in bodies:
            assert classify_response("https://site/", status, body) is not None
