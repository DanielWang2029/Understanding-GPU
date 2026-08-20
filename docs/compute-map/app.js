/* Global AI Compute Map — 2D drill-down: world -> continent -> country -> site.
 *
 * Data comes from docs/compute-map/data.json, built by scripts/build_compute_map.py
 * out of four sources (dataCenterView, Epoch AI, curated global sites, cloud
 * provider region docs) with an explicit deduplication pass.
 */

const ACCEL_COLORS = {
  "NVIDIA GPU": "#76b900",
  "Google TPU": "#4da3ff",
  "AWS Trainium": "#ff9900",
  "AMD Instinct": "#e2231a",
  "Huawei Ascend": "#cf0a2c",
  "Cerebras WSE": "#f05a28",
  "Groq LPU": "#e2508a",
  "Intel Gaudi": "#00a3e0",
  "Intel GPU": "#0068b5",
  "Qualcomm AI100": "#a06bf0",
  "Mixed": "#b39ddb",
  "Other": "#7f8fa1",
};
const STATUS_META = {
  operating:         { label: "Operating",          color: "#35c98a" },
  expanding:         { label: "Operating+expanding", color: "#35c98a" },
  under_construction:{ label: "Under construction", color: "#ffb347" },
  planned:           { label: "Planned",            color: "#8b9bad" },
  announced:         { label: "Announced",          color: "#6c7f93" },
  cancelled:         { label: "Cancelled",          color: "#ff6b6b" },
  unknown:           { label: "Status unknown",     color: "#5b6b7a" },
};
const TIER_META = {
  frontier:     { label: "AI / frontier sites" },
  large:        { label: "Other sites ≥20 MW" },
  small:        { label: "Smaller & colocation" },
  cloud_region: { label: "Cloud regions" },
};
const METRIC_LABEL = {
  power_mw_planned: "MW planned",
  power_mw: "MW operating",
  h100e: "H100-equivalents",
  h100e_planned: "H100e planned",
  chips: "chips",
  sites: "sites",
};

const state = {
  level: "world",           // world | continent | country
  continent: null,
  country: null,            // iso3
  selectedSite: null,
  metric: "power_mw_planned",
  status: new Set(["operating", "expanding", "under_construction", "planned", "announced"]),
  accel: new Set(),         // empty = all
  tiers: new Set(["frontier", "large", "cloud_region"]),
  labels: true,
  showRegions: true,
};

let DATA, WORLD, COUNTRIES, svg, gMap, gCountries, gBubbles, zoom, projection, path, width, height;
const fmt = d3.format(",.0f");
const fmt1 = d3.format(",.1f");

