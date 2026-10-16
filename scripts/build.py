#!/usr/bin/env python3
"""Turn cached rozpocet.sk responses into the "stovka" dataset.

Inputs (cache/, written by fetch.py):
  series.json                 published state-budget revenue & expenditure per year
  {rok}/kapitoly.json         kapitoly of the state budget in that year
  {rok}/fnc-{kap}.json        kapitola expenditure by COFOG (all levels)
  {rok}/ekv-{kap}-{fnc}.json  economic breakdown inside selected kapitola x COFOG cells

Outputs:
  data/kapitola_fnc.csv  auditable snapshot: one row per (rok, kapitola, COFOG
                         4-digit, EKV split) with schválený and skutočnosť in €,
                         plus the tile each row is assigned to
  data/stovka.json       per year and measure: total, revenue, tiles with
                         children and largest kapitoly; taxonomy; provenance

Boundary: the state budget as in the zákon o štátnom rozpočte = sum of kapitoly.
Every euro is assigned to exactly one tile by ordered rules: SPECIAL cells
(split by EKV item), then research codes (RND), then PREFIX_RULES.
The build fails if any year/measure does not reconcile to the published total.

Stdlib only.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import EKV_CELLS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
DATA = ROOT / "data"
RULES_VERSION = "2026-10-16"
MEASURES = {"schvaleny": "schvalene", "skutocnost": "skutocnost"}
TOLERANCE_EUR = 1.0
FIRST_SHOWN = 2006

# ---- taxonomy -------------------------------------------------------------
GROUPS = [
    {"id": "soc", "name": "Sociálne veci", "color": "#2f6fed"},
    {"id": "ludia", "name": "Služby pre ľudí", "color": "#e8692f"},
    {"id": "hosp", "name": "Hospodárstvo", "color": "#17a673"},
    {"id": "bezp", "name": "Bezpečnosť", "color": "#e3a008"},
    {"id": "stat", "name": "Štát a dlh", "color": "#d6457f"},
]

# id, group, full name, short label for the tile (None = same), footnote
TILES = [
    ("dochodky", "soc", "Dôchodky", None,
     "Väčšinu dôchodkov vypláca Sociálna poisťovňa z odvodov, mimo štátneho rozpočtu. "
     "Štátny rozpočet do nej posiela najmä transfer z Všeobecnej pokladničnej správy "
     "(program „Transfer Sociálnej poisťovni“) a platí dávky v starobe cez jednotlivé ministerstvá."),
    ("davky", "soc", "Dávky a sociálna pomoc", "Dávky",
     "Prídavky na deti, rodičovský príspevok, príspevky na kompenzáciu ťažkého zdravotného postihnutia, "
     "pomoc v hmotnej núdzi a ďalšie sociálne výdavky (COFOG 10 okrem staroby a pozostalých)."),
    ("trh", "soc", "Trh práce a zamestnanosť", "Trh práce",
     "Aktívne opatrenia na trhu práce a ďalšie výdavky všeobecnej pracovnej oblasti (COFOG 0412)."),
    ("skolstvo", "ludia", "Školstvo", None,
     "Vzdelávanie za všetky kapitoly (COFOG 09), bez výskumu a vývoja v oblasti vzdelávania."),
    ("zdravie", "ludia", "Zdravotníctvo", None,
     "Vrátane platieb za poistencov štátu, ktoré Ministerstvo zdravotníctva posiela zdravotným "
     "poisťovniam (od roku 2013 ich MF účtuje v sociálnom zabezpečení, predtým v zdravotníctve). "
     "Väčšinu zdravotnej starostlivosti platia zdravotné poisťovne z odvodov, mimo štátneho rozpočtu."),
    ("veda", "ludia", "Veda a výskum", None,
     "Základný výskum a výskum a vývoj vo všetkých oblastiach (všetky výskumné kódy COFOG)."),
    ("kultura", "ludia", "Kultúra, šport a médiá", "Kultúra a šport", None),
    ("byvanie", "ludia", "Bývanie a rozvoj obcí", "Bývanie", None),
    ("doprava", "hosp", "Doprava", None,
     "Cesty, diaľnice, železnice a ďalšia doprava (COFOG 045) za všetky kapitoly."),
    ("podo", "hosp", "Pôdohospodárstvo", None,
     "Poľnohospodárstvo, lesníctvo, rybné hospodárstvo a poľovníctvo (COFOG 042)."),
    ("priemysel", "hosp", "Priemysel, energetika a ostatné", "Priemysel a energetika",
     "Energetika (vrátane kompenzácií cien energií), podpora podnikania, cestovný ruch, "
     "komunikácie a ostatná ekonomická oblasť."),
    ("zp", "hosp", "Životné prostredie", None, None),
    ("obrana", "bezp", "Obrana", None, "COFOG 02 za všetky kapitoly, bez výskumu a vývoja."),
    ("policia", "bezp", "Polícia, hasiči a justícia", None, None),
    ("dlh", "stat", "Obsluha štátneho dlhu", None,
     "Úroky a ďalšie náklady štátneho dlhu. Od roku 2013 ich Všeobecná pokladničná správa "
     "posiela ako transfer organizácii, ktorá dlh spravuje (program „Dlhová služba“)."),
    ("eu", "stat", "Odvod do rozpočtu EÚ", "Odvod do EÚ",
     "Príspevok Slovenska do spoločného rozpočtu Európskej únie (Všeobecná pokladničná správa)."),
    ("vps", "stat", "Finančné a rozpočtové záležitosti VPS (vrátane rezerv)", "Financie VPS vrátane rezerv",
     "Finančné a rozpočtové záležitosti Všeobecnej pokladničnej správy. V schválenom rozpočte sú tu "
     "najmä rozpočtové rezervy a prostriedky, ktoré sa počas roka presúvajú na ministerstvá, preto je "
     "táto dlaždica pri skutočnom čerpaní zvyčajne oveľa menšia."),
    ("sprava", "stat", "Všeobecné verejné služby", "Verejné služby",
     "Parlament, vláda, ministerstvá, zahraničné vzťahy, štatistika, finančná správa a ďalšie "
     "všeobecné služby (COFOG 01 bez dlhu, odvodu do EÚ, výskumu a financií VPS)."),
]
TILE_IDS = [t[0] for t in TILES]

# COFOG codes for research & development (základný výskum + "Výskum a vývoj v oblasti ...")
RND = {"0140", "0150", "0240", "0350", "0550", "0650", "0750", "0850", "0970", "1080"}
RND_PREFIX = ("048",)

# Ordered COFOG prefix rules (first match wins), applied after special cells and R&D.
PREFIX_RULES = [
    ("102", "dochodky"), ("103", "dochodky"), ("10", "davky"),
    ("0412", "trh"), ("09", "skolstvo"), ("07", "zdravie"), ("08", "kultura"), ("06", "byvanie"),
    ("045", "doprava"), ("042", "podo"), ("04", "priemysel"), ("05", "zp"),
    ("02", "obrana"), ("03", "policia"),
    ("017", "dlh"), ("01", "sprava"),
]

# Special (kapitola, COFOG) cells split by EKV item: EKV code -> (tile, child label).
# EKV None = the whole cell. Evidence: kapitola x FNC x EKV cross-tab on rozpocet.sk.
SPECIAL = {
    ("21", "1090"): {"642031": ("zdravie", "Platby za poistencov štátu")},
    ("21", "0760"): {"642031": ("zdravie", "Platby za poistencov štátu")},
    ("48", "0113"): {"649005": ("eu", "Odvod do rozpočtu EÚ")},
    ("48", "1020"): {"641003": ("dochodky", "Transfer Sociálnej poisťovni")},
    ("48", "0112"): {None: ("vps", None)},  # child = EKV item name
}
assert set(SPECIAL) == set(EKV_CELLS), "SPECIAL and fetch.EKV_CELLS must list the same cells"

# Plain-language child names for COFOG groups (3-digit) where the official name is clumsy.
CHILD_NAMES = {
    "011": "Vláda, parlament, financie a zahraničie", "013": "Všeobecné služby štátu",
    "012": "Zahraničná rozvojová pomoc", "016": "Ostatné verejné služby",
    "0111": "Parlament, vláda a ústredné orgány", "0112": "Finančné a rozpočtové záležitosti",
    "0113": "Zahraničné vzťahy", "0121": "Rozvojová pomoc", "0122": "Pomoc cez medzinárodné organizácie",
    "0131": "Personálne služby štátu", "0132": "Plánovanie a štatistika", "0133": "Iné všeobecné služby",
    "0160": "Ostatné verejné služby",
    "021": "Armáda", "022": "Civilná ochrana", "023": "Zahraničná vojenská pomoc",
    "025": "Ostatná obrana",
    "031": "Polícia", "032": "Hasiči", "033": "Súdy", "034": "Väzenstvo",
    "036": "Prokuratúra, záchranné zložky a ostatné",
    "041": "Podpora podnikania a obchodu", "043": "Energetika", "044": "Ťažba a výstavba",
    "046": "Komunikácie", "047": "Cestovný ruch a iné odvetvia", "049": "Ostatná ekonomická oblasť",
    "0421": "Poľnohospodárstvo", "0422": "Lesníctvo", "0423": "Rybárstvo a poľovníctvo",
    "0451": "Cesty a diaľnice", "0452": "Vodná doprava", "0453": "Železnice",
    "0454": "Letecká doprava", "0455": "Potrubná a iná doprava",
    "051": "Odpady", "052": "Odpadové vody", "053": "Znečistenie ovzdušia a vody",
    "054": "Ochrana prírody a krajiny", "056": "Ostatné výdavky na životné prostredie",
    "061": "Rozvoj bývania", "062": "Rozvoj obcí", "063": "Zásobovanie vodou",
    "064": "Verejné osvetlenie", "066": "Ostatné bývanie a vybavenosť",
    "071": "Lieky a zdravotnícke pomôcky", "072": "Ambulantná starostlivosť",
    "073": "Nemocnice", "074": "Verejné zdravotníctvo", "076": "Ostatné zdravotníctvo",
    "081": "Šport a rekreácia", "082": "Kultúra", "083": "Vysielanie a vydavateľstvá",
    "084": "Cirkvi a náboženské spoločnosti", "086": "Ostatná kultúra a rekreácia",
    "091": "Predprimárne a primárne vzdelávanie (MŠ a 1. stupeň ZŠ)",
    "092": "Sekundárne vzdelávanie (2. stupeň ZŠ a stredné školy)",
    "093": "Pomaturitné neterciárne vzdelávanie", "094": "Terciárne vzdelávanie (vysoké školy)",
    "095": "Vzdelávanie bez určenia stupňa", "096": "Stravovanie a ubytovanie žiakov a študentov",
    "098": "Ostatné vzdelávanie",
    "101": "Zdravotné postihnutie a choroba", "102": "Staroba", "103": "Pozostalí",
    "104": "Rodina a deti", "105": "Nezamestnanosť", "106": "Bývanie (sociálne)",
    "107": "Hmotná núdza", "109": "Ostatné sociálne zabezpečenie",
    "0411": "Podpora podnikania a obchodu", "0412": "Trh práce",
    "014": "Základný výskum", "017": "Obsluha štátneho dlhu",
    "0180": "Transfery medzi úrovňami verejnej správy",
}
# tiles whose children are 4-digit codes rather than 3-digit groups
CHILD_LEVEL4 = {"doprava", "podo", "trh", "sprava"}
# tiles whose children are kapitoly (the money flows matter more than COFOG detail)
CHILD_BY_KAPITOLA = {"dochodky", "veda"}

# Readable names for economic items (EKV) that appear as children of split cells.
# The official item names are often grammatical fragments ("Štátnej rozpočtovej
# organizácii"); unknown codes fall back to "<parent category>: <item>".
EKV_NAMES = {
    "637200": "Ostatné služby", "641006": "Transfery štátnym rozpočtovým organizáciám",
    "719200": "Ostatné kapitálové výdavky", "642200": "Ostatné transfery jednotlivcom a neziskovým organizáciám",
    "642016": "Transfery na dôchodkové dávky zo starobného poistenia",
    "637038": "Nezrovnalosti a vratky prostriedkov EÚ", "637039": "Nezrovnalosti a vratky prostriedkov EÚ",
    "637025": "Nezrovnalosti", "635009": "Údržba unikátneho softvéru",
    "637024": "Vyrovnanie kurzových rozdielov", "637020": "Finančné zúčtovanie",
    "644003": "Transfery fyzickým osobám – podnikateľom", "653001": "Manipulačné poplatky (úvery a pôžičky)",
    "647001": "Úhrada majetkovej ujmy", "642031": "Platby za poistencov štátu",
}

# Execution (skutočnosť) is final once NR SR approves the štátny záverečný účet.
# NR SR approved the one for 2025 on 6 Oct 2026 (61. schôdza), see
# https://www.mfsr.sk/sk/financie/statne-vykaznictvo/klucove-dokumenty-uctovne-zavierky/statny-zaverecny-ucet-sr
# Bump this when the next one is approved; later closed years are marked provisional.
FINAL_ACCOUNT_THROUGH = 2025

# Tile x measure pairs whose year-over-year change is not a like-for-like comparison:
# the reason is shown instead of the change. In approved budgets the VPS tile is
# mostly unallocated reserves whose size is a budgeting choice (1,90 € in 2019 vs
# 31,47 € zo stovky in 2020), not spending.
NO_YOY = {
    "vps": {"schvaleny": "Medziročnú zmenu pri tejto dlaždici v schválenom rozpočte neuvádzame: "
                         "jej veľkosť určujú najmä nerozpísané rezervy, nie výdavky, a ich objem sa "
                         "medzi rokmi líši podľa spôsobu zostavenia rozpočtu."},
}

# Documented events / classification notes shown as annotations.
EVENTS = {
    2009: "Slovensko prijalo euro. Sumy za roky 2005 až 2008 sú prepočítané konverzným kurzom 30,1260 Sk/€.",
    2013: "Platby za poistencov štátu sa od roku 2013 účtujú v sociálnom zabezpečení (predtým v "
          "zdravotníctve). Tu sú v oboch prípadoch v dlaždici Zdravotníctvo, takže porovnanie platí.",
    2020: "Pandémia covid-19. Schválený rozpočet bol počas roka novelizovaný.",
}
# Years of the energy crisis: the note quotes the energy spending computed from the data.
ENERGY_YEARS = (2023, 2024)


# ---- helpers --------------------------------------------------------------
def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rnd_or_prefix(code: str) -> str:
    if code in RND or code.startswith(RND_PREFIX):
        return "veda"
    for pre, tile in PREFIX_RULES:
        if code.startswith(pre):
            return tile
    raise ValueError(f"unclassified COFOG code {code}")


def child_key(tile: str, code: str, kap_name: str) -> str:
    if tile in CHILD_BY_KAPITOLA:
        return kap_name
    key = code if tile in CHILD_LEVEL4 else code[:3]
    return CHILD_NAMES.get(key) or CHILD_NAMES.get(code[:3]) or key


def ekv_leaves(payload: list[dict]) -> list[dict]:
    parents = {x["nadurovenKod"] for x in payload}
    return [x for x in payload if x["kod"] not in parents]

def serialize_tiles(acc: dict, label: str, problems: list[str]) -> dict:
    """{tile: {"v", "children", "kap"}} -> published form with sorted children and top 3 kapitoly."""
    tiles = {}
    for tid in TILE_IDS:
        t = acc.get(tid)
        if not t or abs(t["v"]) < 0.5:
            continue
        if t["v"] < 0 or any(v < -TOLERANCE_EUR for v in t["children"].values()):
            # the treemap cannot draw negative areas; never publish them silently
            problems.append(f"{label} {tid}: negative tile or child value")
        children = sorted(((n, round(v)) for n, v in t["children"].items() if abs(v) >= 0.5), key=lambda c: -c[1])
        kap = sorted(((n, round(v)) for n, v in t["kap"].items() if abs(v) >= 0.5), key=lambda c: -c[1])[:3]
        tiles[tid] = {"v": round(t["v"]), "c": children, "k": kap}
    return tiles


def add_estimates(out_years: dict, problems: list[str]) -> list[int]:
    """Add a program-based estimate (estimate.py) for every year that has a parsed bill
    annex but no published COFOG data yet, with a backtest on the year before."""
    from estimate import estimate  # local: estimate.py is only needed when an annex exists

    def kap_names(year: int) -> dict[str, str]:
        names = {}
        for p in (CACHE / str(year)).glob("fnc-*.json"):
            payload = load(p)["data"].get("payload") or []
            if payload:
                names[p.stem.removeprefix("fnc-")] = payload[0]["nazovOrganizacie"].strip()
        return names

    def run(year: int) -> tuple[dict, dict]:
        names = kap_names(year - 1)

        def classify(kap: str, fnc: str, eko: str) -> tuple[str, str]:
            fnc = fnc[:4]   # row-level data uses 5-digit subclasses; published years use 4 digits
            special = SPECIAL.get((kap, fnc))
            hit = special and (special.get(eko) or special.get(None))
            if hit:
                tile, child = hit
                return tile, child or EKV_NAMES.get(eko) or f"Ekonomická položka {eko}"
            tile = rnd_or_prefix(fnc)
            return tile, child_key(tile, fnc, names.get(kap, kap))

        cells, report = estimate(year, classify, names)
        acc: dict = defaultdict(lambda: {"v": 0.0, "children": defaultdict(float), "kap": defaultdict(float)})
        for (tile, child, kap), v in cells.items():
            acc[tile]["v"] += v
            acc[tile]["children"][child] += v
            acc[tile]["kap"][kap] += v
        return serialize_tiles(acc, f"{year} odhad", problems), report

    def shares(tiles: dict, total: float) -> dict:
        return {tid: 100 * t["v"] / total for tid, t in tiles.items()}

    done = []
    for path in sorted(DATA.glob("navrh_*_programy.csv")):
        year = int(path.stem.split("_")[1])
        if str(year) in out_years:
            continue  # published data exists: no estimate (older annexes only serve backtests)
        with (DATA / f"navrh_{year}_suhrn.csv").open(encoding="utf-8") as f:
            meta = next(csv.DictReader(f))
        tiles, report = run(year)
        total = sum(t["v"] for t in tiles.values())
        if abs(total - int(meta["vydavky"])) > len(tiles):   # rounding of each tile to whole euros
            problems.append(f"{year} odhad: tiles {total} != law total {meta['vydavky']}")
        report.update({"zdroj_programy": meta["zdroj_programy"], "zdroj_bilancia": meta["zdroj_bilancia"]})

        # backtest: estimate the previous year the same way and compare with its real split
        prev = out_years.get(str(year - 1), {}).get("schvaleny")
        if prev and (DATA / f"navrh_{year - 1}_programy.csv").exists():
            bt_tiles, _ = run(year - 1)
            bt_total = sum(t["v"] for t in bt_tiles.values())
            est, real = shares(bt_tiles, bt_total), shares(prev["tiles"], prev["total"])
            err = {tid: abs(est.get(tid, 0) - real.get(tid, 0)) for tid in set(est) | set(real)}
            worst = max(err, key=err.get)
            child_err = []
            for tid, t in prev["tiles"].items():
                rc = {n: 100 * v / prev["total"] for n, v in t["c"]}
                ec = {n: 100 * v / bt_total for n, v in bt_tiles.get(tid, {"c": []})["c"]}
                child_err += [abs(ec.get(n, 0) - rc.get(n, 0)) for n in set(rc) | set(ec)]
            report["backtest"] = {
                "rok": year - 1,
                "max_chyba": round(max(err.values()), 2), "max_dlazdica": worst,
                "priemerna_chyba": round(sum(err.values()) / len(err), 2),
                "max_chyba_polozky": round(max(child_err), 2),
                "priemerna_chyba_polozky": round(sum(child_err) / len(child_err), 2),
            }
        out_years[str(year)] = {"schvaleny": {"total": int(meta["vydavky"]), "revenue": int(meta["prijmy"]),
                                              "tiles": tiles, "estimate": report}}
        done.append(year)
    return done



def main() -> None:
    series = load(CACHE / "series.json")
    # 2005 has no execution data and predates the series MF charts itself,
    # so the dataset starts in 2006.
    years = [y for y in sorted(int(y) for y in series["data"]["payload"]) if y >= FIRST_SHOWN]
    this_year = date.today().year

    rows: list[dict] = []          # snapshot rows
    problems: list[str] = []
    residuals: list[dict] = []     # published small cross-tab differences
    out_years: dict[str, dict] = {}
    retrieved: list[str] = [series["retrieved_at"]]

    for y in years:
        retrieved.append(load(CACHE / str(y) / "kapitoly.json")["retrieved_at"])
        pub = series["data"]["payload"][str(y)]
        revenue_rec, spend_rec = pub[0]["hodnoty"], pub[1]["hodnoty"]

        # acc[measure][tile] -> {"v": float, "children": {name: v}, "kap": {name: v}}
        acc = {m: defaultdict(lambda: {"v": 0.0, "children": defaultdict(float), "kap": defaultdict(float)})
               for m in MEASURES}
        have = {m: False for m in MEASURES}

        def add(m: str, tile: str, child: str, kap_name: str, v: float) -> None:
            t = acc[m][tile]
            t["v"] += v
            t["children"][child] += v
            t["kap"][kap_name] += v

        for path in sorted((CACHE / str(y)).glob("fnc-*.json")):
            k = path.stem.removeprefix("fnc-")
            rec = load(path)
            retrieved.append(rec["retrieved_at"])
            payload = rec["data"].get("payload") or []
            if not payload:
                continue  # kapitola did not exist in this year
            kap_name = payload[0]["nazovOrganizacie"].strip()
            leaves = [x for x in payload if len(x["kodKlasifikacie"]) == 4]
            spolu = next((x for x in payload if x["kodKlasifikacie"] == "Spolu"), None)
            for m, field in MEASURES.items():
                lv = sum(x[field] or 0 for x in leaves)
                sv = (spolu or {}).get(field) or 0
                if abs(lv - sv) > TOLERANCE_EUR:
                    problems.append(f"{y} kap {k} {m}: leaves {lv:.2f} != Spolu {sv:.2f}")
                if any(x[field] is not None for x in leaves):
                    have[m] = True

            for x in leaves:
                code = x["kodKlasifikacie"]
                vals = {m: (x[f] or 0.0) for m, f in MEASURES.items()}
                special = SPECIAL.get((k, code))
                if special is None:
                    tile = rnd_or_prefix(code)
                    child = child_key(tile, code, kap_name)
                    for m, v in vals.items():
                        if v:
                            add(m, tile, child, kap_name, v)
                    rows.append({"rok": y, "kapitola": k, "nazov_kapitoly": kap_name, "cofog": code,
                                 "ekv": "", "dlazdica": tile, **{m: round(v, 2) for m, v in vals.items()}})
                    continue

                # split the cell by EKV items using the true kapitola x FNC x EKV cross-tab
                erec = load(CACHE / str(y) / f"ekv-{k}-{code}.json")
                retrieved.append(erec["retrieved_at"])
                eleaves = ekv_leaves(erec["data"].get("payload") or [])
                for m in MEASURES:
                    es = sum(e["hodnoty"].get(m.upper()) or 0.0 for e in eleaves)
                    diff = vals[m] - es
                    if abs(diff) <= TOLERANCE_EUR:
                        continue
                    # The cross-tab and the FNC endpoint occasionally differ by a few
                    # hundred euros (pre-euro conversion rounding). Totals stay exact
                    # because the difference remains in the cell's default tile; we
                    # only publish it. Anything larger than 0.1 % of the cell fails.
                    if abs(diff) > 0.001 * max(abs(vals[m]), 1.0):
                        problems.append(f"{y} kap {k} x {code} {m}: EKV items {es:.2f} != cell {vals[m]:.2f}")
                    residuals.append({"rok": y, "kapitola": k, "cofog": code, "meranie": m,
                                      "rozdiel_eur": round(diff, 2)})
                rest = dict(vals)
                for e in eleaves:
                    ev = {m: (e["hodnoty"].get(m.upper()) or 0.0) for m in MEASURES}
                    hit = special.get(e["kod"]) or special.get(None)
                    if hit is None:
                        continue
                    tile, child = hit
                    if not child:
                        parent = next((p["nazov"].strip() for p in erec["data"]["payload"]
                                       if p["kod"] == e["nadurovenKod"]), "")
                        name = e["nazov"].strip()
                        child = EKV_NAMES.get(e["kod"]) or (f"{parent}: {name[0].lower()}{name[1:]}" if parent else name)
                    for m, v in ev.items():
                        if v:
                            add(m, tile, child, kap_name, v)
                        rest[m] -= v
                    rows.append({"rok": y, "kapitola": k, "nazov_kapitoly": kap_name, "cofog": code,
                                 "ekv": e["kod"], "dlazdica": tile, **{m: round(v, 2) for m, v in ev.items()}})
                # remainder of the cell (EKV items not singled out) follows the normal rules
                tile = rnd_or_prefix(code)
                if any(abs(v) > TOLERANCE_EUR for v in rest.values()):
                    child = child_key(tile, code, kap_name)
                    for m, v in rest.items():
                        if abs(v) > TOLERANCE_EUR:
                            add(m, tile, child, kap_name, v)
                    rows.append({"rok": y, "kapitola": k, "nazov_kapitoly": kap_name, "cofog": code,
                                 "ekv": "zvyšok", "dlazdica": tile, **{m: round(v, 2) for m, v in rest.items()}})

        yd: dict[str, dict] = {}
        for m in MEASURES:
            if not have[m]:
                continue
            if m == "skutocnost" and y >= this_year:
                continue  # current-year execution is partial
            total = sum(t["v"] for t in acc[m].values())
            published = spend_rec["SCHVALENY" if m == "schvaleny" else "SKUTOCNOST"] or 0
            if abs(total - published) > TOLERANCE_EUR:
                problems.append(f"{y} {m}: tiles {total:.2f} != published total {published:.2f}")
            rev = revenue_rec["SCHVALENY" if m == "schvaleny" else "SKUTOCNOST"]
            tiles = serialize_tiles(acc[m], f"{y} {m}", problems)
            entry = {"total": round(total), "revenue": round(rev) if rev is not None else None, "tiles": tiles}
            if m == "skutocnost" and y > FINAL_ACCOUNT_THROUGH:
                entry["provisional"] = True
            yd[m] = entry
        if yd:
            out_years[str(y)] = yd

    estimates = add_estimates(out_years, problems)

    if problems:
        for p in problems:
            print("error:", p, file=sys.stderr)
        sys.exit(f"{len(problems)} reconciliation problem(s); refusing to write data/")

    DATA.mkdir(exist_ok=True)
    with (DATA / "kapitola_fnc.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rok", "kapitola", "nazov_kapitoly", "cofog", "ekv",
                                          "dlazdica", "schvaleny", "skutocnost"])
        w.writeheader()
        w.writerows(rows)

    events = {str(k): v for k, v in EVENTS.items()}
    for y in ENERGY_YEARS:
        yd = out_years.get(str(y), {})
        m = "skutocnost" if "skutocnost" in yd else "schvaleny"
        energy = sum(v for n, v in yd.get(m, {}).get("tiles", {}).get("priemysel", {}).get("c", []) if n == "Energetika")
        if energy:
            label = "skutočné čerpanie" if m == "skutocnost" else "schválený rozpočet"
            amount = f"{energy / 1e9:.2f}".replace(".", ",")
            events[str(y)] = (f"Energetická kríza: výdavky na energetiku (COFOG 043, v dlaždici Priemysel, "
                              f"energetika a ostatné) dosiahli {amount} mld. € ({label}).")

    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules_version": RULES_VERSION,
        "unit": "EUR",
        "boundary": "štátny rozpočet = súčet kapitol (zákon o štátnom rozpočte)",
        "source": {
            "name": "Ministerstvo financií SR, rozpocet.sk (Rozpočtový informačný systém), licencia CC0",
            "fnc": "https://www.rozpocet.sk/api/vs/rozpocet/{kapitola}/prehlad-klasifikacii/vydavky/fnc/{rok}",
            "ekv": "https://www.rozpocet.sk/rest/api/rozpocet/polozkyRozpocetuVSOrg/SK/{kapitola}/{rok}/VS/false/EKV?EKV=SpoluV&FNC={fnc}&DRH=21",
            "totals": "https://www.rozpocet.sk/rest/api/rozpocet/rozpoctyVSOrg/0/{od}/{do}/0/true",
            "retrieved_from": min(retrieved), "retrieved_to": max(retrieved),
        },
        "groups": GROUPS,
        "tiles": [{"id": t[0], "group": t[1], "name": t[2], "short": t[3] or t[2], "note": t[4],
                   "no_yoy": NO_YOY.get(t[0], {})} for t in TILES],
        "events": events,
        "final_account_through": FINAL_ACCOUNT_THROUGH,
        "residuals": residuals,
        "years": out_years,
    }
    (DATA / "stovka.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote data/stovka.json ({len(out_years)} years) and data/kapitola_fnc.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
