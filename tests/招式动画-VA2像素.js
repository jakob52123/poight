// Read-only mirror of the ACTUAL path. Never substitutes sizes or colors.
() => {
  const proto = window.PoightMoveAnimations.prototype, original = proto.path;
  window.va2PixelProbe = { enabled: false, suppress: false, entries: [] };
  proto.path = function (ctx, ...args) {
    const probe = window.va2PixelProbe, cfg = window.PoightVA2Moves[args[0]];
    if (!probe.enabled || !cfg) return original.call(this, ctx, ...args);
    if (probe.suppress) return;
    const canvas = document.createElement("canvas");
    canvas.width = ctx.canvas.width;
    canvas.height = ctx.canvas.height;
    const matrix = ctx.getTransform(), c = canvas.getContext("2d");
    c.setTransform(matrix);
    c.imageSmoothingEnabled = false;
    const symbol = document.createElement("canvas"), sprite = this.sprite;
    symbol.width = canvas.width; symbol.height = canvas.height;
    const cc = symbol.getContext("2d");
    this.sprite = function (context, key, ...rest) {
      if (!cfg.beam && key === "va2-" + cfg.symbol) {
        cc.resetTransform();cc.clearRect(0,0,symbol.width,symbol.height);
        cc.setTransform(matrix); cc.imageSmoothingEnabled = false;
        sprite.call(this, cc, key, ...rest);
      }
      return sprite.call(this, context, key, ...rest);
    };
    try { original.call(this, c, ...args); } finally { this.sprite = sprite; }
    probe.entries.push({ canvas, matrix, args, symbol });
    if (!probe.suppress) original.call(this, ctx, ...args);
  };
  window.measureVA2Pixels = () => {
    const probe = window.va2PixelProbe, api = window.__waterTest, s = api.snapshot();
    const game = document.querySelector("#game"), composite = game.toDataURL();
    const entry = probe.entries.sort((a, b) => {
      const distance = (e) => Math.hypot(e.args[2].x - s.enemy.x, e.args[2].y - s.enemy.y + 16);
      return distance(a) - distance(b);
    })[0];
    if (!entry) throw new Error("No real VA2 draw captured");
    probe.suppress = true; api.step(0);
    const background = game.toDataURL(), bg = game.getContext("2d")
      .getImageData(0, 0, game.width, game.height).data;
    probe.suppress = false; probe.enabled = false; api.step(0);
    const cfg = window.PoightVA2Moves[entry.args[0]], mask = cfg.beam ? entry.canvas : entry.symbol;
    const d = mask.getContext("2d").getImageData(0, 0, mask.width, mask.height).data;
    const [id, root, front] = entry.args, matrix = entry.matrix, inverse = matrix.inverse();
    const dx = front.x - root.x, dy = front.y - root.y, length = Math.hypot(dx, dy) || 1;
    const lum = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
    const pixel = 1 / Math.hypot(matrix.a, matrix.b);
    const sections = Array.from({ length: 8 }, () => ({ min: Infinity, max: -Infinity }));
    let count = 0, colored = 0, saturation = 0, fgSum = 0, bgSum = 0;
    let lo = Infinity, hi = -Infinity, centerSum = 0, centerCount = 0, maxForward = -Infinity;
    for (let y = 0; y < mask.height; y++) for (let x = 0; x < mask.width; x++) {
      const i = (y * mask.width + x) * 4;
      if (d[i + 3] < 250) continue;
      const world = new DOMPoint(x + .5, y + .5).matrixTransform(inverse);
      const along = ((world.x - root.x) * dx + (world.y - root.y) * dy) / length;
      const normal = ((world.y - root.y) * dx - (world.x - root.x) * dy) / length;
      maxForward = Math.max(maxForward, along);
      if (cfg.beam && (along < length * .25 || along > length * .75)) continue;
      lo = Math.min(lo, normal); hi = Math.max(hi, normal);
      if (cfg.beam) {
        const bin = Math.min(7, Math.floor((along / length - .25) * 16));
        sections[bin].min = Math.min(sections[bin].min, normal);
        sections[bin].max = Math.max(sections[bin].max, normal);
      }
      const max = Math.max(d[i], d[i+1], d[i+2]);
      const sat = max ? (max - Math.min(d[i], d[i+1], d[i+2])) / max : 0;
      if (sat > .12) { colored++; saturation += sat; }
      const l = lum(d[i], d[i+1], d[i+2]);
      if (Math.abs(normal) <= 1) { centerSum += l; centerCount++; }
      fgSum += l; bgSum += lum(bg[i], bg[i+1], bg[i+2]); count++;
    }
    return { id, composite, background, mask: mask.toDataURL(), count, height: s.player.body.visibleSize[1],
      opaqueDiameter: hi - lo + pixel, frontOverrun: maxForward - length, pixelSize: pixel,
      minimumBeamWidth: cfg.beam ? Math.min(...sections.map((s) => s.max - s.min + pixel)) : null,
      centerLuma: centerSum / Math.max(1, centerCount),
      saturation: saturation / Math.max(1, colored), colorFraction: colored / Math.max(1, count),
      foregroundLuma: fgSum / count, backgroundLuma: bgSum / count,
      contrast: Math.abs(fgSum - bgSum) / count, hp: s.enemy.hp,
    };
  };
}