function short(n) {
  if (n == null || !isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return (n / 1e6).toFixed(a >= 1e7 ? 0 : 1) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(a >= 1e4 ? 0 : 1) + "k";
  return fmt(n);
}

/* ------------------------------------------------------------------ metrics */
function siteMetric(s, metric) {
  switch (metric) {
    case "power_mw": return s.power_mw || 0;
    case "power_mw_planned": return s.power_mw_planned || s.power_mw || 0;
    case "h100e": return s.h100e || 0;
    case "h100e_planned": return Math.max(s.h100e_planned || 0, s.h100e || 0);
    case "chips": return d3.sum(Object.values(s.chip_families || {}));
    case "sites": return 1;
    default: return 0;
  }
}

function passesFilters(s) {
  if (s.layer === "cloud_region") return state.showRegions && state.tiers.has("cloud_region");
  if (!state.tiers.has(s.tier)) return false;
  if (!state.status.has(s.status)) return false;
  if (state.accel.size) {
    const fams = new Set([...(s.accelerators || []), ...Object.keys(s.chip_families || {})]);
    let hit = false;
    state.accel.forEach(a => { if (fams.has(a)) hit = true; });
    if (!hit) return false;
  }
  return true;
}

function visibleSites() {
  return DATA.sites.filter(passesFilters);
}

function scopeSites() {
  let list = visibleSites();
  if (state.level === "continent") list = list.filter(s => s.continent === state.continent);
  if (state.level === "country") list = list.filter(s => s.iso3 === state.country);
  return list;
}

function dominantAccel(s) {
  const fams = s.chip_families && Object.keys(s.chip_families).length
    ? s.chip_families : null;
  if (fams) return Object.entries(fams).sort((a, b) => b[1] - a[1])[0][0];
  const list = (s.accelerators || []).filter(a => a && a !== "Other");
  if (list.length > 1) return "Mixed";
  return list[0] || "Other";
}

function aggregate(sites) {
  const agg = {
    sites: 0, located: 0, power_mw: 0, power_mw_planned: 0, h100e: 0,
    h100e_planned: 0, capex: 0, chips: {}, chipsPlanned: {}, status: {},
    operators: {}, regions: 0, accel: {},
  };
  sites.forEach(s => {
    if (s.layer === "cloud_region") {
      agg.regions += 1;
      (s.accelerators || []).forEach(a => { agg.accel[a] = (agg.accel[a] || 0) + 1; });
      return;
    }
    agg.sites += 1;
    if (s.lat != null) agg.located += 1;
    agg.power_mw += s.power_mw || 0;
    agg.power_mw_planned += s.power_mw_planned || s.power_mw || 0;
    agg.h100e += s.h100e || 0;
    agg.h100e_planned += Math.max(s.h100e_planned || 0, s.h100e || 0);
    agg.capex += s.capex_usd_b || 0;
    agg.status[s.status] = (agg.status[s.status] || 0) + 1;
    Object.entries(s.chip_families || {}).forEach(([k, v]) => {
      agg.chips[k] = (agg.chips[k] || 0) + v;
    });
    Object.entries(s.chip_families_planned || {}).forEach(([k, v]) => {
      agg.chipsPlanned[k] = (agg.chipsPlanned[k] || 0) + v;
    });
    if (s.operator) {
      agg.operators[s.operator] = (agg.operators[s.operator] || 0) +
        (s.power_mw_planned || s.power_mw || 0);
    }
    (s.accelerators || []).forEach(a => { agg.accel[a] = (agg.accel[a] || 0) + 1; });
  });
  return agg;
}

/* ------------------------------------------------------------------- markers */
function buildNodes() {
  const sites = scopeSites();
  if (state.level === "world") {
    const groups = d3.groups(sites, s => s.continent || "Unknown");
    return groups.map(([name, members]) => makeNode("continent", name, name, members));
  }
  if (state.level === "continent") {
    const groups = d3.groups(sites, s => s.iso3 || "ZZZ");
    return groups.map(([iso3, members]) => makeNode(
      "country", iso3, members[0].country || iso3, members));
  }
  return sites.filter(s => s.lat != null).map(s => ({
    kind: "site", id: s.id, name: s.name, site: s,
    lat: s.lat, lon: s.lon,
    value: siteMetric(s, state.metric),
    accel: dominantAccel(s), status: s.status, count: 1,
    members: [s],
  }));
}

function makeNode(kind, id, name, members) {
  const located = members.filter(s => s.lat != null);
  const weights = located.map(s => Math.max(1, siteMetric(s, state.metric)));
  const wsum = d3.sum(weights) || located.length || 1;
  const lat = located.length ? d3.sum(located, (s, i) => s.lat * weights[i]) / wsum : null;
  const lon = located.length ? d3.sum(located, (s, i) => s.lon * weights[i]) / wsum : null;
  const agg = aggregate(members);
  const chipTotals = {};
  Object.entries(agg.chips).forEach(([k, v]) => { chipTotals[k] = v; });
  const accel = Object.keys(chipTotals).length
    ? Object.entries(chipTotals).sort((a, b) => b[1] - a[1])[0][0]
    : (Object.keys(agg.accel).length > 1 ? "Mixed"
      : (Object.keys(agg.accel)[0] || "Other"));
  return {
    kind, id, name, lat, lon,
    value: d3.sum(members, s => siteMetric(s, state.metric)),
    accel, status: "operating", count: agg.sites, regions: agg.regions,
    agg, members,
  };
}

function radiusScale(nodes) {
  const max = d3.max(nodes, n => n.value) || 1;
  const k = state.level === "country" ? 26 : 40;
  return d3.scaleSqrt().domain([0, max]).range([state.level === "country" ? 3.5 : 6, k]);
}

/* --------------------------------------------------------------- projection */
function setupMap() {
  const wrap = document.getElementById("map-wrap");
  width = wrap.clientWidth;
  height = wrap.clientHeight;
  svg = d3.select("#map").attr("viewBox", [0, 0, width, height]);
  svg.selectAll("*").remove();

  projection = d3.geoNaturalEarth1().fitExtent(
    [[10, 14], [width - 10, height - 14]], { type: "Sphere" });
  path = d3.geoPath(projection);

  gMap = svg.append("g");
  gMap.append("path").attr("class", "sphere").attr("d", path({ type: "Sphere" }));
  gMap.append("path").attr("class", "graticule")
    .attr("d", path(d3.geoGraticule10()));
  gCountries = gMap.append("g");
  gBubbles = gMap.append("g");

  gCountries.selectAll("path")
    .data(COUNTRIES.features)
    .join("path")
    .attr("class", "country")
    .attr("d", path)
    .on("click", (event, f) => {
      const meta = DATA.country_index[f.id];
      if (!meta) return;
      const hasData = DATA.countries.some(c => c.iso3 === meta.iso3);
      if (state.level === "world") {
        if (meta.continent) drillToContinent(meta.continent);
      } else if (hasData) {
        drillToCountry(meta.iso3, meta.continent);
      }
    })
    .on("mousemove", (event, f) => {
      const meta = DATA.country_index[f.id];
      if (!meta) return hideTip();
      const c = DATA.countries.find(x => x.iso3 === meta.iso3);
      showTip(event, `<div class="t-name">${meta.name}</div>` +
        (c ? `<div class="t-row"><b>${fmt(c.sites)}</b> sites · <b>${short(c.power_mw_planned)}</b> MW planned</div>`
           : `<div class="t-row">no tracked sites</div>`) +
        `<div class="t-row">${meta.continent}</div>`);
    })
    .on("mouseleave", hideTip);

  zoom = d3.zoom().scaleExtent([1, 220])
    .on("start", () => svg.classed("grabbing", true))
    .on("end", () => svg.classed("grabbing", false))
    .on("zoom", (event) => {
      gMap.attr("transform", event.transform);
      gMap.selectAll(".country").attr("stroke-width", 0.4 / event.transform.k);
      gBubbles.selectAll(".glyph").attr("stroke-width", 1.4 / Math.sqrt(event.transform.k));
      gBubbles.attr("transform", null);
      gBubbles.selectAll("g.bubble").attr("transform", d => {
        const p = projection([d.lon, d.lat]);
        return `translate(${p[0]},${p[1]}) scale(${1 / event.transform.k})`;
      });
      scheduleLabelPass();
    });
  svg.call(zoom).on("dblclick.zoom", null);
  svg.on("dblclick", () => goUp());
}

let labelTimer = null;
function scheduleLabelPass() {
  if (labelTimer) clearTimeout(labelTimer);
  labelTimer = setTimeout(() => {
    const nodes = gBubbles.selectAll("g.bubble").data();
    if (!nodes.length) return;
    const r = radiusScale(nodes);
    const keep = pickLabels(nodes, r);
    gBubbles.selectAll("g.bubble").select("text.label")
      .style("display", d => state.labels && keep.has(d) ? null : "none");
    gBubbles.selectAll("g.bubble").select("text.sublabel")
      .style("display", d => state.labels && state.level !== "country" && keep.has(d)
        ? null : "none");
  }, 120);
}


function zoomToBounds(bounds, padding = 0.82, duration = 900) {
  const [[x0, y0], [x1, y1]] = bounds;
  const k = Math.max(1, Math.min(180,
    padding * Math.min(width / Math.max(6, x1 - x0), height / Math.max(6, y1 - y0))));
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  svg.transition().duration(duration).ease(d3.easeCubicInOut).call(
    zoom.transform,
    d3.zoomIdentity.translate(width / 2, height / 2).scale(k).translate(-cx, -cy));
}

function featuresFor(pred) {
  return COUNTRIES.features.filter(f => {
    const meta = DATA.country_index[f.id];
    return meta && pred(meta);
  });
}

function boundsOfFeatures(features) {
  if (!features.length) return [[0, 0], [width, height]];
  const fc = { type: "FeatureCollection", features };
  return path.bounds(fc);
}

/* ------------------------------------------------------------------- render */
function render(animate = true) {
  const nodes = buildNodes().filter(n => n.lat != null && n.value >= 0);
  const r = radiusScale(nodes);
  const inScope = new Set();
  if (state.level === "continent") {
    featuresFor(m => m.continent === state.continent).forEach(f => inScope.add(f.id));
  } else if (state.level === "country") {
    featuresFor(m => m.iso3 === state.country).forEach(f => inScope.add(f.id));
  }
  const withData = new Set();
  DATA.countries.forEach(c => {
    Object.entries(DATA.country_index).forEach(([code, m]) => {
      if (m.iso3 === c.iso3) withData.add(code);
    });
  });

  gCountries.selectAll("path")
    .attr("class", f => {
      const meta = DATA.country_index[f.id];
      let cls = "country";
      if (withData.has(f.id)) cls += " has-data";
      if (inScope.has(f.id)) cls += " in-scope";
      if (meta && (state.level === "world" || withData.has(f.id))) cls += " clickable";
      return cls;
    });

  const k = d3.zoomTransform(svg.node()).k;
  const sel = gBubbles.selectAll("g.bubble")
    .data(nodes, d => d.kind + ":" + d.id);

  sel.exit().transition().duration(200).style("opacity", 0).remove();

  const enter = sel.enter().append("g")
    .attr("class", "bubble")
    .attr("transform", d => {
      const p = projection([d.lon, d.lat]);
      return `translate(${p[0]},${p[1]}) scale(${1 / k})`;
    })
    .style("opacity", 0);

  enter.append("path").attr("class", "glyph");
  enter.append("circle").attr("class", "hit");
  enter.append("text").attr("class", "label");
  enter.append("text").attr("class", "sublabel");

  const all = enter.merge(sel);

  all.on("click", (event, d) => {
      event.stopPropagation();
      if (d.kind === "continent") drillToContinent(d.id);
      else if (d.kind === "country") drillToCountry(d.id, state.continent);
      else selectSite(d.site);
    })
    .on("mousemove", (event, d) => showTip(event, tooltipHtml(d)))
    .on("mouseleave", hideTip);

  all.transition().duration(animate ? 450 : 0)
    .style("opacity", 1)
    .attr("transform", d => {
      const p = projection([d.lon, d.lat]);
      const kk = d3.zoomTransform(svg.node()).k;
      return `translate(${p[0]},${p[1]}) scale(${1 / kk})`;
    });

  all.select("path.glyph")
    .attr("d", d => glyphPath(d, r(d.value)))
    .attr("fill", d => {
      const c = ACCEL_COLORS[d.accel] || ACCEL_COLORS.Other;
      if (d.kind === "site" && (d.status === "planned" || d.status === "announced")) return "none";
      return c;
    })
    .attr("fill-opacity", d => d.kind === "site" ? 0.62 : 0.5)
    .attr("stroke", d => {
      if (d.kind === "site") return (STATUS_META[d.status] || STATUS_META.unknown).color;
      return ACCEL_COLORS[d.accel] || ACCEL_COLORS.Other;
    })
    .attr("stroke-dasharray", d => d.kind === "site" && d.status === "under_construction" ? "3,2" : null)
    .attr("stroke-width", 1.4 / Math.sqrt(k));

  all.select("circle.hit").attr("r", d => Math.max(9, r(d.value)));

  const labelled = pickLabels(nodes, r);
  all.select("text.label")
    .attr("y", d => -r(d.value) - 5)
    .style("display", d => state.labels && labelled.has(d) ? null : "none")
    .text(d => labelFor(d));

  all.select("text.sublabel")
    .attr("y", d => -r(d.value) - 5 + 12)
    .attr("text-anchor", "middle")
    .style("display", d => state.labels && state.level !== "country" && labelled.has(d)
      ? null : "none")
    .text(d => d.kind === "site" ? "" :
      `${short(d.value)} ${METRIC_LABEL[state.metric]} · ${fmt(d.count)} sites`);

  all.classed("selected", d => state.selectedSite && d.kind === "site" &&
    d.site.id === state.selectedSite.id);

  renderStats();
  renderBreadcrumb();
  renderLegend(nodes);
  document.getElementById("btn-up").disabled = state.level === "world";
  document.getElementById("hint").textContent =
    state.level === "world" ? "Click a continent to zoom in"
    : state.level === "continent" ? "Click a country to see its data centers"
    : "Click a site for its sources · double-click the map to zoom out";
}

/* Greedy label placement: biggest markers win, anything that would collide with
 * an already-placed label stays unlabelled. Without this the US view turns into
 * a wall of overlapping text. */
function pickLabels(nodes, r) {
  const keep = new Set();
  if (!state.labels) return keep;
  const k = d3.zoomTransform(svg.node()).k || 1;
  const placed = [];
  const limit = state.level === "country" ? 18 : 40;
  const sorted = nodes.slice().sort((a, b) => b.value - a.value);
  for (const d of sorted) {
    if (keep.size >= limit) break;
    const p = projection([d.lon, d.lat]);
    if (!p) continue;
    // screen-space position, accounting for the current zoom transform
    const t = d3.zoomTransform(svg.node());
    const sx = p[0] * t.k + t.x;
    const sy = p[1] * t.k + t.y;
    const w = Math.max(56, (labelFor(d) || "").length * 6.0);
    const h = state.level === "country" ? 13 : 25;
    const top = sy - r(d.value) / Math.max(1, 1) - 6 - h;
    const box = { x0: sx - w / 2, x1: sx + w / 2, y0: top, y1: top + h + 4 };
    if (box.x1 < 0 || box.x0 > width || box.y1 < 0 || box.y0 > height) continue;
    const clash = placed.some(b => !(box.x1 < b.x0 || box.x0 > b.x1 ||
                                     box.y1 < b.y0 || box.y0 > b.y1));
    if (clash) continue;
    placed.push(box);
    keep.add(d);
  }
  return keep;
}


function glyphPath(d, radius) {
  if (d.kind === "site" && d.site.layer === "cloud_region") {
    // diamond = rentable cloud region rather than a physical campus
    const s = Math.max(4, radius * 0.9);
    return `M0,${-s} L${s},0 L0,${s} L${-s},0 Z`;
  }
  return d3.arc()({ innerRadius: 0, outerRadius: Math.max(2.5, radius),
                    startAngle: 0, endAngle: 2 * Math.PI });
}

function labelFor(d) {
  if (d.kind === "continent") return d.name;
  if (d.kind === "country") return d.name;
  return d.value > 0 ? `${d.name}` : d.name;
}

function tooltipHtml(d) {
  if (d.kind !== "site") {
    const a = d.agg;
    return `<div class="t-name">${d.name}</div>` +
      `<div class="t-row"><b>${fmt(a.sites)}</b> sites · <b>${short(a.power_mw)}</b> MW operating · ` +
      `<b>${short(a.power_mw_planned)}</b> MW planned</div>` +
      `<div class="t-row">${short(a.h100e)} H100e installed · ${a.regions} cloud regions</div>` +
      `<div class="t-row">Click to zoom in</div>`;
  }
  const s = d.site;
  if (s.layer === "cloud_region") {
    return `<div class="t-name">${s.name}</div>` +
      `<div class="t-row">${s.city}, ${s.country}</div>` +
      `<div class="t-row"><b>${(s.accelerators || []).join(", ")}</b></div>` +
      `<div class="t-row">${s.chip_detail || ""}</div>`;
  }
  const st = STATUS_META[s.status] || STATUS_META.unknown;
  return `<div class="t-name">${s.name}</div>` +
    `<div class="t-row">${[s.city, s.admin1, s.country].filter(Boolean).join(", ")}</div>` +
    `<div class="t-row"><b style="color:${st.color}">${st.label}</b>` +
    (s.operator ? ` · ${s.operator}` : "") + `</div>` +
    `<div class="t-row">` +
    (s.power_mw ? `<b>${short(s.power_mw)}</b> MW now` : "") +
    (s.power_mw_planned && s.power_mw_planned !== s.power_mw
      ? ` · <b>${short(s.power_mw_planned)}</b> MW planned` : "") + `</div>` +
    (Object.keys(s.chip_families || {}).length
      ? `<div class="t-row">${Object.entries(s.chip_families)
          .map(([k, v]) => `${k} ${short(v)}`).join(" · ")}</div>` : "") +
    `<div class="t-row">${s.sources.length} source${s.sources.length === 1 ? "" : "s"} · click for detail</div>`;
}

/* -------------------------------------------------------------- navigation */
function drillToContinent(name) {
  svg.interrupt();
  state.level = "continent";
  state.continent = name;
  state.country = null;
  state.selectedSite = null;
  const feats = featuresFor(m => m.continent === name);
  zoomToBounds(boundsOfFeatures(feats));
  render();
}

function drillToCountry(iso3, continent) {
  svg.interrupt();
  const meta = Object.values(DATA.country_index).find(m => m.iso3 === iso3);
  state.level = "country";
  state.continent = continent || (meta ? meta.continent : state.continent);
  state.country = iso3;
  state.selectedSite = null;
  const feats = featuresFor(m => m.iso3 === iso3);
  let bounds = boundsOfFeatures(feats);
  const pts = scopeSites().filter(s => s.lat != null)
    .map(s => projection([s.lon, s.lat]));
  if (pts.length > 1) {
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    bounds = [[Math.min(bounds[0][0], d3.min(xs)), Math.min(bounds[0][1], d3.min(ys))],
              [Math.max(bounds[1][0], d3.max(xs)), Math.max(bounds[1][1], d3.max(ys))]];
  }
  zoomToBounds(bounds, 0.78);
  render();
}

function goUp() {
  svg.interrupt();
  if (state.level === "country") {
    const cont = state.continent;
    state.level = "continent";
    state.country = null;
    state.selectedSite = null;
    zoomToBounds(boundsOfFeatures(featuresFor(m => m.continent === cont)));
    render();
  } else if (state.level === "continent") {
    goWorld();
  }
}

function goWorld() {
  svg.interrupt();
  state.level = "world";
  state.continent = null;
  state.country = null;
  state.selectedSite = null;
  svg.transition().duration(800).ease(d3.easeCubicInOut)
    .call(zoom.transform, d3.zoomIdentity);
  render();
}

function selectSite(site) {
  state.selectedSite = site;
  render(false);
  renderDetail(site);
}

/* ------------------------------------------------------------------ sidebar */
function renderBreadcrumb() {
  const el = d3.select("#breadcrumb");
  el.selectAll("*").remove();
  const crumbs = [{ label: "World", go: goWorld, current: state.level === "world" }];
  if (state.continent) {
    crumbs.push({
      label: state.continent,
      go: () => drillToContinent(state.continent),
      current: state.level === "continent",
    });
  }
  if (state.country) {
    const c = DATA.countries.find(x => x.iso3 === state.country);
    crumbs.push({ label: c ? c.name : state.country, go: () => {}, current: true });
  }
  crumbs.forEach((c, i) => {
    if (i) el.append("span").attr("class", "sep").text("›");
    el.append("span")
      .attr("class", "crumb" + (c.current ? " current" : ""))
      .text(c.label)
      .on("click", () => { if (!c.current) c.go(); });
  });
}

function renderStats() {
  const sites = scopeSites();
  const agg = aggregate(sites);
  const title = state.level === "world" ? "Worldwide"
    : state.level === "continent" ? state.continent
    : (DATA.countries.find(c => c.iso3 === state.country) || {}).name || state.country;

  const rows = (obj, colors, unit) => {
    const entries = Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 7);
    const max = d3.max(entries, e => e[1]) || 1;
    return entries.map(([k, v]) => `
      <div class="bar-row">
        <span class="name" title="${k}">${k}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${(v / max * 100).toFixed(1)}%;
          background:${(colors && colors[k]) || "#4da3ff"}"></span></span>
        <span class="val">${unit === "mw" ? short(v) : short(v)}</span>
      </div>`).join("");
  };

  document.getElementById("stats").innerHTML = `
    <div class="field-label">${title}</div>
    <div class="stat-grid">
      <div class="stat"><div class="k">Sites tracked</div><div class="v">${fmt(agg.sites)}
        <small>${fmt(agg.located)} mapped</small></div></div>
      <div class="stat"><div class="k">Cloud regions</div><div class="v">${fmt(agg.regions)}</div></div>
      <div class="stat"><div class="k">Power operating</div><div class="v">${short(agg.power_mw)}
        <small>MW</small></div></div>
      <div class="stat"><div class="k">Power planned</div><div class="v">${short(agg.power_mw_planned)}
        <small>MW at full build</small></div></div>
      <div class="stat"><div class="k">H100-equivalents</div><div class="v">${short(agg.h100e)}
        <small>installed</small></div></div>
      <div class="stat"><div class="k">H100e planned</div><div class="v">${short(agg.h100e_planned)}</div></div>
    </div>
    ${Object.keys(agg.chips).length ? `<h3 class="section">Accelerators installed</h3>
      ${rows(agg.chips, ACCEL_COLORS)}` : ""}
    ${Object.keys(agg.chipsPlanned).length ? `<h3 class="section">Accelerators planned</h3>
      ${rows(agg.chipsPlanned, ACCEL_COLORS)}` : ""}
    <h3 class="section">Status of sites</h3>
    ${rows(agg.status, Object.fromEntries(Object.entries(STATUS_META).map(([k, v]) => [k, v.color])))}
    ${Object.keys(agg.operators).length ? `<h3 class="section">Largest operators by planned MW</h3>
      ${rows(agg.operators, null, "mw")}` : ""}
    ${state.level === "country" ? siteListHtml(sites) : ""}
  `;
  if (state.level === "country") {
    d3.selectAll("#stats .site-link").on("click", function () {
      const id = this.getAttribute("data-id");
      const site = DATA.sites.find(s => s.id === id);
      if (site) selectSite(site);
    });
  }
}

