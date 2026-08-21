/* Loads the two UI bundles and indexes them.
 *
 * The vocabulary matches the registry underneath (see docs/DATA-PIPELINE.md):
 *
 *   source    where data comes from — 15 catalogued feeds, datasets and tables.
 *             sources.json, one entry each, with sample records.
 *   document  one cited URL inside a source. data.json → documents[].
 *   entity    a resolved thing with typed default parameters and provenance.
 *             data.json → entities[].
 *
 * Kept separate from app.js so the shape of the data is documented in one place.
 */
window.ATLAS = {
  raw: null,
  entities: new Map(),      // id -> entity
  byType: new Map(),        // ui type -> [entity]
  relations: [],            // {a, b, verb, weight, sources[], records[]}
  relsByEntity: new Map(),  // id -> [relation index]
  documents: new Map(),     // doc id -> document
  docsByEntity: new Map(),  // entity id -> [doc id]
  sources: new Map(),       // source id -> catalog entry
  sourceList: [],           // catalog in display order
  ready: false,

  async load(dataUrl = "data.json", sourcesUrl = "sources.json") {
    const get = async url => {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${url}: ${r.status} ${r.statusText}`);
      return r.json();
    };
    const [d, cat] = await Promise.all([get(dataUrl), get(sourcesUrl)]);
    this.raw = d;
    this.catalog = cat;

    d.entities.forEach(e => {
      this.entities.set(e.id, e);
      if (!this.byType.has(e.type)) this.byType.set(e.type, []);
      this.byType.get(e.type).push(e);
    });
    this.relations = d.relations;
    d.relations.forEach((r, i) => {
      [r.a, r.b].forEach(id => {
        if (!this.relsByEntity.has(id)) this.relsByEntity.set(id, []);
        this.relsByEntity.get(id).push(i);
      });
    });
    d.documents.forEach(doc => {
      this.documents.set(doc.id, doc);
      doc.entities.forEach(hit => {
        if (!this.docsByEntity.has(hit.entity)) this.docsByEntity.set(hit.entity, []);
        this.docsByEntity.get(hit.entity).push(doc.id);
      });
    });
    // biggest contributors first: a source's weight here is how much of the
    // registry it accounts for
    this.sourceList = cat.sources.slice().sort((a, b) =>
      (b.stats.records || 0) - (a.stats.records || 0));
    this.sourceList.forEach(s => this.sources.set(s.id, s));

    this.byType.forEach(list => list.sort((a, b) => b.weight - a.weight ||
                                                    a.name.localeCompare(b.name)));
    this.ready = true;
    return d;
  },

  type(id) { return this.raw.types[id] || { label: id, color: "#8ea0bd" }; },
  color(entityOrType) {
    const t = typeof entityOrType === "string" ? entityOrType : entityOrType.type;
    return this.type(t).color;
  },
  documentsFor(id) {
    return (this.docsByEntity.get(id) || []).map(did => this.documents.get(did));
  },
  sourceName(id) { return (this.sources.get(id) || {}).name || id; },
  paramSpec(uiType, param) {
    return ((this.raw.param_spec || {})[uiType] || {})[param] || {};
  },
  neighbours(id, { includeCoMention = true } = {}) {
    const out = [];
    (this.relsByEntity.get(id) || []).forEach(ri => {
      const r = this.relations[ri];
      if (!includeCoMention && r.verb === "co-cited") return;
      const otherId = r.a === id ? r.b : r.a;
      const other = this.entities.get(otherId);
      if (other) out.push({ rel: r, other, outgoing: r.a === id });
    });
    return out;
  },
};
