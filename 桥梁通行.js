/* Height-preserving bridge movement across the full Hoenn component.
 * W2 owns surface policy; Route110 switches only at its original height-0 aprons.
 * No source pixels, walls, warp destinations or species capabilities change.
 */
"use strict";
window.PoightBridges = class PoightBridges {
  constructor(world, data) {
    this.world = world;
    for (const key of ["deck", "land", "water", "gateway", "cycling"])
      this[key] = Uint8Array.from(atob(data[key + "B64"]), (c) => c.charCodeAt(0));
    this.gates = new Map((data.gates || []).map((g) => [g.from, g.to]));
  }
  navigation(sx, sy, tx, ty) {
    return [this.world.area(sx, sy), this.world.area(tx, ty)].some(
      (area) => ["Route110", "Route119", "Route120", "FortreeCity"].includes(area?.sourceName),
    );
  }
  layer(i) {
    return !!(this.deck[i] && !this.land[i] && !this.water[i]);
  }
  pass(i, upper = this.layer(i)) {
    const w = this.world;
    if (i < 0 || i >= w.walk.length) return false;
    if (upper) return !!this.deck[i];
    return !!((!this.deck[i] && !this.water[i] && w.walk[i]) || this.land[i] ||
      (w.capabilities.swim && (w.water[i] || this.water[i])));
  }
  clearance(i, upper) {
    if (this.pass(i, upper)) return true;
    if (!upper) return !!(this.gateway[i] ||
      (!this.cycling[i] && this.deck[i] && this.world.elevations[i] === 4));
    const w = this.world;
    if (!this.cycling[i]) return !!(w.walk[i] && [0, 4].includes(w.elevations[i]));
    return !!(w.walk[i] && this.height(i) === 3 &&
      [i - 1, i + 1, i - w.columns, i + w.columns].some((j) => this.gateway[j]));
  }
  height(i) {
    return this.land[i] ? 3 : this.water[i] ? 1 : this.world.elevations[i];
  }
  above(p) {
    const w = this.world, i = w.index(p.x, p.y);
    return !!(p.onBridge || (this.land[i] && !this.deck[i]) ||
      (w.traversalRules[w.behaviors[i]]?.mode === "bridge" && w.elevations[i] === 3));
  }
  next(a, b, upper) {
    const w = this.world;
    if (a < 0 || b < 0 || b >= w.walk.length) return null;
    if (!this.cycling[a] && !this.cycling[b]) {
      if (upper) {
        if (this.deck[b]) return true;
        return this.pass(b, false) && [0, 4].includes(w.elevations[b]) ? false : null;
      }
      // Enter only from the deck-height bank, never from the water/road beneath.
      if (this.deck[b] && !this.deck[a] && this.pass(a, false) &&
          [0, 4].includes(w.elevations[a])) return true;
      if (!this.pass(b, false)) return null;
      if (!this.deck[a] && !this.deck[b]) return w.traversable(a, b) ? false : null;
      const x = this.height(a), y = this.height(b);
      return w.compatible(x, y) || (w.capabilities.swim && [1, 3].includes(x) &&
        [1, 3].includes(y) && (w.water[a] || w.water[b] || this.water[a] || this.water[b]))
        ? false : null;
    }
    if (upper) {
      if (this.deck[b]) return true;
      return this.gateway[a] && this.pass(b, false) && this.height(b) === 3 ? false : null;
    }
    if (this.gateway[b] && this.pass(a, false) && this.height(a) === 3) return true;
    if (!this.pass(b, false)) return null;
    if (!this.deck[a] && !this.deck[b] && !this.water[a] && !this.water[b])
      return w.traversable(a, b) ? false : null;
    const x = this.height(a), y = this.height(b);
    return w.compatible(x, y) || (w.capabilities.swim && [1, 3].includes(x) &&
      [1, 3].includes(y) && (w.water[a] || w.water[b] || this.water[a] || this.water[b]))
      ? false : null;
  }
  freeAt(x, y, r, upper) {
    return this.world.freeAt(x, y, r, upper);
  }
  gate(p, r) {
    const w = this.world, at = w.index(p.x, p.y);
    if (p.bridgeGateLock !== undefined) {
      if (at === p.bridgeGateLock || at === p.bridgeGateLock + w.columns) return;
      delete p.bridgeGateLock;
    }
    if (p.onBridge || !this.gates.has(at) || !w.capabilities.warps) return;
    const to = this.gates.get(at), x = (to % w.columns + 0.5) * w.cell,
      y = (Math.floor(to / w.columns) + 0.5) * w.cell;
    // Safe radius-aware landing, including large bodies; no wall removal.
    for (const [dx, dy] of [[0, 0], [0, 1], [1, 1], [-1, 1]]) {
      const nx = x + dx * w.cell, ny = y + dy * w.cell;
      if (!w.freeAt(nx, ny, r, false)) continue;
      p.x = nx;
      p.y = ny;
      p.onBridge = false;
      p.bridgeGateLock = to;
      return;
    }
  }
  move(p, dx, dy, r) {
    const w = this.world;
    let at = w.index(p.x, p.y);
    let upper = p.onBridge ?? this.layer(at);
    const count = Math.max(1, Math.ceil(Math.hypot(dx, dy) / Math.min(r / 2, 8)));
    for (let i = 0; i < count; i++)
      for (const [x, y] of [[dx / count, 0], [0, dy / count]]) {
        if (!x && !y) continue;
        const crossing = w.seamLinks.crossing(p, p.x + x, p.y + y);
        if (crossing?.blocked) continue;
        const nx = crossing?.x ?? p.x + x, ny = crossing?.y ?? p.y + y;
        const b = w.index(nx, ny), layer = this.next(at, b, upper);
        // Aprons overlap the adjacent land for body clearance, not for layer changes.
        if (layer !== null && this.freeAt(nx, ny, r, layer)) {
          if (crossing) p.seamVisual = {
            x: -crossing.shiftX, y: -crossing.shiftY, left: 0.24,
          };
          p.x = nx;
          p.y = ny;
          upper = layer;
          if (at !== b) w.touchGrass(p);
          p.onBridge = upper;
          this.gate(p, r);
          at = w.index(p.x, p.y);
        }
      }
    p.onBridge = upper;
  }
  path(sx, sy, tx, ty, sourceLayer, targetLayer) {
    const w = this.world, n = w.columns, s = w.cell, total = w.walk.length;
    const startCell = w.nearest(sx, sy, sourceLayer),
      goalCell = w.nearest(tx, ty, targetLayer);
    const upper = sourceLayer ?? this.layer(startCell),
      target = targetLayer ?? this.layer(goalCell);
    if (startCell < 0 || goalCell < 0) return [];
    const node = (i, layer) => i + (layer ? total : 0);
    const start = node(startCell, upper), goal = node(goalCell, target);
    const queue = [{ at: start, f: 0 }], costs = new Map([[start, 0]]);
    const parents = new Map(), closed = new Set();
    const heuristic = (i) => w.seamLinks.connects(sx, sy, tx, ty) ? 0 :
      Math.abs(i % n - goalCell % n) + Math.abs(Math.floor(i / n) - Math.floor(goalCell / n));
    // Binary min heap, bounded exactly like the existing grid navigator.
    const push = (at, f) => {
      queue.push({ at, f });
      let i = queue.length - 1;
      while (i) {
        const p = (i - 1) >> 1;
        if (queue[p].f <= f) break;
        [queue[p], queue[i]] = [queue[i], queue[p]];
        i = p;
      }
    };
    const pop = () => {
      const top = queue[0], last = queue.pop();
      if (queue.length) {
        queue[0] = last;
        let i = 0;
        while (i * 2 + 1 < queue.length) {
          let child = i * 2 + 1;
          if (child + 1 < queue.length && queue[child + 1].f < queue[child].f) child++;
          if (queue[i].f <= queue[child].f) break;
          [queue[i], queue[child]] = [queue[child], queue[i]];
          i = child;
        }
      }
      return top.at;
    };
    while (queue.length && closed.size < 18000) {
      const at = pop();
      if (closed.has(at)) continue;
      closed.add(at);
      if (at === goal) break;
      const a = at % total, layer = at >= total, x = a % n, y = Math.floor(a / n);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const xx = x + dx, yy = y + dy;
        if (xx < 0 || yy < 0 || xx >= n || yy >= w.rows) continue;
        const linked = w.seamLinks.links.get(`${a}:${dx}:${dy}`);
        if (linked === undefined) {
          const sample = w.seamLinks.sample(xx, yy, { x: (x + .5) * s, y: (y + .5) * s });
          if (sample[0] !== xx || sample[1] !== yy) continue;
        }
        const b = linked ?? yy * n + xx, nextLayer = this.next(a, b, layer);
        if (nextLayer === null) continue;
        const ni = node(b, nextLayer);
        const cost = costs.get(at) + (!nextLayer && (w.water[b] || this.water[b]) ? 1.3 : 1);
        if (cost >= (costs.get(ni) ?? Infinity)) continue;
        costs.set(ni, cost);
        parents.set(ni, at);
        push(ni, cost + heuristic(b));
      }
      // The only non-neighbor edges skip the two omitted original gatehouses.
      if (!layer && w.capabilities.warps && this.gates.has(a)) {
        const b = this.gates.get(a), ni = node(b, false), cost = costs.get(at) + 12;
        if (cost < (costs.get(ni) ?? Infinity)) {
          costs.set(ni, cost);
          parents.set(ni, at);
          push(ni, cost + heuristic(b));
        }
      }
    }
    w.lastPathVisited = closed.size;
    if (!closed.has(goal)) return [];
    const result = [];
    for (let at = goal; at !== start; at = parents.get(at)) {
      const i = at % total;
      result.push({ x: (i % n + 0.5) * s, y: (Math.floor(i / n) + 0.5) * s });
      const prev = parents.get(at) % total;
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        if (w.seamLinks.links.get(`${prev}:${dx}:${dy}`) !== i) continue;
        result.push({ x: (prev % n + .5 + dx * .55) * s,
          y: (Math.floor(prev / n) + .5 + dy * .55) * s, seamTo: i });
      }
    }
    return result.reverse();
  }
};
