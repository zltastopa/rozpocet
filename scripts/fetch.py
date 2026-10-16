#!/usr/bin/env python3
"""Download state-budget expenditures by kapitola x COFOG from rozpocet.sk.

For every year we ask the Ministry of Finance's budget information system
(rozpocet.sk, CC0) for:

1. the list of kapitoly (budget chapters) of the state budget in that year,
   together with their total revenue/expenditure (internal web API used by
   rozpocet.sk itself, the only place with a per-year chapter list), and
2. for every kapitola, its expenditures by functional classification
   (COFOG / funkčná klasifikácia) from the documented Open Data API:
   /api/vs/rozpocet/{kapitola}/prehlad-klasifikacii/vydavky/fnc/{rok}
3. for a few (kapitola, COFOG) cells listed in EKV_CELLS, the economic
   classification breakdown inside that cell (kapitola x FNC x EKV cross-tab).

Raw JSON responses go to cache/ (gitignored), each wrapped with its source URL
and retrieval time. The script is idempotent: cached responses are reused, so
a re-run only downloads what is missing; --force re-downloads everything (the
monthly CI refresh starts from an empty cache, so older revisions are picked
up too). Exits non-zero if any response could not be fetched.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
WEB_API = "https://www.rozpocet.sk/rest/api/"
OPEN_API = "https://www.rozpocet.sk/api/vs/"
FIRST_YEAR = 2005
UA = "zltastopa-rozpocet/1.0 (+https://github.com/zltastopa/rozpocet)"

# (kapitola, COFOG) cells whose economic-classification (EKV) breakdown we need,
# because build.py splits them by EKV item (e.g. MZ x 1090 = platby za poistencov
# štátu, VPS x 0113 = odvod do rozpočtu EÚ). Fetched from the true kapitola x FNC x
# EKV cross-tab that rozpocet.sk itself uses, so splits are the real intersection.
EKV_CELLS = [("21", "1090"), ("21", "0760"), ("48", "0113"), ("48", "1020"), ("48", "0112")]


def get_json(url: str, tries: int = 5) -> dict:
    """GET JSON with retries. rozpocet.sk occasionally answers 404 for data that
    exists (seen for kapitola 58 / 2024), so 404 is retried too before giving up."""
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 410):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}: {last}")


def get_text(url: str, tries: int = 5) -> str:
    """GET a CSV body; MF answers 200 with a plain-text message when a year is missing."""
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=600) as r:
                body = r.read().decode("utf-8").lstrip("\ufeff")
            header = body.split("\n", 1)[0].lower()
            if "rok" not in header or "," not in header:   # e.g. "… pre rok 2027 nebol nájdený."
                raise RuntimeError(f"not a CSV: {body[:80]!r}")
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}: {last}")


def cached(path: Path, url: str, force: bool = False) -> dict:
    """Return the API payload for `url`, cached at `path` with its provenance
    (source URL and retrieval time) so build.py can cite exactly what it used."""
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))["data"]
    data = get_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "data": data}
    path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return data


def last_year() -> int:
    """Latest year present in the approved state-budget series."""
    today = date.today().year
    series = get_json(f"{WEB_API}rozpocet/rozpoctyVSOrg/0/{FIRST_YEAR}/{today + 1}/0/true")["payload"]
    return max(int(y) for y in series)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="ignore cache and re-download everything")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    end = last_year()
    years = list(range(FIRST_YEAR, end + 1))

    # whole-state-budget totals (revenue, expenditure) per year, as published
    cached(CACHE / "series.json",
           f"{WEB_API}rozpocet/rozpoctyVSOrg/0/{FIRST_YEAR}/{end}/0/true", force=True)

    # The per-year chapter list can omit a kapitola that still has expenditure
    # (e.g. kapitola 55 in 2011 with 469 897 € actual spending), so every year is
    # queried for the union of all kapitola codes seen in any year plus the
    # current code list; empty answers are cached too and ignored by build.py.
    codes: set[str] = {o["kodOrganizacie"] for o in
                       get_json(f"{OPEN_API}ciselnik/organizacie/0")["payload"] if o["kodOrganizacie"].isdigit()}
    for y in years:
        chapters = cached(CACHE / str(y) / "kapitoly.json",
                          f"{WEB_API}rozpocet/rozpoctyPodorganizaciiVSOrg/0/{y}/0", args.force)
        codes |= set(chapters["payload"])
    jobs = [(y, k) for y in years for k in sorted(codes)]
    print(f"{len(years)} years ({years[0]}-{years[-1]}), {len(codes)} kapitola codes, "
          f"{len(jobs)} requests", file=sys.stderr)

    def fnc(job: tuple[int, str]) -> str | None:
        y, k = job
        url = f"{OPEN_API}rozpocet/{urllib.parse.quote(k)}/prehlad-klasifikacii/vydavky/fnc/{y}"
        try:
            cached(CACHE / str(y) / f"fnc-{k}.json", url, args.force)
        except (urllib.error.HTTPError, RuntimeError) as e:
            return f"{y} kapitola {k}: {e}"
        return None

    def ekv(job: tuple[int, str, str]) -> str | None:
        y, k, f = job
        url = (f"{WEB_API}rozpocet/polozkyRozpocetuVSOrg/SK/{k}/{y}/VS/false/EKV"
               f"?EKV=SpoluV&FNC={f}&DRH=21")
        try:
            cached(CACHE / str(y) / f"ekv-{k}-{f}.json", url, args.force)
        except (urllib.error.HTTPError, RuntimeError) as e:
            return f"{y} kapitola {k} x {f}: {e}"
        return None

    with ThreadPoolExecutor(args.workers) as ex:
        problems = [p for p in ex.map(fnc, jobs) if p]
        have = set(jobs)
        ekv_jobs = [(y, k, f) for y in years for k, f in EKV_CELLS if (y, k) in have]
        problems += [p for p in ex.map(ekv, ekv_jobs) if p]

    # Row-level approved budgets (kapitola x program x COFOG x EKV) and program names
    # for the two years before every year with a parsed bill annex
    # (data/navrh_{rok}_programy.csv); build.py estimates that year's COFOG split from them.
    detail_years = sorted({y - d for p in (ROOT / "data").glob("navrh_*_programy.csv")
                           for y in [int(p.stem.split("_")[1])] for d in (1, 2, 3)})
    for y in detail_years:
        for name, url in ((f"schvaleny-{y}.csv", f"{OPEN_API}schvaleny?rok={y}"),
                          (f"programy-{y}.csv", f"{OPEN_API}programy/{y}?format=csv")):
            path = CACHE / "detail" / name
            if path.exists() and not args.force:
                continue
            try:
                body = get_text(url)
            except (urllib.error.HTTPError, RuntimeError) as e:
                problems.append(f"{name}: {e}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            path.with_suffix(".json").write_text(json.dumps(
                {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")

    for p in problems:
        print("error:", p, file=sys.stderr)
    total = len(jobs) + len(ekv_jobs) + 2 * len(detail_years)
    print(f"done, {total - len(problems)}/{total} responses cached", file=sys.stderr)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
