# Na čo míňa štát?

Keby bola celá štátna kasa Slovenska (štátny rozpočet a Sociálna poisťovňa spolu)
100 €: interaktívny treemap ukazuje, koľko z toho ide na dôchodky, dávky, školstvo,
zdravotníctvo, políciu, armádu, dopravu či na obsluhu štátneho dlhu, za roky
2006 až 2026, skutočné čerpanie len za uzavreté roky. V schválenom rozpočte 2026
ide na dôchodky 30,72 €, na dávky 11,47 € a na školstvo 11,33 €.

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
  percento výdavkov, rozdelenie na položky (vybraná položka je zvýraznená),
  najväčšie rozpočtové kapitoly („Kto to platí“, vrátane Sociálnej poisťovne),
  tá istá dlaždica v druhom type údajov (napr. rezervy schválené vs. skutočne
  minuté), zmena podielu oproti predchádzajúcemu roku a vysvetlivka.
- **Ukazovatele:** výdavky spolu, z toho Sociálna poisťovňa a štátny rozpočet,
  schodok štátneho rozpočtu na 100 € zobrazených výdavkov (nie je to spoločný
  schodok štátu a Sociálnej poisťovne).
- **Stovka v čase:** stopercentné stĺpce 2006 až 2026 s pevným poradím a
  farbami dlaždíc. Kliknutím na stĺpec sa rok zobrazí v treemape.
- **Obsluha štátneho dlhu v čase:** v mld. € (hore) a v € zo stovky (dole),
  2006 až 2027, s upozornením, že od roku 2012 je to transfer organizácii, ktorá
  dlh spravuje (skutočne zaplatené úroky sa od neho môžu líšiť, výrazne v rokoch
  2020 a 2021).
- **Kopírovať / stiahnuť PNG** pre všetky grafy, s názvom, rokom, rozsahom údajov
  a zdrojom vloženým priamo do obrázka.
- Tabuľka hodnôt, ovládanie klávesnicou, zdieľateľný odkaz na rok
  (`#2025-skutocnost`).

Napríklad v schválenom rozpočte na rok 2026 ide z každých 100 € na dôchodky
30,72 €, na dávky 11,47 €, na školstvo 11,33 €, na zdravotníctvo 6,72 € a na
obsluhu štátneho dlhu 4,47 €. Schodok štátneho rozpočtu je 11,24 € na každých
100 € zobrazených výdavkov.

## Odkiaľ sú dáta

