/* Chunked original-map renderer and bounded grid navigation; no generated scenery. */
"use strict";
window.PoightWorld = class PoightWorld {
  static pending = new Map();
  static async load(data, loader) {
    if (!this.pending.has(data.id))
      this.pending.set(
        data.id,
        (async () => {
          const textures = new Map();
          const sources = [
            ...new Set(
              [
                ...(data.streaming ? [] : data.chunks.flatMap((c) => [c.groundSrc, c.overSrc])),
                ...Object.values(data.fieldEffects || {}).map((e) => e.src),
              ].filter(Boolean),
            ),
          ];
          // Bound decoding concurrency; all current region chunks complete before atomic map commit.
          let cursor = 0;
          await Promise.all(
            Array.from({ length: 6 }, async () => {
              while (cursor < sources.length) {
                const src = sources[cursor++];
                textures.set(src, await loader(src));
              }
            }),
          );
          const world = new PoightWorld(data, textures);
          world.loader = loader;
          return world;
        })().catch((e) => {
          this.pending.delete(data.id);
          throw e;
        }),
      );
    return this.pending.get(data.id);
  }
  constructor(data, textures) {
    this.data = data;
    this.textures = textures;
    this.cell = data.cellSize;
    this.columns = data.columns;
    this.rows = data.rows;
    this.walk = Uint8Array.from(atob(data.walkB64), (c) => c.charCodeAt(0));
    this.elevations = Uint8Array.from(atob(data.elevationB64), (c) => c.charCodeAt(0));
    if (
      this.walk.length !== this.columns * this.rows ||
      this.elevations.length !== this.walk.length
    )
      throw new Error("地图网格长度不匹配");
    this.behaviors = Uint8Array.from(atob(data.behaviorB64), (c) => c.charCodeAt(0));
    this.water = Uint8Array.from(atob(data.waterB64 || ""), (c) => c.charCodeAt(0));
    this.capabilities = {};
    this.traversalRules = data.traversalRules || {};
    this.bidirectionalLedges = new Set(data.bidirectionalLedges || []);
    this.seamLinks = new window.PoightSeams(this);
    this.bridges = data.bridges ? new window.PoightBridges(this, data.bridges) : null;
    this.lastDrawChunks = 0;
    this.loading = new Map();
    this.wanted = new Set();
    this.evicted = 0;
    this.streamErrors = [];
    this.visibleMissing = 0;
    this.lastPathVisited = 0;
    this.resetGrass();
    this.data.grassRegions ??= window.PoightGrassStealth.nativeRegions(this);
  }
  async prepareView(x, y, w, h) {
    if (!this.data.streaming) return;
    this.preparing = (this.preparing || 0) + 1;
    try {
      await this.stream(x - w / 2, y - h / 2, w, h);
    } finally {
      this.preparing--;
      this.streamView = null;
    }
  }
  release() {
    if (!this.data.streaming) return;
    this.wanted.clear();
    const effects = new Set(Object.values(this.data.fieldEffects || {}).map((e) => e.src));
    for (const src of this.textures.keys())
      if (!effects.has(src)) {
        this.textures.delete(src);
        this.evicted++;
      }
  }
  stream(x, y, w, h) {
    // 1.5 viewports on each side; keep 3 viewports to avoid boundary thrashing.
    const near = (c, n) => c.x + c.w > x - w * n && c.x < x + w * (1 + n) &&
      c.y + c.h > y - h * n && c.y < y + h * (1 + n);
    const wanted = new Set(), keep = new Set(), jobs = [];
    for (const c of this.data.chunks) {
      if (!near(c, 3)) continue;
      for (const src of [c.groundSrc, c.overSrc].filter(Boolean)) {
        keep.add(src);
        if (near(c, 1.5)) wanted.add(src);
      }
    }
    this.wanted = keep;
    const effects = new Set(Object.values(this.data.fieldEffects || {}).map((e) => e.src));
    for (const src of this.textures.keys())
      if (!keep.has(src) && !effects.has(src)) {
        this.textures.delete(src);
        this.evicted++;
      }
    for (const src of wanted) {
      if (this.textures.has(src)) continue;
      if (!this.loading.has(src)) {
        const job = this.loader(src).then((im) => {
          if (this.wanted.has(src)) this.textures.set(src, im);
        }).finally(() => this.loading.delete(src));
        this.loading.set(src, job);
      }
      jobs.push(this.loading.get(src));
    }
    return Promise.all(jobs);
  }
  index(x, y) {
    const col = Math.floor(x / this.cell),
      row = Math.floor(y / this.cell);
    return col >= 0 && col < this.columns && row >= 0 && row < this.rows
      ? row * this.columns + col
      : -1;
  }
  pass(col, row, upper) {
    if (col < 0 || row < 0 || col >= this.columns || row >= this.rows) return false;
    if (this.bridges) return this.bridges.pass(row * this.columns + col, upper);
    return (
      col >= 0 &&
      col < this.columns &&
      row >= 0 &&
      row < this.rows &&
      (this.walk[row * this.columns + col] === 1 ||
        (this.capabilities.swim && this.water[row * this.columns + col] === 1))
    );
  }
  isWater(x, y, upper) {
    const i = this.index(x, y);
    if (this.bridges && (upper ?? this.bridges.layer(i))) return false;
    return !!(this.capabilities.swim && i >= 0 && (this.water[i] || this.bridges?.water[i]));
  }
  traversable(a, b) {
    if (a < 0 || b < 0) return false;
    if (a === b) return true;
    const dx = b % this.columns - a % this.columns,
      dy = Math.floor(b / this.columns) - Math.floor(a / this.columns);
    for (const at of [a, b]) {
      const rule = this.traversalRules[this.behaviors[at]];
      if (rule?.mode === "ledge" && !this.bidirectionalLedges.has(at) &&
          dx * rule.direction[0] + dy * rule.direction[1] <= 0) return false;
    }
    return [a, b].some((at) => this.traversalRules[this.behaviors[at]]?.elevationLink) ||
      this.compatible(this.elevations[a], this.elevations[b]) ||
      (this.capabilities.swim && (this.water[a] || this.water[b]) &&
        [1, 3].includes(this.elevations[a]) && [1, 3].includes(this.elevations[b]));
  }
  elevation(x, y) {
    const i = this.index(x, y);
    return i < 0 ? 0 : this.elevations[i];
  }
  compatible(a, b) {
    return a === b || a === 0 || b === 0 || a === 15 || b === 15;
  }
  area(x, y) {
    return (
      this.data.areas.find((a) => x >= a.x && y >= a.y && x < a.x + a.w && y < a.y + a.h) || null
    );
  }
  blockers(ax, ay, bx = ax, by = ay, pad = 0, upper) {
    const s = this.cell,
      seen = new Set(),
      result = [],
      steps = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / (s * 0.5)));
    for (let i = 0; i <= steps; i++) {
      const x = ax + ((bx - ax) * i) / steps,
        y = ay + ((by - ay) * i) / steps;
      const reach = pad + s * 0.51; // Supercover candidate cells, exact geometry is checked by caller.
      for (let row = Math.floor((y - reach) / s); row <= Math.floor((y + reach) / s); row++)
        for (let col = Math.floor((x - reach) / s); col <= Math.floor((x + reach) / s); col++) {
          const key = col + "," + row;
          if (seen.has(key)) continue;
          seen.add(key);
          const [sc, sr] = this.seamLinks.sample(col, row, { x: ax, y: ay });
          const inBounds = sc >= 0 && sr >= 0 && sc < this.columns && sr < this.rows;
          const legal = this.bridges && upper !== undefined
            ? inBounds && this.bridges.clearance(sr * this.columns + sc, upper)
            : this.pass(sc, sr);
          if (!legal)
            result.push({ x: col * s, y: row * s, w: s, h: s, type: "emerald", column: col, row });
        }
    }
    return result;
  }
  freeAt(x, y, r = 18, upper) {
    if (this.bridges) upper ??= this.bridges.layer(this.index(x, y));
    return this.blockers(x, y, x, y, r, upper).every(
      (o) =>
        Math.hypot(
          x - Math.max(o.x, Math.min(o.x + o.w, x)),
          y - Math.max(o.y, Math.min(o.y + o.h, y)),
        ) >= r,
    );
  }
  movementScale(p, dx, dy) {
    const rule = this.traversalRules[this.behaviors[this.index(p.x, p.y)]];
    if (!rule || rule.mode !== "water" || !this.capabilities.swim) return 1;
    if (!rule.current) return rule.speed || 1;
    const dot = dx * rule.current[0] + dy * rule.current[1];
    return dot < 0 ? rule.againstSpeed : dot > 0 ? rule.withSpeed : 1;
  }
  move(p, dx, dy, r = 18) {
    const scale = this.movementScale(p, dx, dy);
    dx *= scale;
    dy *= scale;
    if (this.bridges) return this.bridges.move(p, dx, dy, r);
    // Small swept steps, including dash/rush, prevent tunneling; slide each axis separately.
    const count = Math.max(1, Math.ceil(Math.hypot(dx, dy) / Math.min(r / 2, 8)));
    for (let i = 0; i < count; i++)
      for (const [x, y] of [
        [dx / count, 0],
        [0, dy / count],
      ]) {
        const crossing = this.seamLinks.crossing(p, p.x + x, p.y + y);
        if (crossing?.blocked) continue;
        const nx = crossing?.x ?? p.x + x,
          ny = crossing?.y ?? p.y + y;
        if (
          this.freeAt(nx, ny, r) &&
          this.traversable(this.index(p.x, p.y), this.index(nx, ny))
        ) {
          const old = this.index(p.x, p.y);
          if (crossing) p.seamVisual = {
            x: -crossing.shiftX, y: -crossing.shiftY, left: 0.24,
          };
          p.x = nx;
          p.y = ny;
          if (old !== this.index(p.x, p.y)) this.touchGrass(p);
        }
      }
  }
  resetGrass() {
    this.grassEffects = [];
    this.grassTriggered = 0;
  }
  grassType(x, y) {
    const i = this.index(x, y),
      b = i >= 0 ? this.behaviors[i] : -1;
    return (
      Object.entries(this.data.fieldEffects || {}).find(([k, e]) => e.behaviors.includes(b))?.[0] ||
      null
    );
  }
  touchGrass(p) {
    if (p.hp <= 0 || p.char?.flightHeight || p.jumpHeight > 2) return;
    const type = this.grassType(p.x, p.y);
    if (!type) return;
    const at = this.index(p.x, p.y),
      key = (p.isPlayer ? "p" : "e") + ":" + at;
    const old = this.grassEffects.find((e) => e.key === key);
    if (old) old.age = 0;
    else this.grassEffects.push({ key, at, type, age: 0 });
    this.grassTriggered++;
    if (this.grassEffects.length > 32) this.grassEffects.shift();
  }
  grassFrame(e) {
    let age = e.age;
    const d = this.data.fieldEffects[e.type];
    for (const q of d.sequence) {
      if (age < q.duration) return q.frame;
      age -= q.duration;
    }
    return d.idleFrame;
  }
  updateGrass(dt, actors) {
    this.seamLinks.tick(dt, actors);
    for (const e of this.grassEffects) e.age += dt;
    this.grassEffects = this.grassEffects.filter(
      (e) =>
        e.age < this.data.fieldEffects[e.type].duration ||
        actors.some((p) => p.hp > 0 && !p.char.flightHeight && this.index(p.x, p.y) === e.at),
    );
  }
  drawGrass(ctx, actors) {
    const all = [...this.grassEffects];
    for (const p of actors) {
      if (p.hp <= 0 || p.char.flightHeight || p.jumpHeight > 2) continue;
      const type = this.grassType(p.x, p.y),
        at = this.index(p.x, p.y);
      if (type && !all.some((e) => e.at === at)) all.push({ at, type, age: Infinity });
    }
    for (const e of all) {
      const d = this.data.fieldEffects[e.type],
        im = this.textures.get(d.src);
      if (!im) continue;
      const x = (e.at % this.columns) * this.cell,
        y = Math.floor(e.at / this.columns) * this.cell;
      ctx.drawImage(im, this.grassFrame(e) * 16, 0, 16, 16, x, y, this.cell, this.cell);
    }
  }
  nearest(x, y, upper) {
    const col = Math.max(0, Math.min(this.columns - 1, Math.floor(x / this.cell))),
      row = Math.max(0, Math.min(this.rows - 1, Math.floor(y / this.cell)));
    for (let radius = 0; radius <= 10; radius++) {
      let best = -1,
        distance = Infinity;
      for (let dy = -radius; dy <= radius; dy++)
        for (let dx = -radius; dx <= radius; dx++) {
          if (radius && Math.abs(dx) !== radius && Math.abs(dy) !== radius) continue;
          const xx = col + dx,
            yy = row + dy;
          if (!this.pass(xx, yy, upper)) continue;
          const d = (this.cell * (xx + 0.5) - x) ** 2 + (this.cell * (yy + 0.5) - y) ** 2;
          if (d < distance) {
            distance = d;
            best = yy * this.columns + xx;
          }
        }
      if (best >= 0) return best;
    }
    return -1;
  }
  waypointReached(p, point) {
    // A seam doorway is consumed only after crossing, not by the usual 22px arrival tolerance.
    return point.seamTo !== undefined
      ? this.index(p.x, p.y) === point.seamTo
      : Math.hypot(point.x - p.x, point.y - p.y) < 22;
  }
  findPath(sx, sy, tx, ty, sourceLayer, targetLayer) {
    if (this.bridges?.navigation(sx, sy, tx, ty))
      return this.bridges.path(sx, sy, tx, ty, sourceLayer, targetLayer);
    const start = this.nearest(sx, sy),
      goal = this.nearest(tx, ty);
    this.lastPathVisited = 0;
    if (start < 0 || goal < 0) return [];
    const n = this.columns,
      s = this.cell,
      gx = goal % n,
      gy = Math.floor(goal / n),
      h = (i) => {
        const dx = Math.abs((i % n) - gx),
          dy = Math.abs(Math.floor(i / n) - gy);
        // A portal can shorten geometric distance by two cells; zero remains admissible.
        return this.seamLinks.edges.length ? 0 : Math.max(dx, dy) + 0.41421356237 * Math.min(dx, dy);
      };
    const heap = [],
      score = new Map([[start, 0]]),
      parent = new Map(),
      closed = new Set();
    const push = (i, f) => {
      heap.push({ i, f });
      let at = heap.length - 1;
      while (at) {
        const p = (at - 1) >> 1;
        if (heap[p].f <= f) break;
        [heap[p], heap[at]] = [heap[at], heap[p]];
        at = p;
      }
    };
    const pop = () => {
      const value = heap[0],
        last = heap.pop();
      if (heap.length) {
        heap[0] = last;
        let at = 0;
        while (true) {
          let a = at * 2 + 1,
            b = a + 1;
          if (a >= heap.length) break;
          if (b < heap.length && heap[b].f < heap[a].f) a = b;
          if (heap[at].f <= heap[a].f) break;
          [heap[at], heap[a]] = [heap[a], heap[at]];
          at = a;
        }
      }
      return value.i;
    };
    const legal = (a, b) => this.traversable(a, b);
    push(start, h(start));
    let found = false;
    while (heap.length && closed.size < 18000) {
      const at = pop();
      if (closed.has(at)) continue;
      closed.add(at);
      if (at === goal) {
        found = true;
        break;
      }
      const x = at % n,
        y = Math.floor(at / n);
      for (const [dx, dy] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
        [1, 1],
        [-1, 1],
        [1, -1],
        [-1, -1],
      ]) {
        const linked = this.seamLinks.links.get(`${at}:${dx}:${dy}`);
        if (linked === undefined) {
          const sample = this.seamLinks.sample(x + dx, y + dy,
            { x: (x + 0.5) * s, y: (y + 0.5) * s });
          if (sample[0] !== x + dx || sample[1] !== y + dy) continue;
        }
        const ni = linked ?? (y + dy) * n + x + dx,
          xx = ni % n,
          yy = Math.floor(ni / n);
        if (!this.pass(xx, yy) || closed.has(ni) || !legal(at, ni)) continue;
        if (
          dx &&
          dy &&
          (!this.pass(xx, y) ||
            !this.pass(x, yy) ||
            !legal(at, y * n + xx) ||
            !legal(at, yy * n + x))
        )
          continue;
        const value = score.get(at) + (dx && dy ? Math.SQRT2 : 1) *
          (this.capabilities.swim && this.water[ni] ? 1.3 : 1);
        if (value < (score.get(ni) ?? Infinity)) {
          score.set(ni, value);
          parent.set(ni, at);
          push(ni, value + h(ni));
        }
      }
    }
    this.lastPathVisited = closed.size;
    if (!found) return [];
    const result = [];
    for (let at = goal; at !== start; at = parent.get(at))
      {
        result.push({ x: ((at % n) + 0.5) * s, y: (Math.floor(at / n) + 0.5) * s });
        const prev = parent.get(at);
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          if (this.seamLinks.links.get(`${prev}:${dx}:${dy}`) !== at) continue;
          // Steer at the physical doorway first; after crossing, replan in destination space.
          result.push({ x: ((prev % n) + 0.5 + dx * 0.55) * s,
            y: (Math.floor(prev / n) + 0.5 + dy * 0.55) * s, seamTo: at });
        }
      }
    return result.reverse();
  }
  draw(ctx, cx, cy, w, h, key) {
    if (key === "ground" && this.data.streaming && !this.preparing) {
      const viewKey = [cx, cy, w, h].map((v) => Math.floor(v / 128)).join();
      if (this.streamView !== viewKey) {
        this.streamView = viewKey;
        this.stream(cx, cy, w, h).catch((e) => {
          this.streamErrors.push(String(e));
          this.streamView = null; // Retry; errors stay visible to acceptance tooling.
        });
      }
    }
    let count = 0, missing = 0;
    for (const c of this.data.chunks) {
      const src = c[key + "Src"];
      if (!src || c.x + c.w <= cx || c.y + c.h <= cy || c.x >= cx + w || c.y >= cy + h) continue;
      const im = this.textures.get(src);
      if (im) {
        ctx.drawImage(im, c.x - cx, c.y - cy, c.w, c.h);
        count++;
      } else missing++;
    }
    if (key === "ground") {
      this.lastDrawChunks = count;
      this.visibleMissing = missing;
    }
  }
  stats() {
    return {
      chunks: this.data.chunks.length,
      textures: this.textures.size,
      loading: this.loading.size,
      evicted: this.evicted,
      visibleMissing: this.visibleMissing,
      streamErrors: this.streamErrors,
      residentSources: [...this.textures.keys()],
      lastDrawChunks: this.lastDrawChunks,
      lastPathVisited: this.lastPathVisited,
      fullWorldCanvas: false,
      sourceMaps: this.data.areas.length,
      grassTriggered: this.grassTriggered,
      grassActive: this.grassEffects.length,
      grassFrames: this.grassEffects.map((e) => ({
        at: e.at,
        type: e.type,
        frame: this.grassFrame(e),
        age: e.age,
      })),
    };
  }
};
