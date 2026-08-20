/* Entity Atlas — two views over one dataset.
 *
 *   Entity grid   : categories as cards, entities as chips, relations as curves.
 *   Source search : pick entities, list every source that mentions them, and
 *                   open any source on its own page with its recognition trace.
 *
 * Both views read window.ATLAS (see data-loader.js). Routing is hash-based so
 * any state is linkable: #grid/<entity>, #search/<entity,entity>, #source/<id>.
 */

const S = {
  tab: "grid",
  selected: null,
  hiddenTypes: new Set(),
  gridFilter: "",
  expanded: new Set(),          // types shown in full rather than capped
  curves: true,
  coMention: false,
  picked: [],                   // entity ids chosen in the search tab
  query: "",
  mode: "any",
  sort: "relevance",
  kinds: new Set(),             // empty = all source kinds
  openSource: null,
  cursor: -1,                   // keyboard position in the suggestion list
};

const CAP = { site: 84, region: 53, company: 58, chip: 49, country: 35, component: 8 };
const KIND_LABEL = {
  news: "news", vendor: "vendor doc", registry: "registry", filing: "filing",
  government: "government", paper: "paper", dataset: "dataset", pricing: "pricing",
  report: "report",
};

const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = n => (n == null ? "—" : n.toLocaleString("en-US"));

function dot(color, size = 7) {
  return `<span class="dot" style="background:${color};width:${size}px;height:${size}px"></span>`;
}
function typeDot(e, size) { return dot(ATLAS.color(e), size); }

/* ====================================================================== */
/* top bar                                                                */
/* ====================================================================== */
function renderTopStats() {
  const st = ATLAS.raw.stats;
  $("#topstats").innerHTML = [
    [fmt(st.entities), "entities"],
    [fmt(st.relations), "relations"],
    [fmt(st.sources), "sources"],
    [fmt(st.recognitions), "recognitions"],
  ].map(([v, k]) => `<div><b>${v}</b>${k}</div>`).join("");
  $("#brand-sub").textContent =
    `${st.sources} sources · ${st.entities} entities · built ${ATLAS.raw.generated_at}`;
}

