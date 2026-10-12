// Mirror the production paint dispatch at its actual Canvas transform, never a test renderer.
() => {
  window.heroProbe = { enabled: false, suppress: false, id: null, kind: null, last: null };
  const shake = window.PoightArena.shakeFrame;
  window.PoightArena.shakeFrame = function (ctx, canvas, ...args) {
    const p = window.heroProbe;
    if (p.enabled && p.id === "thunder" && p.target) {
      const c = p.target.getContext("2d");
      c.setTransform(ctx.getTransform());
      shake.call(this, c, p.target, ...args);
    }
    return shake.call(this, ctx, canvas, ...args);
  };
  const core = window.PoightMoveAnimations.prototype, sprite = core.sprite;
  core.sprite = function (ctx, key, x, y, size, ...rest) {
    const p = window.heroProbe;
    const hit = this.bursts.find(b => b.id === p.id && Math.hypot(b.x-x, b.y-y) < 1);
    if (p.enabled && key.startsWith("core-impact-") && hit) {
      if (p.suppress) return;
      const layer = document.createElement("canvas");
      layer.width = ctx.canvas.width; layer.height = ctx.canvas.height;
      const c = layer.getContext("2d"), matrix = ctx.getTransform();
      c.setTransform(matrix); c.imageSmoothingEnabled = false;
      sprite.call(this, c, key, x, y, size, ...rest);
      const data = c.getImageData(0, 0, layer.width, layer.height).data;
      let count = 0;
      for (let i = 3; i < data.length; i += 4) if (data[i] >= 250) count++;
      p.contact = { id: hit.id, x, y, time: this.time, age: hit.age, count };
    }
    return sprite.call(this, ctx, key, x, y, size, ...rest);
  };
  const proto = window.PoightHeroVisuals.prototype, paint = proto.paint;
  const electrify = proto.electrify;
  proto.electrify = function (ctx, target, ...args) {
    const p = window.heroProbe;
    if (p.enabled && p.id === "thunder" && target.id === 6) {
      const canvas = document.createElement("canvas");
      canvas.width = ctx.canvas.width; canvas.height = ctx.canvas.height;
      const c = canvas.getContext("2d");
      c.setTransform(ctx.getTransform()); c.imageSmoothingEnabled = false;
      c.drawImage(...args);
      p.target = canvas;
      p.shockAge = this.shocks.get(target);
      const flash = document.createElement("canvas");
      flash.width = canvas.width; flash.height = canvas.height;
      const f = flash.getContext("2d"); f.setTransform(ctx.getTransform());
      electrify.call(this, f, target, ...args);
      const pixels = f.getImageData(0, 0, flash.width, flash.height).data;
      p.flashPixels = 0;
      for (let i = 3; i < pixels.length; i += 4) if (pixels[i] > 200) p.flashPixels++;
    }
    return electrify.call(this, ctx, target, ...args);
  };
  proto.paint = function (ctx, s) {
    const p = window.heroProbe;
    if (!p.enabled || p.id !== s.id) return paint.call(this, ctx, s);
    const customContact = (s.kind === "claw" && s.id === "dragonclaw") ||
      (s.kind === "thunder" && s.part === "ring");
    if (s.kind === p.kind || customContact) {
      const canvas = document.createElement("canvas");
      canvas.width = ctx.canvas.width;
      canvas.height = ctx.canvas.height;
      const c = canvas.getContext("2d"), matrix = ctx.getTransform();
      c.setTransform(matrix);
      c.imageSmoothingEnabled = false;
      const flames = [], texture = this.texture, strokes = [], line = this.line;
      this.line = function (g, points, width, color) {
        strokes.push({ points, width, color });
        return line.call(this, g, points, width, color);
      };
      this.texture = function (g, key, x, y, size, ...rest) {
        if (s.kind === "projectile" && ["flame0", "flame1"].includes(key)) {
          const tile = document.createElement("canvas");
          tile.width = canvas.width;
          tile.height = canvas.height;
          const tc = tile.getContext("2d");
          tc.setTransform(matrix);
          tc.imageSmoothingEnabled = false;
          texture.call(this, tc, key, x, y, size, ...rest);
          flames.push({ canvas: tile, x, y, size });
        }
        return texture.call(this, g, key, x, y, size, ...rest);
      };
      try { paint.call(this, c, s); } finally { this.texture = texture; this.line = line; }
      const entry = { canvas, matrix, s: { ...s }, flames, strokes };
      if (s.kind !== "thunder" || s.part === "bolt") p.last = entry;
      if (s.part === "ring") p.ring = entry;
      if (customContact) {
        const d = c.getImageData(0, 0, canvas.width, canvas.height).data;
        let count = 0;
        for (let i = 3; i < d.length; i += 4) if (d[i] >= 250) count++;
        const age = s.kind === "claw" ? s.age : Math.max(0, s.since);
        p.contact = { id: s.id, time: this.core.time, age, count };
      }
    }
    if (!p.suppress) paint.call(this, ctx, s);
  };
  window.measureHeroRevision = () => {
    const p = window.heroProbe, entry = p.id === "thunder" ? p.ring : p.last;
    if (!entry) return null;
    const { canvas, matrix, s } = entry, unit = 1 / Math.hypot(matrix.a, matrix.b);
    const inv = matrix.inverse(), w = canvas.width, h = canvas.height;
    const d = canvas.getContext("2d").getImageData(0, 0, w, h).data;
    const seen = new Uint8Array(w * h), components = [];
    for (let at = 0; at < w * h; at++) {
      if (seen[at] || d[at * 4 + 3] < 250) continue;
      const queue = [at]; seen[at] = 1;
      let lo = Infinity, hi = -Infinity, nlo = Infinity, nhi = -Infinity;
      for (let i = 0; i < queue.length; i++) {
        const k = queue[i], x = k % w, y = Math.floor(k / w);
        const q = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
        const along = (q.x + q.y) / Math.SQRT2, normal = (q.y - q.x) / Math.SQRT2;
        lo = Math.min(lo, along); hi = Math.max(hi, along);
        nlo = Math.min(nlo, normal); nhi = Math.max(nhi, normal);
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx, yy = y + dy, j = yy * w + xx;
          if (xx < 0 || xx >= w || yy < 0 || yy >= h || seen[j] || d[j * 4 + 3] < 250) continue;
          seen[j] = 1; queue.push(j);
        }
      }
      components.push({ count: queue.length, length: hi - lo + unit, width: nhi - nlo + unit });
    }
    let target = 0, original = 0, ringMin = Infinity, ringMax = -Infinity, center = 0;
    const game = document.querySelector("#game");
    const full = game.getContext("2d").getImageData(0, 0, w, h).data;
    const raw = p.target?.getContext("2d").getImageData(0, 0, w, h).data;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      if (raw && raw[i + 3] >= 250) {
        target++;
        if ([0, 1, 2].every(c => Math.abs(raw[i + c] - full[i + c]) <= 8)) original++;
      }
      if (s.part !== "ring" || d[i + 3] < 250) continue;
      const q = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
      ringMin = Math.min(ringMin, q.x); ringMax = Math.max(ringMax, q.x);
      if (Math.hypot(q.x - s.x, (q.y - s.y) / .52) < s.targetHeight * .30) center++;
    }
    let boltOpaque = 0;
    if (p.id === "thunder" && p.last) {
      const b = p.last.canvas.getContext("2d").getImageData(0, 0, w, h).data;
      for (let i = 3; i < b.length; i += 4) if (b[i] >= 250) boltOpaque++;
    }
    return { components, age: s.age, flashPixels: p.flashPixels, boltOpaque,
      targetPixels: target, originalPixels: original,
      originalFraction: target ? original / target : null, shockAge: p.shockAge,
      ringDiameter: Number.isFinite(ringMin) ? ringMax - ringMin + unit : 0,
      ringCenterPixels: center };
  };
  window.measureHeroPixels = () => {
    const p = window.heroProbe, entry = p.last, api = window.__waterTest;
    if (!entry) return null;
    const game = document.querySelector("#game"), composite = game.toDataURL();
    p.suppress = true;
    api.step(0);
    const background = game.toDataURL();
    const bg = game.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    p.suppress = false;
    api.step(0);
    const { canvas, matrix, s, flames, strokes } = entry, inv = matrix.inverse();
    const d = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
    const root = s.root || { x: s.x, y: s.y };
    const angle = s.kind === "beam" ? Math.atan2(s.front.y - root.y, s.front.x - root.x)
      : s.kind === "thunder" ? Math.PI / 2 : s.angle || 0;
    const ux = Math.cos(angle), uy = Math.sin(angle), unit = 1 / Math.hypot(matrix.a, matrix.b);
    const length = s.kind === "beam" ? Math.hypot(s.front.x - root.x, s.front.y - root.y) : 1;
    const sections = Array.from({ length: 8 }, () => ({ min: Infinity, max: -Infinity }));
    let count = 0, bright = 0, sat = 0, colored = 0, fg = 0, back = 0;
    let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    let nmin = Infinity, nmax = -Infinity, center = 0, centerN = 0;
    const lum = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
    for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
      const i = (y * canvas.width + x) * 4;
      if (d[i + 3] < 250) continue;
      const q = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
      const along = (q.x - root.x) * ux + (q.y - root.y) * uy;
      const normal = (q.y - root.y) * ux - (q.x - root.x) * uy;
      if (s.kind === "beam" && (along < length * .25 || along > length * .75)) continue;
      xmin = Math.min(xmin, q.x); xmax = Math.max(xmax, q.x);
      ymin = Math.min(ymin, q.y); ymax = Math.max(ymax, q.y);
      nmin = Math.min(nmin, normal); nmax = Math.max(nmax, normal);
      if (s.kind === "beam") {
        const bin = Math.min(7, Math.floor((along / length - .25) * 16));
        sections[bin].min = Math.min(sections[bin].min, normal);
        sections[bin].max = Math.max(sections[bin].max, normal);
        if (Math.abs(normal) < 1) { center += lum(d[i], d[i + 1], d[i + 2]); centerN++; }
      }
      const max = Math.max(d[i], d[i + 1], d[i + 2]);
      const saturation = max ? (max - Math.min(d[i], d[i + 1], d[i + 2])) / max : 0;
      if (saturation > .12) { colored++; sat += saturation; }
      const l = lum(d[i], d[i + 1], d[i + 2]);
      if (l >= 230) bright++;
      fg += l; back += lum(bg[i], bg[i + 1], bg[i + 2]); count++;
    }
    const centers = flames.map(f => {
      const data = f.canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let xlo = Infinity, xhi = -Infinity, ylo = Infinity, yhi = -Infinity, count = 0;
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        if (data[(y * canvas.width + x) * 4 + 3] < 250) continue;
        const q = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
        xlo = Math.min(xlo, q.x); xhi = Math.max(xhi, q.x);
        ylo = Math.min(ylo, q.y); yhi = Math.max(yhi, q.y); count++;
      }
      return { x: (xlo + xhi) / 2, y: (ylo + yhi) / 2,
        width: xhi - xlo + unit, height: yhi - ylo + unit, count };
    });
    return { composite, background, mask: canvas.toDataURL(), kind: s.kind, count, bright,
      width: xmax - xmin + unit, height: ymax - ymin + unit, normal: nmax - nmin + unit,
      minimumBeamWidth: s.kind === "beam"
        ? Math.min(...sections.map(s => s.max - s.min + unit)) : null,
      centerLuma: center / Math.max(1, centerN), contrast: Math.abs(fg - back) / count,
      saturation: sat / Math.max(1, colored), colorFraction: colored / Math.max(1, count),
      centers, sourceHeight: api.snapshot().player.body.visibleSize[1],
      targetHeight: api.snapshot().enemy.body.visibleSize[1], time: api.snapshot().animation.time,
      strokes: s.kind === "thunder" ? strokes : [],
      screenTop: new DOMPoint(0, ymin).matrixTransform(matrix).y,
      bounds: { xmin, xmax, ymin, ymax } };
  };
}