function siteListHtml(sites) {
  const list = sites.slice().sort((a, b) =>
    siteMetric(b, state.metric) - siteMetric(a, state.metric));
  return `<h3 class="section">Sites in view (${list.length})</h3>
    <ul class="site-list">${list.map(s => `
      <li><span class="n site-link" data-id="${s.id}">${s.name}</span>
        <span class="m">${short(siteMetric(s, state.metric))}</span></li>`).join("")}</ul>`;
}

function renderDetail(s) {
  const el = document.getElementById("detail");
  if (!s) {
    el.innerHTML = `<p class="muted">Click a continent to zoom in, then a country,
      then a data center. Every site lists its own sources.</p>`;
    return;
  }
  const st = STATUS_META[s.status] || STATUS_META.unknown;
  const chipRow = (obj) => Object.entries(obj).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `<span class="badge" style="background:${ACCEL_COLORS[k] || "#7f8fa1"};
      color:#08131e">${k} ${short(v)}</span>`).join("");
  const bySet = {};
  s.sources.forEach(src => {
    (bySet[src.dataset] = bySet[src.dataset] || []).push(src.url);
  });

  el.innerHTML = `
    <h2>${s.name}</h2>
    <div class="where">${[s.city, s.admin1, s.country].filter(Boolean).join(", ")}
      ${s.lat != null ? `· ${s.lat.toFixed(3)}, ${s.lon.toFixed(3)}
      <span class="muted">(${s.coord_precision})</span>` : ""}</div>
    <div>
      <span class="badge" style="background:${st.color};color:#08131e">${st.label}</span>
      ${s.layer === "cloud_region" ? `<span class="badge" style="background:#4da3ff;color:#08131e">cloud region</span>` : ""}
      ${s.tier === "frontier" ? `<span class="badge" style="background:#b39ddb;color:#08131e">frontier AI site</span>` : ""}
    </div>
    <dl class="kv">
      ${s.operator ? `<dt>Operator</dt><dd>${s.operator}</dd>` : ""}
      ${s.tenant ? `<dt>Tenant / user</dt><dd>${s.tenant}</dd>` : ""}
      ${s.power_mw ? `<dt>Power now</dt><dd>${fmt(s.power_mw)} MW</dd>` : ""}
      ${s.power_mw_planned ? `<dt>Power planned</dt><dd>${fmt(s.power_mw_planned)} MW at full build</dd>` : ""}
      ${s.h100e ? `<dt>H100-equivalents</dt><dd>${fmt(s.h100e)} installed</dd>` : ""}
      ${s.h100e_planned ? `<dt>H100e planned</dt><dd>${fmt(s.h100e_planned)}</dd>` : ""}
      ${s.capex_usd_b ? `<dt>Capital cost</dt><dd>$${fmt1(s.capex_usd_b)}B (modelled)</dd>` : ""}
      ${s.year ? `<dt>Year</dt><dd>${fmt(s.year)}</dd>` : ""}
      ${s.category ? `<dt>Category</dt><dd>${s.category}</dd>` : ""}
    </dl>
    ${Object.keys(s.chip_families || {}).length
      ? `<h3 class="section">Accelerators installed</h3><div>${chipRow(s.chip_families)}</div>` : ""}
    ${Object.keys(s.chip_families_planned || {}).length
      ? `<h3 class="section">Accelerators planned</h3><div>${chipRow(s.chip_families_planned)}</div>` : ""}
    ${s.chip_detail ? `<div class="muted" style="font-size:12px;margin-top:6px">${s.chip_detail}</div>` : ""}
    ${s.aka && s.aka.length ? `<h3 class="section">Also referred to as</h3>
      <div class="muted" style="font-size:12.5px">${s.aka.join(" · ")}</div>` : ""}
    ${s.records.length > 1 ? `<h3 class="section">Merged from ${s.records.length} source records</h3>
      ${s.records.map(r => `<div class="record">
        <div class="rname">${r.name}</div>
        <div class="rmeta">${r.dataset}${r.operator ? " · " + r.operator : ""}
          ${r.power_mw ? " · " + fmt(r.power_mw) + " MW" : ""} · ${r.sources} sources</div>
      </div>`).join("")}` : `<h3 class="section">Provenance</h3>
      <div class="muted" style="font-size:12.5px">Single record from ${s.datasets.join(", ")}</div>`}
    ${s.confidence ? `<h3 class="section">Confidence</h3>
      <div class="muted" style="font-size:12px">${s.confidence}</div>` : ""}
    ${s.notes ? `<div class="muted" style="font-size:12px;margin-top:6px">${s.notes}</div>` : ""}
    <h3 class="section">Sources (${s.sources.length})</h3>
    ${Object.entries(bySet).map(([ds, urls]) => `
      <ul class="src-list">${urls.map(u => `<li><span class="tag">${ds}</span>
        <a href="${u}" target="_blank" rel="noopener">${u.replace(/^https?:\/\//, "").slice(0, 74)}</a></li>`).join("")}</ul>`).join("")}
  `;
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ------------------------------------------------------------------ legend */
function renderLegend(nodes) {
  const used = new Set(nodes.map(n => n.accel));
  const items = Object.entries(ACCEL_COLORS)
    .filter(([k]) => used.has(k) || k === "Mixed")
    .map(([k, c]) => `<span class="lg-item"><span class="sw" style="background:${c}"></span>${k}</span>`)
    .join("");
  const statuses = ["operating", "under_construction", "planned"]
    .map(k => `<span class="lg-item"><span class="sw" style="background:${STATUS_META[k].color}"></span>
      ${STATUS_META[k].label}</span>`).join("");
  document.getElementById("legend").innerHTML = `
    <div class="lg-title">Marker colour — dominant accelerator</div>
    <div class="lg-items">${items}</div>
    <div class="lg-title" style="margin-top:8px">Outline — status</div>
    <div class="lg-items status-row">${statuses}
      <span class="lg-item">◆ cloud region (no capacity counted)</span></div>
    <div class="lg-title" style="margin-top:8px">Marker area ∝ ${METRIC_LABEL[state.metric]}</div>`;
}

