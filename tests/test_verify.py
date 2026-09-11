"""Data-verification unit tests. Run: python3 -m pytest tests/ -q"""
import csv
import json
import os
import sys

sys.path.insert(0, ".")

from scrapeforge.verify import (EXIT_EMPTY, EXIT_OK, read_records,
                                verify_file, verify_records)


def test_verify_records_ok():
    res = verify_records([{"a": "1"}, {"a": "2"}], min_rows=1, sample=1)
    assert res.ok and res.rows == 2 and len(res.sample) == 1


def test_verify_records_empty_fails():
    res = verify_records([], min_rows=1)
    assert not res.ok and res.rows == 0 and "need at least" in res.reason


def test_verify_records_min_rows():
    res = verify_records([{"a": "1"}], min_rows=5)
    assert not res.ok


def test_verify_file_csv_roundtrip(tmp_path):
    p = tmp_path / "out.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "url"])
        w.writeheader()
        w.writerows([{"title": "x", "url": "u"}, {"title": "y", "url": "v"}])
    res = verify_file(str(p))
    assert res.ok and res.rows == 2


def test_verify_file_empty_csv_fails(tmp_path):
    p = tmp_path / "empty.csv"
    open(p, "w").close()
    res = verify_file(str(p))
    assert not res.ok and res.rows == 0


def test_verify_file_json(tmp_path):
    p = tmp_path / "out.json"
    p.write_text(json.dumps([{"a": "1"}]), encoding="utf-8")
    assert verify_file(str(p)).rows == 1


def test_verify_file_jsonl(tmp_path):
    p = tmp_path / "out.jsonl"
    p.write_text('{"a": "1"}\n{"a": "2"}\n', encoding="utf-8")
    assert verify_file(str(p)).rows == 2


def test_read_records_missing_file_reports_error():
    res = verify_file("/nonexistent/does-not-exist.csv")
    assert not res.ok and "Error" in res.reason
