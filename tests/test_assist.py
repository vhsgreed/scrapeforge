"""init / try / fetch tests against saved fixture pages (no network).
Run: python3 -m pytest tests/ -q"""
import json
import os
import sys

sys.path.insert(0, ".")

import pytest
import yaml

from scrapeforge import cli, scrape
from scrapeforge.suggest import explain_matches, suggest

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def page(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def rows_for(html, s):
    from scrapeforge.extract import extract_page
    return extract_page(html, {"items": s.items, "fields": s.fields})


def test_books_catalogue():
    html = page("books.html")
    s = suggest(html)
    # The card, not its layout wrapper, and not the sidebar or footer lists.
    assert s.items == {"selector": "article.product_pod"}
    assert s.paginate == {"selector": "li.next a"}
    rows = rows_for(html, s)
    assert len(rows) == 6
    # Full title from the title attribute, not the truncated link text.
    assert rows[0]["title"] == "A Light in the Attic"
    assert rows[4]["title"] == "Sapiens: A Brief History of Humankind"
    assert rows[0]["price"] == 51.77
    assert rows[0]["url"] == "catalogue/book_0/index.html"
    assert "availability" in s.fields
    assert not any("btn" in n for n in s.fields)   # no "Add to basket" field


def test_shop_with_utility_classes_and_lazy_images():
    html = page("shop.html")
    s = suggest(html)
    assert s.items == {"selector": "div.product-card"}   # css-1x9f2k, p-4 dropped
    assert s.paginate == {"selector": "a[rel~=next]"}
    rows = rows_for(html, s)
    assert [r["price"] for r in rows] == [49.0, 219.0, 24.5, 1089.99, 89.0]
    assert rows[0]["image"] == "/img/0.webp"            # data-src, not data: URI
    assert rows[0]["brand"] == "Nordhem"


def test_js_shell_falls_back_to_embedded_json():
    html = page("nextjs.html")
    s = suggest(html)
    assert s.items == {"json": "next_data", "path": "props.pageProps.results.hits"}
    rows = rows_for(html, s)
    assert rows[1] == {"id": 2, "title": "Clamp desk lamp", "price_value": 39.5,
                       "price_currency": "EUR", "url": "/l/2"}


def test_table_rows():
    trs = "".join(
        f'<tr class="athing" id="{i}"><td class="title"><span class="rank">{i}.</span>'
        f'<span class="titleline"><a href="https://ex.com/{i}">Story number {i} about things</a></span></td></tr>'
        f'<tr><td class="subtext"><span class="score">{i * 3} points</span></td></tr>'
        for i in range(1, 8))
    html = f"<html><body><table class='itemlist'>{trs}</table>" \
           f"<a class='morelink' href='?p=2'>More</a></body></html>"
    s = suggest(html)
    assert s.items == {"selector": "tr.athing"}
    assert s.paginate == {"selector": "a", "next_text": "More"}
    rows = rows_for(html, s)
    assert rows[0]["title"] == "Story number 1 about things"
    assert rows[0]["url"] == "https://ex.com/1"


def test_nothing_repeated():
    assert suggest("<html><body><p>just one paragraph</p></body></html>") is None


def test_init_writes_a_config_that_runs(tmp_path, capsys):
    out = tmp_path / "books.yaml"
    cli.main(["init", os.path.join(FIX, "books.html"), "--out", str(out)])
    printed = capsys.readouterr().out
    assert "6 items" in printed and "field coverage" in printed
    cfg = yaml.safe_load(out.read_text())
    assert cfg["items"]["selector"] == "article.product_pod"
    res = scrape(str(out), log=None)
    assert len(res.rows) == 6


def test_init_refuses_to_overwrite(tmp_path):
    out = tmp_path / "x.yaml"
    out.write_text("keep me")
    with pytest.raises(SystemExit) as e:
        cli.main(["init", os.path.join(FIX, "books.html"), "--out", str(out)])
    assert e.value.code == 1 and out.read_text() == "keep me"


def test_init_nothing_found_exits_2(tmp_path):
    f = tmp_path / "p.html"
    f.write_text("<html><body><p>one</p></body></html>")
    with pytest.raises(SystemExit) as e:
        cli.main(["init", str(f), "--out", str(tmp_path / "c.yaml")])
    assert e.value.code == 2


def test_try_counts_and_values(capsys):
    cli.main(["try", os.path.join(FIX, "books.html"), "p.price_color",
              "--in", "article.product_pod", "--limit", "2"])
    out = capsys.readouterr().out
    assert "6 items match" in out and "found in 6, missing in 0" in out
    assert '"£51.77"' in out and '"£53.74"' in out and "£50.10" not in out


def test_try_zero_matches_hints_and_exit_2(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["try", os.path.join(FIX, "books.html"), "p.price"])
    assert e.value.code == 2
    assert "p.price_color" in capsys.readouterr().out


def test_try_warns_about_devtools_paths():
    res = explain_matches(page("books.html"),
                          "body > div > div > div > ol > li:nth-child(1)")
    assert any("DevTools" in w for w in res["warnings"])


def test_try_on_js_shell_points_at_embedded_json():
    res = explain_matches(page("nextjs.html"), "div.product")
    assert any("embedded JSON" in h for h in res["hints"])


def test_fetch_saves_file(tmp_path, capsys):
    out = tmp_path / "saved.html"
    cli.main(["fetch", os.path.join(FIX, "shop.html"), "--out", str(out)])
    assert out.read_text() == page("shop.html")
