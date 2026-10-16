#!/usr/bin/env python3
"""Render index.html: "Kam ide stovka" – the Slovak state budget shrunk to 100 €.

Reads data/stovka.json (written by build.py) and the Žltá Stopa badge, and
writes one self-contained page (data, CSS, JS inlined; no external requests).
The interactive parts (treemap, time chart, tooltips, PNG export) are vanilla
JS in assets/app.js and assets/style.css, inlined here.

Stdlib only.
"""
from __future__ import annotations

import base64
import html
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data" / "stovka.json").read_text(encoding="utf-8"))
CSS = (ROOT / "assets" / "style.css").read_text(encoding="utf-8")
JS = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")
BADGE = "data:image/png;base64," + base64.b64encode((ROOT / "assets" / "projekt-zlta-stopa.png").read_bytes()).decode()
SITE = "rozpocet.zltastopa.sk"
REPO = "https://github.com/zltastopa/rozpocet"

# Tiles whose note changes how the number should be read get a numbered footnote
# on the tile itself (the rest show their note in the tooltip only).
FOOTNOTED = ["dochodky", "zdravie", "dlh", "vps"]


def esc(s) -> str:
    return html.escape(str(s))


def sk_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def main() -> None:
    years = sorted(DATA["years"], key=int)
    first, last = years[0], years[-1]
    tiles = {t["id"]: t for t in DATA["tiles"]}
    footnotes = "".join(
        f"<li id=\"pozn-{tid}\"><b>{esc(tiles[tid]['name'])}:</b> {esc(tiles[tid]['note'])}</li>"
        for tid in FOOTNOTED)
    residuals = "; ".join(
        f"{r['rok']}, kapitola {r['kapitola']} × COFOG {r['cofog']} ({'skutočnosť' if r['meranie'] == 'skutocnost' else 'schválený'}): "
        f"{r['rozdiel_eur']:,.2f} €".replace(",", " ").replace(".", ",")
        for r in DATA["residuals"]) or "žiadne"
    src = DATA["source"]
    est_years = [y for y in years if DATA["years"][y].get("schvaleny", {}).get("estimate")]
    real_years = [y for y in years if y not in est_years]
    last = real_years[-1] + (f" (a odhad {', '.join(est_years)})" if est_years else "")
    sk_eur = lambda v: f"{v / 1e9:.2f}".replace(".", ",") + " mld. €"
    sk_num = lambda v: f"{v:.2f}".replace(".", ",")
    # An estimated year: what is exact, what is estimated, how, and how well it worked before.
    next_year_note = ""
    for y in est_years:
        x = DATA["years"][y]["schvaleny"]["estimate"]
        bt = x.get("backtest")
        levels = "; ".join(f"{lv['popis']}: {sk_eur(lv['suma'])}" for lv in x["levels"] if lv["suma"])
        next_year_note += (
            f"<p><b>Rok {y} je odhad.</b> Celkové výdavky a príjmy sú zo zákona o štátnom rozpočte na rok {y} "
            f"(<a href=\"{esc(x['zdroj_bilancia'])}\">bilancia</a>), rozdelenie podľa funkčnej klasifikácie však "
            f"ministerstvo zatiaľ nezverejnilo. Sumy všetkých programov a vybraných podprogramov sú z prílohy č. 4 "
            f"(<a href=\"{esc(x['zdroj_programy'])}\">výdavky na programy vlády</a>, vládny návrh, ktorý NR SR schválila "
            f"s rovnakými celkovými výdavkami); každý program sme rozdelili do dlaždíc podľa toho, ako sa ten istý "
            f"program delil v schválenom rozpočte na rok {x['zaklad'][0]} (údaje po riadkoch z rozpocet.sk). "
            f"Ak MF v zozname programov uvádza názov, program sa prevezme len pri zhode názvu; pri "
            f"{sk_eur(x['bez_overenia_nazvu'])} (programy, pri ktorých zoznam MF uvádza len podprogramy, napr. "
            f"Program Slovensko či Strategický plán SPP) sa dala overiť len zhoda kódu. Použité úrovne: {levels}. "
            + (f"Spätný test: rovnakým postupom odhadnutý rok {bt['rok']} sa od skutočného rozdelenia líšil v priemere o "
               f"{sk_num(bt['priemerna_chyba'])} € zo stovky na dlaždicu (najviac {sk_num(bt['max_chyba'])} €) a o "
               f"{sk_num(bt['priemerna_chyba_polozky'])} € na položku (najviac {sk_num(bt['max_chyba_polozky'])} €). "
               "Je to chyba v minulosti, nie záruka presnosti odhadu. " if bt else "")
            + "Aj rozdelenie dlaždíc medzi kapitoly je odhadnuté. Keď ministerstvo zverejní skutočné rozdelenie, "
            "odhad sa pri najbližšej mesačnej obnove dát automaticky nahradí.</p>")
    next_year = int(years[-1]) + 1
    if str(next_year) not in DATA["years"]:
        next_year_note += (f"<p><b>Rok {next_year}:</b> zatiaľ chýba. Štátny rozpočet na rok {next_year} je schválený, "
                           f"ale rozpočet Sociálnej poisťovne na rok {next_year} a rozdelenie výdavkov štátu podľa oblastí "
                           "ešte nie sú na rozpocet.sk. Bez nich by stovka nebola celá, preto rok doplníme, až keď budú "
                           "k dispozícii (pri mesačnej obnove dát).</p>")
    payload = json.dumps({**DATA, "footnoted": FOOTNOTED, "site": SITE}, ensure_ascii=False,
                         separators=(",", ":")).replace("</", "<\\/")

    page = f"""<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kam ide stovka: štátny rozpočet SR zmenšený na 100 € | Projekt Žltá Stopa</title>
<meta name="description" content="Na čo ide každých 100 € zo štátneho rozpočtu Slovenska? Interaktívne, za roky {first} až {last}, z otvorených dát Ministerstva financií SR. Projekt Žltá Stopa.">
<meta property="og:title" content="Kam ide stovka zo štátneho rozpočtu | Projekt Žltá Stopa">
<meta property="og:description" content="Štátny rozpočet Slovenska zmenšený na 100 €. Školstvo, dávky, dôchodky, dlh, obrana… za roky {first} až {last}.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://{SITE}/">
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brandbar">
    <h1>Kam ide stovka</h1>
    <a class="badge" href="https://www.zltastopa.sk" target="_blank" rel="noopener" aria-label="Projekt Žltá Stopa">
      <img src="{BADGE}" alt="Projekt Žltá Stopa" width="118" height="38">
    </a>
  </div>
  <p class="tagline">Štátny rozpočet a Sociálna poisťovňa zmenšené na 100&nbsp;€</p>
  <p class="sub">Keby štát minul namiesto miliárd len jednu stovku, koľko by išlo na dôchodky, školy,
    dávky, armádu či úroky z dlhu? Každá dlaždica predstavuje podiel na výdavkoch, za roky {first} až {last}.
    Keď na dlaždicu prejdeš kurzorom alebo na ňu ťukneš, uvidíš, z čoho sa skladá a kto ju platí.</p>
  <p class="scope"><b>Čo je v stovke:</b> štátny rozpočet (súčet kapitol zo zákona o štátnom rozpočte) a
    Sociálna poisťovňa, ktorá na Slovensku vypláca dôchodky a ďalšie dávky z odvodov. V Česku sú dôchodky
    priamo v štátnom rozpočte, u nás ich bez Sociálnej poisťovne nevidno. Peniaze, ktoré štát Sociálnej
    poisťovni posiela, počítame len raz, tam, kde ich vyplatí. <b>Mimo stovky</b> sú zdravotné poisťovne
    (ako v Česku), obce a kraje. Je to rozdelenie výdavkov, nie toho, kam idú dane jedného človeka.</p>
</header>

<div class="kpis" id="kpis" aria-live="polite"></div>

<section class="main-chart">
  <div class="controls">
    <div class="seg" role="radiogroup" aria-label="Typ údajov">
      <button type="button" role="radio" data-measure="schvaleny">Schválený rozpočet</button>
      <button type="button" role="radio" data-measure="skutocnost">Skutočnosť</button>
    </div>
    <div class="years" id="years" role="radiogroup" aria-label="Rok"></div>
  </div>
  <h2 class="ctitle" id="ctitle"></h2>
  <p class="csub" id="csub"></p>
  <div class="tm" id="tm"></div>
  <div class="legend" id="legend"></div>
  <p class="small-tiles" id="small"></p>
  <p class="event" id="event" hidden></p>
  <ol class="foot" id="foot">{footnotes}</ol>
  <div class="chart-tools" data-chart="tm"><button class="ct" data-act="copy" type="button">Kopírovať obrázok</button><button class="ct" data-act="download" type="button">Stiahnuť PNG</button></div>
  <details class="tablebox"><summary>Tabuľka hodnôt</summary><div id="table"></div></details>
</section>

<section>
  <h2>Stovka v čase</h2>
  <p class="desc">Každý stĺpec je jeden rok rozdelený na 100&nbsp;€. Všetky stĺpce majú rovnakú výšku,
    ukazujú teda <b>podiely</b>, nie rast výdavkov (ten je v popise pod rokom). Klikni na stĺpec a hore sa zobrazí
    daný rok. V schválených rozpočtoch 2020 až 2023 je vidno veľký pás „Financie VPS vrátane rezerv“:
    peniaze, ktoré sa počas roka presunuli na ministerstvá.</p>
  <div class="tc-scroll"><div id="tc"></div></div>
  <div class="chart-tools" data-chart="tc"><button class="ct" data-act="copy" type="button">Kopírovať obrázok</button><button class="ct" data-act="download" type="button">Stiahnuť PNG</button></div>
</section>

<footer>
  <h2>Metodika a zdroje</h2>
  <p><b>Zdroj:</b> {esc(src['name'])}. Výdavky každej kapitoly štátneho rozpočtu podľa funkčnej
    klasifikácie (COFOG) z verejného Open Data API (<code>{esc(src['fnc'])}</code>); výdavky Sociálnej
    poisťovne podľa ekonomickej klasifikácie a pre vybrané položky štátu aj prienik s ekonomickou
    klasifikáciou (<code>…/polozkyRozpocetuVSOrg/…</code>), ktorý používa samotný portál rozpocet.sk.
    Stiahnuté {sk_date(src['retrieved_from'])} až {sk_date(src['retrieved_to'])}.</p>
  <p><b>Hranica:</b> stovka = výdavky štátneho rozpočtu (súčet kapitol, pre rok 2026 presne
    32&nbsp;899&nbsp;667&nbsp;683&nbsp;€ ako v zákone č.&nbsp;303/2025 Z.&nbsp;z.) + výdavky Sociálnej poisťovne
    − transfer zo štátneho rozpočtu do Sociálnej poisťovne (Všeobecná pokladničná správa, položka 641003;
    v roku 2026 2,34 mld.&nbsp;€, rovnako ako príjem Sociálnej poisťovne „transfer zo ŠR“) − presuny medzi
    vlastnými fondmi Sociálnej poisťovne (jej položka 641003, v schválených rozpočtoch vždy nula).
    Pri roku 2023 sa výdavky Sociálnej poisťovne po tomto odpočte (11,92 mld.&nbsp;€) líšia od jej vlastnej
    Správy o hospodárení (11,95 mld.&nbsp;€) o 34 mil.&nbsp;€, ktoré nevieme vysvetliť; je to približná kontrola,
    nie úplné zosúladenie. Odvody, ktoré štát platí ako zamestnávateľ, sa neodpočítavajú (podobne ako v
    európskej metodike, kde nejde o transfer). Všetky kapitoly a roky sú skontrolované, či neposielajú do
    Sociálnej poisťovne ďalšie transfery; päť drobných jednorazových prípadov (spolu menej ako 0,3 mil.&nbsp;€)
    nemá v dátach uvedeného príjemcu a ponechávame ich ako výdavok štátu. Súhrn „Štátny rozpočet“ z API
    nepoužívame, lebo pridáva aj účty ako Štátny dlh a niektoré peniaze počíta dvakrát (raz ako transfer z
    kapitoly, raz ako výdavok príjemcu). <b>Schválený rozpočet</b> je rozpočet podľa zákona o štátnom rozpočte
    vrátane jeho prípadných noviel počas roka (napríklad v roku 2020 sa výdavky novelou zvýšili z
    18,56 na 26,32 mld.&nbsp;€), tak ako ho vedie ministerstvo. <b>Skutočnosť</b> je skutočné čerpanie;
    konečná je po schválení štátneho záverečného účtu (naposledy za rok {DATA['final_account_through']}),
    za neskoršie uzavreté roky je označená ako predbežná a za bežný rok sa nezobrazuje, lebo je neúplná.
    Sumy pred rokom 2009 sú prepočítané z korún kurzom 30,1260&nbsp;Sk/€, tak ako ich zverejňuje ministerstvo.</p>
  <p><b>Dlaždice:</b> každé euro je priradené práve raz, podľa pravidiel v poradí: (1) platby
    Ministerstva zdravotníctva za poistencov štátu (ekonomická položka 642031) idú do Zdravotníctva,
    hoci ich MF od roku 2013 vedie v sociálnom zabezpečení; odvod do rozpočtu EÚ (649005) zo Všeobecnej
    pokladničnej správy má vlastnú dlaždicu; finančné a rozpočtové záležitosti VPS (vrátane rezerv) tiež;
    (2) všetok výskum a vývoj ide do Vedy a výskumu; (3) zvyšok štátu podľa skupín COFOG. Sociálna
    poisťovňa podľa ekonomickej klasifikácie (jej rozdelenie podľa COFOG v schválených rozpočtoch 2006 až
    2008 chýba): dôchodky zo starobného a invalidného poistenia (vrátane pozostalostných) do Dôchodkov,
    nemocenské, materské, úrazové dávky, dávka v nezamestnanosti a správa poisťovne do Dávok.
    Skript skontroluje, že súčet dlaždíc sa pre každý rok a typ údajov zhoduje na euro so zverejnenými
    celkami (štát + Sociálna poisťovňa − transfery medzi nimi); inak dáta nezverejní. Drobné rozdiely medzi dvoma
    zdrojmi MF pri rozdelení položiek: {esc(residuals)} (zostávajú v pôvodnej dlaždici).</p>
  {next_year_note}
  <p><b>Dáta na stiahnutie:</b> <a href="data/stovka.json">stovka.json</a> (to, čo vidíš na stránke),
    <a href="data/kapitola_fnc.csv">kapitola_fnc.csv</a> (každá kapitola × COFOG × rok s priradenou dlaždicou).
    Kód: <a href="{REPO}" target="_blank" rel="noopener">github.com/zltastopa/rozpocet</a>.
    Inšpirácia: <a href="https://www.novinky.cz/clanek/ekonomika-statni-rozpocet-v-tisicikorune-pulka-jde-na-duchody-davky-a-uroky-z-dluhu-40597265" target="_blank" rel="noopener">Novinky.cz</a>.
    Vygenerované {sk_date(DATA['generated'])}.</p>
  <a class="parent-link" href="https://www.zltastopa.sk" target="_blank" rel="noopener">Projekt Žltá Stopa ↗</a>
</footer>
</div>
<div class="tip" id="tip" role="tooltip" hidden></div>
<script>window.STOVKA = {payload};</script>
<script>
{JS}
</script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote index.html ({len(page)} bytes)")


if __name__ == "__main__":
    main()
