"""Output writers: CSV, JSON, JSONL. Path "-" writes to stdout."""
from __future__ import annotations

import contextlib
import csv
import json
import sys


@contextlib.contextmanager
def _open(out_path: str):
    if out_path == "-":
        yield sys.stdout
        sys.stdout.flush()
    else:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            yield f


def write(rows: list[dict], out_path: str, fmt: str = "csv") -> None:
    fmt = (fmt or "csv").lower()
    if fmt not in ("csv", "json", "jsonl"):
        raise ValueError(f"unknown format: {fmt}")
    with _open(out_path) as f:
        if fmt == "csv":
            _write_csv(rows, f)
        elif fmt == "json":
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(rows: list[dict], f) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    for row in rows[1:]:
        fieldnames += [k for k in row if k not in fieldnames]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
