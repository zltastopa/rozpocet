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

Usage: python scripts/parse_navrh.py 2027      # state budget program annex
       python scripts/parse_navrh.py sp 2027   # Sociálna poisťovňa budget, row level
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 2027: annexes of the law as passed by NR SR on 14 Oct 2026 ("Schválené znenie", III. čítanie
# of parlamentná tlač 1555; identical, line by line, to the government proposal UV-27305/2026).
# nrsr.sk serves them only inside a zip; "URL#member" picks the PDF by its name prefix.
# 2026: annexes of the promulgated law 303/2025 Z. z. (slov-lex), used only to
# backtest the estimate method against the real 2026 COFOG split.
NRSR_1555 = "http://www.nrsr.sk/web/Dynamic/DownloadSslpZip.aspx?MasterId=11020&section=3_citanie&WFTID="
SOURCES = {
    2027: {
        "annex4": NRSR_1555 + "#Príloha tlac 1555 c. 4",
        "annex1": NRSR_1555 + "#Príloha tlac 1555 c.1",
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
    url, _, member = url.partition("#")
    # nrsr.sk rejects non-browser user agents
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (zltastopa-rozpocet/1.0)"})
    body = urllib.request.urlopen(req, timeout=180).read()
    if member:
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            # zip names are CP852 encoded but flagged as CP437
            names = {i.filename.encode("cp437").decode("cp852"): i for i in z.infolist()}
            body = z.read(next(i for n, i in names.items() if n.startswith(member)))
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "a.pdf"
        pdf.write_bytes(body)
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


# Sociálna poisťovňa budget (government material, approved by an NR SR resolution):
# Príloha a has a row-level table (druh, IČO 30807484, zdroj, COFOG, EKV) in euros.
# 2027: UV-27306/2026, https://rokovania.gov.sk/RVL/Material/32285/1 — approved unchanged by NR SR
# (parlamentná tlač 1558, hlasovanie č. 228 on 14 Oct 2026; the finance committee's resolution
# VFR 340 states expenditure of 15 545 698 tis. €, equal to the 'Spolu' parsed here).
SP_SOURCES = {
    2027: ("https://rokovania.gov.sk/download.dat?id=685E2ECE65D94CB7976B49E636999089-36659E1E379E0A90838E2F810E930542",
           "schválený uznesením NR SR 14. 10. 2026, hlasovanie č. 228, parlamentná tlač 1558"),
}
SP_ROW = re.compile(r"^\s*3\s+30807484\s+(\S+)\s+(?:NEALOK\s+)?(\d{4})\s+(\d{3,6})\s+(\d{1,3}(?: \d{3})*)\s{2,}")


def main_sp(year: int) -> None:
    """Write data/navrh_{rok}_sp.csv (expenditure rows) and _sp_suhrn.csv (total, state transfer).
    Rows must sum exactly to the table's 'Spolu'; the state transfer is revenue item 312001."""
    lines = pdf_text(SP_SOURCES[year][0]).splitlines()
    start = next(i for i, ln in enumerate(lines) if re.search(r"^Výdavky\s+\( v eurách", ln))
    rows, spolu = [], None
    for ln in lines[start + 1:]:
        if s := re.match(r"^Spolu\s*:\s+([\d ]+?)\s{2,}", ln):
            spolu = num(s.group(1))
            break
        if m := SP_ROW.match(ln):
            rows.append({"zdroj": m.group(1), "cofog": m.group(2), "ekv": m.group(3), "suma": num(m.group(4))})
        elif re.match(r"^\s*3\s+30807484", ln):
            sys.exit(f"unparsed Sociálna poisťovňa row: {ln.strip()[:120]}")
    if spolu is None or sum(r["suma"] for r in rows) != spolu:
        sys.exit(f"Sociálna poisťovňa rows {sum(r['suma'] for r in rows)} != Spolu {spolu}")
    transfer = sum(num(m.group(1)) for ln in lines[:start]
                   if (m := re.match(r"^\s*3\s+30807484\s+111\s+312001\s+(\d{1,3}(?: \d{3})*)\s{2,}", ln)))
    out = ROOT / "data" / f"navrh_{year}_sp.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (ROOT / "data" / f"navrh_{year}_sp_suhrn.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rok", "vydavky_spolu", "transfer_zo_sr", "zdroj", "schvalenie"])
        w.writerow([year, spolu, transfer, *SP_SOURCES[year]])
    print(f"wrote {out.name} ({len(rows)} rows, Spolu {spolu:,} €, transfer zo ŠR {transfer:,} €)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sp":
        main_sp(int(sys.argv[2]) if len(sys.argv) > 2 else 2027)
    else:
        main()
