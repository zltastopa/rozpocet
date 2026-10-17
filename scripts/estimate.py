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
    ("presna_suma", "presná suma z hlavnej knihy rozpočtu alebo rozpočtu Sociálnej poisťovne"),
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


# Plán obnovy a odolnosti ends in 2026: the 2027 main book shows zdroj POO 0 in 2027 N for
# every kapitola except VPS (whose programs are carved out exactly), so a 2027 program has no
# POO money and its POO-funded rows (ZDR 1P..) of a year earlier must not shape its split
POO_LAST_YEAR = 2026


def load_rows(year: int, classify, drop_poo: bool) -> list[tuple[str, str, str, str, str, str, float]]:
    """(kapitola, program, EKV, FNC, tile, child, €) for approved state-budget expenditure rows."""
    out = []
    with (DETAIL / f"schvaleny-{year}.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["TYP"] != "VYDAVKY" or r["DRH"] != "211" or r["ORG"] == "120":
                continue  # only kapitoly of the state budget (not Štátny dlh, SURO, SFA)
            if drop_poo and r["ZDR"].startswith("1P"):
                continue
            v = float(r["SCHV_ROK"] or 0)
            if v:
                tile, child = classify(r["ORG"], r["FNC"], r["EKO"])
                out.append((r["ORG"], r["PRG"], r["EKO"], r["FNC"], tile, child, v))
    return out


def row_filter(spec: str):
    """'PRG|EKV|FNC' (prefixes, empty = any) -> predicate on (program, EKV, FNC)."""
    prg, eko, fnc = (spec.split("|") + ["", ""])[:3]
    return lambda p, e, f: p.startswith(prg) and e.startswith(eko) and f.startswith(fnc)


def load_names(year: int) -> dict[tuple[str, str], str]:
    with (DETAIL / f"programy-{year}.csv").open(encoding="utf-8") as f:
        return {(r["kapitola"][:2], r["kod"]): r["nazov"] for r in csv.DictReader(f)}


def detail_meta(year: int) -> dict:
    return json.loads((DETAIL / f"schvaleny-{year}.json").read_text(encoding="utf-8"))


def pieces(annex: list[dict]) -> list[dict]:
    """Disjoint pieces: every listed node (program or subprogram) minus its directly
    nested listed subprograms. Subprograms can nest (0HW01 > 0HW0101), so a node's
    direct children are the listed codes under it with no other listed code between.
    A code "PRG~EKV" is one economic item inside program PRG (e.g. 0HW02~649005, the
    odvod do rozpočtu EÚ): its parent's remainder then also excludes rows of that item.
    A code "PRG#NN" is a purpose the main book itemises inside PRG (e.g. MO's hospital
    transfer); its "zaklad" lists the base-year rows it replaces ('PRG|EKV|FNC', ';'),
    which the parent's remainder then excludes so the purpose is not counted twice."""
    out = []
    by_kap = defaultdict(list)
    for r in annex:
        by_kap[r["kapitola"]].append(r)
    for kap, rows in by_kap.items():
        programs = [r for r in rows if r["podprogram"] == "0"]
        subs = [r for r in rows if r["podprogram"] == "1"]
        orphans = [s for s in subs if not any(s["program"].startswith(p["program"]) for p in programs)]
        if orphans:
            raise ValueError(f"kapitola {kap}: subprograms without a program {[s['program'] for s in orphans]}")
        for p in programs:
            nodes = [p] + [s for s in subs if s["program"].startswith(p["program"]) and s["program"] != p["program"]]
            for n in nodes:
                code = n["program"]
                below = [s for s in nodes if s["program"] != code and s["program"].startswith(code)]
                direct = [s for s in below if not any(o is not s and s["program"].startswith(o["program"])
                                                      for o in below)]
                rest = int(n["suma"]) - sum(int(s["suma"]) for s in direct)
                if rest < 0:
                    raise ValueError(f"kapitola {kap} {code}: listed subprograms exceed it")
                out.append({"kap": kap, "code": code, "name": n["nazov"], "amount": rest,
                            "exclude": [s["program"] for s in direct if "~" not in s["program"]],
                            "exclude_eko": {s["program"].split("~")[1] for s in direct if "~" in s["program"]},
                            "exclude_rows": [row_filter(f) for s in direct
                                             for f in (s.get("zaklad") or "").split(";") if f]})
    return [p for p in out if p["amount"]]


def estimate(year: int, classify, kap_names: dict[str, str], known: list[dict] | None = None) -> tuple[dict, dict]:
    """Return ({(tile, child, kap): €}, report) for `year` from its annex.
    `known` lists exact amounts the annex does not itemise (from MF's main book or SP's
    budget), e.g. VPS groups or the transfer to Sociálna poisťovňa. Each is carved out of
    its parent program like a listed subprogram; with a "tile" it is assigned there
    directly, otherwise it is spread like that program's rows a year earlier."""
    annex = list(csv.DictReader((ROOT / "data" / f"navrh_{year}_programy.csv").open(encoding="utf-8")))
    known = known or []
    annex += [{"kapitola": k["kap"], "nazov_kapitoly": "", "program": k["code"], "nazov": k["name"],
               "podprogram": "1", "suma": str(k["amount"]), "zaklad": k.get("zaklad", "")} for k in known]
    fixed = {(k["kap"], k["code"]): (k["tile"], k["child"]) for k in known if k.get("tile")}
    drop_poo = year > POO_LAST_YEAR
    r1, r2 = load_rows(year - 1, classify, drop_poo), load_rows(year - 2, classify, drop_poo)
    n1, n2 = load_names(year - 1), load_names(year - 2)

    def shares(rows, pred) -> dict:
        acc = defaultdict(float)
        for kap, prg, eko, fnc, tile, child, v in rows:
            if pred(kap, prg, eko, fnc):
                acc[(tile, child)] += v
        tot = sum(acc.values())
        return {k: v / tot for k, v in acc.items()} if tot > 0 else {}

    def matches(p):
        return lambda prg, eko, fnc: (prg.startswith(p["code"]) and not any(prg.startswith(x) for x in p["exclude"])
                                      and eko not in p["exclude_eko"]
                                      and not any(f(prg, eko, fnc) for f in p["exclude_rows"]))

    out = defaultdict(float)
    level_amount = defaultdict(float)
    unverified = 0.0   # amount whose program code has no name in MF's program list
    uncertain = 0.0
    uncertain_parts = []
    for p in pieces(annex):
        m = matches(p)
        chosen = (("presna_suma", {fixed[(p["kap"], p["code"])]: 1.0}, True)
                  if (p["kap"], p["code"]) in fixed else None)
        for level, rows, names, same_kap in (() if chosen else
                                             (("program_r1", r1, n1, True), ("program_r2", r2, n2, True),
                                              ("program_ina_kapitola", r1, n1, False))):
            if same_kap:
                # cross-ministry programs are named only in the gestor's kapitola
                known_name = names.get((p["kap"], p["code"])) or next(
                    (nm for (k, c), nm in names.items() if c == p["code"]), None)
                ident = same_name(p["name"], known_name)
                sh = shares(rows, lambda k, prg, eko, fnc: k == p["kap"] and m(prg, eko, fnc)) if ident is not False else {}
            else:
                cands = {k for (k, c), nm in names.items() if c == p["code"] and same_name(p["name"], nm)}
                ident = bool(cands) or None
                sh = shares(rows, lambda k, prg, eko, fnc: k in cands and m(prg, eko, fnc)) if cands else {}
            if sh:
                chosen = (level, sh, ident)
                break
        if chosen is None:
            sh = shares(r1, lambda k, prg, eko, fnc: k == p["kap"])
            chosen = ("kapitola", sh, True) if sh else ("celok", shares(r1, lambda *_: True), True)
        level, sh, ident = chosen
        level_amount[level] += p["amount"]
        if ident is None:
            unverified += p["amount"]
        for (tile, child), s in sh.items():
            out[(tile, child, kap_names.get(p["kap"], p["kap"]))] += p["amount"] * s
        # money whose tile is genuinely uncertain: what the program did NOT spend on its
        # main tile a year earlier (a program that went wholly to one tile adds nothing)
        by_tile = defaultdict(float)
        for (tile, _), s in sh.items():
            by_tile[tile] += s
        if level != "presna_suma":
            u = p["amount"] * (1 - max(by_tile.values()))
            uncertain += u
            if u:
                top = max(by_tile, key=by_tile.get)
                uncertain_parts.append({"kapitola": kap_names.get(p["kap"], p["kap"]), "program": p["code"],
                                        "nazov": p["name"], "suma": round(p["amount"]), "neiste": round(u),
                                        "podiely": {t: round(s, 3) for t, s in sorted(by_tile.items(), key=lambda x: -x[1])},
                                        "hlavna": top})

    total = sum(int(r["suma"]) for r in annex if r["podprogram"] == "0")
    if abs(sum(out.values()) - total) > 1:
        raise ValueError(f"estimate for {year} does not add up: {sum(out.values()):.0f} != {total}")
    report = {
        "levels": [{"id": lid, "popis": desc, "suma": round(level_amount.get(lid, 0))} for lid, desc in LEVELS],
        "bez_overenia_nazvu": round(unverified),
        "neiste": round(uncertain),
        "neiste_programy": sorted(uncertain_parts, key=lambda x: -x["neiste"])[:8],
        "zaklad": [year - 1, year - 2],
        "zdroje_riadkov": [detail_meta(year - 1)["url"], detail_meta(year - 2)["url"]],
    }
    return dict(out), report
