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

Raw JSON responses go to cache/ (gitignored). The script is idempotent:
cached responses are reused, so a re-run only downloads what is missing.
Pass --refresh to re-download the most recent two years (whose numbers still
change as the budget is executed and the closing account is published).

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
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
WEB_API = "https://www.rozpocet.sk/rest/api/"
OPEN_API = "https://www.rozpocet.sk/api/vs/"
FIRST_YEAR = 2005
UA = "zltastopa-rozpocet/1.0 (+https://github.com/zltastopa/rozpocet)"


def get_json(url: str, tries: int = 4) -> dict:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 410):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed after {tries} tries: {url}: {last}")


def cached(path: Path, url: str, refresh: bool) -> dict:
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = get_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def last_year() -> int:
    """Latest year present in the approved state-budget series."""
    today = date.today().year
    series = get_json(f"{WEB_API}rozpocet/rozpoctyVSOrg/0/{FIRST_YEAR}/{today + 1}/0/true")["payload"]
    return max(int(y) for y in series)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download the two most recent years")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    end = last_year()
    years = list(range(FIRST_YEAR, end + 1))
    fresh = {end, end - 1} if args.refresh else set()

    # whole-state-budget totals (revenue, expenditure) per year, as published
    cached(CACHE / "series.json",
           f"{WEB_API}rozpocet/rozpoctyVSOrg/0/{FIRST_YEAR}/{end}/0/true", refresh=True)

    jobs: list[tuple[int, str]] = []
    for y in years:
        chapters = cached(CACHE / str(y) / "kapitoly.json",
                          f"{WEB_API}rozpocet/rozpoctyPodorganizaciiVSOrg/0/{y}/0", y in fresh)
        jobs += [(y, k) for k in sorted(chapters["payload"])]
    print(f"{len(years)} years ({years[0]}-{years[-1]}), {len(jobs)} kapitola-years", file=sys.stderr)

    def one(job: tuple[int, str]) -> str | None:
        y, k = job
        url = f"{OPEN_API}rozpocet/{urllib.parse.quote(k)}/prehlad-klasifikacii/vydavky/fnc/{y}"
        try:
            cached(CACHE / str(y) / f"fnc-{k}.json", url, y in fresh)
        except urllib.error.HTTPError as e:
            return f"{y} {k}: HTTP {e.code}"
        return None

    with ThreadPoolExecutor(args.workers) as ex:
        problems = [p for p in ex.map(one, jobs) if p]
    for p in problems:
        print("warning:", p, file=sys.stderr)
    print(f"done, {len(jobs) - len(problems)} ok, {len(problems)} missing", file=sys.stderr)


if __name__ == "__main__":
    main()
