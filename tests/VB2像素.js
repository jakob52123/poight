// Read-only mirror of production coat/path and P6 ring, at the real Canvas transform.
() => {
  const fx = window.PoightVB2;
  window.vb2Probe = { enabled: false, suppress: false, mid: null, last: null, star: null,
    actor: null };
  const mirror = (ctx, draw) => {
    const c = document.createElement("canvas");
    c.width = ctx.canvas.width; c.height = ctx.canvas.height;
    const g = c.getContext("2d"), matrix = ctx.getTransform();
    g.setTransform(matrix); g.imageSmoothingEnabled = false;
    draw(g);
    return { canvas: c, matrix };
  };
  // Mirror the real caster drawImage, including pose/alpha/transform. No surrogate body box.
  const pose = window.PoightRevision3.pose;
  let actor = null;
  window.PoightRevision3.pose = function (p) {
    actor = p;
    return pose.call(this, p);
  };
  const drawImage = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function (...args) {
    const p = window.vb2Probe;
    if (p.enabled && actor?.attack?.id === p.mid &&
        Object.values(actor.images).includes(args[0]) && this.canvas.id === "game") {
      p.actor = mirror(this, g => {
        g.globalAlpha = this.globalAlpha;
        g.filter = this.filter;
        drawImage.apply(g, args);
      });
    }
    return drawImage.apply(this, args);
  };
  const paint = fx.paint;
  fx.paint = function (ctx, e, api, charging = false) {
    const p = window.vb2Probe;
    if (!p.enabled || e.id !== p.mid) return paint.call(this, ctx, e, api, charging);
    const entry = mirror(ctx, c => {
      if (e.contacted || e.group?.hit.size) api.animations.clipContactCenters(c);
      paint.call(this, c, e, api, charging);
    });
    p.last = { ...entry, point: { ...e.drawAnchor }, angle: e.a, age: e.age, charging,
      height: e.owner.char.body.visibleSize[1] };
    if (!p.suppress) paint.call(this, ctx, e, api, charging);
  };
  // Retain the complete actual scene (including actors), but remove contact overlays
  // together with the coat when obtaining its backdrop. A ring is not a background.
  const contact = fx.contact;
  fx.contact = function (ctx, ...args) {
    if (window.vb2Probe.enabled && window.vb2Probe.suppressContacts) return;
    return contact.call(this, ctx, ...args);
  };
  const burst = window.PoightMoveAnimations.prototype.drawBurst;
  window.PoightMoveAnimations.prototype.drawBurst = function (ctx, b, ...args) {
    const p = window.vb2Probe;
    if (p.enabled && b.id === p.mid)
      p.star = { ...mirror(ctx, c => {
        this.clipContactCenters(c);
        burst.call(this, c, b, ...args);
      }), size: b.size };
    if (!p.enabled || !p.suppressContacts) return burst.call(this, ctx, b, ...args);
  };
  window.measureVB2 = () => {
    const p = window.vb2Probe, entry = p.last, api = window.__waterTest,
      game = document.querySelector("#game"), composite = game.toDataURL(),
      actual = game.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    // Keep the original coat-only caster-retention control. Contact is a distinct layer.
    p.suppress = true; p.suppressContacts = false; api.step(0);
    const coatBackground = game.getContext('2d')
      .getImageData(0, 0, game.width, game.height).data;
    p.suppressContacts = true; api.step(0);
    const background = game.toDataURL(), bg = game.getContext("2d")
      .getImageData(0, 0, game.width, game.height).data;
    p.suppress = false; p.suppressContacts = false; api.step(0);
    const scan = (layer, backdrop = null) => {
      const c = layer.canvas, d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data,
        inv = layer.matrix.inverse(), pixel = 1 / Math.hypot(layer.matrix.a, layer.matrix.b),
        lum = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
      let n = 0, sat = 0, colored = 0, fore = 0, back = 0,
        minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
        const i = (y * c.width + x) * 4;
        if (d[i + 3] < 250) continue;
        const pt = new DOMPoint(x + .5, y + .5).matrixTransform(inv);
        minX = Math.min(minX, pt.x); maxX = Math.max(maxX, pt.x);
        minY = Math.min(minY, pt.y); maxY = Math.max(maxY, pt.y);
        const rgb = [d[i], d[i + 1], d[i + 2]], top = Math.max(...rgb),
          s = top ? (top - Math.min(...rgb)) / top : 0;
        if (s > .12) { sat += s; colored++; }
        fore += lum(...rgb);
        if (backdrop) back += lum(backdrop[i], backdrop[i + 1], backdrop[i + 2]);
        n++;
      }
      return { count: n, opaqueWidth: maxX - minX + pixel, opaqueHeight: maxY - minY + pixel,
        saturation: sat / Math.max(1, colored), colorFraction: colored / Math.max(1, n),
        foregroundLuma: fore / n, backgroundLuma: back / n, contrast: (fore - back) / n };
    };
    const body = p.actor?.canvas.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    let bodyCount = 0, retained = 0;
    if (body) for (let i = 0; i < body.length; i += 4) {
      if (!body[i + 3]) continue;
      bodyCount++;
      if (actual[i] === coatBackground[i] && actual[i + 1] === coatBackground[i + 1] &&
          actual[i + 2] === coatBackground[i + 2])
        retained++;
    }
    return { ...scan(entry, bg), bodyCount, bodyRetained: retained / Math.max(1, bodyCount),
      height: entry.height, age: entry.age, charging: entry.charging,
      point: entry.point, hp: api.snapshot().enemy.hp, star: p.star ? scan(p.star) : null,
      composite, background, mask: entry.canvas.toDataURL(),
      starMask: p.star?.canvas.toDataURL() };
  };
}
