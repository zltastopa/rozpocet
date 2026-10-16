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
    # The next year's budget appears only once MF publishes its COFOG split; say so
    # only while it is missing, so the note disappears by itself after a refresh.
    next_year = int(last) + 1
    next_year_note = "" if str(next_year) in DATA["years"] else (
        f"<p><b>Rok {next_year}:</b> rozdelenie rozpočtu na rok {next_year} podľa funkčnej klasifikácie "
        "ministerstvo na rozpocet.sk zatiaľ nezverejnilo"
        + (" (parlament rozpočet schválil 14. 10. 2026, prílohy zákona však toto rozdelenie neobsahujú)"
           if next_year == 2027 else "")
        + ". Doplní sa automaticky pri najbližšej mesačnej obnove dát, keď bude k dispozícii.</p>")
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
  <p class="tagline">Štátny rozpočet Slovenska zmenšený na 100&nbsp;€</p>
  <p class="sub">Keby štát z rozpočtu minul namiesto miliárd len jednu stovku, koľko by išlo na školy,
    dávky, dôchodky, armádu či úroky z dlhu? Každá dlaždica predstavuje podiel na výdavkoch štátneho
    rozpočtu, za roky {first} až {last}. Keď na dlaždicu prejdeš kurzorom alebo na ňu ťukneš, uvidíš,
    z čoho sa skladá a z ktorých rozpočtových kapitol sa financuje.</p>
  <p class="scope"><b>Čo sa počíta:</b> štátny rozpočet, teda súčet kapitol zo zákona o štátnom rozpočte,
    vrátane transferov, ktoré štát posiela Sociálnej poisťovni a zdravotným poisťovniam. Nepočítajú sa
    dôchodky a zdravotná starostlivosť, ktoré tieto inštitúcie platia z odvodov, ani rozpočty obcí a krajov.
    Je to rozdelenie výdavkov štátu, nie toho, kam idú dane jedného človeka.</p>
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
    klasifikácie (COFOG) z verejného Open Data API (<code>{esc(src['fnc'])}</code>) a pre vybrané
    položky aj prienik s ekonomickou klasifikáciou (<code>…/polozkyRozpocetuVSOrg/…</code>), ktorý
    používa samotný portál rozpocet.sk. Stiahnuté {sk_date(src['retrieved_from'])} až {sk_date(src['retrieved_to'])}.</p>
  <p><b>Hranica:</b> štátny rozpočet = súčet kapitol (pre rok 2026 presne 32&nbsp;899&nbsp;667&nbsp;683&nbsp;€
    ako v zákone č.&nbsp;303/2025 Z.&nbsp;z.). Nepoužívame súhrn „Štátny rozpočet“ z API, ktorý
    pridáva aj účty ako Štátny dlh a tým niektoré peniaze počíta dvakrát (raz ako transfer z kapitoly,
    raz ako výdavok príjemcu). <b>Schválený rozpočet</b> je rozpočet podľa zákona o štátnom rozpočte
    vrátane jeho prípadných noviel počas roka (napríklad v roku 2020 sa výdavky novelou zvýšili z
    18,56 na 26,32 mld.&nbsp;€), tak ako ho vedie ministerstvo. <b>Skutočnosť</b> je skutočné čerpanie;
    konečná je po schválení štátneho záverečného účtu (naposledy za rok {DATA['final_account_through']}),
    za neskoršie uzavreté roky je označená ako predbežná a za bežný rok sa nezobrazuje, lebo je neúplná.
    Sumy pred rokom 2009 sú prepočítané z korún kurzom 30,1260&nbsp;Sk/€, tak ako ich zverejňuje ministerstvo.</p>
  <p><b>Dlaždice:</b> každé euro je priradené práve raz, podľa pravidiel v poradí: (1) platby
    Ministerstva zdravotníctva za poistencov štátu (ekonomická položka 642031) idú do Zdravotníctva,
    hoci ich MF od roku 2013 vedie v sociálnom zabezpečení; odvod do rozpočtu EÚ (649005) a transfer
    Sociálnej poisťovni (641003) zo Všeobecnej pokladničnej správy majú vlastné dlaždice; finančné
    a rozpočtové záležitosti VPS (vrátane rezerv) tiež; (2) všetok výskum a vývoj ide do Vedy a výskumu;
    (3) zvyšok podľa skupín COFOG. Skript skontroluje, že súčet dlaždíc sa pre každý rok a typ údajov
    zhoduje so zverejneným celkom na euro presne; inak dáta nezverejní. Drobné rozdiely medzi dvoma
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
