/* Entity Atlas — three views over one registry.
 *
 *   Entity grid      : categories as cards, entities as chips, relations as
 *                      curves, and each entity's typed parameters with the
 *                      source that filled them.
 *   Data sources     : every catalogued source line by line, and for each one
 *                      what it fills, what it should not be trusted for, and
 *                      real example records it produced.
 *   Document search  : pick entities, list every cited document that mentions
 *                      them, and open one to see its recognition trace.
 *
 * All three read window.ATLAS (see data-loader.js). Routing is hash-based so any
 * state is linkable: #grid/<entity>, #sources/<source>, #search/<entity,entity>,
 * #doc/<id>.
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
  kinds: new Set(),             // empty = all document kinds
  openDoc: null,
  openSourceId: null,           // catalogued source shown in the sources tab
  srcFilter: "",
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
  const cat = ATLAS.catalog.stats;
  $("#topstats").innerHTML = [
    [fmt(cat.sources), "sources"],
    [fmt(cat.records), "records"],
    [fmt(st.entities), "entities"],
    [fmt(st.relations), "relations"],
    [fmt(st.documents), "documents"],
  ].map(([v, k]) => `<div><b>${v}</b>${k}</div>`).join("");
  // echoes the label on the compute map's link here, so the two pages read as a pair
  $("#brand-sub").textContent =
    `information grid and search · ${cat.sources} sources · ${fmt(cat.records)} records · ` +
    `${fmt(st.entities)} entities`;
}

function setTab(tab, { push = true } = {}) {
  S.tab = tab;
  $$("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
  $("#tab-grid").classList.toggle("on", tab === "grid");
  $("#tab-sources").classList.toggle("on", tab === "sources");
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
  const n = e.document_count || 0;
  return `<span class="node${e.weight >= 5 ? " big" : ""}" data-id="${e.id}" title="">
    ${typeDot(e)}<span class="nm">${esc(e.name)}</span>${n ? `<span class="ct">${fmt(n)}</span>` : ""}
  </span>`;
}

function tipFor(e) {
  if (!e) return "";
  const rel = ATLAS.neighbours(e.id, { includeCoMention: true }).length;
  return `<div class="tn">${esc(e.name)}</div>
    <div class="tr">${esc(ATLAS.type(e.type).label)}</div>
    <div class="tr">${fmt(e.document_count)} documents · ${fmt(rel)} relations</div>
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
                 <span class="ct">${fmt(o.document_count)}</span></div>`).join("")}
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
           <span class="ct">${fmt(e.document_count)}</span></div>`).join("")}
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
    const cat = ATLAS.catalog.stats;
    host.innerHTML = `
      <div class="dt-head"><h2>How this atlas is built</h2></div>
      <div class="dt-body">
        <p>Three layers, in one direction. ${cat.sources} catalogued
           <b>sources</b> produce ${fmt(cat.records)} dated <b>records</b>, and those records
           fill the typed parameters of ${fmt(st.entities)} <b>entities</b>. Every filled
           parameter names the record and source behind it, so any number here can be
           walked back to a document.</p>
        <p class="muted" style="font-size:12px">Open the <b>Data sources</b> tab to see each
           source, what it fills, what it should not be trusted for, and real records it
           produced.</p>

        <h3 class="sub">Recognition channels</h3>
        ${Object.entries(ATLAS.raw.methods).map(([m, text]) => `
          <div style="margin-bottom:9px">
            <span class="method" style="margin:0 0 3px">${m}</span>
            <div class="muted" style="font-size:12px">${esc(text)}</div>
          </div>`).join("")}

        <h3 class="sub">Parameter coverage by type</h3>
        ${Object.entries(st.coverage || {}).sort((a, b) => b[1] - a[1]).map(([t, pct]) => `
          <div class="cov">
            <span class="nm">${dot(ATLAS.color(t), 7)}${esc(ATLAS.type(t).label)}</span>
            <span class="bar"><i style="width:${pct}%"></i></span>
            <span class="faint">${pct}%</span>
          </div>`).join("")}

        <h3 class="sub">Records by confidence</h3>
        ${Object.entries(cat.by_confidence).sort((a, b) => b[1] - a[1]).map(([k, n]) => `
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
            <span class="conf ${k}">${esc(k)}</span>
            <span class="muted" style="font-size:12px">${fmt(n)} records</span>
          </div>`).join("")}

        <h3 class="sub">Documents by kind</h3>
        ${Object.entries(st.by_kind).sort((a, b) => b[1] - a[1]).map(([k, n]) => `
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
            <span class="kind ${k}">${esc(KIND_LABEL[k] || k)}</span>
            <span class="muted" style="font-size:12px">${fmt(n)}</span>
          </div>`).join("")}
      </div>`;
    return;
  }
  const e = ATLAS.entities.get(S.selected);
  const srcs = ATLAS.documentsFor(e.id).sort((a, b) =>
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
      ${paramTable(e)}
      ${e.aliases && e.aliases.length ? `<h3 class="sub">Recognised as</h3>
        <div class="tags">${e.aliases.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</div>` : ""}
      ${(e.merged_from || []).length ? `<h3 class="sub">Names folded into this entity</h3>
        <div class="tags">${e.merged_from.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</div>` : ""}

      <h3 class="sub">Relations <span class="n">${fmt(Array.from(groups.values())
        .reduce((a, b) => a + b.length, 0))}</span></h3>
      ${Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length).map(([verb, list]) => `
        <div class="rel-group">
          <div class="rel-verb">${esc(verb)}</div>
          <div class="rel-items">${list.slice(0, 18).map(o =>
            `<span class="pill" data-goto="${o.id}">${typeDot(o, 6)}${esc(o.name)}</span>`).join("")}
            ${list.length > 18 ? `<span class="faint">+${list.length - 18}</span>` : ""}</div>
        </div>`).join("") || `<div class="faint">no relations recorded</div>`}

      <h3 class="sub">Documents mentioning this entity <span class="n">${fmt(srcs.length)}</span></h3>
      ${shown.map(s => docCard(s, new Set([e.id]))).join("") || `<div class="faint">none</div>`}
      ${srcs.length > shown.length ? `<div class="btn" id="see-all-src">
        See all ${fmt(srcs.length)} documents in search →</div>` : ""}
    </div>`;

  $$("#entity-detail .pill[data-goto]").forEach(el =>
    el.onclick = () => selectEntity(el.dataset.goto));
  $$("#entity-detail .prov[data-src]").forEach(el =>
    el.onclick = () => openSourceEntry(el.dataset.src));
  $$("#entity-detail .src").forEach(el =>
    el.onclick = () => openDoc(el.dataset.sid));
  const seeAll = $("#see-all-src");
  if (seeAll) seeAll.onclick = () => { S.picked = [e.id]; S.mode = "any"; goSearch(); };
}

/* The typed default parameters of an entity's type, with what filled each one.
 * Empty parameters are listed too: "nobody has published this" is a finding. */
