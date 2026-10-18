(function () {
  "use strict";
  const D = window.STOVKA;
  const YEARS = Object.keys(D.years).map(Number).sort((a, b) => a - b);
  const GROUPS = D.groups;
  const GROUP = Object.fromEntries(GROUPS.map(g => [g.id, g]));
  const TILES = D.tiles;
  const TILE = Object.fromEntries(TILES.map(t => [t.id, t]));
  const MEASURE_LABEL = { schvaleny: "schválený rozpočet", skutocnost: "skutočnosť" };
  const SVGNS = "http://www.w3.org/2000/svg";
  const FOOT = Object.fromEntries(D.footnoted.map((id, i) => [id, i + 1]));
  const SUP = ["", "¹", "²", "³", "⁴", "⁵", "⁶"];

  // ---- colours: tile = tint of its group colour, fixed by position in TILES ----
  function mix(hex, t) {
    const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    const m = c => Math.round(c + (255 - c) * t);
    return "#" + ((1 << 24) + (m(r) << 16) + (m(g) << 8) + m(b)).toString(16).slice(1);
  }
  function lum(hex) {
    const n = parseInt(hex.slice(1), 16);
    const ch = [n >> 16, (n >> 8) & 255, n & 255].map(c => { c /= 255; return c <= .03928 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4); });
    return .2126 * ch[0] + .7152 * ch[1] + .0722 * ch[2];
  }
  const COLOR = {};
  GROUPS.forEach(g => TILES.filter(t => t.group === g.id).forEach((t, i) => { COLOR[t.id] = mix(g.color, [0, .22, .4, .55][i] ?? .6); }));
  // white text needs >= 4.5:1 against the fill, otherwise use ink
  const TEXT = Object.fromEntries(Object.entries(COLOR).map(([k, c]) => [k, 1.05 / (lum(c) + .05) >= 4.5 ? "#fff" : "#1b2130"]));

  // ---- formatting (Slovak) ----
  const nf2 = new Intl.NumberFormat("sk-SK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf1 = new Intl.NumberFormat("sk-SK", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf0 = new Intl.NumberFormat("sk-SK", { maximumFractionDigits: 0 });
  // non-breaking spaces keep the unit on the same line as the number
  const eur = x => (x > 0 && x < 0.01) ? "< 1\u00a0cent" : nf2.format(x) + "\u00a0€";
  const mil = x => nf1.format(x / 1e6) + "\u00a0mil.\u00a0€";
  const mld = x => nf2.format(x / 1e9) + "\u00a0mld.\u00a0€";
  const amt = x => Math.abs(x) >= 1e9 ? mld(x) : mil(x);
  const pct = x => nf1.format(x) + "\u00a0%";
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // ---- state + URL hash (#2025-skutocnost) ----
  // default: the latest year with published data (an estimate is one click away)
  const isEst = (y, m = "schvaleny") => !!((D.years[y] || {})[m] || {}).estimate;
  const state = { year: YEARS.filter(y => !isEst(y)).pop(), measure: "schvaleny" };
  function available(y, m) { return !!(D.years[y] && D.years[y][m]); }
  const EST_LINE = "Rozdelenie do oblastí je čiastočne odhadnuté.";
  // the full method (incl. the share of mixed programs) is in the collapsed #odhad methodology block
  const estText = y => `Rok ${y}: súčty sú presné, rozdelenie do oblastí čiastočne odhadujeme podľa starších rozpočtov.`;
  function readHash() {
    const m = location.hash.match(/^#(\d{4})(?:-(schvaleny|skutocnost))?$/);
    if (m && available(+m[1], m[2] || "schvaleny")) { state.year = +m[1]; state.measure = m[2] || "schvaleny"; }
  }
  function writeHash() {
    const h = "#" + state.year + (state.measure === "skutocnost" ? "-skutocnost" : "");
    if (location.hash !== h) history.replaceState(null, "", h);
  }
  const entry = (y = state.year, m = state.measure) => (D.years[y] || {})[m];

  // ---- squarified treemap (Bruls, Huizing, van Wijk) ----
  function worst(row, side) {
    let s = 0, mx = -Infinity, mn = Infinity;
    for (const r of row) { s += r.a; if (r.a > mx) mx = r.a; if (r.a < mn) mn = r.a; }
    const s2 = s * s, w2 = side * side;
    return Math.max(w2 * mx / s2, s2 / (w2 * mn));
  }
  function squarify(items, x, y, w, h) {
    items = items.filter(i => i.v > 0).sort((a, b) => b.v - a.v);
    const total = items.reduce((s, i) => s + i.v, 0), out = [];
    if (total <= 0 || w <= 0 || h <= 0) return out;
    let rest = items.map(i => ({ item: i, a: i.v * w * h / total }));
    while (rest.length) {
      const side = Math.min(w, h);
      let n = 1, cur = worst(rest.slice(0, 1), side);
      while (n < rest.length) { const nx = worst(rest.slice(0, n + 1), side); if (nx > cur) break; cur = nx; n++; }
      const row = rest.slice(0, n), sum = row.reduce((s, r) => s + r.a, 0);
      if (w >= h) {
        const cw = sum / h; let cy = y;
        row.forEach(r => { const rh = r.a / cw; out.push({ item: r.item, x, y: cy, w: cw, h: rh }); cy += rh; });
        x += cw; w -= cw;
      } else {
        const ch = sum / w; let cx = x;
        row.forEach(r => { const rw = r.a / ch; out.push({ item: r.item, x: cx, y, w: rw, h: ch }); cx += rw; });
        y += ch; h -= ch;
      }
      rest = rest.slice(n);
    }
    return out;
  }
  function inset(r, p) { return { x: r.x + p, y: r.y + p, w: Math.max(0, r.w - 2 * p), h: Math.max(0, r.h - 2 * p) }; }

  // ---- DOM helpers ----
  const $ = id => document.getElementById(id);
  function el(name, attrs, parent) {
    const e = document.createElementNS(SVGNS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, str, cls, size, fill) {
    const t = el("text", { x, y, class: cls, "font-size": size, fill }, parent);
    t.textContent = str;
    return t;
  }
  const measureCtx = document.createElement("canvas").getContext("2d");
  function textW(s, size, weight) {
    measureCtx.font = `${weight} ${size}px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif`;
    return measureCtx.measureText(s).width;
  }
  // greedy word wrap into at most maxLines; the last line is ellipsized if needed
  function wrapName(str, size, maxW, maxLines) {
    const words = str.split(" "), lines = [];
    let cur = "";
    for (let i = 0; i < words.length; i++) {
      const t = cur ? cur + " " + words[i] : words[i];
      if (textW(t, size, 500) <= maxW) { cur = t; continue; }
      if (cur) lines.push(cur);
      cur = words[i];
      if (lines.length === maxLines) { cur = null; break; }
    }
    if (cur !== null && cur) lines.push(cur);
    const truncated = lines.length > maxLines || cur === null || lines.some(l => textW(l, size, 500) > maxW);
    const out = lines.slice(0, maxLines);
    if (truncated && out.length) {
      let last = out[out.length - 1];
      while (last.length > 1 && textW(last + "…", size, 500) > maxW) last = last.slice(0, -1);
      out[out.length - 1] = last.length > 1 ? last.trimEnd() + "…" : "";
      if (!out[out.length - 1]) out.pop();
    }
    return out;
  }

  // ---- tooltip ----
  const tip = $("tip");
  let tipFor = null;
  // pinned = opened by a tap/keyboard: the tooltip accepts scrolling and stays put
  function showTip(html, x, y, pinned) {
    tip.innerHTML = html; tip.hidden = false;
    tip.classList.toggle("pinned", !!pinned);
    const r = tip.getBoundingClientRect();
    let left = x + 16, top = y + 16;
    if (left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - 16);
    if (top + r.height > innerHeight - 8) top = Math.max(8, innerHeight - r.height - 8);
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function hideTip() {
    tip.hidden = true; tipFor = null; openedBy = null; tip.classList.remove("pinned");
    document.querySelectorAll(".tile.hl").forEach(t => t.classList.remove("hl"));
    document.querySelectorAll(".sub.on").forEach(s => s.classList.remove("on"));
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideTip(); });

  function share(v, e) { return 100 * v / e.total; }
  function tileTip(id, childIdx) {
    const e = entry(), t = e.tiles[id], meta = TILE[id];
    const row = (c, i) => `<div class="r${i === childIdx ? " on" : ""}"><span>${esc(c[0])}</span><span>${eur(share(c[1], e))}</span></div>`;
    const N = t.c.length <= 4 ? 4 : 3;   // max 4 rows incl. "ďalšie"
    let rows = t.c.slice(0, N).map(row).join("");
    if (t.c.length > N) {
      if (childIdx != null && childIdx >= N) rows += row(t.c[childIdx], childIdx);   // hovered item outside the top N
      const rest = t.c.filter((c, i) => i >= N && i !== childIdx);
      if (rest.length) rows += `<div class="r"><span>ďalšie (${rest.length})</span><span>${eur(share(rest.reduce((s, c) => s + c[1], 0), e))}</span></div>`;
    }
    // payers are omitted when the breakdown already lists them (tiles split by kapitola)
    const kids = new Set(t.c.map(c => c[0]));
    const kap = t.k.some(k => kids.has(k[0])) ? "" : [...t.k].sort((a, b) => b[1] - a[1]).filter((k, i) => i === 0 || k[1] >= 0.1 * t.v).slice(0, 3)
      .map(k => `<div class="r"><span>${esc(k[0])}</span><span>${amt(k[1])}</span></div>`).join("");
    let yoy = "";
    const prev = entry(state.year - 1);
    const noYoy = (meta.no_yoy || {})[state.measure];
    if (prev && noYoy) yoy = `<div class="yoy">${esc(noYoy)}</div>`;
    else if (prev) {
      const pv = prev.tiles[id] ? share(prev.tiles[id].v, prev) : 0, d = share(t.v, e) - pv;
      yoy = `<div class="yoy">Oproti ${state.year - 1}: <b>${Math.abs(d) < 0.005 ? "bez zmeny" : (d >= 0 ? "+" : "−") + eur(Math.abs(d))}</b> zo stovky</div>`;
    }
    const est = !!e.estimate, approx = est ? "≈ " : "";
    // the other measure of the same year (approved vs actually spent): one short line
    const oe = D.years[state.year][state.measure === "schvaleny" ? "skutocnost" : "schvaleny"];
    const both = oe ? `<div class="yoy">${state.measure === "schvaleny" ? "Skutočne minuté" : "Schválené"}: <b>${eur(oe.tiles[id] ? share(oe.tiles[id].v, oe) : 0)}</b> zo stovky${oe.provisional ? " (predbežne)" : ""}</div>` : "";
    return `<div class="tt">${esc(meta.name)}${FOOT[id] ? SUP[FOOT[id]] : ""}</div>`
      + `<div class="big">${approx}${eur(share(t.v, e))} zo stovky</div>`
      + `<div class="meta">${approx}${amt(t.v)}${est ? " · odhad" : ""}</div>`
      + (t.c.length > 1 || childIdx != null ? `<div class="rows">${rows}</div>` : "")
      + (kap ? `<div class="h">Kto platí najviac</div>${kap}` : "")
      + yoy + both + (FOOT[id] && meta.note ? `<div class="note">${esc(meta.note)}</div>` : "");
  }

  // ---- treemap ----
  const tm = $("tm");
  let tmSvg = null;
  function layout(width) {
    const e = entry(), mobile = width < 560;
    const H = Math.round(mobile ? width * 1.45 : Math.min(640, Math.max(440, width * .62)));
    const groups = GROUPS.map(g => ({ id: g.id, v: TILES.filter(t => t.group === g.id).reduce((s, t) => s + ((e.tiles[t.id] || {}).v || 0), 0) }));
    const out = [];
    for (const gr of squarify(groups, 0, 0, width, H)) {
      const items = TILES.filter(t => t.group === gr.item.id && e.tiles[t.id]).map(t => ({ id: t.id, v: e.tiles[t.id].v }));
      const box = inset(gr, 2);
      for (const tr of squarify(items, box.x, box.y, box.w, box.h)) out.push({ id: tr.item.id, r: inset(tr, 1.5) });
    }
    return { W: width, H, tiles: out };
  }
  function drawTreemap() {
    const e = entry(), width = Math.max(300, Math.round(tm.clientWidth));
    const L = layout(width);
    const svg = el("svg", { id: "tmsvg", viewBox: `0 0 ${L.W} ${L.H}`, width: L.W, height: L.H, role: "group",
      "aria-label": `Kam ide stovka zo štátnej kasy ${state.year}: štátny rozpočet a Sociálna poisťovňa spolu (${MEASURE_LABEL[state.measure]})` });
    const small = [];
    for (const { id, r } of L.tiles) {
      const t = e.tiles[id], fill = COLOR[id], ink = TEXT[id], s = share(t.v, e);
      const g = el("g", { class: "tile", "data-id": id, tabindex: 0, role: "button", "aria-describedby": "tip",
        "aria-label": `${TILE[id].name}: ${eur(s)} zo stovky, ${amt(t.v)}` }, svg);
      el("rect", { class: "bg", x: r.x, y: r.y, width: r.w, height: r.h, rx: 2, fill }, g);
      // children as sub-rectangles (only when the tile is big enough to read them)
      let labelBox = r;
      if (t.c.length > 1 && r.w > 60 && r.h > 50) {
        const kids = squarify(t.c.map((c, i) => ({ i, v: c[1] })), r.x, r.y, r.w, r.h);
        kids.forEach((k, n) => {
          el("rect", { class: "sub", "data-child": k.item.i, x: k.x, y: k.y, width: k.w, height: k.h }, g);
          if (n === 0) labelBox = k;
        });
        // label goes in the largest child unless it is much smaller than the tile
        if (labelBox.w < 90 || labelBox.h < 46) labelBox = r;
      }
      const big = Math.min(26, Math.max(15, Math.sqrt(r.w * r.h) / 9));
      const name = TILE[id].short + (FOOT[id] ? SUP[FOOT[id]] : "");
      const lbl = (e.estimate ? "≈ " : "") + eur(s);
      const pad = 8;
      // prefer the largest child; if the amount does not fit there, use the whole tile
      if (labelBox !== r && (labelBox.h < big + 22 || labelBox.w - 2 * pad < textW(lbl, big, 700))) labelBox = r;
      const bw = labelBox.w - 2 * pad;
      if (labelBox.h >= big + 22 && bw >= textW(lbl, big, 700)) {
        const maxLines = Math.max(1, Math.min(3, Math.floor((labelBox.h - pad - big - 4) / 15)));
        const lines = wrapName(name, 13, bw, maxLines);
        // when the label sits on the whole tile, sub-rectangle lines would cross it:
        // paint a tile-coloured backdrop exactly behind the text block
        if (labelBox === r && g.querySelector(".sub")) {
          const tw = Math.max(textW(lbl, big, 700), ...lines.map(l => textW(l, 13, 500)));
          el("rect", { x: r.x + 1, y: r.y + 1, width: Math.min(r.w - 2, tw + pad * 1.5), height: Math.min(r.h - 2, pad + big + 6 + lines.length * 15),
            fill, "pointer-events": "none" }, g);
        }
        text(g, labelBox.x + pad, labelBox.y + pad + big * .85, lbl, "tl-amt", big, ink);
        lines.forEach((ln, i) => text(g, labelBox.x + pad, labelBox.y + pad + big + 15 + i * 15, ln, "tl-name", 13, ink));
        if (!lines.length || lines[lines.length - 1].endsWith("…")) small.push(id);
      } else if (r.h >= 22 && r.w - 8 >= textW(lbl, 12, 700)) {
        text(g, r.x + 4, r.y + 16, lbl, "tl-amt", 12, ink);
        small.push(id);
      } else {
        small.push(id);
      }
    }
    tm.replaceChildren(svg);
    tmSvg = svg;
    // tiles whose name is not (fully) visible: list with amounts, tappable
    const sm = $("small");
    sm.innerHTML = small.length ? `<span class="lbl">Menšie oblasti:</span>` + small.sort((a, b) => e.tiles[b].v - e.tiles[a].v)
      .map(id => `<button type="button" data-id="${id}" title="${esc(TILE[id].name)}">${esc(TILE[id].short)} <b>${eur(share(e.tiles[id].v, e))}</b></button>`).join("") : "";
  }
  function tileEvent(ev) {
    const g = ev.target.closest && ev.target.closest(".tile");
    if (!g) return null;
    const sub = ev.target.closest(".sub");
    return { g, id: g.dataset.id, child: sub ? +sub.dataset.child : null };
  }
  function highlight(g, child) {
    document.querySelectorAll(".tile.hl").forEach(t => t !== g && t.classList.remove("hl"));
    g.classList.add("hl");
    g.querySelectorAll(".sub").forEach(s => s.classList.toggle("on", child != null && +s.dataset.child === child));
  }
  // Input model: mouse hover shows a following tooltip; a tap (touch/pen) toggles a
  // pinned, scrollable tooltip; keyboard focus shows a pinned tooltip. Focus that is
  // a side effect of a pointer press is ignored so it cannot fight the tap toggle.
  let lastPointer = { type: "mouse", t: 0 }, openedBy = null;
  document.addEventListener("pointerdown", ev => { lastPointer = { type: ev.pointerType, t: Date.now() }; }, true);
  const fromPointer = () => Date.now() - lastPointer.t < 600;
  tm.addEventListener("pointermove", ev => {
    if (ev.pointerType !== "mouse" || openedBy === "pin") return;   // a pinned tooltip stays put
    const h = tileEvent(ev);
    if (!h) return hideTip();
    highlight(h.g, h.child);
    tipFor = h.id; openedBy = "mouse";
    showTip(tileTip(h.id, h.child), ev.clientX, ev.clientY);
  });
  tm.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse" && openedBy === "mouse") hideTip(); });
  tm.addEventListener("click", ev => {
    const h = tileEvent(ev);
    if (!h) return;
    // a click (mouse) or tap (touch) pins a scrollable tooltip; the same again unpins it
    const mode = lastPointer.type === "mouse" ? "pin" : "tap";
    if (tipFor === h.id && openedBy === mode) { openedBy = null; return hideTip(); }
    highlight(h.g, h.child); tipFor = h.id; openedBy = mode;
    showTip(tileTip(h.id, h.child), ev.clientX, ev.clientY, true);
  });
  tm.addEventListener("focusin", ev => {
    const g = ev.target.closest(".tile"); if (!g || fromPointer()) return;
    const b = g.getBoundingClientRect();
    highlight(g, null); tipFor = g.dataset.id; openedBy = "key";
    showTip(tileTip(g.dataset.id, null), b.left + Math.min(b.width, 120) - 16, b.top + 10, true);
  });
  tm.addEventListener("focusout", () => { if (openedBy === "key") hideTip(); });
  // ↑/↓ scroll an open tooltip while focus is on what opened it (a tile, a
  // "Menšie dlaždice" button or a time-chart column); ←/→ move between tiles
  document.addEventListener("keydown", ev => {
    if ((ev.key !== "ArrowDown" && ev.key !== "ArrowUp") || tip.hidden) return;
    if (!document.activeElement || !document.activeElement.closest("#tm, #small, #tc, #pc, #dc")) return;
    ev.preventDefault();
    tip.scrollTop += ev.key === "ArrowDown" ? 60 : -60;
  });
  tm.addEventListener("keydown", ev => {
    const g = ev.target.closest && ev.target.closest(".tile");
    if (g && (ev.key === "Enter" || ev.key === " ")) {   // same pin/unpin as a mouse click
      ev.preventDefault();
      if (tipFor === g.dataset.id && openedBy === "pin") return hideTip();
      const b = g.getBoundingClientRect();
      highlight(g, null); tipFor = g.dataset.id; openedBy = "pin";
      return showTip(tileTip(g.dataset.id, null), b.left + Math.min(b.width, 120) - 16, b.top + 10, true);
    }
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    const all = [...tm.querySelectorAll(".tile")], i = all.indexOf(document.activeElement);
    if (i < 0) return;
    ev.preventDefault();
    all[(i + (ev.key === "ArrowRight" ? 1 : all.length - 1)) % all.length].focus();
  });
  // "Ako?" in the 2027 note opens the collapsed methodology block (without touching the #year hash)
  $("event").addEventListener("click", ev => {
    const a = ev.target.closest('a[href="#odhad"]'), d = $("odhad"); if (!a || !d) return;
    ev.preventDefault(); d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" });
    d.querySelector("summary").focus({ preventScroll: true });
  });
  $("small").addEventListener("click", ev => {
    const b = ev.target.closest("button[data-id]"); if (!b) return;
    const r = b.getBoundingClientRect();
    tipFor = b.dataset.id; openedBy = "tap";
    showTip(tileTip(b.dataset.id, null), r.left, r.bottom - 8, true);
    ev.stopPropagation();
  });
  document.addEventListener("click", ev => { if (!ev.target.closest(".tile, #small button, .col, #tip")) hideTip(); });

  // ---- header, KPIs, legend, table ----
  function groupSums(e) {
    return GROUPS.map(g => ({ g, v: TILES.filter(t => t.group === g.id).reduce((s, t) => s + ((e.tiles[t.id] || {}).v || 0), 0) }));
  }
  function drawText() {
    const e = entry(), y = state.year, meas = MEASURE_LABEL[state.measure];
    $("ctitle").textContent = `Kam ide stovka zo štátnej kasy ${y}${e.estimate ? " (odhad)" : ""}`;
    $("csub").innerHTML = `Štátny rozpočet a Sociálna poisťovňa spolu, bez zdravotných poisťovní, obcí a krajov.<br>100&nbsp;€ = <b>${mld(e.total)}</b> výdavkov · ${meas}`
      + (e.provisional ? `<span class="prov" title="Pred schválením záverečného účtu sa údaje ešte môžu spresniť.">predbežné</span>` : "")
      + (e.estimate ? `<span class="prov est">odhad rozdelenia</span>` : "");
    const ev = $("event");
    const notes = [e.estimate ? estText(y) : null, D.events[y] ? `Rok ${y}: ${D.events[y]}` : null].filter(Boolean);
    ev.hidden = !notes.length;
    ev.classList.toggle("est", !!e.estimate);
    ev.innerHTML = esc(notes.join(" ")) + (e.estimate ? ` <a href="#odhad" aria-label="Ako vznikol odhad?">Ako?</a>` : "");
    // KPIs
    // deficit: the state budget's own cash balance, expressed per 100 € of the displayed spending
    // (it is not a combined balance of the state and Sociálna poisťovňa)
    const stateGap = e.revenue == null ? null : e.state_total - e.revenue;
    const gap = stateGap == null ? null : 100 * stateGap / e.total;
    const prevE = entry(y - 1);
    const growth = prevE ? 100 * (e.total / prevE.total - 1) : null;
    $("kpis").innerHTML =
      `<div class="kpi"><div class="n">${mld(e.total)}</div><div class="l">výdavky štátnej kasy ${y}${growth == null ? "" : `, ${growth >= 0 ? "+" : "−"}${pct(Math.abs(growth))} oproti ${y - 1}`}</div></div>`
      + `<div class="kpi" title="Štátny rozpočet ${mld(e.state_total - e.transfer)} bez transferu ${mld(e.transfer)} do Sociálnej poisťovne (ten by bol započítaný dvakrát)."><div class="n">${mld(e.sp_total - e.sp_internal)}</div><div class="l">z toho Sociálna poisťovňa</div></div>`
      + (gap == null ? `<div class="kpi"><div class="n">–</div><div class="l">bilancia nie je k dispozícii</div></div>`
        : gap >= 0 ? `<div class="kpi" title="Schodok štátneho rozpočtu ${mld(stateGap)}; nie je to spoločný schodok štátu a Sociálnej poisťovne."><div class="n">${eur(gap)}</div><div class="l">schodok štátneho rozpočtu na 100&nbsp;€ zobrazených výdavkov</div></div>`
          : `<div class="kpi" title="Prebytok štátneho rozpočtu ${mld(-stateGap)}."><div class="n">${eur(-gap)}</div><div class="l">prebytok štátneho rozpočtu na 100&nbsp;€ zobrazených výdavkov</div></div>`);
    // legend
    $("legend").innerHTML = groupSums(e).map(({ g, v }) => `<span><span class="sw" style="background:${g.color}"></span>${esc(g.name)}<b>${eur(share(v, e))}</b></span>`).join("");
    // table
    const prev = entry(y - 1);
    let rows = "";
    for (const { g, v } of groupSums(e)) {
      rows += `<tr class="grp"><td><span class="sw" style="background:${g.color}"></span>${esc(g.name)}</td><td>${eur(share(v, e))}</td><td>${amt(v)}</td><td></td></tr>`;
      for (const t of TILES.filter(t => t.group === g.id && e.tiles[t.id]).sort((a, b) => e.tiles[b.id].v - e.tiles[a.id].v)) {
        const tv = e.tiles[t.id].v;
        let d = "";
        if (prev && (t.no_yoy || {})[state.measure]) d = "neporovnateľné";
        else if (prev) { const x = share(tv, e) - (prev.tiles[t.id] ? share(prev.tiles[t.id].v, prev) : 0); d = (x >= 0 ? "+" : "−") + eur(Math.abs(x)); }
        rows += `<tr><td>${esc(t.name)}</td><td>${eur(share(tv, e))}</td><td>${amt(tv)}</td><td>${d}</td></tr>`;
      }
    }
    $("table").innerHTML = `<div class="tbl-scroll"><table><caption class="sr">${esc($("ctitle").textContent)}, ${meas}</caption><thead><tr><th>Oblasť</th><th>Zo stovky</th><th>Suma</th><th>Medziročná zmena</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  // ---- controls ----
  const yearsBox = $("years");
  yearsBox.innerHTML = YEARS.map(y => `<button type="button" role="radio" data-year="${y}"${isEst(y) ? ' class="est" title="Rozdelenie do oblastí je odhad"' : ""}>${y}${isEst(y) ? " odhad" : ""}</button>`).join("");
  function drawControls() {
    document.querySelectorAll(".seg button").forEach(b => {
      const on = b.dataset.measure === state.measure;
      b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1;
    });
    yearsBox.querySelectorAll("button").forEach(b => {
      const y = +b.dataset.year, on = y === state.year, ok = available(y, state.measure);
      b.disabled = !ok;
      b.title = ok ? "" : "Skutočnosť za tento rok nie je k dispozícii.";
      b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1;
      if (on) b.scrollIntoView({ block: "nearest", inline: "center" });
    });
  }
  function setState(year, measure) {
    if (measure && measure !== state.measure) {
      state.measure = measure;
      if (!available(state.year, measure)) {   // fall back to the latest year that has it
        state.year = YEARS.filter(y => available(y, measure)).pop();
      }
    }
    if (year && available(year, state.measure)) state.year = year;
    hideTip(); writeHash(); render();
  }
  const seg = document.querySelector(".seg");
  seg.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if (b) setState(null, b.dataset.measure);
  });
  seg.addEventListener("keydown", ev => {   // radio group: arrows move the selection
    if (!["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
    ev.preventDefault();
    setState(null, state.measure === "schvaleny" ? "skutocnost" : "schvaleny");
    seg.querySelector(`[data-measure="${state.measure}"]`).focus();
  });
  yearsBox.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if (b && !b.disabled) setState(+b.dataset.year);
  });
  yearsBox.addEventListener("keydown", ev => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    const ok = YEARS.filter(y => available(y, state.measure)), i = ok.indexOf(state.year);
    const n = ok[Math.max(0, Math.min(ok.length - 1, i + (ev.key === "ArrowRight" ? 1 : -1)))];
    setState(n);
    yearsBox.querySelector(`[data-year="${n}"]`).focus();
  });
  window.addEventListener("hashchange", () => { hideTip(); readHash(); render(); });

  // ---- time chart: 100 % stacked columns, fixed band order & colours ----
  const tc = $("tc");
  function drawTime() {
    const m = state.measure, n = YEARS.length;
    const avail = tc.parentElement.clientWidth;
    const colW = Math.max(30, Math.min(44, (avail - 60) / n)), gap = Math.round(colW * .22);
    const ml = 34, mr = 8, mt = 10, mb = 66, ph = 360;
    const W = Math.round(ml + mr + n * colW), H = mt + ph + mb;
    const svg = el("svg", { id: "tcsvg", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group",
      "aria-label": `Podiel jednotlivých oblastí na výdavkoch štátnej kasy ${YEARS[0]} až ${YEARS[n - 1]} (${MEASURE_LABEL[m]})` });
    for (let p = 0; p <= 100; p += 25) {
      const yy = mt + ph - ph * p / 100;
      el("line", { x1: ml, x2: W - mr, y1: yy, y2: yy, stroke: "#e8eaf0" }, svg);
      text(svg, ml - 6, yy + 4, p + "\u00a0€", "ax", 11, "#6b7280").setAttribute("text-anchor", "end");
    }
    YEARS.forEach((y, i) => {
      const e = entry(y, m), x = ml + i * colW;
      const g = el("g", { class: "col" + (y === state.year ? " sel" : ""), "data-year": y, tabindex: e ? 0 : -1, role: "button", "aria-describedby": "tip" }, svg);
      el("rect", { class: "colbg", x, y: mt, width: colW, height: ph, fill: "transparent" }, g);
      const yl = text(g, x + colW / 2, mt + ph + 16, "’" + String(y).slice(2), "yl", 11.5, "#6b7280");
      yl.setAttribute("text-anchor", "middle");
      if (!e) {
        el("rect", { x: x + gap / 2, y: mt, width: colW - gap, height: ph, fill: "none", stroke: "#cdd2dc", "stroke-dasharray": "4 3" }, g);
        const t = text(g, x + colW / 2, mt + ph / 2, "zatiaľ nie", "ax", 10, "#6b7280");
        t.setAttribute("text-anchor", "middle"); t.setAttribute("transform", `rotate(-90 ${x + colW / 2} ${mt + ph / 2})`);
        g.setAttribute("aria-label", `${y}: skutočnosť zatiaľ nie je k dispozícii`);
        return;
      }
      let acc = 0;
      const est = !!e.estimate;
      for (const t of TILES) {
        const tv = (e.tiles[t.id] || {}).v || 0;
        if (tv <= 0) continue;
        const h = ph * tv / e.total, yy = mt + ph - ph * acc / e.total - h;
        el("rect", { class: "band", "data-tile": t.id, x: x + gap / 2, y: yy, width: colW - gap, height: Math.max(0, h - .6), fill: COLOR[t.id],
          "fill-opacity": est ? .6 : 1 }, g);
        acc += tv;
      }
      if (est) {   // an estimated split is hatched and labelled, never shown like data
        if (!svg.querySelector("#hatch")) {
          const defs = el("defs", {}, svg);
          const pat = el("pattern", { id: "hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
          el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "#fff", "stroke-width": 2, "stroke-opacity": .7 }, pat);
        }
        el("rect", { x: x + gap / 2, y: mt, width: colW - gap, height: ph, fill: "url(#hatch)", "pointer-events": "none" }, g);
        text(g, x + colW / 2, mt + ph + 42, "odhad", "ax", 9.5, "#8a5a00").setAttribute("text-anchor", "middle");
      }
      const prev = entry(y - 1, m);
      if (prev) {
        const gr = 100 * (e.total / prev.total - 1);
        const t2 = text(g, x + colW / 2, mt + ph + 30, (gr >= 0 ? "+" : "−") + nf0.format(Math.abs(gr)) + "\u00a0%", "ax", 9.5, "#6b7280");
        t2.setAttribute("text-anchor", "middle");
      }
      if (D.events[y]) {
        el("circle", { cx: x + colW / 2, cy: mt + ph + 41, r: 3, fill: "#1b2130" }, g);
      }
      const top = groupSums(e).sort((a, b) => b.v - a.v).slice(0, 3).map(s => `${s.g.name} ${eur(share(s.v, e))}`).join(", ");
      g.setAttribute("aria-label", `${y}: ${mld(e.total)}; ${top}. Enter zobrazí rok v hlavnom grafe.`);
    });
    text(svg, ml, H - 4, "pod rokom: rast výdavkov oproti predchádzajúcemu roku · ● poznámka k roku (v bublinke)", "ax", 10, "#6b7280");
    tc.replaceChildren(svg);
  }
  function colTip(y, tileId) {
    const e = entry(y, state.measure);
    if (!e) return `<div class="tt">${y}</div><div class="meta">Skutočnosť za tento rok nie je k dispozícii.</div>`;
    let head = `<div class="tt">${y} · ${MEASURE_LABEL[state.measure]}${e.provisional ? " (predbežné)" : ""}${e.estimate ? ' <span class="prov">odhad</span>' : ""}</div><div class="meta">100&nbsp;€ = ${amt(e.total)}</div>`;
    if (tileId && e.tiles[tileId]) {
      const t = e.tiles[tileId], approx = e.estimate ? "≈ " : "";
      head += `<div class="big">${approx}${eur(share(t.v, e))}</div><div class="meta">${esc(TILE[tileId].name)} · ${approx}${amt(t.v)}</div>`;
    }
    const rows = groupSums(e).map(({ g, v }) => `<div class="r"><span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;background:${g.color}"></span>${esc(g.name)}</span><span>${eur(share(v, e))}</span></div>`).join("");
    return head + `<div class="rows">${rows}</div>` + (e.estimate ? `<div class="note">${EST_LINE}</div>` : "")
      + (D.events[y] ? `<div class="note">${esc(D.events[y])}</div>` : "");
  }
  tc.addEventListener("pointermove", ev => {
    if (ev.pointerType !== "mouse") return;
    const c = ev.target.closest(".col"); if (!c) return hideTip();
    const s = ev.target.closest(".band");
    openedBy = "mouse";
    showTip(colTip(+c.dataset.year, s && s.dataset.tile), ev.clientX, ev.clientY);
  });
  tc.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") hideTip(); });
  tc.addEventListener("click", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    const y = +c.dataset.year, s = ev.target.closest(".band");
    if (available(y, state.measure)) setState(y);   // redraws the chart
    if (lastPointer.type !== "mouse") { openedBy = "tap"; showTip(colTip(y, s && s.dataset.tile), ev.clientX, ev.clientY, true); }
  });
  tc.addEventListener("focusin", ev => {
    const c = ev.target.closest(".col"); if (!c || fromPointer()) return;
    const b = c.getBoundingClientRect();
    openedBy = "key";
    showTip(colTip(+c.dataset.year, null), b.right, b.top + 40, true);
  });
  tc.addEventListener("focusout", () => { if (openedBy === "key") hideTip(); });
  tc.addEventListener("keydown", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setState(+c.dataset.year); tc.querySelector(`.col[data-year="${c.dataset.year}"]`).focus(); }
  });

  // ---- approved vs actually spent per year (independent of the measure toggle) ----
  const pc = $("pc");
  // slate and a darker site orange: >= 3:1 on white and on the hover/selection band (#eef1f7)
  const PC_LESS = "#64748b", PC_MORE = "#d95d24";
  const PY = YEARS.filter(y => available(y, "schvaleny") && available(y, "skutocnost"));
  const sgn = x => x >= 0 ? "+" : "−";
  function planVal(y) {
    const s = D.years[y].schvaleny, a = D.years[y].skutocnost, d = a.total - s.total;
    return { s, a, d, p: 100 * d / s.total, prov: !!a.provisional, est: !!(s.estimate || a.estimate) };
  }
  function drawPlan() {
    const n = PY.length, avail = pc.parentElement.clientWidth;
    const colW = Math.max(26, Math.min(44, (avail - 60) / n));
    const ml = 48, mr = 12, mt = 26, ph = 210, mb = 40;
    const W = Math.round(ml + mr + n * colW), H = mt + ph + mb;
    const vals = PY.map(planVal), ds = vals.map(v => v.p);
    const step = Math.max(...ds.map(Math.abs)) > 12 ? 5 : 2;
    const top = Math.ceil(Math.max(0, ...ds) / step) * step, bot = Math.floor(Math.min(0, ...ds) / step) * step;
    const yv = v => mt + ph * (top - v) / (top - bot || 1);
    const svg = el("svg", { id: "pcsvg", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group",
      "aria-label": `Rozdiel medzi skutočnými a schválenými výdavkami ${PY[0]} až ${PY[n - 1]}` });
    text(svg, ml, mt - 12, "% schváleného rozpočtu", "ax", 11, "#6b7280");
    for (let t = bot; t <= top; t += step) {
      el("line", { x1: ml, x2: W - mr, y1: yv(t), y2: yv(t), stroke: t === 0 ? "#9aa1ae" : "#e8eaf0" }, svg);
      text(svg, ml - 6, yv(t) + 4, t > 0 ? `+${t} %` : t < 0 ? `−${-t} %` : "0", "ax", 11, "#6b7280").setAttribute("text-anchor", "end");
    }
    const pat = el("pattern", { id: "hatch3", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, el("defs", {}, svg));
    el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "#fff", "stroke-width": 2, "stroke-opacity": .7 }, pat);
    PY.forEach((y, i) => {
      const v = vals[i], x = ml + i * colW, cx = x + colW / 2, gw = colW * .22;
      const g = el("g", { class: "col" + (y === state.year ? " sel" : ""), "data-year": y, tabindex: 0, role: "button", "aria-describedby": "tip" }, svg);
      el("rect", { class: "colbg", x, y: mt, width: colW, height: ph, fill: "transparent" }, g);
      text(g, cx, H - mb + 16, "’" + String(y).slice(2), "yl", 11.5, "#6b7280").setAttribute("text-anchor", "middle");
      const y0 = yv(0), y1 = yv(ds[i]), r = { x: x + gw / 2, y: Math.min(y0, y1), width: colW - gw, height: Math.max(1, Math.abs(y1 - y0)) };
      el("rect", Object.assign({ fill: v.d < 0 ? PC_LESS : PC_MORE }, r), g);
      if (v.prov) {
        el("rect", Object.assign({ fill: "url(#hatch3)", "pointer-events": "none" }, r), g);
        text(g, cx, H - mb + 30, "predb.", "ax", 9.5, "#8a5a00").setAttribute("text-anchor", "middle");
      }
      g.setAttribute("aria-label", `${y}: rozdiel ${sgn(v.d)}${mld(Math.abs(v.d))} (${sgn(v.d)}${pct(Math.abs(v.p))})${v.prov ? ", predbežné" : ""}. Enter zobrazí rok v hlavnom grafe.`);
    });
    text(svg, ml, H - 4, "pod nulou: minuli menej, než schválili · nad nulou: viac", "ax", 10, "#6b7280");
    pc.replaceChildren(svg);
  }
  function planTip(y) {
    const v = planVal(y), st = v.s.tiles, at = v.a.tiles;
    const ids = [...new Set(Object.keys(st).concat(Object.keys(at)))];
    const dv = id => ((at[id] || {}).v || 0) - ((st[id] || {}).v || 0);
    const rows = ids.sort((a, b) => Math.abs(dv(b)) - Math.abs(dv(a))).slice(0, 3)
      .map(id => `<div class="r"><span>${esc(TILE[id].short)}</span><span>${v.est ? "≈ " : ""}${sgn(dv(id))}${mld(Math.abs(dv(id)))}</span></div>`).join("");
    return `<div class="tt">${y}${v.prov ? " (predbežné)" : ""}</div>`
      + `<div class="meta">Schválené ${mld(v.s.total)} · Skutočne ${mld(v.a.total)}</div>`
      + `<div class="big">Rozdiel ${sgn(v.d)}${mld(Math.abs(v.d))} (${sgn(v.d)}${pct(Math.abs(v.p))})</div>`
      + `<div class="meta">Najväčšie rozdiely:</div><div class="rows">${rows}</div>`;
  }
  pc.addEventListener("pointermove", ev => {
    if (ev.pointerType !== "mouse") return;
    const c = ev.target.closest(".col"); if (!c) return hideTip();
    openedBy = "mouse"; showTip(planTip(+c.dataset.year), ev.clientX, ev.clientY);
  });
  pc.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") hideTip(); });
  pc.addEventListener("click", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    const y = +c.dataset.year;
    if (available(y, state.measure)) setState(y);
    if (lastPointer.type !== "mouse") { openedBy = "tap"; showTip(planTip(y), ev.clientX, ev.clientY, true); }
  });
  pc.addEventListener("focusin", ev => {
    const c = ev.target.closest(".col"); if (!c || fromPointer()) return;
    const b = c.getBoundingClientRect(); openedBy = "key";
    showTip(planTip(+c.dataset.year), b.right, b.top + 40, true);
  });
  pc.addEventListener("focusout", () => { if (openedBy === "key") hideTip(); });
  pc.addEventListener("keydown", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setState(+c.dataset.year); pc.querySelector(`.col[data-year="${c.dataset.year}"]`).focus(); }
  });

  // ---- debt service over time: bars in mld. € (top), € zo stovky (bottom), shared years ----
  const dc = $("dc");
  const DEBT_NOTE = "Od roku 2012 ide o transfer správcovi dlhu, nie o zaplatené úroky.";
  function debtVal(y, m = state.measure) {
    const e = entry(y, m);
    if (!e) return null;
    const v = (e.tiles.dlh || {}).v || 0;
    return { v, s: share(v, e), est: !!e.estimate, prov: !!e.provisional };
  }
  function drawDebt() {
    const n = YEARS.length, avail = dc.parentElement.clientWidth;
    const colW = Math.max(30, Math.min(44, (avail - 60) / n));
    const ml = 40, mr = 22, mt = 22, h1 = 190, gapP = 34, h2 = 120, mb = 40;
    const W = Math.round(ml + mr + n * colW), H = mt + h1 + gapP + h2 + mb;
    const vals = YEARS.map(y => debtVal(y));
    const maxV = Math.max(...vals.filter(Boolean).map(d => d.v)) / 1e9;
    const topV = Math.ceil(maxV * 2) / 2, topS = Math.ceil(Math.max(...vals.filter(Boolean).map(d => d.s)));
    const svg = el("svg", { id: "dcsvg", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group",
      "aria-label": `Obsluha štátneho dlhu ${YEARS[0]} až ${YEARS[n - 1]} (${MEASURE_LABEL[state.measure]})` });
    const y1 = v => mt + h1 - h1 * v / topV, y2 = s => mt + h1 + gapP + h2 - h2 * s / topS;
    text(svg, ml, mt - 8, "mld. €", "ax", 11, "#6b7280");
    for (let t = 0; t <= topV + 1e-9; t += topV > 1 ? 0.5 : 0.25) {
      el("line", { x1: ml, x2: W - mr, y1: y1(t), y2: y1(t), stroke: "#e8eaf0" }, svg);
      text(svg, ml - 6, y1(t) + 4, String(t).replace(".", ","), "ax", 11, "#6b7280").setAttribute("text-anchor", "end");
    }
    text(svg, ml, mt + h1 + gapP - 8, "€ zo stovky", "ax", 11, "#6b7280");
    for (let t = 0; t <= topS; t += topS > 4 ? 2 : 1) {
      el("line", { x1: ml, x2: W - mr, y1: y2(t), y2: y2(t), stroke: "#e8eaf0" }, svg);
      text(svg, ml - 6, y2(t) + 4, String(t), "ax", 11, "#6b7280").setAttribute("text-anchor", "end");
    }
    if (!svg.querySelector("#hatch2")) {
      const pat = el("pattern", { id: "hatch2", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, el("defs", {}, svg));
      el("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "#fff", "stroke-width": 2, "stroke-opacity": .7 }, pat);
    }
    // line in the bottom panel: a gap wherever the measure has no data (never bridged)
    let path = "", pen = false;
    YEARS.forEach((y, i) => {
      const d = vals[i], cx = ml + i * colW + colW / 2;
      if (!d) { pen = false; return; }
      path += (pen ? "L" : "M") + cx + " " + y2(d.s) + " "; pen = true;
    });
    el("path", { d: path, fill: "none", stroke: COLOR.dlh, "stroke-width": 2.5 }, svg);
    YEARS.forEach((y, i) => {
      const d = vals[i], x = ml + i * colW, cx = x + colW / 2, gw = colW * .22;
      const g = el("g", { class: "col" + (y === state.year ? " sel" : ""), "data-year": y, tabindex: d ? 0 : -1, role: "button", "aria-describedby": "tip" }, svg);
      el("rect", { class: "colbg", x, y: mt, width: colW, height: h1 + gapP + h2, fill: "transparent" }, g);
      text(g, cx, H - mb + 16, "’" + String(y).slice(2), "yl", 11.5, "#6b7280").setAttribute("text-anchor", "middle");
      if (!d) {
        text(g, cx, mt + h1 - 6, "–", "ax", 12, "#6b7280").setAttribute("text-anchor", "middle");
        g.setAttribute("aria-label", `${y}: ${MEASURE_LABEL[state.measure]} zatiaľ nie je k dispozícii`);
        return;
      }
      el("rect", { x: x + gw / 2, y: y1(d.v / 1e9), width: colW - gw, height: mt + h1 - y1(d.v / 1e9), fill: COLOR.dlh,
        "fill-opacity": d.est ? .6 : 1 }, g);
      el("circle", { cx, cy: y2(d.s), r: 3.2, fill: d.est ? "#fff" : COLOR.dlh, stroke: COLOR.dlh, "stroke-width": 1.5 }, g);
      if (d.est) {
        el("rect", { x: x + gw / 2, y: y1(d.v / 1e9), width: colW - gw, height: mt + h1 - y1(d.v / 1e9), fill: "url(#hatch2)", "pointer-events": "none" }, g);
        text(g, cx, H - mb + 30, "odhad", "ax", 9.5, "#8a5a00").setAttribute("text-anchor", "middle");
      }
      g.setAttribute("aria-label", `${y}: ${mld(d.v)}, ${eur(d.s)} zo stovky${d.est ? ", odhad" : ""}. Enter zobrazí rok v hlavnom grafe.`);
    });
    dc.replaceChildren(svg);
  }
  function debtTip(y) {
    const d = debtVal(y), meas = MEASURE_LABEL[state.measure];
    if (!d) return `<div class="tt">${y}</div><div class="meta">${meas}: zatiaľ nie je k dispozícii.</div>`;
    const p = debtVal(y - 1);   // same measure only
    const chg = p ? `<div class="yoy">Oproti ${y - 1}: <b>${d.v >= p.v ? "+" : "−"}${mld(Math.abs(d.v - p.v))}</b>, podiel ${d.s >= p.s ? "+" : "−"}${eur(Math.abs(d.s - p.s))} zo stovky</div>` : "";
    return `<div class="tt">${y} · ${meas}${d.prov ? " (predbežné)" : ""}${d.est ? ' <span class="prov">odhad</span>' : ""}</div>`
      + `<div class="big">${d.est ? "≈ " : ""}${mld(d.v)}</div><div class="meta">${d.est ? "≈ " : ""}${eur(d.s)} zo stovky štátnej kasy</div>`
      + chg + lowNote(y) + (y >= 2012 ? `<div class="note">${DEBT_NOTE}</div>` : "");
  }
  // transfer years (since 2012) where the actual transfer fell far short of the approved one
  // (2020: 0,80 of 1,16; 2021: 0,66 of 1,11 mld. €)
  function lowNote(y) {
    const a = debtVal(y, "skutocnost"), s = debtVal(y, "schvaleny");
    if (y < 2012 || !a || !s || a.v >= 0.75 * s.v) return "";
    return `<div class="note">Transfer: ${mld(a.v)} zo schválených ${mld(s.v)}.</div>`;
  }
  dc.addEventListener("pointermove", ev => {
    if (ev.pointerType !== "mouse") return;
    const c = ev.target.closest(".col"); if (!c) return hideTip();
    openedBy = "mouse"; showTip(debtTip(+c.dataset.year), ev.clientX, ev.clientY);
  });
  dc.addEventListener("pointerleave", ev => { if (ev.pointerType === "mouse") hideTip(); });
  dc.addEventListener("click", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    const y = +c.dataset.year;
    if (available(y, state.measure)) setState(y);
    if (lastPointer.type !== "mouse") { openedBy = "tap"; showTip(debtTip(y), ev.clientX, ev.clientY, true); }
  });
  dc.addEventListener("focusin", ev => {
    const c = ev.target.closest(".col"); if (!c || fromPointer()) return;
    const b = c.getBoundingClientRect(); openedBy = "key";
    showTip(debtTip(+c.dataset.year), b.right, b.top + 40, true);
  });
  dc.addEventListener("focusout", () => { if (openedBy === "key") hideTip(); });
  dc.addEventListener("keydown", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setState(+c.dataset.year); dc.querySelector(`.col[data-year="${c.dataset.year}"]`).focus(); }
  });

  // ---- render all ----
  function render() { drawControls(); drawText(); drawTreemap(); drawTime(); drawPlan(); drawDebt(); }
  let rz = 0;
  window.addEventListener("resize", () => { cancelAnimationFrame(rz); rz = requestAnimationFrame(() => { drawTreemap(); drawTime(); drawPlan(); drawDebt(); }); });

  // ---- PNG export (copy / download) with title, scope caveat and source baked in ----
  const FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
  const EXPORT_CSS = `text{font-family:${FONT}}.tl-amt{font-weight:700}.tl-name{font-weight:500}.tile .sub{fill:none;stroke:rgba(255,255,255,.85);stroke-width:1}`;
  const SCOPE = "Štátny rozpočet a Sociálna poisťovňa bez vzájomných transferov. Bez zdravotných poisťovní, obcí a krajov.";
  function exportMeta(which) {
    const meas = MEASURE_LABEL[state.measure], e = entry();
    if (which === "tm") return {
      title: `Kam ide stovka zo štátnej kasy ${state.year}${e.estimate ? " (odhad)" : ""}`,
      sub: `100 € = ${mld(e.total)} výdavkov (${meas}${e.provisional ? ", predbežné údaje" : ""})`,
      legend: true,
      extra: [e.estimate ? `${state.year}: ${EST_LINE.charAt(0).toLowerCase() + EST_LINE.slice(1)}` : "",
        smallList()].concat(D.footnoted.filter(id => e.tiles[id])
        .map(id => `${SUP[FOOT[id]]} ${TILE[id].name}: ${TILE[id].note}`)).filter(Boolean)
    };
    const prov = YEARS.some(y => (entry(y) || {}).provisional);
    const estY = YEARS.filter(y => isEst(y, state.measure));
    if (which === "pc") return {
      title: `Plán a skutočnosť, ${PY[0]} – ${PY[PY.length - 1]}`,
      sub: `Skutočné výdavky oproti schváleným, v % schváleného rozpočtu · sivá: menej, oranžová: viac${PY.some(y => planVal(y).prov) ? " · šrafované: predbežné" : ""}`,
      legend: false, extra: ["Celkový rozdiel robia najmä nevyčerpané peniaze, prostriedky z minulých rokov a eurofondy; presuny rezerv menia len rozdelenie medzi oblasťami."] };
    if (which === "dc") return {
      title: `Obsluha štátneho dlhu, ${YEARS[0]} – ${YEARS[YEARS.length - 1]}`,
      sub: `${meas}${prov ? " (posledný uzavretý rok predbežne)" : ""} · hore mld. €, dole € zo stovky štátnej kasy${estY.length ? ` · ${estY.join(", ")}: odhad (šrafované)` : ""}`,
      legend: false, extra: [DEBT_NOTE] };
    return { title: `Stovka zo štátnej kasy v čase, ${YEARS[0]} – ${YEARS[YEARS.length - 1]}`,
      sub: `${meas}${prov ? " (posledný uzavretý rok predbežne)" : ""}${estY.length ? ` · ${estY.join(", ")}: rozdelenie je odhad (šrafované)` : ""} · rovnaká výška stĺpcov = podiely, nie rast výdavkov`, legend: true,
      extra: estY.length ? [`${estY.join(", ")}: ${EST_LINE}`] : [] };
  }
  function smallList() {
    const bs = [...$("small").querySelectorAll("button")];
    return bs.length ? "Menšie oblasti: " + bs.map(b => `${b.title} ${b.querySelector("b").textContent}`).join(", ") : "";
  }
  function wrapLines(g, str, maxW) {
    const words = str.split(" "), lines = []; let cur = "";
    for (const w of words) { const t = cur ? cur + " " + w : w; if (g.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
    if (cur) lines.push(cur);
    return lines;
  }
  function rasterize(svg, meta, cb) {
    const W = +svg.getAttribute("width"), H = +svg.getAttribute("height"), S = 2, pad = 16;
    const clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", SVGNS);
    clone.querySelectorAll(".hl,.sel,.on").forEach(n => n.classList.remove("hl", "on"));
    const st = document.createElementNS(SVGNS, "style"); st.textContent = EXPORT_CSS; clone.insertBefore(st, clone.firstChild);
    const img = new Image();
    img.onload = () => {
      const CW = Math.max(W + 2 * pad, 640);
      const probe = document.createElement("canvas").getContext("2d");
      probe.font = `700 20px ${FONT}`;
      const titleL = wrapLines(probe, meta.title, CW - 2 * pad);
      probe.font = `13px ${FONT}`;
      const subL = wrapLines(probe, meta.sub, CW - 2 * pad);
      probe.font = `12px ${FONT}`;
      const scope = (meta.extra || []).flatMap(x => wrapLines(probe, x, CW - 2 * pad)).concat(wrapLines(probe, SCOPE, CW - 2 * pad));
      const legendItems = meta.legend ? groupSums(entry()).map(s => s.g) : [];
      const head = 8 + titleL.length * 26 + subL.length * 18 + 14, legendH = legendItems.length ? 26 : 0, foot = 26 + scope.length * 16;
      const c = document.createElement("canvas");
      c.width = CW * S; c.height = (head + H + legendH + foot) * S;
      const g = c.getContext("2d"); g.scale(S, S);
      g.fillStyle = "#fff"; g.fillRect(0, 0, CW, head + H + legendH + foot);
      g.fillStyle = "#1b2130"; g.font = `700 20px ${FONT}`; g.textBaseline = "alphabetic";
      let hy = 28;
      for (const l of titleL) { g.fillText(l, pad, hy); hy += 26; }
      g.fillStyle = "#6b7280"; g.font = `13px ${FONT}`;
      hy -= 6;
      for (const l of subL) { g.fillText(l, pad, hy); hy += 18; }
      g.drawImage(img, pad, head, W, H);
      let lx = pad, ly = head + H + 18;
      g.font = `600 12px ${FONT}`;
      for (const gr of legendItems) {
        g.fillStyle = gr.color; g.fillRect(lx, ly - 10, 11, 11);
        g.fillStyle = "#1b2130"; g.fillText(gr.name, lx + 16, ly); lx += 26 + g.measureText(gr.name).width;
      }
      let fy = head + H + legendH + 16;
      g.font = `12px ${FONT}`; g.fillStyle = "#6b7280";
      for (const l of scope) { g.fillText(l, pad, fy); fy += 16; }
      g.font = `600 13px ${FONT}`; g.fillStyle = "#2f6fed"; g.fillText(D.site, pad, fy + 4);
      g.textAlign = "right"; g.fillStyle = "#6b7280"; g.font = `12px ${FONT}`;
      g.fillText("Projekt Žltá Stopa · dáta: rozpocet.sk (MF SR)", CW - pad, fy + 4);
      cb(c);
    };
    img.onerror = () => cb(null);
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(clone));
  }
  function flash(btn, txt) {
    const o = btn.dataset.orig || btn.textContent; btn.dataset.orig = o;
    btn.textContent = txt; btn.classList.add("ok");
    setTimeout(() => { btn.textContent = o; btn.classList.remove("ok"); }, 1600);
  }
  function dl(blob, name) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name + ".png"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
  }
  const toBlob = (svg, meta) => new Promise(res => rasterize(svg, meta, c => c ? c.toBlob(res, "image/png") : res(null)));
  document.addEventListener("click", ev => {
    const btn = ev.target.closest(".ct"); if (!btn) return;
    const which = btn.closest(".chart-tools").dataset.chart;
    const svg = which === "tm" ? tmSvg : $(which + "svg");
    if (!svg) return;
    const meta = exportMeta(which);
    const name = { tm: `stovka-${state.year}-${state.measure}`, tc: `stovka-v-case-${state.measure}`,
                   dc: `obsluha-dlhu-${state.measure}`, pc: "plan-a-skutocnost" }[which];
    const save = p => p.then(b => { if (b) { dl(b, name); flash(btn, "Stiahnuté ✓"); } else flash(btn, "Chyba"); });
    if (btn.dataset.act === "download") return save(toBlob(svg, meta));
    if (navigator.clipboard && window.ClipboardItem) {   // Safari needs write() inside the gesture
      const p = toBlob(svg, meta);
      navigator.clipboard.write([new ClipboardItem({ "image/png": p })])
        .then(() => flash(btn, "Skopírované ✓")).catch(() => save(p));
    } else save(toBlob(svg, meta));
  });

  readHash(); writeHash(); render();
})();