Všetko je z portálu [rozpocet.sk](https://www.rozpocet.sk) Ministerstva
financií SR (licencia CC0):

1. **Výdavky kapitol podľa funkčnej klasifikácie (COFOG)**, verejné Open Data API:
   `https://www.rozpocet.sk/api/vs/rozpocet/{kapitola}/prehlad-klasifikacii/vydavky/fnc/{rok}`
   (schválený, upravený rozpočet a skutočnosť).
2. **Zoznam kapitol a zverejnené celkové príjmy a výdavky** štátneho rozpočtu
   z rozhrania, ktoré používa samotný portál
   (`/rest/api/rozpocet/rozpoctyPodorganizaciiVSOrg/…`, `/rest/api/rozpocet/rozpoctyVSOrg/…`).
3. **Prienik kapitola × COFOG × ekonomická klasifikácia** pre šesť buniek, ktoré
   treba rozdeliť podľa ekonomickej položky, a pre transfery 641003 všetkých kapitol
   (`/rest/api/rozpocet/polozkyRozpocetuVSOrg/SK/{kapitola}/{rok}/VS/false/EKV?FNC={cofog}…`).
4. **Výdavky Sociálnej poisťovne** (organizácia 203) podľa ekonomickej
   klasifikácie z toho istého rozhrania
   (`/rest/api/rozpocet/polozkyRozpocetuVSOrg/SK/203/{rok}/VS/false/EKV?EKV=SpoluV&FNC=Spolu`).

## Metodika

- **Hranica:** stovka = výdavky štátneho rozpočtu (súčet kapitol, presne ako v
  zákone o štátnom rozpočte, pre rok 2026 32 899 667 683 €) + výdavky Sociálnej
  poisťovne − transfer zo štátneho rozpočtu do Sociálnej poisťovne (VPS, položka
  641003, v roku 2026 2,34 mld. €, rovnako ako jej príjem „transfer zo ŠR“) − presuny
  medzi vlastnými fondmi Sociálnej poisťovne (jej 641003, v schválených
  rozpočtoch vždy nula). Dôvod: na Slovensku vypláca dôchodky Sociálna poisťovňa
  mimo štátneho rozpočtu, v Česku ich platí priamo štátny rozpočet. Bez nej by
  stovka dôchodky skoro nevidela. Mimo stovky sú zdravotné poisťovne (ako v
  Česku), obce a kraje. Kontrola za rok 2023 voči Správe o hospodárení
  Sociálnej poisťovne: 11,92 vs. 11,95 mld. €, 34 mil. € nevysvetlených.
  Súhrn „Štátny rozpočet“ z API sa nepoužíva, lebo pridáva aj účty Štátny dlh,
  SURO a SFA a niektoré peniaze tak počíta dvakrát.
- **Sociálna poisťovňa** je triedená podľa ekonomickej klasifikácie (jej COFOG
  v schválených rozpočtoch 2006 až 2008 chýba): dôchodky zo starobného a
  invalidného poistenia → Dôchodky, nemocenské, materské a úrazové dávky, dávka v
  nezamestnanosti a správa poisťovne → Dávky.
- **Dlaždice:** každé euro je priradené práve raz, podľa pravidiel v poradí
  (`scripts/build.py`):
  1. bunky rozdelené podľa ekonomickej položky: platby Ministerstva
     zdravotníctva za poistencov štátu (642031) → Zdravotníctvo (MF ich od roku
     2013 vedie v sociálnom zabezpečení, predtým v zdravotníctve, takže
     porovnanie v čase platí), odvod do rozpočtu EÚ (649005) zo Všeobecnej
     pokladničnej správy a finančné a rozpočtové záležitosti VPS vrátane rezerv
     majú vlastné dlaždice,
  2. všetok výskum a vývoj → Veda a výskum,
  3. zvyšok podľa skupín COFOG.
- **Typ údajov:** schválený = rozpočet podľa zákona o štátnom rozpočte vrátane
  noviel počas roka, tak ako ho vedie MF (napr. 2020: pôvodne 18,56, po novele
  26,32 mld. €), skutočnosť = čerpanie. Skutočnosť je konečná po schválení
  štátneho záverečného účtu (`FINAL_ACCOUNT_THROUGH` v `build.py`, teraz 2025,
  schválený NR SR 6. 10. 2026). Neskoršie uzavreté roky sú označené ako
  predbežné, bežný rok sa nezobrazuje. Rok 2005 chýba (bez údajov o čerpaní). Sumy pred
  rokom 2009 sú prepočítané z korún kurzom 30,1260 Sk/€ tak, ako ich zverejňuje MF.
- **Kontroly:** `build.py` nezapíše dáta, ak pre ktorýkoľvek rok a typ údajov
  nesedí (na 1 €) súčet listov COFOG so „Spolu“ kapitoly, súčet dlaždíc so
  zverejnenými celkami (štát + Sociálna poisťovňa − transfery), ak sa v
  ktorejkoľvek kapitole objaví nový transfer 641003 (päť známych drobných,
  spolu pod 0,3 mil. €, je vymenovaných), alebo ak rozdelenie bunky podľa
  ekonomickej klasifikácie o viac ako 0,1 %. Jediný drobný rozdiel medzi dvoma
  zdrojmi MF (1 384,98 €, 2006) je zverejnený v `data/stovka.json` a zostáva v
  pôvodnej dlaždici. `fetch.py` končí chybou, ak sa niečo nepodarí stiahnuť.
- **Zoznam kapitol:** zoznam kapitol pre rok niekedy vynechá kapitolu s
  výdavkami (kapitola 55 v roku 2011, 469 897 €), preto sa každý rok pýtame na
  všetky kódy kapitol zo všetkých rokov.
- **Rok 2027 je čiastočne odhad.** Presné sú: celkové výdavky a príjmy štátu
  (príloha č. 1 zákona), výdavky Sociálnej poisťovne (jej schválený rozpočet po
  riadkoch, `data/navrh_2027_sp.csv`, bez finančných operácií) a transfer zo štátu
  do nej (2 000 000 000 €, rovnako v oboch dokumentoch). Rozdelenie výdavkov štátu
  do oblastí ministerstvo zatiaľ nezverejnilo, preto ho skladáme
  (`scripts/estimate.py`) presne tam, kde sa dá, a odhadujeme len zvyšok:
  - **Presne podľa hlavnej knihy** (`data/navrh_polozky.csv`, každá suma so
    zdrojom): odvod do EÚ, položky „Správy ostatných výdavkov“ (napr. 700 mil. €
    do štátnych finančných aktív, 482 mil. € na sociálne a prorodinné zmeny) a
    účelové sumy vnútri programov ministerstiev, napr. 560 + 50 mil. € vojenským
    nemocniciam, 138 mil. € na výsluhové dávky vojakov, Akadémia PZ, 13. dôchodok,
    Program Slovensko na bývanie, celý program 076 MŽP. Položka s kódom COFOG sa
    zaradí rovnako ako riadky rozpočtu. Riadky predchádzajúceho roka, ktoré
    nahrádza (stĺpec `zaklad`), sa zo zvyšku programu vynechajú, aby sa
    nezapočítali dvakrát.
  - **Zvyšok programov** z prílohy č. 4 (`data/navrh_2027_programy.csv`) sa
    rozdelí tak, ako sa ten istý program delil v schválenom rozpočte 2026 (inak
    2025, inak podľa celej kapitoly), bez riadkov Plánu obnovy (zdroj 1P), lebo
    ten v roku 2027 už v kapitolách nie je.
  Väčšina programov išla v roku 2026 celá do jednej oblasti. Programy, ktoré
  miešajú viac oblastí, dali vtedy mimo svojej hlavnej oblasti spolu asi
  1,06 mld. € (≈ 2,16 € zo stovky 2027). Práve toto rozdelenie odhadujeme, hlavne
  v programoch 077 (vysoké školy: školstvo alebo veda), 0D6 MV (polícia alebo
  správa) a 072 MF (daňová alebo colná správa), ktoré hlavná kniha nerozpisuje.
  Spätný test na roku 2026 na tej istej hranici, s účelovými sumami len z
  vtedajšej hlavnej knihy (a energetickej položky VPS doplnenej parlamentom):
  chyba dlaždice v priemere 0,11 € zo stovky, najviac 0,58 €. Na stránke je rok
  výrazne označený („odhad“, „≈“, šrafovanie). Keď MF zverejní skutočné
  členenie, odhad sa automaticky nahradí. Odhad 2027:
  dôchodky ≈ 29,33 €, dávky ≈ 11,81 €, školstvo ≈ 10,65 €, zdravotníctvo ≈ 6,18 €.

Rozhodnutia o hraniciach, kategóriách a zobrazení boli prediskutované a
odsúhlasené v nezávislej revízii (Codex).

## Ako je to zostavené

```
scripts/fetch.py    # stiahne odpovede API do cache/ (s URL a časom stiahnutia)
scripts/build.py    # -> data/stovka.json + data/kapitola_fnc.csv (s kontrolami)
scripts/render.py   # -> index.html (vloží assets/style.css, assets/app.js a dáta)
scripts/parse_navrh.py 2027  # príloha č. 4 návrhu zákona -> data/navrh_2027_*.csv (treba pdftotext)
scripts/estimate.py # odhad rozdelenia roka bez zverejnených údajov (volá ho build.py)
```

Iba štandardná knižnica Pythonu 3.12, bez závislostí. Na stránke je vanilla JS
(vlastný squarified treemap), žiadne externé požiadavky.

```bash
python scripts/fetch.py     # ~3 minúty, idempotentné, --force stiahne všetko znova
python scripts/build.py
python scripts/render.py
python -m http.server       # a otvor http://localhost:8000
```

## Nasadenie

- `.github/workflows/deploy.yml`: pri každom pushi do `main` vyrenderuje
  stránku z commitnutých dát a nasadí ju na GitHub Pages.
- `.github/workflows/refresh.yml`: raz mesačne (a na požiadanie) stiahne všetky
  roky nanovo, prebuduje dáta a commitne ich, ak sa zmenil
  `data/kapitola_fnc.csv`. Potom spustí nasadenie.
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
