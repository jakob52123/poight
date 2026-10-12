/* Browser-side verification of the actual runtime, not a second Python pathfinder. */
() => {
  const catalog = window.__waterTest.catalog();
  const worlds = catalog.terrains.map((data) => {
    const w = new window.PoightWorld(data, new Map());
    w.capabilities = { swim: true, dive: true, warps: true };
    return w;
  });
  const main = worlds[0], results = [];
  const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail });
  const fixtures = Object.entries(main.traversalRules).map(([code, rule]) => {
    const n = 7, h = 5, size = n * h, b = Number(code);
    const enc = (v) => btoa(String.fromCharCode(...v));
    const data = { cellSize: 48, columns: n, rows: h, chunks: [], areas: [],
      walkB64: enc(Array(size).fill(rule.mode === "water" ? 0 : 1)),
      waterB64: enc(Array(size).fill(rule.mode === "water" ? 1 : 0)),
      behaviorB64: enc(Array(size).fill(b)), elevationB64: enc(Array(size).fill(3)),
      traversalRules: main.traversalRules };
    const w = new window.PoightWorld(data, new Map());
    w.capabilities = { swim: true };
    if (rule.mode === "water") {
      const [dx, dy] = rule.current || [0, 1];
      for (const sign of [-1, 1]) {
        const p = { x: 168, y: 120 };
        w.move(p, sign * dx * 16, sign * dy * 16, 20);
        const expected = 16 * (rule.current ? sign < 0 ? 0.5 : 1.5 : rule.speed || 1);
        check(`Speed ${code}/${sign}`, Math.abs(Math.hypot(p.x - 168, p.y - 120) - expected) < 1e-7,
          { expected, actual: Math.hypot(p.x - 168, p.y - 120) });
      }
      w.capabilities.swim = false;
      check(`No swim capability blocks ${code}`, !w.pass(3, 2));
    }
    if (rule.mode === "ledge") {
      const a = 2 * n + 3, [dx, dy] = rule.direction, b = a + dx + dy * n;
      check(`One-way ledge ${code}`, w.traversable(a, b) && !w.traversable(b, a));
      w.bidirectionalLedges = new Set([a, b]);
      check(`Registered ledge return ${code}`, w.traversable(b, a));
    }
    return code;
  });
  check(
    "All policy entries exercised",
    fixtures.length === Object.keys(main.traversalRules).length,
  );
  // Actual source cells: moving a body across a center-to-center edge, not pass() alone.
  for (const [code, rule] of Object.entries(main.traversalRules)) {
    const b = Number(code);
    if (!["bridge", "land"].includes(rule.mode) && b !== 19 && !rule.current) continue;
    let sourceCount = 0, walked = false;
    for (let a = 0; a < main.walk.length; a++) {
      if (main.behaviors[a] !== b) continue;
      sourceCount++;
      if (walked) continue;
      const x = a % main.columns, y = Math.floor(a / main.columns);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const next = (y + dy) * main.columns + x + dx;
        if (!main.pass(x + dx, y + dy) || !main.traversable(a, next)) continue;
        if (rule.mode === "water" && main.behaviors[next] !== b) continue;
        const p = { x: (x + 0.5) * 48, y: (y + 0.5) * 48 };
        if (!main.freeAt(p.x, p.y, 20) || !main.freeAt(p.x + dx * 48, p.y + dy * 48, 20)) continue;
        const scale = main.movementScale(p, dx, dy);
        main.move(p, dx * 48 / scale, dy * 48 / scale, 20);
        if (Math.hypot(p.x - (x + dx + 0.5) * 48, p.y - (y + dy + 0.5) * 48) < 1e-6) {
          walked = true;
          break;
        }
      }
    }
    if (sourceCount) check(`Source body traversal ${code}`, walked, { sourceCount });
  }
  const offsets = [], graph = new Map(), reverse = new Map();
  let total = 0;
  for (const w of worlds) {
    offsets.push(total);
    total += w.walk.length;
  }
  const add = (a, b) => {
    if (!graph.has(a)) graph.set(a, []);
    if (!reverse.has(b)) reverse.set(b, []);
    graph.get(a).push(b);
    reverse.get(b).push(a);
  };
  for (let j = 0; j < worlds.length; j++) {
    const w = worlds[j], off = offsets[j], n = w.columns;
    for (let a = 0; a < w.walk.length; a++) {
      if (!w.pass(a % n, Math.floor(a / n))) continue;
      const x = a % n, y = Math.floor(a / n);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const linked = w.seamLinks.links.get(`${a}:${dx}:${dy}`);
        const b = linked ?? (y + dy) * n + x + dx;
        if (linked === undefined) {
          if (x + dx < 0 || x + dx >= n || y + dy < 0 || y + dy >= w.rows) continue;
          const sample = w.seamLinks.sample(x + dx, y + dy,
            { x: (x + 0.5) * 48, y: (y + 0.5) * 48 });
          if (sample[0] !== x + dx || sample[1] !== y + dy) continue;
        }
        if (w.pass(b % n, Math.floor(b / n)) && w.traversable(a, b)) add(off + a, off + b);
      }
    }
    for (const warp of w.data.warps || []) {
      const scene = catalog.scenes.find((s) => s.id === warp.destScene);
      // Interior scenes are deliberately hidden from catalog.scenes; resolve from original destMap.
      const dest = worlds.findIndex((v) => scene ? v.data.id === scene.terrainID :
        v.data.areas.some((a) => a.id === warp.destMap));
      const other = worlds[dest];
      add(off + warp.row * n + warp.col,
        offsets[dest] + Math.floor(warp.y / 48) * other.columns + Math.floor(warp.x / 48));
    }
  }
  const spawn = catalog.scenes.find((s) => s.id === "emerald-littleroottown").spawns.player;
  const start = main.index(spawn.x, spawn.y);
  const flood = (edges) => {
    const seen = new Set([start]), q = [start];
    for (let at = 0; at < q.length; at++)
      for (const b of edges.get(q[at]) || [])
        if (!seen.has(b)) { seen.add(b); q.push(b); }
    return seen;
  };
  const forward = flood(graph), backward = flood(reverse);
  for (const area of main.data.areas) {
    let reach = false, both = false;
    for (let y = area.gridY; y < area.gridY + area.rows; y++)
      for (let x = area.gridX; x < area.gridX + area.columns; x++) {
        const a = y * main.columns + x;
        if (forward.has(a)) reach = true;
        if (forward.has(a) && backward.has(a)) both = true;
      }
    check(`Runtime reach ${area.sourceName}`, reach);
    check(`Runtime return ${area.sourceName}`, both);
  }
  for (const edge of main.seamLinks.edges) {
    const [x, y, xx, yy] = edge.pairs[Math.floor(edge.pairs.length / 2)];
    const p = { x: (x + 0.5) * 48, y: (y + 0.5) * 48 };
    const tx = (xx + 0.5) * 48, ty = (yy + 0.5) * 48;
    const path = main.findPath(p.x, p.y, tx, ty);
    check(`Seam disables straight-line AI shortcut ${edge.from}/${edge.to}`,
      main.seamLinks.connects(p.x, p.y, tx, ty));
    for (let tick = 0; tick < 360 && path.length; tick++) {
      while (path.length && main.waypointReached(p, path[0])) path.shift();
      if (!path.length) break;
      const dx = path[0].x - p.x, dy = path[0].y - p.y;
      const length = Math.hypot(dx, dy) || 1;
      main.move(p, dx / length * 1.5, dy / length * 1.5, 20);
    }
    check(`A* body follows seam doorway ${edge.from}/${edge.to}`,
      main.area(p.x, p.y)?.id === edge.to && Math.hypot(p.x - tx, p.y - ty) < 22,
      { x: p.x, y: p.y, tx, ty });
  }
  return results;
};
