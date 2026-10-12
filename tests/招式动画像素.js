// Read-only raster probe: replay the real renderer to a transparent canvas at its real transform.
// No combat or draw parameters are replaced. suppress is only used for the same-frame background.
() => {
  const proto = window.PoightMoveAnimations.prototype;
  window.pixelProbe = { enabled: false, suppress: false, last: null };
  for (const method of ["path", "drawNova"]) {
    const original = proto[method];
    proto[method] = function (ctx, ...args) {
      const probe = window.pixelProbe;
      if (!probe.enabled) return original.call(this, ctx, ...args);
      const canvas = document.createElement("canvas");
      canvas.width = ctx.canvas.width;
      canvas.height = ctx.canvas.height;
      const c = canvas.getContext("2d"), matrix = ctx.getTransform();
      c.setTransform(matrix);
      c.imageSmoothingEnabled = ctx.imageSmoothingEnabled;
      const beads = [];
      const sprite = this.sprite;
      this.sprite = function (context, key, ...rest) {
        if (key === "core-water") {
          const bead = document.createElement("canvas");
          bead.width = canvas.width;
          bead.height = canvas.height;
          const bc = bead.getContext("2d");
          bc.setTransform(matrix);
          bc.imageSmoothingEnabled = false;
          sprite.call(this, bc, key, ...rest);
          beads.push(bead);
        }
        return sprite.call(this, context, key, ...rest);
      };
      try { original.call(this, c, ...args); } finally { this.sprite = sprite; }
      probe.last = { canvas, beads, matrix, args, method };
      if (!probe.suppress) original.call(this, ctx, ...args);
    };
  }
  window.measureMovePixels = () => {
    const probe = window.pixelProbe, entry = probe.last, api = window.__waterTest;
    const s = api.snapshot(), game = document.querySelector("#game");
    const composite = game.toDataURL();
    probe.suppress = true;
    api.step(0);
    const bg = game.toDataURL(),
      b = game.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    probe.suppress = false;
    api.step(0);
    const { canvas, matrix, args, beads, method } = entry;
    const inverse = matrix.inverse(),
      d = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    const nova = method === "drawNova", root = nova ? args[0] : args[1],
      front = nova ? root : args[2];
    const dx = front.x - root.x, dy = front.y - root.y, length = Math.hypot(dx, dy) || 1;
    const lum = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
    let count = 0, colored = 0, saturation = 0, foreground = 0, background = 0, bright = 0;
    let lo = Infinity, hi = -Infinity, radialMin = Infinity, radialMax = -Infinity;
    let centerLuma = 0, centerCount = 0;
    const sections = Array.from({ length: 8 }, () => ({ min: Infinity, max: -Infinity }));
    for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
      const i = (y * canvas.width + x) * 4;
      if (d[i + 3] < 250) continue; // Opaque body, NOT glow or an advertised lineWidth.
      const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse);
      const along = ((p.x - root.x) * dx + (p.y - root.y) * dy) / length;
      if (!nova && (along < length * .25 || along > length * .75)) continue;
      const radius = Math.hypot(p.x - root.x, p.y - root.y);
      if (nova && Math.abs(radius - root.radius) > 10) continue;
      const normal = ((p.y - root.y) * dx - (p.x - root.x) * dy) / length;
      lo = Math.min(lo, normal); hi = Math.max(hi, normal);
      radialMin = Math.min(radialMin, radius); radialMax = Math.max(radialMax, radius);
      const r = d[i], g = d[i + 1], blue = d[i + 2], max = Math.max(r, g, blue);
      const sat = max ? (max - Math.min(r, g, blue)) / max : 0;
      // White highlights/beam core are specified separately; do not average them into hue chroma.
      if (sat > .12) { colored++; saturation += sat; }
      const l = lum(r, g, blue);
      if (!nova) {
        const bin = Math.min(7, Math.floor((along / length - .25) * 16));
        sections[bin].min = Math.min(sections[bin].min, normal);
        sections[bin].max = Math.max(sections[bin].max, normal);
        if (Math.abs(normal) < 1) { centerLuma += l; centerCount++; }
      }
      if (l >= 230) bright++;
      foreground += l;
      background += lum(b[i], b[i + 1], b[i + 2]);
      count++;
    }
    let beadDiameter = null;
    if (beads.length) {
      const data = beads.at(-1).getContext("2d")
        .getImageData(0, 0, canvas.width, canvas.height).data;
      let min = Infinity, max = -Infinity;
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        if (data[(y * canvas.width + x) * 4 + 3] < 250) continue;
        const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse);
        const n = (p.y * dx - p.x * dy) / length;
        min = Math.min(min, n); max = Math.max(max, n);
      }
      beadDiameter = max - min + 1 / matrix.a;
    }
    return { composite, background: bg, mask: canvas.toDataURL(), count,
      beadCount: beads.length, beadDiameter, opaqueWidth: hi - lo + 1 / matrix.a,
      minimumBeamWidth: nova ? null : Math.min(...sections.map(s => s.max - s.min + 1 / matrix.a)),
      centerLuma: centerLuma / Math.max(1, centerCount),
      saturation: saturation / Math.max(1, colored), colorFraction: colored / Math.max(1, count),
      foregroundLuma: foreground / count, backgroundLuma: background / count,
      contrast: Math.abs(foreground - background) / count, brightPixels: bright,
      radialMin, radialMax, radius: nova ? root.radius : null,
      height: s.player.body.visibleSize[1], hp: s.enemy.hp,
    };
  };
}
