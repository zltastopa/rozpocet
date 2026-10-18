#!/usr/bin/env python3
"""Render index.html: "Na čo míňa štát?" – the Slovak state budget shrunk to 100 €.

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
    sk_num = lambda v: f"{v:.2f}".replace(".", ",")
    # An estimated year: short bullets for the collapsed methodology block (README has the long version).
    next_year_note = ""
    for y in est_years:
        e = DATA["years"][y]["schvaleny"]
        x = e["estimate"]
        bt = x.get("backtest")
        mixed = sk_num(100 * x["neiste"] / e["total"])
        next_year_note += (
            f"<details id=\"odhad\"><summary>Rok {y}: čo je presné a čo odhad</summary><ul>"
            f"<li><b>Presné:</b> celkové výdavky a príjmy štátu (<a href=\"{esc(x['zdroj_bilancia'])}\">zákon, príloha č. 1</a>), "
            f"Sociálna poisťovňa (<a href=\"{esc(x['zdroj_sp'])}\">schválený rozpočet</a>) a transfer medzi nimi.</li>"
            f"<li><b>Presné:</b> sumy, ktorých účel uvádza hlavná kniha rozpočtu, napríklad 560 + 50 mil. € vojenským "
            f"nemocniciam alebo odvod do EÚ (<a href=\"data/navrh_polozky.csv\">zoznam so zdrojmi</a>).</li>"
            f"<li><b>Odhad:</b> ostatné <a href=\"{esc(x['zdroj_programy'])}\">programy zo zákona</a> delíme podľa rozpočtu "
            f"{x['zaklad'][0]}{', prípadne ' + str(x['zaklad'][1]) if len(x['zaklad']) > 1 else ''} alebo celej kapitoly; "
            f"riadky Plánu obnovy vynechávame. Programy, ktoré miešajú oblasti, dali v roku {x['zaklad'][0]} mimo svojej "
            f"hlavnej oblasti ≈ {mixed} € zo stovky; práve toto rozdelenie je odhad.</li>"
            + (f"<li><b>Test:</b> rovnaký postup na roku {bt['rok']} sa mýlil priemerne o {sk_num(bt['priemerna_chyba'])} € "
               f"na dlaždicu, najviac o {sk_num(bt['max_chyba'])} €.</li>" if bt else "")
            + "<li>Keď ministerstvo zverejní skutočné rozdelenie, odhad sa pri mesačnej obnove nahradí.</li></ul></details>")
    next_year = int(years[-1]) + 1
    if str(next_year) not in DATA["years"] and not est_years:
        next_year_note += (f"<details><summary>Rok {next_year}</summary><ul><li>Doplní sa, keď budú zverejnené rozpočty "
                           f"štátu aj Sociálnej poisťovne na rok {next_year}.</li></ul></details>")
    payload = json.dumps({**DATA, "footnoted": FOOTNOTED, "site": SITE}, ensure_ascii=False,
                         separators=(",", ":")).replace("</", "<\\/")

    page = f"""<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Na čo míňa štát? Štátna kasa ako jedna stovka | Projekt Žltá Stopa</title>
<meta name="description" content="Na čo ide každých 100 € zo štátnej kasy Slovenska, teda zo štátneho rozpočtu a Sociálnej poisťovne? Interaktívne, za roky {first} až {last}, z otvorených dát Ministerstva financií SR. Projekt Žltá Stopa.">
<meta property="og:title" content="Na čo míňa štát? Štátna kasa ako jedna stovka">
<meta property="og:description" content="Štátny rozpočet a Sociálna poisťovňa zmenšené na 100 €. Dôchodky, dávky, školstvo, dlh, obrana… za roky {first} až {last}.">
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
    <h1>Na čo míňa štát?</h1>
    <a class="badge" href="https://www.zltastopa.sk" target="_blank" rel="noopener" aria-label="Projekt Žltá Stopa">
      <img src="{BADGE}" alt="Projekt Žltá Stopa" width="118" height="38">
    </a>
  </div>
  <p class="tagline">Keby bola celá štátna kasa jedna stovka</p>
  <p class="sub">Koľko z nej ide na dôchodky, školy, dávky, obranu či obsluhu dlhu? Roky {first} až {last}.</p>
</header>

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
  <div class="kpis" id="kpis" aria-live="polite"></div>
  <p class="event" id="event" hidden></p>
  <ol class="foot" id="foot">{footnotes}</ol>
  <div class="chart-tools" data-chart="tm"><button class="ct" data-act="copy" type="button">Kopírovať obrázok</button><button class="ct" data-act="download" type="button">Stiahnuť PNG</button></div>
  <details class="tablebox"><summary>Tabuľka hodnôt</summary><div id="table"></div></details>
</section>

