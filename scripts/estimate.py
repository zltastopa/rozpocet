"""Estimate a year's COFOG split from its bill's program annex (used by build.py).

MF publishes the COFOG split of a budget only after loading it into rozpocet.sk.
Before that, the most detailed public breakdown is the program annex of the
bill (data/navrh_{rok}_programy.csv, parsed by parse_navrh.py): the amount of
every program and of some subprograms, per kapitola. The amounts are exact;
how each program splits over the tiles is not, so we borrow it from the
row-level approved budgets of previous years (cache/detail/schvaleny-{rok}.csv):

1. pieces: every program minus its listed subprograms, and every listed subprogram
2. each piece is spread like the rows of the same kapitola and program code
   (excluding listed subprograms) one year earlier, else two years earlier, else
   like the same code in any kapitola one year earlier – but only if the program
   name matches (codes can be reused for different programs); last resorts are
   the kapitola's whole budget a year earlier and finally the whole state budget
3. rows are classified by exactly the same rules as the published years

The amount handled at each fallback level is reported, and the method is
backtested on the previous year at the same annex granularity.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "cache" / "detail"

LEVELS = [
    ("program_r1", "rovnaký program v tej istej kapitole o rok skôr"),
    ("program_r2", "rovnaký program v tej istej kapitole o dva roky skôr"),
    ("program_ina_kapitola", "rovnaký program v inej kapitole o rok skôr"),
    ("kapitola", "celá kapitola o rok skôr"),
    ("celok", "celý štátny rozpočet o rok skôr"),
]


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-záäčďéíĺľňóôŕšťúýž]+", " ", s.lower()).strip()


def same_name(a: str | None, b: str | None) -> bool | None:
    """True/False if both names are known, None if the code has no name in the list."""
    if not a or not b:
        return None
    a, b = _norm(a), _norm(b)
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.75


def load_rows(year: int, classify) -> list[tuple[str, str, str, str, float]]:
    """(kapitola, program, tile, child, €) for approved state-budget expenditure rows."""
    out = []
    with (DETAIL / f"schvaleny-{year}.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["TYP"] != "VYDAVKY" or r["DRH"] != "211" or r["ORG"] == "120":
                continue  # only kapitoly of the state budget (not Štátny dlh, SURO, SFA)
            v = float(r["SCHV_ROK"] or 0)
            if v:
                tile, child = classify(r["ORG"], r["FNC"], r["EKO"])
                out.append((r["ORG"], r["PRG"], tile, child, v))
    return out


def load_names(year: int) -> dict[tuple[str, str], str]:
    with (DETAIL / f"programy-{year}.csv").open(encoding="utf-8") as f:
        return {(r["kapitola"][:2], r["kod"]): r["nazov"] for r in csv.DictReader(f)}


def detail_meta(year: int) -> dict:
    return json.loads((DETAIL / f"schvaleny-{year}.json").read_text(encoding="utf-8"))


def pieces(annex: list[dict]) -> list[dict]:
    out = []
    by_kap = defaultdict(list)
    for r in annex:
        by_kap[r["kapitola"]].append(r)
    for kap, rows in by_kap.items():
        programs = [r for r in rows if r["podprogram"] == "0"]
        subs = [r for r in rows if r["podprogram"] == "1"]
        for p in programs:
            mine = [s for s in subs if s["program"].startswith(p["program"]) and s["program"] != p["program"]]
            rest = int(p["suma"]) - sum(int(s["suma"]) for s in mine)
            if rest < 0:
                raise ValueError(f"kapitola {kap} program {p['program']}: subprograms exceed the program")
            out.append({"kap": kap, "code": p["program"], "name": p["nazov"], "amount": rest,
                        "exclude": [s["program"] for s in mine]})
            out += [{"kap": kap, "code": s["program"], "name": s["nazov"], "amount": int(s["suma"]), "exclude": []}
                    for s in mine]
        orphans = [s for s in subs if not any(s["program"].startswith(p["program"]) for p in programs)]
        if orphans:
            raise ValueError(f"kapitola {kap}: subprograms without a program {[s['program'] for s in orphans]}")
    return [p for p in out if p["amount"]]


def estimate(year: int, classify, kap_names: dict[str, str]) -> tuple[dict, dict]:
    """Return ({(tile, child, kap): €}, report) for `year` from its annex."""
    annex = list(csv.DictReader((ROOT / "data" / f"navrh_{year}_programy.csv").open(encoding="utf-8")))
    r1, r2 = load_rows(year - 1, classify), load_rows(year - 2, classify)
    n1, n2 = load_names(year - 1), load_names(year - 2)

    def shares(rows, pred) -> dict:
        acc = defaultdict(float)
        for kap, prg, tile, child, v in rows:
            if pred(kap, prg):
                acc[(tile, child)] += v
        tot = sum(acc.values())
        return {k: v / tot for k, v in acc.items()} if tot > 0 else {}

    def matches(code, exclude):
        return lambda prg: prg.startswith(code) and not any(prg.startswith(x) for x in exclude)

    out = defaultdict(float)
    level_amount = defaultdict(float)
    unverified = 0.0   # amount whose program code has no name in MF's program list
    for p in pieces(annex):
        m = matches(p["code"], p["exclude"])
        chosen = None
        for level, rows, names, same_kap in (("program_r1", r1, n1, True), ("program_r2", r2, n2, True),
                                             ("program_ina_kapitola", r1, n1, False)):
            if same_kap:
                ident = same_name(p["name"], names.get((p["kap"], p["code"])))
                sh = shares(rows, lambda k, prg: k == p["kap"] and m(prg)) if ident is not False else {}
            else:
                cands = {k for (k, c), nm in names.items() if c == p["code"] and same_name(p["name"], nm)}
                ident = bool(cands) or None
                sh = shares(rows, lambda k, prg: k in cands and m(prg)) if cands else {}
            if sh:
                chosen = (level, sh, ident)
                break
        if chosen is None:
            sh = shares(r1, lambda k, prg: k == p["kap"])
            chosen = ("kapitola", sh, True) if sh else ("celok", shares(r1, lambda k, prg: True), True)
        level, sh, ident = chosen
        level_amount[level] += p["amount"]
        if ident is None:
            unverified += p["amount"]
        for (tile, child), s in sh.items():
            out[(tile, child, kap_names.get(p["kap"], p["kap"]))] += p["amount"] * s

    total = sum(int(r["suma"]) for r in annex if r["podprogram"] == "0")
    if abs(sum(out.values()) - total) > 1:
        raise ValueError(f"estimate for {year} does not add up: {sum(out.values()):.0f} != {total}")
    report = {
        "levels": [{"id": lid, "popis": desc, "suma": round(level_amount.get(lid, 0))} for lid, desc in LEVELS],
        "bez_overenia_nazvu": round(unverified),
        "zaklad": [year - 1, year - 2],
        "zdroje_riadkov": [detail_meta(year - 1)["url"], detail_meta(year - 2)["url"]],
    }
    return dict(out), report