function setTab(tab, { push = true } = {}) {
  S.tab = tab;
  $$("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $("#tab-grid").classList.toggle("on", tab === "grid");
  $("#tab-search").classList.toggle("on", tab === "search");
  if (tab === "grid") requestAnimationFrame(drawWires);
  if (push) writeHash();
}

/* ====================================================================== */
/* GRID — legend, cards, wires                                            */
/* ====================================================================== */
function renderLegend() {
  const counts = ATLAS.raw.stats.by_type;
  $("#legend").innerHTML = Object.entries(ATLAS.raw.types).map(([t, meta]) => `
    <div class="legend-row${S.hiddenTypes.has(t) ? " off" : ""}" data-type="${t}">
      ${dot(meta.color, 9)}<span class="nm">${esc(meta.label)}</span>
      <span class="ct">${fmt(counts[t] || 0)}</span>
    </div>`).join("");
  $$("#legend .legend-row").forEach(row => {
    row.onclick = () => {
      const t = row.dataset.type;
      S.hiddenTypes.has(t) ? S.hiddenTypes.delete(t) : S.hiddenTypes.add(t);
      renderLegend(); renderCards(); renderSide();
    };
  });
}

function visibleEntities(type) {
  const q = S.gridFilter.trim().toLowerCase();
  let list = ATLAS.byType.get(type) || [];
  if (q) {
    list = list.filter(e => e.name.toLowerCase().includes(q) ||
                            (e.aliases || []).some(a => a.includes(q)));
  }
  return list;
}

function renderCards() {
  const wrap = $("#cards");
  const types = Object.keys(ATLAS.raw.types).filter(t => !S.hiddenTypes.has(t));
  wrap.innerHTML = types.map(t => {
    const all = visibleEntities(t);
    const cap = S.expanded.has(t) ? all.length : (CAP[t] || 60);
    const shown = all.slice(0, cap);
    const meta = ATLAS.raw.types[t];
    const wide = t === "site" || all.length > 60;
    return `
      <div class="card${wide ? " wide" : ""}" data-type="${t}">
        <div class="card-head">
          ${dot(meta.color, 9)}<span class="t">${esc(meta.label)}</span>
          ${all.length > shown.length
            ? `<span class="more" data-more="${t}">show all ${fmt(all.length)}</span>`
            : (S.expanded.has(t) && all.length > (CAP[t] || 60)
                ? `<span class="more" data-more="${t}">show top ${CAP[t] || 60}</span>` : "")}
          <span class="n">${fmt(shown.length)}${all.length > shown.length ? " / " + fmt(all.length) : ""}</span>
        </div>
        <div class="card-body${S.expanded.has(t) ? "" : " capped"}">
          ${shown.map(nodeChip).join("") || `<span class="faint">no matches</span>`}
        </div>
      </div>`;
  }).join("");

  $$("#cards .more").forEach(el => {
    el.onclick = ev => {
      ev.stopPropagation();
      const t = el.dataset.more;
      S.expanded.has(t) ? S.expanded.delete(t) : S.expanded.add(t);
      renderCards(); paintSelection();
    };
  });
  $$("#cards .node").forEach(el => {
    el.onclick = () => selectEntity(el.dataset.id);
    el.onmouseenter = ev => showTip(ev, tipFor(ATLAS.entities.get(el.dataset.id)));
    el.onmousemove = ev => moveTip(ev);
    el.onmouseleave = hideTip;
  });
  paintSelection();
}

function nodeChip(e) {
  const n = (e.sources || []).length;
  return `<span class="node${e.weight >= 5 ? " big" : ""}" data-id="${e.id}" title="">
    ${typeDot(e)}<span class="nm">${esc(e.name)}</span>${n ? `<span class="ct">${fmt(n)}</span>` : ""}
  </span>`;
}

function tipFor(e) {
  if (!e) return "";
  const rel = ATLAS.neighbours(e.id, { includeCoMention: true }).length;
  return `<div class="tn">${esc(e.name)}</div>
    <div class="tr">${esc(ATLAS.type(e.type).label)}</div>
    <div class="tr">${fmt((e.sources || []).length)} sources · ${fmt(rel)} relations</div>
    ${e.summary ? `<div class="tr" style="margin-top:4px">${esc(e.summary.slice(0, 150))}</div>` : ""}`;
}

function selectEntity(id, { push = true } = {}) {
  S.selected = id === S.selected ? null : id;
  paintSelection();
  renderSide();
  renderEntityDetail();
  if (push) writeHash();
}

function paintSelection() {
  const sel = S.selected;
  const near = new Set();
  if (sel) {
    ATLAS.neighbours(sel, { includeCoMention: S.coMention })
      .forEach(n => near.add(n.other.id));
  }
  $$("#cards .node").forEach(el => {
    const id = el.dataset.id;
    el.classList.toggle("sel", id === sel);
    el.classList.toggle("rel", !!sel && near.has(id));
    el.classList.toggle("dim", !!sel && id !== sel && !near.has(id));
  });
  $$("#grid-side .ent-row").forEach(el =>
    el.classList.toggle("on", el.dataset.id === sel));
  drawWires();
  $("#grid-hint").textContent = sel
    ? `${ATLAS.entities.get(sel).name} — ${near.size} related entities`
    : "Click an entity to light up its relations";
}

function drawWires() {
  const svg = $("#wires");
  const scroller = $("#grid-scroll");
  if (!svg || !scroller) return;
  svg.setAttribute("width", scroller.scrollWidth);
  svg.setAttribute("height", scroller.scrollHeight);
  svg.style.width = scroller.scrollWidth + "px";
  svg.style.height = scroller.scrollHeight + "px";
  if (!S.selected || !S.curves) { svg.innerHTML = ""; return; }

  const box = scroller.getBoundingClientRect();
  const pos = id => {
    const el = $(`#cards .node[data-id="${cssEscape(id)}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {
      x: r.left - box.left + scroller.scrollLeft + r.width / 2,
      y: r.top - box.top + scroller.scrollTop + r.height / 2,
    };
  };
  const from = pos(S.selected);
  if (!from) { svg.innerHTML = ""; return; }

  const parts = [];
  ATLAS.neighbours(S.selected, { includeCoMention: S.coMention }).forEach(n => {
    const to = pos(n.other.id);
    if (!to) return;
    const colour = ATLAS.color(n.other);
    const dx = to.x - from.x, dy = to.y - from.y;
    const bow = Math.min(120, Math.hypot(dx, dy) * 0.26);
    const c1 = { x: from.x + dx * 0.35, y: from.y + dy * 0.15 - bow };
    const c2 = { x: from.x + dx * 0.65, y: from.y + dy * 0.85 - bow };
    const w = Math.max(0.7, Math.min(2.6, (n.rel.weight || 1) * 0.5));
    parts.push(`<path d="M${from.x},${from.y} C${c1.x},${c1.y} ${c2.x},${c2.y} ${to.x},${to.y}"
      fill="none" stroke="${colour}" stroke-width="${w}" stroke-opacity="0.5"
      stroke-linecap="round"/>`);
  });
  parts.push(`<circle cx="${from.x}" cy="${from.y}" r="4.5" fill="#fff" fill-opacity="0.9"/>`);
  svg.innerHTML = parts.join("");
}

function cssEscape(s) { return String(s).replace(/"/g, '\\"'); }

/* left rail: type lists, or the relations of the selected entity */
function renderSide() {
  const host = $("#grid-side");
  if (S.selected) {
    const e = ATLAS.entities.get(S.selected);
    const groups = new Map();
    ATLAS.neighbours(S.selected, { includeCoMention: true }).forEach(n => {
      const verb = n.rel.verb + (n.outgoing ? "" : " ←");
      if (!groups.has(verb)) groups.set(verb, []);
      groups.get(verb).push(n.other);
    });
    const total = Array.from(groups.values()).reduce((a, b) => a + b.length, 0);
    host.innerHTML = `
      <div class="side-group">
        <div class="side-head">Connected to <span class="v">${esc(e.name)}</span></div>
        <div class="faint" style="padding:0 5px 8px">${fmt(total)} relations</div>
        ${Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length).map(([verb, list]) => `
          <div class="rel-group">
            <div class="rel-verb">${esc(verb)} · ${list.length}</div>
            ${list.slice(0, 40).sort((a, b) => b.weight - a.weight)
              .map(o => `<div class="ent-row" data-id="${o.id}">${typeDot(o)}
                 <span class="nm">${esc(o.name)}</span>
                 <span class="ct">${fmt((o.sources || []).length)}</span></div>`).join("")}
            ${list.length > 40 ? `<div class="faint" style="padding:2px 6px">+${list.length - 40} more</div>` : ""}
          </div>`).join("")}
      </div>`;
  } else {
    const types = Object.keys(ATLAS.raw.types).filter(t => !S.hiddenTypes.has(t));
    host.innerHTML = types.map(t => {
      const list = visibleEntities(t).slice(0, 28);
      if (!list.length) return "";
      return `<div class="side-group">
        <div class="side-head">${esc(ATLAS.raw.types[t].label)}
          <span class="v">top ${list.length}</span></div>
        ${list.map(e => `<div class="ent-row" data-id="${e.id}">${typeDot(e)}
           <span class="nm">${esc(e.name)}</span>
           <span class="ct">${fmt((e.sources || []).length)}</span></div>`).join("")}
      </div>`;
    }).join("");
  }
  $$("#grid-side .ent-row").forEach(el => {
    el.onclick = () => selectEntity(el.dataset.id);
    el.onmouseenter = ev => showTip(ev, tipFor(ATLAS.entities.get(el.dataset.id)));
    el.onmousemove = moveTip;
    el.onmouseleave = hideTip;
  });
}

/* right rail: the selected entity */
function renderEntityDetail() {
  const host = $("#entity-detail");
  if (!S.selected) {
    const st = ATLAS.raw.stats;
    host.innerHTML = `
      <div class="dt-head"><h2>How this atlas is built</h2></div>
      <div class="dt-body">
        <p>Every source URL in the repository's datasets is resolved to entities four ways.
           Each hit records <em>how</em> it was found, so a source's page shows its working
           rather than just a list of tags.</p>
        ${Object.entries(ATLAS.raw.methods).map(([m, text]) => `
          <div style="margin-bottom:9px">
            <span class="method" style="margin:0 0 3px">${m}</span>
            <div class="muted" style="font-size:12px">${esc(text)}</div>
          </div>`).join("")}
        <h3 class="sub">Sources by kind</h3>
        ${Object.entries(st.by_kind).sort((a, b) => b[1] - a[1]).map(([k, n]) => `
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
            <span class="kind ${k}">${esc(KIND_LABEL[k] || k)}</span>
            <span class="muted" style="font-size:12px">${fmt(n)}</span>
          </div>`).join("")}
        <h3 class="sub">Sources by dataset</h3>
        ${Object.entries(st.by_dataset).sort((a, b) => b[1] - a[1]).map(([k, n]) => `
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px">
            <span>${esc(k)}</span><span class="faint">${fmt(n)}</span>
          </div>`).join("")}
      </div>`;
    return;
  }
  const e = ATLAS.entities.get(S.selected);
  const srcs = ATLAS.sourcesFor(e.id).sort((a, b) =>
    (b.date || "").localeCompare(a.date || "") || a.publisher.localeCompare(b.publisher));
  const shown = srcs.slice(0, 25);
  const groups = new Map();
  ATLAS.neighbours(e.id, { includeCoMention: true }).forEach(n => {
    if (!groups.has(n.rel.verb)) groups.set(n.rel.verb, []);
    groups.get(n.rel.verb).push(n.other);
  });

  host.innerHTML = `
    <div class="dt-head">
      <h2>${esc(e.name)}</h2>
      <span class="badge" style="background:${ATLAS.color(e)};color:#06111c">
        ${esc(ATLAS.type(e.type).label)}</span>
      ${e.vendor ? `<span class="badge" style="background:#1b2436;color:var(--dim)">${esc(e.vendor)}</span>` : ""}
      ${e.status ? `<span class="badge" style="background:#1b2436;color:var(--dim)">${esc(e.status.replace(/_/g, " "))}</span>` : ""}
    </div>
    <div class="dt-body">
      ${e.summary ? `<p>${esc(e.summary)}</p>` : ""}
      ${(e.metrics || []).length ? `<div class="metrics">${e.metrics.map(([k, v]) =>
        `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</div>` : ""}
      ${e.aliases && e.aliases.length ? `<h3 class="sub">Recognised as</h3>
        <div class="tags">${e.aliases.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</div>` : ""}

      <h3 class="sub">Relations <span class="n">${fmt(Array.from(groups.values())
        .reduce((a, b) => a + b.length, 0))}</span></h3>
      ${Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length).map(([verb, list]) => `
        <div class="rel-group">
          <div class="rel-verb">${esc(verb)}</div>
          <div class="rel-items">${list.slice(0, 18).map(o =>
            `<span class="pill" data-goto="${o.id}">${typeDot(o, 6)}${esc(o.name)}</span>`).join("")}
            ${list.length > 18 ? `<span class="faint">+${list.length - 18}</span>` : ""}</div>
        </div>`).join("") || `<div class="faint">no relations recorded</div>`}

      <h3 class="sub">Sources mentioning this entity <span class="n">${fmt(srcs.length)}</span></h3>
      ${shown.map(s => srcCard(s, new Set([e.id]))).join("") || `<div class="faint">none</div>`}
      ${srcs.length > shown.length ? `<div class="btn" id="see-all-src">
        See all ${fmt(srcs.length)} sources in search →</div>` : ""}
    </div>`;

  $$("#entity-detail .pill[data-goto]").forEach(el =>
    el.onclick = () => selectEntity(el.dataset.goto));
  $$("#entity-detail .src").forEach(el =>
    el.onclick = () => openSource(el.dataset.sid));
  const seeAll = $("#see-all-src");
  if (seeAll) seeAll.onclick = () => { S.picked = [e.id]; S.mode = "any"; goSearch(); };
}

/* ====================================================================== */
/* source cards (shared by both tabs)                                     */
/* ====================================================================== */
function srcCard(s, highlight = new Set()) {
  const tags = s.entities.slice(0, 9).map(r => {
    const e = ATLAS.entities.get(r.entity);
    if (!e) return "";
    const on = highlight.has(r.entity);
    return `<span class="tag${on ? " hit" : ""}" title="${esc(r.methods.map(m =>
      m.method + ": " + m.span).join(" · "))}">${esc(e.name)}</span>`;
  }).join("");
  return `
    <div class="src" data-sid="${s.id}">
      <div class="src-top">
        <span class="kind ${s.kind}">${esc(KIND_LABEL[s.kind] || s.kind)}</span>
        <span class="pub">${esc(s.publisher)}</span>
        ${s.date ? `<span class="date">${esc(s.date)}</span>` : ""}
      </div>
      ${s.title ? `<div class="ttl">${esc(s.title)}</div>` : ""}
      <div class="url">${esc(s.url.replace(/^https:\/\//, "").slice(0, 110))}</div>
      ${(s.attached_to || []).length ? `<div class="attached">cited for
        ${s.attached_to.slice(0, 2).map(a => esc(a)).join(" · ")}${s.attached_to.length > 2
          ? ` <span class="faint">+${s.attached_to.length - 2}</span>` : ""}</div>` : ""}
      <div class="tags">${tags}${s.entities.length > 9
        ? `<span class="tag">+${s.entities.length - 9}</span>` : ""}</div>
    </div>`;
}

/* ====================================================================== */
/* SEARCH tab                                                             */
/* ====================================================================== */
function renderChips() {
  $("#chips").innerHTML = S.picked.map(id => {
    const e = ATLAS.entities.get(id);
    if (!e) return "";
    return `<span class="chip" data-id="${id}">${typeDot(e)}${esc(e.name)}
      <span class="x" title="Remove">×</span></span>`;
  }).join("");
  $$("#chips .chip .x").forEach(x => {
    x.onclick = () => {
      S.picked = S.picked.filter(i => i !== x.parentElement.dataset.id);
      renderChips(); runSearch(); writeHash();
    };
  });
}

function suggestions(q) {
  const query = q.trim().toLowerCase();
  const scored = [];
  ATLAS.entities.forEach(e => {
    if (S.picked.includes(e.id)) return;
    const name = e.name.toLowerCase();
    let score = 0;
    if (!query) score = e.weight;
    else if (name === query) score = 1000;
    else if (name.startsWith(query)) score = 500 - name.length;
    else if (name.includes(query)) score = 260 - name.length;
    else if ((e.aliases || []).some(a => a.startsWith(query))) score = 200;
    else if ((e.aliases || []).some(a => a.includes(query))) score = 120;
    if (!score) return;
    scored.push([score + e.weight * 3 + (e.sources || []).length * 0.05, e]);
  });
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, 12).map(s => s[1]);
}

function renderSuggest() {
  const list = suggestions(S.query);
  const box = $("#suggest");
  if (!list.length) {
    box.innerHTML = `<div class="sg-empty">No entity matches “${esc(S.query)}”.</div>`;
    box.classList.add("on");
    return;
  }
  S.cursor = Math.min(S.cursor, list.length - 1);
  box.innerHTML = list.map((e, i) => `
    <div class="sg${i === S.cursor ? " cur" : ""}" data-id="${e.id}">
      ${typeDot(e)}<span class="nm">${esc(e.name)}</span>
      <span class="ty">${esc(ATLAS.type(e.type).label)}</span>
      <span class="ct">${fmt((e.sources || []).length)} src</span>
    </div>`).join("");
  box.classList.add("on");
  $$("#suggest .sg").forEach(el => { el.onclick = () => addPick(el.dataset.id); });
}

function addPick(id) {
  if (!id || S.picked.includes(id)) return;
  S.picked.push(id);
  S.query = "";
  $("#q").value = "";
  S.cursor = -1;
  $("#suggest").classList.remove("on");
  renderChips();
  runSearch();
  writeHash();
}

function matchingSources() {
  const picked = S.picked.filter(id => ATLAS.entities.has(id));
  let list;
  if (!picked.length) {
    list = Array.from(ATLAS.sources.values());
  } else if (S.mode === "all") {
    list = Array.from(ATLAS.sources.values()).filter(s => {
      const ids = new Set(s.entities.map(r => r.entity));
      return picked.every(p => ids.has(p));
    });
  } else {
    const seen = new Set();
    list = [];
    picked.forEach(p => (ATLAS.srcByEntity.get(p) || []).forEach(sid => {
      if (!seen.has(sid)) { seen.add(sid); list.push(ATLAS.sources.get(sid)); }
    }));
  }
  if (S.kinds.size) list = list.filter(s => S.kinds.has(s.kind));

  const relevance = s => {
    let score = 0;
    s.entities.forEach(r => { if (picked.includes(r.entity)) score += 10 + r.score; });
    score += Math.min(4, s.entities.length * 0.2);
    if (s.kind === "vendor" || s.kind === "filing" || s.kind === "government") score += 1.5;
    if (s.kind === "registry") score -= 1.5;
    return score;
  };
  if (S.sort === "date") {
    list.sort((a, b) => (b.date || "").localeCompare(a.date || "") || relevance(b) - relevance(a));
  } else if (S.sort === "publisher") {
    list.sort((a, b) => a.publisher.localeCompare(b.publisher) || relevance(b) - relevance(a));
  } else {
    list.sort((a, b) => relevance(b) - relevance(a) ||
                        (b.date || "").localeCompare(a.date || ""));
  }
  return list;
}

function renderKindFilters(list) {
  const counts = {};
  list.forEach(s => { counts[s.kind] = (counts[s.kind] || 0) + 1; });
  const kinds = Object.keys(ATLAS.raw.stats.by_kind);
  $("#kind-filters").innerHTML = kinds.map(k => `
    <span class="pill${S.kinds.has(k) ? " on" : ""}" data-kind="${k}">
      ${esc(KIND_LABEL[k] || k)} <span class="faint">${fmt(counts[k] || 0)}</span></span>`).join("");
  $$("#kind-filters .pill").forEach(el => {
    el.onclick = () => {
      const k = el.dataset.kind;
      S.kinds.has(k) ? S.kinds.delete(k) : S.kinds.add(k);
      runSearch(); writeHash();
    };
  });
}

let shownLimit = 60;
function runSearch({ resetLimit = true } = {}) {
  if (resetLimit) shownLimit = 60;
  $("#source-page").classList.remove("on");
  $("#results").classList.remove("off");
  $("#results-head").classList.remove("off");

  // kind counts are computed before the kind filter is applied
  const savedKinds = S.kinds; S.kinds = new Set();
  const unfiltered = matchingSources();
  S.kinds = savedKinds;
  renderKindFilters(unfiltered);

  const list = matchingSources();
  const picked = new Set(S.picked);
  const label = S.picked.length
    ? S.picked.map(id => ATLAS.entities.get(id)?.name).filter(Boolean)
        .join(S.mode === "all" ? " AND " : " OR ")
    : "everything";
  $("#results-head").innerHTML = `
    <span class="big">${fmt(list.length)} source${list.length === 1 ? "" : "s"}</span>
    <span class="muted">for ${esc(label)}</span>`;
  $("#results").innerHTML = list.slice(0, shownLimit).map(s => srcCard(s, picked)).join("")
    || `<div class="panel-box muted">No sources match. Try “Any of”, or remove a filter.</div>`;
  if (list.length > shownLimit) {
    $("#results").innerHTML += `<div class="btn ghost" id="more-results">
      Show ${Math.min(60, list.length - shownLimit)} more of ${fmt(list.length)}</div>`;
    $("#more-results").onclick = () => { shownLimit += 60; runSearch({ resetLimit: false }); };
  }
  $$("#results .src").forEach(el => el.onclick = () => openSource(el.dataset.sid));
}

/* ---------------------------------------------------------------- source page */
function openSource(id, { push = true } = {}) {
  const s = ATLAS.sources.get(id);
  if (!s) return;
  S.openSource = id;
  setTab("search", { push: false });
  $("#results").classList.add("off");
  $("#results-head").classList.add("off");
  const page = $("#source-page");
  page.classList.add("on");

  const related = Array.from(ATLAS.sources.values())
    .filter(o => o.id !== s.id)
    .map(o => {
      const mine = new Set(s.entities.map(r => r.entity));
      const shared = o.entities.filter(r => mine.has(r.entity)).length;
      return { o, shared };
    })
    .filter(x => x.shared >= 2)
    .sort((a, b) => b.shared - a.shared)
    .slice(0, 6);

  page.innerHTML = `
    <div class="sp-head">
      <div class="grow">
        <div class="sp-meta" style="margin-bottom:7px">
          <span class="btn ghost" id="sp-back">← Back to results</span>
          <span class="kind ${s.kind}">${esc(KIND_LABEL[s.kind] || s.kind)}</span>
          <span>${esc(s.publisher)}</span>
          ${s.date ? `<span class="faint">${esc(s.date)}</span>` : ""}
          <span class="faint">${esc(s.id)}</span>
        </div>
        <h2>${esc(s.title || s.url.replace(/^https:\/\//, ""))}</h2>
        <div class="sp-meta">
          <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>
        </div>
        ${(s.attached_to || []).length ? `<div class="sp-meta" style="margin-top:6px">
          <span class="faint">cited in our datasets for</span>
          ${s.attached_to.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</div>` : ""}
        <div class="faint" style="font-size:11.5px;margin-top:6px">
          Title is derived from the URL — these datasets store bare links, not headlines.</div>
      </div>
    </div>

    <div class="panel-box">
      <h3 class="sub" style="margin-top:0">Recognised entities
        <span class="n">${s.entities.length}</span></h3>
      <table class="rec">
        <thead><tr><th>Entity</th><th>Type</th><th>How it was recognised</th><th>Score</th></tr></thead>
        <tbody>
          ${s.entities.map(r => {
            const e = ATLAS.entities.get(r.entity);
            if (!e) return "";
            return `<tr>
              <td class="ent"><span class="pill" data-goto="${e.id}">${typeDot(e, 6)}${esc(e.name)}</span></td>
              <td class="faint">${esc(ATLAS.type(e.type).label)}</td>
              <td>${r.methods.map(m => `<span class="method">${esc(m.method)}</span>
                    <code>${esc(m.span)}</code>`).join(" ")}</td>
              <td class="faint">${r.score.toFixed(1)}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
      <div class="muted" style="font-size:11.5px;margin-top:9px">
        ${Object.entries(ATLAS.raw.methods).map(([m, t]) =>
          `<div><span class="method" style="margin:0">${m}</span> ${esc(t)}</div>`).join("")}
      </div>
    </div>

    <div class="panel-box">
      <h3 class="sub" style="margin-top:0">Cited by</h3>
      <div class="tags">${s.datasets.map(d => `<span class="tag hit">${esc(d)}</span>`).join("")}</div>
      ${s.contexts.length ? `<h3 class="sub">Context that travelled with the link</h3>
        ${s.contexts.map(c => `<div class="ctx">${esc(c)}</div>`).join("")}` : ""}
      ${s.records.length ? `<h3 class="sub">Attached record${s.records.length > 1 ? "s" : ""}</h3>
        ${s.records.map(r => `<div class="metrics">${Object.entries(r).map(([k, v]) =>
          `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</div>`).join("")}` : ""}
    </div>

    ${related.length ? `<div class="panel-box">
      <h3 class="sub" style="margin-top:0">Sources sharing entities with this one</h3>
      ${related.map(x => srcCard(x.o, new Set(s.entities.map(r => r.entity)))).join("")}
    </div>` : ""}`;

  $("#sp-back").onclick = () => {
    S.openSource = null;
    page.classList.remove("on");
    runSearch({ resetLimit: false });
    writeHash();
  };
  $$("#source-page .pill[data-goto]").forEach(el => el.onclick = () => {
    S.selected = el.dataset.goto;
    setTab("grid");
    renderCards(); renderSide(); renderEntityDetail();
    requestAnimationFrame(() => {
      const node = $(`#cards .node[data-id="${cssEscape(S.selected)}"]`);
      if (node) node.scrollIntoView({ behavior: "smooth", block: "center" });
      paintSelection();
    });
  });
  $$("#source-page .src").forEach(el => el.onclick = () => openSource(el.dataset.sid));
  window.scrollTo({ top: 0 });
  $("#tab-search").scrollTop = 0;
  if (push) writeHash();
}

function goSearch() {
  setTab("search", { push: false });
  renderChips();
  runSearch();
  writeHash();
}

/* ====================================================================== */
/* tooltip                                                                */
/* ====================================================================== */
function showTip(ev, html) {
  if (!html) return;
  const t = $("#tooltip");
  t.innerHTML = html;
  t.style.opacity = 1;
  moveTip(ev);
}
function moveTip(ev) {
  const t = $("#tooltip");
  const pad = 14;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + t.offsetWidth > window.innerWidth) x = ev.clientX - t.offsetWidth - pad;
  if (y + t.offsetHeight > window.innerHeight) y = ev.clientY - t.offsetHeight - pad;
  t.style.left = x + "px"; t.style.top = y + "px";
}
function hideTip() { $("#tooltip").style.opacity = 0; }

/* ====================================================================== */
/* hash routing                                                           */
/* ====================================================================== */
function writeHash() {
  let h;
  if (S.openSource) h = `#source/${S.openSource}`;
  else if (S.tab === "search") {
    h = "#search" + (S.picked.length ? "/" + S.picked.join(",") : "");
    if (S.mode === "all") h += "?all";
  } else {
    h = "#grid" + (S.selected ? "/" + S.selected : "");
  }
  if (location.hash !== h) history.replaceState(null, "", h);
}

function readHash() {
  const raw = decodeURIComponent(location.hash.replace(/^#/, ""));
  const [path, qs] = raw.split("?");
  const [head, ...rest] = path.split("/");
  const arg = rest.join("/");
  if (head === "source" && ATLAS.sources.has(arg)) { openSource(arg, { push: false }); return; }
  if (head === "search") {
    S.mode = qs === "all" ? "all" : "any";
    S.picked = arg ? arg.split(",").filter(id => ATLAS.entities.has(id)) : [];
    $$("#match-mode button").forEach(b => b.classList.toggle("on", b.dataset.mode === S.mode));
    setTab("search", { push: false });
    renderChips(); runSearch();
    return;
  }
  if (arg && ATLAS.entities.has(arg)) S.selected = arg;
  setTab("grid", { push: false });
  renderCards(); renderSide(); renderEntityDetail();
}

/* ====================================================================== */
/* init                                                                   */
/* ====================================================================== */
ATLAS.load().then(() => {
  renderTopStats();
  renderLegend();
  renderCards();
  renderSide();
  renderEntityDetail();
  renderChips();

  $$("#tabs button").forEach(b => b.onclick = () => {
    S.openSource = null;
    $("#source-page").classList.remove("on");
    setTab(b.dataset.tab);
    if (b.dataset.tab === "search") runSearch();
  });

  $("#grid-filter").oninput = ev => {
    S.gridFilter = ev.target.value;
    renderCards(); renderSide();
  };
  $("#toggle-curves").onchange = ev => { S.curves = ev.target.checked; drawWires(); };
  $("#toggle-comention").onchange = ev => { S.coMention = ev.target.checked; paintSelection(); renderSide(); };
  $("#btn-clear").onclick = () => selectEntity(null);
  $("#grid-scroll").addEventListener("scroll", () => { hideTip(); }, { passive: true });
  window.addEventListener("resize", () => requestAnimationFrame(drawWires));

  const q = $("#q");
  q.oninput = () => { S.query = q.value; S.cursor = -1; renderSuggest(); };
  q.onfocus = () => renderSuggest();
  q.onkeydown = ev => {
    const items = $$("#suggest .sg");
    if (ev.key === "ArrowDown") { S.cursor = Math.min(S.cursor + 1, items.length - 1); renderSuggest(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { S.cursor = Math.max(S.cursor - 1, 0); renderSuggest(); ev.preventDefault(); }
    else if (ev.key === "Enter") {
      const pick = items[S.cursor >= 0 ? S.cursor : 0];
      if (pick) addPick(pick.dataset.id);
      ev.preventDefault();
    } else if (ev.key === "Escape") { $("#suggest").classList.remove("on"); }
    else if (ev.key === "Backspace" && !q.value && S.picked.length) {
      S.picked.pop(); renderChips(); runSearch(); writeHash();
    }
  };
  document.addEventListener("click", ev => {
    if (!ev.target.closest("#searchbox") && !ev.target.closest("#suggest")) {
      $("#suggest").classList.remove("on");
    }
  });
  $("#q-clear").onclick = () => {
    S.picked = []; S.query = ""; S.kinds.clear(); q.value = "";
    renderChips(); runSearch(); writeHash();
  };
  $$("#match-mode button").forEach(b => b.onclick = () => {
    S.mode = b.dataset.mode;
    $$("#match-mode button").forEach(x => x.classList.toggle("on", x === b));
    runSearch(); writeHash();
  });
  $$("#sort-mode button").forEach(b => b.onclick = () => {
    S.sort = b.dataset.sort;
    $$("#sort-mode button").forEach(x => x.classList.toggle("on", x === b));
    runSearch();
  });

  window.addEventListener("keydown", ev => {
    if (ev.key === "/" && document.activeElement.tagName !== "INPUT") {
      ev.preventDefault();
      (S.tab === "grid" ? $("#grid-filter") : $("#q")).focus();
    }
    if (ev.key === "Escape" && S.tab === "grid" && S.selected) selectEntity(null);
  });
  window.addEventListener("hashchange", readHash);

  readHash();
}).catch(err => {
  document.body.insertAdjacentHTML("afterbegin",
    `<div style="padding:20px;color:#ff8f8f">Failed to load data.json — ${esc(err.message)}</div>`);
  console.error(err);
});
