/* Loads data.json and indexes it.
 *
 * Kept separate from app.js so the shape of the dataset is documented in one
 * place: entities, relations (a -> b with a verb), and sources whose
 * `entities[]` records which entity was recognised and by which method.
 */
window.ATLAS = {
  raw: null,
  entities: new Map(),      // id -> entity
  byType: new Map(),        // type -> [entity]
  relations: [],            // {a, b, verb, weight, evidence[]}
  relsByEntity: new Map(),  // id -> [relation index]
  sources: new Map(),       // id -> source
  srcByEntity: new Map(),   // entity id -> [source id]
  ready: false,

  async load(url = "data.json") {
    const d = await fetch(url).then(r => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.json();
    });
    this.raw = d;
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
    d.sources.forEach(s => {
      this.sources.set(s.id, s);
      s.entities.forEach(rec => {
        if (!this.srcByEntity.has(rec.entity)) this.srcByEntity.set(rec.entity, []);
        this.srcByEntity.get(rec.entity).push(s.id);
      });
    });
    // heaviest first inside each type — drives grid ordering
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
  sourcesFor(id) { return (this.srcByEntity.get(id) || []).map(sid => this.sources.get(sid)); },
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
