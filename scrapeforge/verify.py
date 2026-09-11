"""Data-level verification. An empty result is a failure, not a success.

Fleet lesson, from building roughly 30 production scrapers: a run that reports
SUCCEEDED with zero rows means nothing. The status code and the exit code only
prove the process finished. They do not prove anything was extracted. So this
module asserts row counts, prints a sample, and fails loudly with a non-zero
exit when the result is empty.

Exit codes (the contract):
  0  at least min_rows records found
  1  I/O or parse error
  2  fewer than min_rows records (empty result is the common case)
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_EMPTY = 2


@dataclass
class VerifyResult:
    ok: bool
    rows: int
    min_rows: int
    sample: list[dict]
    source: str
    reason: str = ""


def verify_records(rows: list[dict], min_rows: int = 1, sample: int = 3,
                   source: str = "records") -> VerifyResult:
    """Assert a record count and capture a sample. Never raises on empty."""
    n = len(rows)
    ok = n >= min_rows
    reason = "" if ok else f"only {n} row(s), need at least {min_rows}"
    return VerifyResult(ok, n, min_rows, rows[:sample], source, reason)


def read_records(path: str, fmt: str | None = None) -> list[dict]:
    """Read a dataset file back in. Format inferred from the extension."""
    if fmt is None:
        ext = os.path.splitext(path)[1].lower()
        fmt = {".json": "json", ".jsonl": "jsonl"}.get(ext, "csv")
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if fmt == "csv":
        if not text:
            return []
        return list(csv.DictReader(text.splitlines()))
    if not text:
        return []
    if fmt == "json":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    if fmt == "jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    raise ValueError(f"unknown format: {fmt}")


def verify_file(path: str, fmt: str | None = None, min_rows: int = 1,
                sample: int = 3) -> VerifyResult:
    try:
        rows = read_records(path, fmt)
    except Exception as e:  # noqa: BLE001 - reported as a hard error, not a raise
        return VerifyResult(False, 0, min_rows, [], path,
                            f"{type(e).__name__}: {e}")
    return verify_records(rows, min_rows, sample, source=path)


def print_report(res: VerifyResult, stream=None) -> None:
    stream = stream or sys.stdout
    print(f"[verify] {res.source}: {res.rows} row(s), minimum {res.min_rows}",
          file=stream)
    if res.sample:
        print(f"[verify] sample ({len(res.sample)}):", file=stream)
        for row in res.sample:
            print("  " + json.dumps(row, ensure_ascii=False), file=stream)
    if res.ok:
        print("[verify] OK", file=stream)
    else:
        print(f"[verify] FAIL: {res.reason}", file=stream)
