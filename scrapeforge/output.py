"""Output writers: CSV, JSON, JSONL."""
from __future__ import annotations

import csv
import json


def write(rows: list[dict], out_path: str, fmt: str = "csv") -> None:
    fmt = (fmt or "csv").lower()
    if fmt == "csv":
        _write_csv(rows, out_path)
    elif fmt == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"unknown format: {fmt}")


def _write_csv(rows: list[dict], out_path: str) -> None:
    if not rows:
        open(out_path, "w", encoding="utf-8").close()
        return
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
