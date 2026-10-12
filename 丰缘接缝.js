/* Explicit original-connection offsets; raw elevation/collision/bridge cells stay intact. */
"use strict";
window.PoightSeams = class PoightSeams {
  constructor(world) {
    this.world = world;
    this.edges = (world.data.seams || []).filter((e) => e.shift?.some(Boolean));
    this.links = new Map();
    this.boundaries = new Map();
    for (const edge of this.edges) {
      const area = world.data.areas.find((a) => a.id === edge.from);
      const target = world.data.areas.find((a) => a.id === edge.to);
      for (let y = area.gridY; y < area.gridY + area.rows; y++)
        for (let x = area.gridX; x < area.gridX + area.columns; x++) {
          const near = { left: x < area.gridX + 2, right: x >= area.gridX + area.columns - 2,
            up: y < area.gridY + 2, down: y >= area.gridY + area.rows - 2 }[edge.direction];
          if (!near) continue;
          const key = y * world.columns + x;
          if (!this.boundaries.has(key)) this.boundaries.set(key, []);
          this.boundaries.get(key).push({ edge, area, target });
        }
      const [dx, dy] = this.direction(edge.direction);
      for (const [x, y, xx, yy] of edge.pairs) {
        const a = y * world.columns + x;
        this.links.set(`${a}:${dx}:${dy}`, yy * world.columns + xx);
      }
    }
  }
  connects(ax, ay, bx, by) {
    const a = this.world.area(ax, ay)?.id, b = this.world.area(bx, by)?.id;
    return a !== b && this.edges.some((e) => e.from === a && e.to === b);
  }
  direction(d) {
    return { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] }[d];
  }
  sample(col, row, anchor) {
    const w = this.world;
    const boundaries = this.boundaries.get(w.index(anchor.x, anchor.y));
    if (!boundaries) return [col, row];
    for (const { edge, area, target } of boundaries) {
      const outside = { left: col < area.gridX, right: col >= area.gridX + area.columns,
        up: row < area.gridY, down: row >= area.gridY + area.rows }[edge.direction];
      if (!outside) continue;
      const [dx, dy] = edge.shift;
      if (col + dx >= target.gridX && col + dx < target.gridX + target.columns &&
          row + dy >= target.gridY && row + dy < target.gridY + target.rows)
        return [col + dx, row + dy];
    }
    return [col, row];
  }
  crossing(p, nx, ny) {
    const w = this.world;
    const a = w.index(p.x, p.y), b = w.index(nx, ny);
    if (a === b) return null;
    const dx = b % w.columns - a % w.columns;
    const dy = Math.floor(b / w.columns) - Math.floor(a / w.columns);
    const next = this.links.get(`${a}:${dx}:${dy}`);
    if (next === undefined) {
      const [col, row] = this.sample(b % w.columns, Math.floor(b / w.columns), p);
      return col !== b % w.columns || row !== Math.floor(b / w.columns) ? { blocked: true } : null;
    }
    const shiftX = (next % w.columns - b % w.columns) * w.cell;
    const shiftY = (Math.floor(next / w.columns) - Math.floor(b / w.columns)) * w.cell;
    return { x: nx + shiftX, y: ny + shiftY, shiftX, shiftY };
  }
  // Presentation interpolates the 2-cell correction over 240ms; simulation commits atomically.
  tick(dt, actors) {
    for (const p of actors) {
      if (!p.seamVisual) continue;
      p.seamVisual.left = Math.max(0, p.seamVisual.left - dt);
      if (!p.seamVisual.left) delete p.seamVisual;
    }
  }
  static visual(p) {
    const v = p.seamVisual;
    const k = v ? v.left / 0.24 : 0;
    return { x: p.x + (v?.x || 0) * k, y: p.y + (v?.y || 0) * k };
  }
};