/* -------------------------------------------------------------- tooltip etc */
function showTip(event, html) {
  const t = d3.select("#tooltip");
  const wrap = document.getElementById("map-wrap").getBoundingClientRect();
  t.html(html).style("opacity", 1);
  const node = t.node();
  let x = event.clientX - wrap.left + 14;
  let y = event.clientY - wrap.top + 12;
  if (x + node.offsetWidth > wrap.width) x -= node.offsetWidth + 28;
  if (y + node.offsetHeight > wrap.height) y -= node.offsetHeight + 24;
  t.style("left", x + "px").style("top", y + "px");
}
function hideTip() { d3.select("#tooltip").style("opacity", 0); }

/* ------------------------------------------------------------------ filters */
function buildFilterUi() {
  const statusEl = d3.select("#status-filters");
  Object.entries(STATUS_META).forEach(([key, meta]) => {
    if (key === "unknown" || key === "expanding") return;
    statusEl.append("span")
      .attr("class", "chip" + (state.status.has(key) ? " on" : ""))
      .style("background", state.status.has(key) ? meta.color : null)
      .html(`<span class="dot" style="background:${meta.color}"></span>${meta.label}`)
      .on("click", function () {
        if (state.status.has(key)) {
          state.status.delete(key);
          if (key === "operating") state.status.delete("expanding");
        } else {
          state.status.add(key);
          if (key === "operating") state.status.add("expanding");
        }
        d3.select(this).classed("on", state.status.has(key))
          .style("background", state.status.has(key) ? meta.color : null);
        render(false);
      });
  });

  const accelEl = d3.select("#accel-filters");
  const present = new Set();
  DATA.sites.forEach(s => {
    (s.accelerators || []).forEach(a => present.add(a));
    Object.keys(s.chip_families || {}).forEach(a => present.add(a));
  });
  ["NVIDIA GPU", "Google TPU", "AWS Trainium", "AMD Instinct", "Huawei Ascend",
   "Cerebras WSE", "Groq LPU", "Intel GPU", "Intel Gaudi", "Qualcomm AI100"]
    .filter(a => present.has(a))
    .forEach(a => {
      accelEl.append("span")
        .attr("class", "chip")
        .html(`<span class="dot" style="background:${ACCEL_COLORS[a]}"></span>${a}`)
        .on("click", function () {
          if (state.accel.has(a)) state.accel.delete(a); else state.accel.add(a);
          d3.select(this).classed("on", state.accel.has(a))
            .style("background", state.accel.has(a) ? ACCEL_COLORS[a] : null);
          render(false);
        });
    });

  const tierEl = d3.select("#tier-filters");
  const tierCounts = d3.rollup(DATA.sites, v => v.length, d => d.tier);
  Object.entries(TIER_META).forEach(([key, meta]) => {
    tierEl.append("span")
      .attr("class", "chip" + (state.tiers.has(key) ? " on" : ""))
      .style("background", state.tiers.has(key) ? "#4da3ff" : null)
      .text(`${meta.label} (${tierCounts.get(key) || 0})`)
      .on("click", function () {
        if (state.tiers.has(key)) state.tiers.delete(key); else state.tiers.add(key);
        d3.select(this).classed("on", state.tiers.has(key))
          .style("background", state.tiers.has(key) ? "#4da3ff" : null);
        render(false);
      });
  });
}