function paramTable(e) {
  const spec = (ATLAS.raw.param_spec || {})[e.type] || {};
  const names = Object.keys(spec);
  if (!names.length) return "";
  const filled = names.filter(n => e.params[n] !== undefined);
  const missing = names.filter(n => e.params[n] === undefined);
  const row = n => {
    const p = e.provenance[n] || {};
    const conflicts = (e.conflicts || {})[n] || [];
    const unit = spec[n].unit && spec[n].unit !== "year" ? ` ${spec[n].unit}` : "";
    const origin = p.source === "derived"
      ? `<span class="prov derived" title="${esc(p.note || "computed by the pipeline")}">derived</span>`
      : p.source
        ? `<span class="prov" data-src="${esc(p.source)}" title="${esc(ATLAS.sourceName(p.source))}${p.as_of ? " · as of " + p.as_of : ""}${p.note ? " · " + p.note : ""}">${esc(ATLAS.sourceName(p.source))}</span>`
        : "";
    return `<tr>
      <td class="p" title="${esc(spec[n].desc || "")}">${esc(n.replace(/_/g, " "))}</td>
      <td class="v">${esc(fmtClaim(e.params[n]))}${esc(unit)}</td>
      <td class="s">${origin}${p.confidence
        ? `<span class="conf ${esc(p.confidence)}">${esc(p.confidence)}</span>` : ""}
        ${conflicts.length ? `<span class="clash" title="${esc(conflicts.map(c =>
          `${ATLAS.sourceName(c.source)}: ${fmtClaim(c.value)}`).join(" · "))}">${conflicts.length} other value${conflicts.length > 1 ? "s" : ""}</span>` : ""}</td>
    </tr>`;
  };
  return `
    <h3 class="sub">Parameters
      <span class="n">${filled.length}/${names.length}</span></h3>
    <table class="params"><tbody>${filled.map(row).join("")}</tbody></table>
    ${missing.length ? `<div class="unfilled">nothing published for
      ${missing.map(n => `<span class="tag">${esc(n.replace(/_/g, " "))}</span>`).join("")}</div>` : ""}`;
}

/* ====================================================================== */
/* DATA SOURCES tab                                                       */
/* ====================================================================== */
const SRC_KIND_LABEL = {
  pipeline: "pipeline", dataset: "dataset", "document-set": "documents",
  api: "api", derived: "derived", registry: "registry",
};

function trustLabel(t) {
  if (t >= 0.9) return "document of record";
  if (t >= 0.75) return "first party";
  if (t >= 0.6) return "second hand, transparent";
  if (t >= 0.4) return "modelled estimate";
  return "aggregated, method unstated";
}

function renderSourceList() {
  const q = S.srcFilter.trim().toLowerCase();
  const list = ATLAS.sourceList.filter(s => !q ||
    (s.name + " " + s.publisher + " " + s.scope + " " + s.id).toLowerCase().includes(q));
  $("#src-count").textContent = `${list.length} of ${ATLAS.sourceList.length}`;
  $("#source-list").innerHTML = list.map(s => `
    <div class="src-row${s.id === S.openSourceId ? " on" : ""}" data-src="${esc(s.id)}">
      <div class="r1">
        <span class="skind ${esc(s.kind)}">${esc(SRC_KIND_LABEL[s.kind] || s.kind)}</span>
        <span class="nm">${esc(s.name)}</span>
      </div>
      <div class="r2">
        <span class="pub">${esc(s.publisher)}</span>
        <span class="nums">${fmt(s.stats.records)} records · ${fmt(s.stats.entities)} entities</span>
      </div>
      <div class="bar"><i style="width:${Math.max(2, Math.round(100 * s.trust))}%"></i></div>
    </div>`).join("") || `<div class="faint pad">no sources match</div>`;
  $$("#source-list .src-row").forEach(el =>
    el.onclick = () => openSourceEntry(el.dataset.src));
}

function openSourceEntry(id, { push = true } = {}) {
  const s = ATLAS.sources.get(id);
  if (!s) return;
  S.openSourceId = id;
  setTab("sources", { push: false });
  renderSourceList();

  const fillsByType = new Map();
  (s.fills || []).forEach(path => {
    const [type, param] = path.split(".");
    if (!fillsByType.has(type)) fillsByType.set(type, []);
    fillsByType.get(type).push(param);
  });

  const field = (label, value, extra = "") => value
    ? `<div class="kv"><dt>${esc(label)}</dt><dd>${value}${extra}</dd></div>` : "";

  $("#source-detail").innerHTML = `
    <div class="dt-head">
      <h2>${esc(s.name)}</h2>
      <span class="badge skind ${esc(s.kind)}">${esc(SRC_KIND_LABEL[s.kind] || s.kind)}</span>
      <span class="badge" style="background:#1b2436;color:var(--dim)">${esc(s.id)}</span>
    </div>
    <div class="dt-body">
      <p>${esc(s.scope || "")}</p>

      <div class="kvs">
        ${field("Publisher", esc(s.publisher))}
        ${field("Access", `${esc(s.access || "")} · ${esc(s.format || "")}`)}
        ${field("Snapshot", esc(s.retrieved || "—"), s.cadence
          ? ` <span class="faint">upstream changes ${esc(s.cadence)}</span>` : "")}
        ${field("Licence", esc(s.licence || "—"))}
        ${field("Trust", `${s.trust.toFixed(2)} <span class="faint">${esc(trustLabel(s.trust))}</span>`)}
        ${field("Default confidence", `<span class="conf ${esc(s.confidence_default)}">${esc(s.confidence_default)}</span>`)}
        ${field("Adapter", `<code>${esc(s.adapter)}</code>`)}
        ${field("Local snapshot", s.local_path ? `<code>${esc(s.local_path)}</code>` : "")}
        ${field("Landing page", `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url.replace(/^https?:\/\//, "").slice(0, 70))}</a>`)}
        ${field("Attribution", esc(s.attribution || ""))}
      </div>

      <div class="stat-row">
        <div><b>${fmt(s.stats.records)}</b>records</div>
        <div><b>${fmt(s.stats.documents)}</b>documents</div>
        <div><b>${fmt(s.stats.entities)}</b>entities touched</div>
      </div>

      ${s.caveats ? `<div class="caveat"><b>Known limits.</b> ${esc(s.caveats)}</div>` : ""}

      <h3 class="sub">Record kinds it produces</h3>
      <div class="tags">${Object.entries(s.stats.record_kinds || {})
        .sort((a, b) => b[1] - a[1])
        .map(([k, n]) => `<span class="tag hit" title="${esc((ATLAS.catalog.schema.record_kinds || {})[k] || "")}">
          ${esc(k)} <span class="faint">${fmt(n)}</span></span>`).join("") || "—"}</div>

      <h3 class="sub">Entity parameters it fills <span class="n">${(s.fills || []).length}</span></h3>
      ${fillsByType.size ? Array.from(fillsByType.entries()).map(([type, params]) => `
        <div class="fills">
          <div class="ft">${esc(type)}</div>
          <div class="tags">${params.map(p => `<span class="tag">${esc(p)}</span>`).join("")}</div>
        </div>`).join("")
        : `<div class="faint">Nothing: this source is evidence, not attributes.</div>`}

      <h3 class="sub">Example data from this source <span class="n">${s.samples.length}</span></h3>
      <p class="muted" style="font-size:11.5px;margin-top:-4px">
        Real records, exactly as the pipeline stored them, with the entities each one
        was labelled with and how.</p>
      ${s.samples.map(sampleCard).join("") || `<div class="faint">none</div>`}

      ${s.top_entities.length ? `<h3 class="sub">Entities it contributes most to</h3>
        <div class="tags">${s.top_entities.map(e => `
          <span class="tag" data-goto="${esc(e.entity)}">${dot(ATLAS.color(e.type), 6)}
          ${esc(e.name)} <span class="faint">${fmt(e.records)}</span></span>`).join("")}</div>` : ""}

      ${s.top_documents.length ? `<h3 class="sub">Documents it cites</h3>
        ${s.top_documents.map(d => `<div class="doc-line">
          <span class="kind ${esc(d.kind)}">${esc(KIND_LABEL[d.kind] || d.kind)}</span>
          <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title || d.url.replace(/^https?:\/\//, "").slice(0, 80))}</a>
          <span class="faint">${esc(d.publisher)}</span>
        </div>`).join("")}` : ""}
    </div>`;

  $$("#source-detail .tag[data-goto]").forEach(el => el.onclick = () => {
    S.selected = el.dataset.goto;
    setTab("grid");
    renderCards(); renderSide(); renderEntityDetail(); paintSelection();
  });
  $("#source-detail").scrollTop = 0;
  if (push) writeHash();
}

function sampleCard(r) {
  return `
    <div class="sample">
      <div class="s-top">
        <span class="rkind">${esc(r.kind)}</span>
        ${r.subject_name ? `<span class="subj">${esc(r.subject_name)}</span>` : ""}
        ${r.date ? `<span class="date">${esc(r.date)}</span>` : ""}
        <span class="conf ${esc(r.confidence)}">${esc(r.confidence)}</span>
        <span class="rid">${esc(r.id)}</span>
      </div>
      <table class="claims">
        <tbody>${r.claims.map(([k, v]) => `<tr>
          <td class="k">${esc(k)}${r.units[k] ? ` <span class="faint">${esc(r.units[k])}</span>` : ""}</td>
          <td class="v">${esc(v)}</td></tr>`).join("")}</tbody>
      </table>
      ${r.entities.length ? `<div class="s-ents">
        <span class="faint">labelled with</span>
        ${r.entities.map(e => `<span class="tag" title="${esc(e.methods.map(m =>
          m.method + ": " + m.span).join(" · "))}">${esc(e.name)}
          <span class="faint">${e.methods.map(m => m.method).join(",")}</span></span>`).join("")}
      </div>` : ""}
      ${r.documents.length ? `<div class="s-docs">${r.documents.map(u =>
        `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").slice(0, 78))}</a>`).join("")}</div>` : ""}
      ${r.raw_ref ? `<div class="s-raw">from <code>${esc(r.raw_ref)}</code></div>` : ""}
    </div>`;
}

function fmtClaim(v) {
  if (v == null) return "—";
  if (Array.isArray(v)) return v.slice(0, 5).join(", ");
  if (typeof v === "object") {
    return Object.entries(v).slice(0, 4)
      .map(([k, n]) => `${k} ${typeof n === "number" ? fmt(n) : n ?? ""}`).join(", ");
  }
  if (typeof v === "number") return fmt(Math.abs(v) >= 100 ? Math.round(v) : v);
  return String(v);
}

/* ====================================================================== */
/* document cards (shared by the grid and search tabs)                    */
/* ====================================================================== */
function docCard(s, highlight = new Set()) {
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
    scored.push([score + e.weight * 3 + e.document_count * 0.05, e]);
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
      <span class="ct">${fmt(e.document_count)} docs</span>
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

function matchingDocuments() {
  const picked = S.picked.filter(id => ATLAS.entities.has(id));
  let list;
  if (!picked.length) {
    list = Array.from(ATLAS.documents.values());
  } else if (S.mode === "all") {
    list = Array.from(ATLAS.documents.values()).filter(s => {
      const ids = new Set(s.entities.map(r => r.entity));
      return picked.every(p => ids.has(p));
    });
  } else {
    const seen = new Set();
    list = [];
    picked.forEach(p => (ATLAS.docsByEntity.get(p) || []).forEach(sid => {
      if (!seen.has(sid)) { seen.add(sid); list.push(ATLAS.documents.get(sid)); }
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
  $("#doc-page").classList.remove("on");
  $("#results").classList.remove("off");
  $("#results-head").classList.remove("off");

  // kind counts are computed before the kind filter is applied
  const savedKinds = S.kinds; S.kinds = new Set();
  const unfiltered = matchingDocuments();
  S.kinds = savedKinds;
  renderKindFilters(unfiltered);

  const list = matchingDocuments();
  const picked = new Set(S.picked);
  const label = S.picked.length
    ? S.picked.map(id => ATLAS.entities.get(id)?.name).filter(Boolean)
        .join(S.mode === "all" ? " AND " : " OR ")
    : "everything";
  $("#results-head").innerHTML = `
    <span class="big">${fmt(list.length)} document${list.length === 1 ? "" : "s"}</span>
    <span class="muted">for ${esc(label)}</span>`;
  $("#results").innerHTML = list.slice(0, shownLimit).map(s => docCard(s, picked)).join("")
    || `<div class="panel-box muted">No documents match. Try “Any of”, or remove a filter.</div>`;
  if (list.length > shownLimit) {
    $("#results").innerHTML += `<div class="btn ghost" id="more-results">
      Show ${Math.min(60, list.length - shownLimit)} more of ${fmt(list.length)}</div>`;
    $("#more-results").onclick = () => { shownLimit += 60; runSearch({ resetLimit: false }); };
  }
  $$("#results .src").forEach(el => el.onclick = () => openDoc(el.dataset.sid));
}

/* ---------------------------------------------------------------- source page */
function openDoc(id, { push = true } = {}) {
  const s = ATLAS.documents.get(id);
  if (!s) return;
  S.openDoc = id;
  setTab("search", { push: false });
  $("#results").classList.add("off");
  $("#results-head").classList.add("off");
  const page = $("#doc-page");
  page.classList.add("on");

  const related = Array.from(ATLAS.documents.values())
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
      <h3 class="sub" style="margin-top:0">Cited by these data sources</h3>
      <div class="tags">${s.sources.map(d =>
        `<span class="tag hit" data-src="${esc(d)}">${esc(ATLAS.sourceName(d))}</span>`).join("")}</div>
      ${s.contexts.length ? `<h3 class="sub">Context that travelled with the link</h3>
        ${s.contexts.map(c => `<div class="ctx">${esc(c)}</div>`).join("")}` : ""}
      ${s.claims.length ? `<h3 class="sub">What the citing record${s.claims.length > 1 ? "s" : ""} claimed</h3>
        ${s.claims.map(r => `<div class="metrics">${Object.entries(r).map(([k, v]) =>
          `<div><dt>${esc(k)}</dt><dd>${esc(fmtClaim(v))}</dd></div>`).join("")}</div>`).join("")}` : ""}
    </div>

    ${related.length ? `<div class="panel-box">
      <h3 class="sub" style="margin-top:0">Documents sharing entities with this one</h3>
      ${related.map(x => docCard(x.o, new Set(s.entities.map(r => r.entity)))).join("")}
    </div>` : ""}`;

  $("#sp-back").onclick = () => {
    S.openDoc = null;
    page.classList.remove("on");
    runSearch({ resetLimit: false });
    writeHash();
  };
  $$("#doc-page .pill[data-goto]").forEach(el => el.onclick = () => {
    S.selected = el.dataset.goto;
    setTab("grid");
    renderCards(); renderSide(); renderEntityDetail();
    requestAnimationFrame(() => {
      const node = $(`#cards .node[data-id="${cssEscape(S.selected)}"]`);
      if (node) node.scrollIntoView({ behavior: "smooth", block: "center" });
      paintSelection();
    });
  });
  $$("#doc-page .src").forEach(el => el.onclick = () => openDoc(el.dataset.sid));
  $$("#doc-page .tag[data-src]").forEach(el => el.onclick = ev => {
    ev.stopPropagation();
    S.openDoc = null;
    $("#doc-page").classList.remove("on");
    openSourceEntry(el.dataset.src);
  });
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
  if (S.openDoc) h = `#doc/${S.openDoc}`;
  else if (S.tab === "sources") {
    h = "#sources" + (S.openSourceId ? "/" + S.openSourceId : "");
  } else if (S.tab === "search") {
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
  if ((head === "doc" || head === "source") && ATLAS.documents.has(arg)) {
    openDoc(arg, { push: false }); return;
  }
  if (head === "sources") {
    setTab("sources", { push: false });
    renderSourceList();
    openSourceEntry(ATLAS.sources.has(arg) ? arg : ATLAS.sourceList[0].id, { push: false });
    return;
  }
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
    S.openDoc = null;
    $("#doc-page").classList.remove("on");
    setTab(b.dataset.tab);
    if (b.dataset.tab === "search") runSearch();
    if (b.dataset.tab === "sources") {
      renderSourceList();
      openSourceEntry(S.openSourceId || ATLAS.sourceList[0].id);
    }
  });

  $("#src-filter").oninput = ev => { S.srcFilter = ev.target.value; renderSourceList(); };

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
      ({ grid: $("#grid-filter"), sources: $("#src-filter"), search: $("#q") })[S.tab].focus();
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
