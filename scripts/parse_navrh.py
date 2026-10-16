#!/usr/bin/env python3
"""Parse the program annex of a state-budget bill into data/navrh_{rok}_programy.csv.

The annex "Výdavky štátneho rozpočtu na realizáciu programov vlády SR a častí
programov vlády SR" (Príloha č. 4 k zákonu o štátnom rozpočte) lists, per
kapitola, the amount of each program, of each part of a cross-ministry program
and of some subprograms (lines whose name starts with "- "). It is the most
detailed public breakdown of a budget before MF loads it into rozpocet.sk, and
build.py turns it into a clearly labelled estimate by COFOG.

Needs `pdftotext` (poppler) – run locally; the parsed CSV is committed and CI
never re-parses. Validates that program lines sum exactly to each kapitola
total and to the law's expenditure total; refuses to write otherwise.

Usage: python scripts/parse_navrh.py 2027
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 2027: government material UV-27305/2026 "Návrh rozpočtu verejnej správy na roky
# 2027 až 2029" (approved by the government 5 Oct 2026; NR SR passed the law 14 Oct
# 2026 with the same expenditure total), https://rokovania.gov.sk/RVL/Material/32287/1
# 2026: annexes of the promulgated law 303/2025 Z. z. (slov-lex), used only to
# backtest the estimate method against the real 2026 COFOG split.
SOURCES = {
    2027: {
        "annex4": "https://rokovania.gov.sk/download.dat?id=63E54DA3C9454411B2AA8E6F1F080BFC-D92237231DA2898822FE99FEB3F75026",
        "annex1": "https://rokovania.gov.sk/download.dat?id=C9974B510A9C4DDE94229857CCB55396-C9A4CA771E8882B413E0C8AC012A62A8",
    },
    2026: {
        "annex4": "https://static.slov-lex.sk/pdf/prilohy/SK/ZZ/2025/303/20260101_5779543-2.pdf",
        "annex1": "https://static.slov-lex.sk/pdf/prilohy/SK/ZZ/2025/303/20260101_5779539-2.pdf",
    },
}

HEADER = re.compile(r"^\s{10,}(\d{2})\s+-\s+(.+?)\s+\(\s*v eurách\s*\)")
TOTAL = re.compile(r"Výdavky spolu za kapitolu\s+([\d ]+)$")
LINE = re.compile(r"^(?P<code>[0-9][0-9A-Z]{2,6})\s+(?P<name>.*?)\s{2,}(?P<v>\d{1,3}(?: \d{3})+|\d+)\s*$")


def pdf_text(url: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "a.pdf"
        req = urllib.request.Request(url, headers={"User-Agent": "zltastopa-rozpocet/1.0"})
        pdf.write_bytes(urllib.request.urlopen(req, timeout=180).read())
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                              capture_output=True, text=True).stdout


def num(s: str) -> int:
    return int(s.replace(" ", ""))


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    src = SOURCES[year]
    annex1 = pdf_text(src["annex1"])
    spend = num(re.search(r"Výdavky spolu\s+([\d ]+)\n", annex1).group(1))
    revenue = num(re.search(r"Príjmy spolu\s+([\d ]+)\n", annex1).group(1))

    kap = kap_name = None
    totals: dict[str, int] = {}
    rows = []
    for ln in pdf_text(src["annex4"]).splitlines():
        if m := HEADER.match(ln):
            kap, kap_name = m.group(1), m.group(2).strip()
            continue
        if m := TOTAL.search(ln):
            totals[kap] = num(m.group(1))
            continue
        if kap and (m := LINE.match(ln)):
            name = m.group("name").strip()
            rows.append({"kapitola": kap, "nazov_kapitoly": kap_name, "program": m.group("code"),
                         "nazov": name.lstrip("- ").strip(), "podprogram": int(name.startswith("-")),
                         "suma": num(m.group("v"))})

    sums = Counter()
    for r in rows:
        if not r["podprogram"]:
            sums[r["kapitola"]] += r["suma"]
    bad = [k for k in totals if totals[k] != sums[k]]
    if bad or sum(totals.values()) != spend:
        sys.exit(f"annex does not reconcile: kapitoly {bad}, Σ {sum(totals.values())} vs výdavky {spend}")

    out = ROOT / "data" / f"navrh_{year}_programy.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = ROOT / "data" / f"navrh_{year}_suhrn.csv"
    with meta.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rok", "vydavky", "prijmy", "zdroj_programy", "zdroj_bilancia"])
        w.writerow([year, spend, revenue, src["annex4"], src["annex1"]])
    print(f"wrote {out.name} ({len(rows)} rows, {len(totals)} kapitol, výdavky {spend:,} €) and {meta.name}")


if __name__ == "__main__":
    main()