/* --------------------------------------------------------------------- init */
Promise.all([
  d3.json("data.json"),
  d3.json("vendor/countries-110m.json"),
]).then(([data, world]) => {
  DATA = data;
  WORLD = world;
  COUNTRIES = topojson.feature(world, world.objects.countries);

  document.getElementById("asof").textContent =
    `${DATA.sites.filter(s => s.layer !== "cloud_region").length} sites · ` +
    `${DATA.sites.filter(s => s.layer === "cloud_region").length} cloud regions · as of ${DATA.as_of}`;

  const src = DATA.sources;
  document.getElementById("source-note").innerHTML =
    `Built from ${Object.keys(src).length - 1} datasets: ` +
    `<b>dataCenterView</b> (${src["dataCenterView"].records} US records), ` +
    `<b>Epoch AI</b> (${src["Epoch AI"].records} frontier sites, CC-BY), ` +
    `<b>curated global</b> (${src["curated"].records}), ` +
    `<b>cloud region docs</b> (${src["cloud regions"].records}).<br>
     Epoch power, chip and capex figures are model estimates, not company disclosures.
     ${DATA.merge_log.length} duplicate records were merged into single sites.`;

  setupMap();
  buildFilterUi();
  render(false);

  d3.select("#metric").on("change", function () {
    state.metric = this.value;
    render();
  });
  d3.select("#btn-up").on("click", goUp);
  d3.select("#btn-reset").on("click", goWorld);
  d3.select("#toggle-labels").on("change", function () {
    state.labels = this.checked; render(false);
  });
  d3.select("#toggle-regions").on("change", function () {
    state.showRegions = this.checked; render(false);
  });
  d3.select(window).on("keydown", (event) => {
    if (event.key === "Escape") goUp();
    if (event.key === "Home") goWorld();
  });
  window.addEventListener("resize", () => {
    const t = { level: state.level, continent: state.continent, country: state.country };
    setupMap();
    if (t.level === "continent") drillToContinent(t.continent);
    else if (t.level === "country") drillToCountry(t.country, t.continent);
    else render(false);
  });
}).catch(err => {
  document.getElementById("detail").innerHTML =
    `<p class="muted">Failed to load data: ${err}</p>`;
  console.error(err);
});
