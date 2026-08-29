#!/usr/bin/env python3
"""Scrape SEMICON Taiwan exhibitor list (official expo.semi.org page).

Outputs CSV: company, booth_no, booth_id. One page, tier 1 (static).

Usage: python3 semicon-exhibitors.py [--out exhibitors.csv]
"""
import argparse
import csv
import re
import sys

import httpx
from bs4 import BeautifulSoup

URL = "https://expo.semi.org/taiwan2026/Public/Exhibitors.aspx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def scrape() -> list[dict]:
    r = httpx.get(URL, timeout=30, follow_redirects=True,
                  headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    rows = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "eBooth.aspx" not in href:
            continue
        name = a.get_text(strip=True)
        if not name:
            continue
        m_id = re.search(r"BoothID=(\d+)", href)
        booth_id = m_id.group(1) if m_id else ""
        booth_no = ""
        tr = a.find_parent("tr")
        if tr:
            for td in tr.find_all("td"):
                m = re.search(r"\b([A-Z]\d{4})\b", td.get_text(strip=True))
                if m:
                    booth_no = m.group(1)
                    break
        rows.append({"company": name, "booth_no": booth_no,
                     "booth_id": booth_id})
    # dedupe by company, keep first
    seen, uniq = set(), []
    for r_ in rows:
        if r_["company"] not in seen:
            seen.add(r_["company"])
            uniq.append(r_)
    return uniq


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="semicon-taiwan-2026-exhibitors.csv")
    args = p.parse_args()
    rows = scrape()
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company", "booth_no", "booth_id"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} exhibitors -> {args.out}")


if __name__ == "__main__":
    main()