<section>
  <h2>Stovka v čase</h2>
  <p class="desc">Každý stĺpec delí ročné výdavky na 100&nbsp;€, ukazuje podiely. Klik na stĺpec vyberie rok.</p>
  <div class="tc-scroll"><div id="tc"></div></div>
  <div class="chart-tools" data-chart="tc"><button class="ct" data-act="copy" type="button">Kopírovať obrázok</button><button class="ct" data-act="download" type="button">Stiahnuť PNG</button></div>
</section>

<section>
  <h2>Obsluha štátneho dlhu v čase</h2>
  <p class="desc">Hore v miliardách eur, dole zo stovky.
    Od roku 2012 je to transfer správcovi dlhu, nie priamo zaplatené úroky; v rokoch 2020 a 2021 štát
    poslal výrazne menej, než schválil.</p>
  <div class="tc-scroll"><div id="dc"></div></div>
  <div class="chart-tools" data-chart="dc"><button class="ct" data-act="copy" type="button">Kopírovať obrázok</button><button class="ct" data-act="download" type="button">Stiahnuť PNG</button></div>
</section>

<footer>
  <h2>Metodika a zdroje</h2>
  <p class="desc">Zdroj: {esc(src['name'])} (CC0), stiahnuté {sk_date(src['retrieved_to'])}.
    Dáta: <a href="data/stovka.json">stovka.json</a>, <a href="data/kapitola_fnc.csv">kapitola_fnc.csv</a>.
    Kód: <a href="{REPO}" target="_blank" rel="noopener">github.com/zltastopa/rozpocet</a>.
    Inšpirácia: <a href="https://www.novinky.cz/clanek/ekonomika-statni-rozpocet-v-tisicikorune-pulka-jde-na-duchody-davky-a-uroky-z-dluhu-40597265" target="_blank" rel="noopener">Novinky.cz</a>.</p>
  <details><summary>Čo je v stovke</summary><ul>
    <li>Štátny rozpočet (súčet kapitol zo zákona, pre rok 2026 presne 32&nbsp;899&nbsp;667&nbsp;683&nbsp;€) a Sociálna poisťovňa.
      V Česku sú dôchodky v štátnom rozpočte, u nás ich vypláca Sociálna poisťovňa, preto ju pridávame.</li>
    <li>Transfer štátu do Sociálnej poisťovne (v roku 2026 2,34 mld.&nbsp;€) aj presuny medzi jej fondmi odpočítavame, aby sa peniaze nerátali dvakrát.</li>
    <li>Mimo stovky sú zdravotné poisťovne, obce a kraje. Je to rozdelenie výdavkov, nie toho, kam idú dane jedného človeka.</li>
    <li>Súhrn „Štátny rozpočet“ z API nepoužívame: pridáva účet Štátny dlh a niektoré peniaze ráta dvakrát.</li>
    <li>Odvody, ktoré štát platí ako zamestnávateľ, ostávajú. Päť drobných transferov
      bez uvedeného príjemcu (spolu menej ako 0,3 mil.&nbsp;€) ostáva výdavkom štátu.</li>
    <li>Kontrola: v roku 2023 sa výdavky Sociálnej poisťovne po odpočte líšia od jej Správy o hospodárení o 34 mil.&nbsp;€, ktoré nevieme vysvetliť.</li>
  </ul></details>
  <details><summary>Schválený rozpočet a skutočnosť</summary><ul>
    <li><b>Schválený rozpočet:</b> podľa zákona vrátane noviel počas roka (v roku 2020 z 18,56 na 26,32 mld.&nbsp;€).</li>
    <li><b>Skutočnosť:</b> skutočné čerpanie je konečné do roku {DATA['final_account_through']}, neskoršie uzavreté roky sú predbežné, bežný rok sa nezobrazuje.</li>
    <li>Sumy pred rokom 2009 sú prepočítané kurzom 30,1260&nbsp;Sk/€.</li>
  </ul></details>
  <details><summary>Ako sa delí do dlaždíc</summary><ul>
    <li>Každé euro je práve v jednej dlaždici: štát podľa funkčnej klasifikácie COFOG, Sociálna poisťovňa podľa druhu výdavku.</li>
    <li>Výnimky: platby za poistencov štátu (642031) idú do Zdravotníctva, všetok výskum do Vedy a výskumu,
      odvod do EÚ a financie VPS majú vlastné dlaždice.</li>
    <li>Sociálna poisťovňa: starobné, invalidné a pozostalostné dôchodky do Dôchodkov; nemocenské, materské,
      úrazové dávky, dávka v nezamestnanosti a správa do Dávok.</li>
    <li>Súčet dlaždíc kontrolujeme so zverejnenými celkami (tolerancia 1&nbsp;€); zobrazené sumy sú zaokrúhlené.</li>
    <li>Drobné rozdiely medzi dvoma zdrojmi MF: {esc(residuals)}.</li>
  </ul></details>
  {next_year_note}
  <p class="desc">Vygenerované {sk_date(DATA['generated'])}.</p>
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
