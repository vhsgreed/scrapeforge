"""Incremental runs: keep only rows that are new or changed since last time."""
from __future__ import annotations


def _norm(v) -> str:
    return "" if v is None else str(v)


def _row_id(row: dict, key: list[str] | None) -> tuple:
    if key:
        return tuple(_norm(row.get(k)) for k in key)
    return tuple(sorted((k, _norm(v)) for k, v in row.items()))


def diff_rows(current: list[dict], previous: list[dict],
              key: list[str] | None = None) -> tuple[list[dict], dict]:
    """Rows of `current` that are new or changed relative to `previous`.

    Values compare as strings, so a CSV read back from disk (all strings)
    diffs cleanly against freshly typed rows.
    key: field names that identify a row (e.g. ["url"]). A row whose key is
         unseen is "new"; a seen key with any different value is "changed".
         Without a key, a row is new unless an identical row existed.
    Each returned row gets a `_change` column: "new" or "changed".
    """
    prev = {}
    for row in previous:
        prev[_row_id(row, key)] = row
    out, counts = [], {"new": 0, "changed": 0, "unchanged": 0}
    for row in current:
        old = prev.get(_row_id(row, key))
        if old is None:
            change = "new"
        elif key and any(_norm(row.get(k)) != _norm(old.get(k)) for k in row):
            change = "changed"
        else:
            counts["unchanged"] += 1
            continue
        counts[change] += 1
        out.append({**row, "_change": change})
    return out, counts
