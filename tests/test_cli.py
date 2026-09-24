"""CLI dispatch tests (no network). Run: python3 -m pytest tests/ -q"""
import sys

sys.path.insert(0, ".")

import pytest

from scrapeforge import batchprobe, cli, pageprobe


def _capture(monkeypatch, module):
    seen = {}
    monkeypatch.setattr(module, "run", lambda args: seen.setdefault("args", args))
    return seen


def test_batchprobe_dispatch_passes_parsed_args(monkeypatch):
    seen = _capture(monkeypatch, batchprobe)
    cli.main(["batchprobe", "a.txt", "b.txt", "--out", "r.csv", "--workers", "2"])
    a = seen["args"]
    assert (a.files, a.out, a.workers) == (["a.txt", "b.txt"], "r.csv", 2)


def test_pageprobe_dispatch_passes_parsed_args(monkeypatch):
    seen = _capture(monkeypatch, pageprobe)
    cli.main(["pageprobe", "u.txt", "--tiers", "t.csv"])
    a = seen["args"]
    assert (a.files, a.tiers, a.out, a.workers) == (
        ["u.txt"], "t.csv", "pagination-matrix.csv", pageprobe.WORKERS)


def test_subcommand_defaults_match_standalone_parsers(monkeypatch):
    # One argument definition per command: the CLI and the module agree.
    seen = _capture(monkeypatch, batchprobe)
    cli.main(["batchprobe", "a.txt"])
    via_cli = seen.pop("args")
    batchprobe.main(["a.txt"])
    assert vars(via_cli).keys() >= vars(seen["args"]).keys()
    assert via_cli.workers == seen["args"].workers == batchprobe.WORKERS


def test_does_not_touch_sys_argv(monkeypatch):
    _capture(monkeypatch, batchprobe)
    before = list(sys.argv)
    cli.main(["batchprobe", "a.txt"])
    assert sys.argv == before


def test_unknown_subcommand_exits_2():
    with pytest.raises(SystemExit) as e:
        cli.main(["nope"])
    assert e.value.code == 2
