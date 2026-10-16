# Kam ide stovka

Štátny rozpočet Slovenska zmenšený na 100 €. Interaktívny treemap ukazuje,
koľko z každej stovky výdavkov štátneho rozpočtu ide na školstvo, dávky,
dôchodky, zdravotníctvo, políciu, armádu, dopravu či na obsluhu štátneho dlhu,
za každý rok od 2006 po 2026, schválený rozpočet aj skutočné čerpanie.

Slovenská obdoba vizualizácie
[„Kam jde tisícovka ze státního rozpočtu“](https://www.novinky.cz/clanek/ekonomika-statni-rozpocet-v-tisicikorune-pulka-jde-na-duchody-davky-a-uroky-z-dluhu-40597265)
z Novinky.cz.

**Live:** https://rozpocet.zltastopa.sk

## Čo v tom nájdeš

Jedna samostatná stránka [`index.html`](index.html) (dáta, štýly aj skript sú
vložené priamo v nej, otvorí sa aj offline):

- **Treemap stovky** pre zvolený rok a typ údajov (schválený rozpočet /
  skutočnosť). Plocha dlaždice = podiel zo stovky. Dlaždice sú v piatich
  skupinách (Sociálne veci, Služby pre ľudí, Hospodárstvo, Bezpečnosť, Štát a
  dlh) a delia sa na menšie obdĺžniky podľa toho, z čoho sa skladajú.
- **Bublinka po nabehnutí** (alebo ťuknutí): suma zo stovky, milióny eur,
  percento výdavkov, rozpad na položky (aktuálna je zvýraznená), najväčšie
  rozpočtové kapitoly, ktoré dlaždicu platia, zmena podielu oproti
  predchádzajúcemu roku a vysvetlivka.
- **Ukazovatele:** výdavky, príjmy a „z každých 100 € výdavkov chýba X € v
  príjmoch“ (hotovostný schodok štátneho rozpočtu).
- **Stovka v čase:** stopercentné stĺpce 2006 až 2026 s pevným poradím a
  farbami dlaždíc; kliknutím na stĺpec sa rok zobrazí v treemape.
- **Kopírovať / stiahnuť PNG** pre oba grafy, s názvom, rokom, rozsahom údajov
  a zdrojom vloženým priamo do obrázka.
- Tabuľka hodnôt, ovládanie klávesnicou, zdieľateľný odkaz na rok
  (`#2025-skutocnost`).

Napríklad v schválenom rozpočte na rok 2026 ide z každých 100 € na školstvo
15,72 €, na dávky 10,44 €, na dôchodky a zdravotníctvo po 9,32 € a na obsluhu
štátneho dlhu 6,20 €. Na každých 100 € výdavkov chýba v príjmoch 15,60 €.

## Odkiaľ sú dáta

Všetko je z portálu [rozpocet.sk](https://www.rozpocet.sk) Ministerstva
financií SR (licencia CC0):

1. **Výdavky kapitol podľa funkčnej klasifikácie (COFOG)**, verejné Open Data API:
   `https://www.rozpocet.sk/api/vs/rozpocet/{kapitola}/prehlad-klasifikacii/vydavky/fnc/{rok}`
   (schválený, upravený rozpočet a skutočnosť).
2. **Zoznam kapitol a zverejnené celkové príjmy a výdavky** štátneho rozpočtu
   z rozhrania, ktoré používa samotný portál
   (`/rest/api/rozpocet/rozpoctyPodorganizaciiVSOrg/…`, `/rest/api/rozpocet/rozpoctyVSOrg/…`).
3. **Prienik kapitola × COFOG × ekonomická klasifikácia** pre päť buniek, ktoré
   treba rozdeliť podľa ekonomickej položky
   (`/rest/api/rozpocet/polozkyRozpocetuVSOrg/SK/{kapitola}/{rok}/VS/false/EKV?FNC={cofog}…`).

## Metodika

- **Hranica:** štátny rozpočet = súčet kapitol, presne ako v zákone o štátnom
  rozpočte (pre rok 2026 32 899 667 683 €, zákon č. 303/2025 Z. z.). Súhrn
  „Štátny rozpočet“ z API sa nepoužíva, lebo pridáva aj účty Štátny dlh, SURO a
  SFA a niektoré peniaze tak počíta dvakrát. Transfery Sociálnej poisťovni a
  zdravotným poisťovniam sú zahrnuté, ich vlastné výdavky z odvodov nie.
- **Dlaždice:** každé euro je priradené práve raz, podľa pravidiel v poradí
  (`scripts/build.py`):
  1. bunky rozdelené podľa ekonomickej položky: platby Ministerstva
     zdravotníctva za poistencov štátu (642031) → Zdravotníctvo (MF ich od roku
     2013 vedie v sociálnom zabezpečení, predtým v zdravotníctve, takže
     porovnanie v čase platí); odvod do rozpočtu EÚ (649005) a transfer
     Sociálnej poisťovni (641003) zo Všeobecnej pokladničnej správy; finančné
     a rozpočtové záležitosti VPS vrátane rezerv;
  2. všetok výskum a vývoj → Veda a výskum;
  3. zvyšok podľa skupín COFOG.
- **Typ údajov:** schválený = pôvodne schválený zákon; skutočnosť = čerpanie.
  Skutočnosť za bežný rok sa nezobrazuje (je neúplná), posledný uzavretý rok je
  označený ako predbežný. Rok 2005 chýba (bez údajov o čerpaní). Sumy pred
  rokom 2009 sú prepočítané z korún kurzom 30,1260 Sk/€ tak, ako ich zverejňuje MF.
- **Kontroly:** `build.py` nezapíše dáta, ak pre ktorýkoľvek rok a typ údajov
  nesedí (na 1 €) súčet listov COFOG so „Spolu“ kapitoly, súčet dlaždíc so
  zverejneným celkom štátneho rozpočtu, alebo rozdelenie bunky podľa
  ekonomickej klasifikácie o viac ako 0,1 %. Jediný drobný rozdiel medzi dvoma
  zdrojmi MF (1 384,98 €, 2006) je zverejnený v `data/stovka.json` a zostáva v
  pôvodnej dlaždici. `fetch.py` končí chybou, ak sa niečo nepodarí stiahnuť.
- **Zoznam kapitol:** zoznam kapitol pre rok niekedy vynechá kapitolu s
  výdavkami (kapitola 55 v roku 2011, 469 897 €), preto sa každý rok pýtame na
  všetky kódy kapitol zo všetkých rokov.
- **Rok 2027:** rozpočet schválila NR SR 14. 10. 2026, ale jeho rozdelenie podľa
  funkčnej klasifikácie zatiaľ nie je zverejnené (prílohy zákona ani vládny
  materiál ho neobsahujú). Mesačná obnova ho doplní, keď sa objaví na rozpocet.sk.

Rozhodnutia o hraniciach, kategóriách a zobrazení boli prediskutované a
odsúhlasené v nezávislej revízii (Codex).

## Ako je to zostavené

```
scripts/fetch.py    # stiahne odpovede API do cache/ (s URL a časom stiahnutia)
scripts/build.py    # -> data/stovka.json + data/kapitola_fnc.csv (s kontrolami)
scripts/render.py   # -> index.html (vloží assets/style.css, assets/app.js a dáta)
```

Iba štandardná knižnica Pythonu 3.12, bez závislostí; na stránke vanilla JS
(vlastný squarified treemap), žiadne externé požiadavky.

```bash
python scripts/fetch.py     # ~3 minúty, idempotentné; --force stiahne všetko znova
python scripts/build.py
python scripts/render.py
python -m http.server       # a otvor http://localhost:8000
```

## Nasadenie

- `.github/workflows/deploy.yml`: pri každom pushi do `main` vyrenderuje
  stránku z commitnutých dát a nasadí ju na GitHub Pages.
- `.github/workflows/refresh.yml`: raz mesačne (a na požiadanie) stiahne všetky
  roky nanovo, prebuduje dáta a commitne ich, ak sa zmenil
  `data/kapitola_fnc.csv`; potom spustí nasadenie.
- Vlastná doména cez `CNAME` (`rozpocet.zltastopa.sk`).

## Súbory

- `index.html`: samostatná stránka.
- `data/stovka.json`: to, čo zobrazuje stránka: pre každý rok a typ údajov
  celkové výdavky a príjmy, dlaždice s položkami a najväčšími kapitolami,
  taxonómia, zdroje a čas stiahnutia.
- `data/kapitola_fnc.csv`: auditovateľný snapshot, jeden riadok na rok ×
  kapitola × COFOG (× ekonomická položka pri rozdelených bunkách) s priradenou
  dlaždicou, schválený rozpočet a skutočnosť v eurách.
- `cache/`: surové odpovede API (gitignored, obnoviteľné cez `fetch.py`).

## Súvisiace

- [zltastopa.sk](https://zltastopa.sk/): domovská stránka Žltá Stopa
- [letokruhy](https://github.com/zltastopa/letokruhy): vekové zloženie NR SR

Súčasť projektu **Žltá Stopa**. Licencia MIT, dáta CC0 (MF SR).
