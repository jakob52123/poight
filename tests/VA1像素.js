// Observe the actual shot path and head sprite in the real Canvas transform.
() => {
  const p = window.PoightMoveAnimations.prototype, original = p.path;
  window.va1Probe = { enabled: false, suppress: false, last: null };
  p.path = function (ctx, id, root, front, ...rest) {
    const probe = window.va1Probe;
    if (!probe.enabled || !window.PoightVA1Shots[id])
      return original.call(this, ctx, id, root, front, ...rest);
    const make = () => {
      const c = document.createElement("canvas");
      c.width = ctx.canvas.width; c.height = ctx.canvas.height;
      const draw = c.getContext("2d");
      draw.setTransform(ctx.getTransform()); draw.imageSmoothingEnabled = false;
      return c;
    };
    const canvas = make(), head = make(), sprite = this.sprite;
    this.sprite = function (c, key, x, y, ...args) {
      if (key === "va1-" + id && Math.hypot(x - front.x, y - front.y) < .001)
        sprite.call(this, head.getContext("2d"), key, x, y, ...args);
      return sprite.call(this, c, key, x, y, ...args);
    };
    try { original.call(this, canvas.getContext("2d"), id, root, front, ...rest); }
    finally { this.sprite = sprite; }
    probe.last = { canvas, head, matrix: ctx.getTransform(), id, root, front, rest };
    if (!probe.suppress) original.call(this, ctx, id, root, front, ...rest);
  };
  window.measureVA1 = () => {
    const probe = window.va1Probe, e = probe.last, api = window.__waterTest;
    const composite = document.querySelector("#game").toDataURL();
    probe.suppress = true; api.step(0);
    const game = document.querySelector("#game"), background = game.toDataURL();
    const bg = game.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    probe.suppress = false; api.step(0);
    const c = e.head, data = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    const inv = e.matrix.inverse(), scale = Math.hypot(e.matrix.a, e.matrix.b);
    const dx = e.front.x - e.root.x, dy = e.front.y - e.root.y, len = Math.hypot(dx, dy) || 1;
    const luma = (r, g, b) => r * .2126 + g * .7152 + b * .0722;
    let count = 0, colored = 0, saturation = 0, fg = 0, bgSum = 0;
    let lo = Infinity, hi = -Infinity, sliceCount = 0;
    for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
      const i = (y * c.width + x) * 4;
      if (data[i + 3] < 250) continue;
      const v = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
      const along = ((v.x - e.front.x) * dx + (v.y - e.front.y) * dy) / len;
      const normal = ((v.y - e.front.y) * dx - (v.x - e.front.x) * dy) / len;
      // Actual central normal chord of the head; no glow/trail/canvas padding in size.
      if (Math.abs(along) <= 2) {
        lo = Math.min(lo, normal); hi = Math.max(hi, normal); sliceCount++;
      }
      const r = data[i], g = data[i+1], b = data[i+2];
      const max = Math.max(r, g, b), sat = max ? (max - Math.min(r, g, b)) / max : 0;
      if (sat > .12) { colored++; saturation += sat; }
      fg += luma(r, g, b); bgSum += luma(bg[i], bg[i+1], bg[i+2]); count++;
    }
    return { composite, background, mask: e.canvas.toDataURL(), head: c.toDataURL(),
      id: e.id, height: api.snapshot().player.body.visibleSize[1],
      diameter: hi - lo + 1 / scale, sliceCount, count,
      saturation: saturation / Math.max(1, colored), colorFraction: colored / Math.max(1, count),
      foregroundLuma: fg / count, backgroundLuma: bgSum / count,
      contrast: Math.abs(fg - bgSum) / count, front: e.front, root: e.root };
  };
}
