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
  const eur = x => (x > 0 && x < 0.005) ? "< 0,01 €" : nf2.format(x) + " €";
  const mil = x => nf1.format(x / 1e6) + " mil. €";
  const mld = x => nf2.format(x / 1e9) + " mld. €";
  const pct = x => nf1.format(x) + " %";
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // ---- state + URL hash (#2025-skutocnost) ----
  const state = { year: YEARS[YEARS.length - 1], measure: "schvaleny" };
  function available(y, m) { return !!(D.years[y] && D.years[y][m]); }
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
  function showTip(html, x, y) {
    tip.innerHTML = html; tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let left = x + 16, top = y + 16;
    if (left + r.width > innerWidth - 8) left = Math.max(8, x - r.width - 16);
    if (top + r.height > innerHeight - 8) top = Math.max(8, innerHeight - r.height - 8);
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function hideTip() { tip.hidden = true; tipFor = null; document.querySelectorAll(".tile.hl").forEach(t => t.classList.remove("hl")); }
  document.addEventListener("keydown", e => { if (e.key === "Escape") hideTip(); });

  function share(v, e) { return 100 * v / e.total; }
  function tileTip(id, childIdx) {
    const e = entry(), t = e.tiles[id], meta = TILE[id], g = GROUP[meta.group];
    const rows = t.c.slice(0, 6).map((c, i) => `<div class="r${i === childIdx ? " on" : ""}"><span>${esc(c[0])}</span><span>${eur(share(c[1], e))}</span></div>`).join("");
    const more = t.c.length > 6 ? `<div class="r"><span>ďalšie (${t.c.length - 6})</span><span>${eur(share(t.c.slice(6).reduce((s, c) => s + c[1], 0), e))}</span></div>` : "";
    const kap = t.k.map(k => `<div class="r"><span>${esc(k[0])}</span><span>${mil(k[1])}</span></div>`).join("");
    let yoy = "";
    const prev = entry(state.year - 1);
    if (prev) {
      const pv = prev.tiles[id] ? share(prev.tiles[id].v, prev) : 0, d = share(t.v, e) - pv;
      const cls = d > 0.005 ? "up" : d < -0.005 ? "down" : "";
      yoy = `<div class="yoy">Zmena podielu oproti ${state.year - 1}: <b class="${cls}">${d >= 0 ? "+" : "−"}${eur(Math.abs(d))}</b> zo stovky (vtedy ${eur(pv)})</div>`;
    }
    const ev = D.events[state.year] ? `<div class="note">Rok ${state.year}: ${esc(D.events[state.year])}</div>` : "";
    return `<div class="tt">${esc(meta.name)}${FOOT[id] ? SUP[FOOT[id]] : ""}</div>`
      + `<div class="big">${eur(share(t.v, e))} zo stovky</div>`
      + `<div class="meta">${mil(t.v)} · ${pct(share(t.v, e))} výdavkov štátneho rozpočtu · ${esc(g.name)}</div>`
      + (t.c.length > 1 || childIdx != null ? `<div class="rows">${rows}${more}</div>` : "")
      + (kap ? `<div class="h">Najväčšie rozpočtové kapitoly</div>${kap}` : "")
      + yoy + (meta.note ? `<div class="note">${esc(meta.note)}</div>` : "") + ev;
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
    const svg = el("svg", { id: "tmsvg", viewBox: `0 0 ${L.W} ${L.H}`, width: L.W, height: L.H, role: "img",
      "aria-label": `Kam ide stovka zo štátneho rozpočtu ${state.year} (${MEASURE_LABEL[state.measure]})` });
    const small = [];
    for (const { id, r } of L.tiles) {
      const t = e.tiles[id], fill = COLOR[id], ink = TEXT[id], s = share(t.v, e);
      const g = el("g", { class: "tile", "data-id": id, tabindex: 0, role: "button",
        "aria-label": `${TILE[id].name}: ${eur(s)} zo stovky, ${mil(t.v)}` }, svg);
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
      const amt = eur(s);
      const pad = 8, bw = labelBox.w - 2 * pad;
      if (labelBox.h >= big + 22 && bw >= textW(amt, big, 700)) {
        text(g, labelBox.x + pad, labelBox.y + pad + big * .85, amt, "tl-amt", big, ink);
        const maxLines = Math.max(1, Math.min(3, Math.floor((labelBox.h - pad - big - 4) / 15)));
        const lines = wrapName(name, 13, bw, maxLines);
        lines.forEach((ln, i) => text(g, labelBox.x + pad, labelBox.y + pad + big + 15 + i * 15, ln, "tl-name", 13, ink));
        if (!lines.length || lines[lines.length - 1].endsWith("…")) small.push(id);
      } else if (r.h >= 22 && r.w - 8 >= textW(amt, 12, 700)) {
        text(g, r.x + 4, r.y + 16, amt, "tl-amt", 12, ink);
        small.push(id);
      } else {
        small.push(id);
      }
    }
    tm.replaceChildren(svg);
    tmSvg = svg;
    // tiles whose name is not (fully) visible: list with amounts, tappable
    const sm = $("small");
    sm.innerHTML = small.length ? "<b>Menšie dlaždice:</b> " + small.sort((a, b) => e.tiles[b].v - e.tiles[a].v)
      .map(id => `<button type="button" data-id="${id}">${esc(TILE[id].name)} ${eur(share(e.tiles[id].v, e))}</button>`).join(" · ") : "";
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
  tm.addEventListener("mousemove", ev => {
    const h = tileEvent(ev);
    if (!h) return hideTip();
    highlight(h.g, h.child);
    tipFor = h.id;
    showTip(tileTip(h.id, h.child), ev.clientX, ev.clientY);
  });
  tm.addEventListener("mouseleave", () => { hideTip(); document.querySelectorAll(".sub.on").forEach(s => s.classList.remove("on")); });
  tm.addEventListener("click", ev => {   // touch: tap toggles the tooltip
    const h = tileEvent(ev);
    if (!h) return;
    if (tipFor === h.id && ev.pointerType !== "mouse") return hideTip();
    highlight(h.g, h.child); tipFor = h.id;
    showTip(tileTip(h.id, h.child), ev.clientX, ev.clientY);
  });
  tm.addEventListener("focusin", ev => {
    const g = ev.target.closest(".tile"); if (!g) return;
    const b = g.getBoundingClientRect();
    highlight(g, null); tipFor = g.dataset.id;
    showTip(tileTip(g.dataset.id, null), b.left + Math.min(b.width, 120) - 16, b.top + 10);
  });
  tm.addEventListener("focusout", hideTip);
  tm.addEventListener("keydown", ev => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    const all = [...tm.querySelectorAll(".tile")], i = all.indexOf(document.activeElement);
    if (i < 0) return;
    ev.preventDefault();
    all[(i + (ev.key === "ArrowRight" ? 1 : all.length - 1)) % all.length].focus();
  });
  $("small").addEventListener("click", ev => {
    const b = ev.target.closest("button[data-id]"); if (!b) return;
    const r = b.getBoundingClientRect();
    tipFor = b.dataset.id;
    showTip(tileTip(b.dataset.id, null), r.left, r.bottom - 8);
    ev.stopPropagation();
  });
  document.addEventListener("click", ev => { if (!ev.target.closest(".tile, #small button, .col")) hideTip(); });

  // ---- header, KPIs, legend, table ----
  function groupSums(e) {
    return GROUPS.map(g => ({ g, v: TILES.filter(t => t.group === g.id).reduce((s, t) => s + ((e.tiles[t.id] || {}).v || 0), 0) }));
  }
  function drawText() {
    const e = entry(), y = state.year, meas = MEASURE_LABEL[state.measure];
    $("ctitle").textContent = `Kam ide stovka zo štátneho rozpočtu ${y}`;
    $("csub").innerHTML = `100 € = <b>${mil(e.total)}</b> výdavkov štátneho rozpočtu (${meas}) · plocha dlaždice = podiel zo stovky`
      + (e.provisional ? `<span class="prov" title="Pred schválením záverečného účtu sa údaje ešte môžu spresniť.">predbežné</span>` : "");
    const ev = $("event");
    ev.hidden = !D.events[y];
    ev.textContent = D.events[y] ? `Rok ${y}: ${D.events[y]}` : "";
    // KPIs
    const gap = e.revenue == null ? null : 100 * (e.total - e.revenue) / e.total;
    const top = Object.entries(e.tiles).sort((a, b) => b[1].v - a[1].v)[0];
    const prevE = entry(y - 1);
    const growth = prevE ? 100 * (e.total / prevE.total - 1) : null;
    $("kpis").innerHTML =
      `<div class="kpi"><div class="n">${mld(e.total)}</div><div class="l">výdavky štátneho rozpočtu ${y} (${meas})${growth == null ? "" : `, ${growth >= 0 ? "+" : "−"}${pct(Math.abs(growth))} oproti ${y - 1}`}</div></div>`
      + `<div class="kpi"><div class="n">${e.revenue == null ? "–" : mld(e.revenue)}</div><div class="l">príjmy štátneho rozpočtu ${y}</div></div>`
      + (gap == null ? `<div class="kpi"><div class="n">–</div><div class="l">bilancia nie je k dispozícii</div></div>`
        : gap >= 0 ? `<div class="kpi"><div class="n">${eur(gap)}</div><div class="l">z každých 100 € výdavkov chýba v príjmoch (hotovostný schodok štátneho rozpočtu ${mld(e.total - e.revenue)})</div></div>`
          : `<div class="kpi"><div class="n">${eur(-gap)}</div><div class="l">na každých 100 € výdavkov zostáva v príjmoch navyše (prebytok)</div></div>`)
      + `<div class="kpi"><div class="n">${eur(share(top[1].v, e))}</div><div class="l">najväčšia dlaždica: ${esc(TILE[top[0]].name)}</div></div>`;
    // legend
    $("legend").innerHTML = groupSums(e).map(({ g, v }) => `<span><span class="sw" style="background:${g.color}"></span>${esc(g.name)}<b>${eur(share(v, e))}</b></span>`).join("");
    // table
    const prev = entry(y - 1);
    let rows = "";
    for (const { g, v } of groupSums(e)) {
      rows += `<tr class="grp"><td><span class="sw" style="background:${g.color}"></span>${esc(g.name)}</td><td></td><td>${eur(share(v, e))}</td><td>${mil(v)}</td><td></td></tr>`;
      for (const t of TILES.filter(t => t.group === g.id && e.tiles[t.id]).sort((a, b) => e.tiles[b.id].v - e.tiles[a.id].v)) {
        const tv = e.tiles[t.id].v;
        let d = "";
        if (prev) { const x = share(tv, e) - (prev.tiles[t.id] ? share(prev.tiles[t.id].v, prev) : 0); d = (x >= 0 ? "+" : "−") + nf2.format(Math.abs(x)); }
        rows += `<tr><td>${esc(t.name)}</td><td>${esc(g.name)}</td><td>${eur(share(tv, e))}</td><td>${mil(tv)}</td><td>${d}</td></tr>`;
      }
    }
    $("table").innerHTML = `<table><caption class="sr">${esc($("ctitle").textContent)}, ${meas}</caption><thead><tr><th>Dlaždica</th><th>Skupina</th><th>€ zo stovky</th><th>Suma</th><th>Zmena oproti ${y - 1}</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  // ---- controls ----
  const yearsBox = $("years");
  yearsBox.innerHTML = YEARS.map(y => `<button type="button" role="radio" data-year="${y}">${y}</button>`).join("");
  function drawControls() {
    document.querySelectorAll(".seg button").forEach(b => {
      const on = b.dataset.measure === state.measure;
      b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1;
    });
    yearsBox.querySelectorAll("button").forEach(b => {
      const y = +b.dataset.year, on = y === state.year, ok = available(y, state.measure);
      b.disabled = !ok;
      b.title = ok ? "" : "Skutočnosť za bežný rok ešte nie je uzavretá";
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
  document.querySelector(".seg").addEventListener("click", ev => {
    const b = ev.target.closest("button"); if (b) setState(null, b.dataset.measure);
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
  window.addEventListener("hashchange", () => { readHash(); render(); });

  // ---- time chart: 100 % stacked columns, fixed band order & colours ----
  const tc = $("tc");
  function drawTime() {
    const m = state.measure, n = YEARS.length;
    const avail = tc.parentElement.clientWidth;
    const colW = Math.max(30, Math.min(44, (avail - 60) / n)), gap = Math.round(colW * .22);
    const ml = 34, mr = 8, mt = 10, mb = 50, ph = 360;
    const W = Math.round(ml + mr + n * colW), H = mt + ph + mb;
    const svg = el("svg", { id: "tcsvg", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
      "aria-label": `Podiel jednotlivých oblastí na výdavkoch štátneho rozpočtu ${YEARS[0]} až ${YEARS[n - 1]} (${MEASURE_LABEL[m]})` });
    for (let p = 0; p <= 100; p += 25) {
      const yy = mt + ph - ph * p / 100;
      el("line", { x1: ml, x2: W - mr, y1: yy, y2: yy, stroke: "#e8eaf0" }, svg);
      text(svg, ml - 6, yy + 4, p + " €", "ax", 11, "#6b7280").setAttribute("text-anchor", "end");
    }
    YEARS.forEach((y, i) => {
      const e = entry(y, m), x = ml + i * colW;
      const g = el("g", { class: "col" + (y === state.year ? " sel" : ""), "data-year": y, tabindex: e ? 0 : -1, role: "button" }, svg);
      el("rect", { class: "colbg", x, y: mt, width: colW, height: ph, fill: "transparent" }, g);
      const yl = text(g, x + colW / 2, mt + ph + 16, "’" + String(y).slice(2), "yl", 11.5, "#6b7280");
      yl.setAttribute("text-anchor", "middle");
      if (!e) {
        el("rect", { x: x + gap / 2, y: mt, width: colW - gap, height: ph, fill: "none", stroke: "#cdd2dc", "stroke-dasharray": "4 3" }, g);
        const t = text(g, x + colW / 2, mt + ph / 2, "zatiaľ nie", "ax", 10, "#9aa0ab");
        t.setAttribute("text-anchor", "middle"); t.setAttribute("transform", `rotate(-90 ${x + colW / 2} ${mt + ph / 2})`);
        g.setAttribute("aria-label", `${y}: skutočnosť zatiaľ nie je k dispozícii`);
        return;
      }
      let acc = 0;
      for (const t of TILES) {
        const tv = (e.tiles[t.id] || {}).v || 0;
        if (tv <= 0) continue;
        const h = ph * tv / e.total, yy = mt + ph - ph * acc / e.total - h;
        el("rect", { class: "band", "data-tile": t.id, x: x + gap / 2, y: yy, width: colW - gap, height: Math.max(0, h - .6), fill: COLOR[t.id] }, g);
        acc += tv;
      }
      const prev = entry(y - 1, m);
      if (prev) {
        const gr = 100 * (e.total / prev.total - 1);
        const t2 = text(g, x + colW / 2, mt + ph + 30, (gr >= 0 ? "+" : "−") + nf0.format(Math.abs(gr)) + "%", "ax", 9.5, "#9aa0ab");
        t2.setAttribute("text-anchor", "middle");
      }
      if (D.events[y]) {
        el("circle", { cx: x + colW / 2, cy: mt + ph + 41, r: 3, fill: "#1b2130" }, g);
      }
      const top = groupSums(e).sort((a, b) => b.v - a.v).slice(0, 3).map(s => `${s.g.name} ${eur(share(s.v, e))}`).join(", ");
      g.setAttribute("aria-label", `${y}: ${mld(e.total)}; ${top}. Enter zobrazí rok v hlavnom grafe.`);
    });
    text(svg, ml, H - 2, "rast výdavkov oproti predch. roku · ● poznámka k roku", "ax", 10, "#9aa0ab");
    tc.replaceChildren(svg);
  }
  function colTip(y, tileId) {
    const e = entry(y, state.measure);
    if (!e) return `<div class="tt">${y}</div><div class="meta">Skutočnosť za tento rok zatiaľ nie je k dispozícii.</div>`;
    let head = `<div class="tt">${y} · ${MEASURE_LABEL[state.measure]}${e.provisional ? " (predbežné)" : ""}</div><div class="meta">100 € = ${mil(e.total)}</div>`;
    if (tileId && e.tiles[tileId]) {
      const t = e.tiles[tileId];
      head += `<div class="big">${eur(share(t.v, e))}</div><div class="meta">${esc(TILE[tileId].name)} · ${mil(t.v)}</div>`;
    }
    const rows = groupSums(e).map(({ g, v }) => `<div class="r"><span><span style="display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;background:${g.color}"></span>${esc(g.name)}</span><span>${eur(share(v, e))}</span></div>`).join("");
    return head + `<div class="rows">${rows}</div>` + (D.events[y] ? `<div class="note">${esc(D.events[y])}</div>` : "");
  }
  tc.addEventListener("mousemove", ev => {
    const c = ev.target.closest(".col"); if (!c) return hideTip();
    const s = ev.target.closest(".band");
    showTip(colTip(+c.dataset.year, s && s.dataset.tile), ev.clientX, ev.clientY);
  });
  tc.addEventListener("mouseleave", hideTip);
  tc.addEventListener("click", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    const y = +c.dataset.year, s = ev.target.closest(".band");
    if (available(y, state.measure)) setState(y);
    if (ev.pointerType !== "mouse") showTip(colTip(y, s && s.dataset.tile), ev.clientX, ev.clientY);
  });
  tc.addEventListener("focusin", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    const b = c.getBoundingClientRect();
    showTip(colTip(+c.dataset.year, null), b.right, b.top + 40);
  });
  tc.addEventListener("focusout", hideTip);
  tc.addEventListener("keydown", ev => {
    const c = ev.target.closest(".col"); if (!c) return;
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); setState(+c.dataset.year); tc.querySelector(`.col[data-year="${c.dataset.year}"]`).focus(); }
  });

  // ---- render all ----
  function render() { drawControls(); drawText(); drawTreemap(); drawTime(); }
  let rz = 0;
  window.addEventListener("resize", () => { cancelAnimationFrame(rz); rz = requestAnimationFrame(() => { drawTreemap(); drawTime(); }); });

  // ---- PNG export (copy / download) with title, scope caveat and source baked in ----
  const FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
  const EXPORT_CSS = `text{font-family:${FONT}}.tl-amt{font-weight:700}.tl-name{font-weight:500}.tile .sub{fill:none;stroke:rgba(255,255,255,.85);stroke-width:1}`;
  const SCOPE = "Štátny rozpočet (súčet kapitol) vrátane transferov Sociálnej poisťovni a zdravotným poisťovniam; ich výdavky z odvodov nie sú zahrnuté.";
  function exportMeta(which) {
    const meas = MEASURE_LABEL[state.measure], e = entry();
    if (which === "tm") return {
      title: `Kam ide stovka zo štátneho rozpočtu ${state.year}`,
      sub: `100 € = ${mil(e.total)} výdavkov (${meas}${e.provisional ? ", predbežné údaje" : ""})`,
      legend: true
    };
    const prov = YEARS.some(y => (entry(y) || {}).provisional);
    return { title: `Stovka zo štátneho rozpočtu v čase, ${YEARS[0]} – ${YEARS[YEARS.length - 1]}`,
      sub: `${meas}${prov ? " (posledný uzavretý rok predbežne)" : ""} · rovnaká výška stĺpcov = podiely, nie rast výdavkov`, legend: true };
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
      probe.font = `12px ${FONT}`;
      const scope = wrapLines(probe, SCOPE, CW - 2 * pad);
      const legendItems = meta.legend ? groupSums(entry()).map(s => s.g) : [];
      const head = 58, legendH = legendItems.length ? 26 : 0, foot = 26 + scope.length * 16;
      const c = document.createElement("canvas");
      c.width = CW * S; c.height = (head + H + legendH + foot) * S;
      const g = c.getContext("2d"); g.scale(S, S);
      g.fillStyle = "#fff"; g.fillRect(0, 0, CW, head + H + legendH + foot);
      g.fillStyle = "#1b2130"; g.font = `700 20px ${FONT}`; g.textBaseline = "alphabetic";
      g.fillText(meta.title, pad, 28);
      g.fillStyle = "#6b7280"; g.font = `13px ${FONT}`; g.fillText(meta.sub, pad, 48);
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
      g.textAlign = "right"; g.fillStyle = "#9aa0ab"; g.font = `12px ${FONT}`;
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
    const svg = which === "tm" ? tmSvg : $("tcsvg");
    if (!svg) return;
    const meta = exportMeta(which);
    const name = which === "tm" ? `stovka-${state.year}-${state.measure}` : `stovka-v-case-${state.measure}`;
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
