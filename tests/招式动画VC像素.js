// Mirror ONLY calls from the actual combat renderer, using its actual Canvas transform.
() => {
  window.vcProbe = { enabled: false, suppress: false, last: null };
  const proto = window.PoightMoveAnimations.prototype;
  for (const method of ["path", "drawNova", "vcZone", "vcSupport", "vcSurf"]) {
    const original = proto[method];
    proto[method] = function (ctx, ...args) {
      const probe = window.vcProbe;
      const id = method === "path" ? args[0] : args[0].id;
      if (!probe.enabled || !window.PoightVC.config[id]) return original.call(this, ctx, ...args);
      const canvas = document.createElement("canvas");
      canvas.width = ctx.canvas.width;
      canvas.height = ctx.canvas.height;
      const c = canvas.getContext("2d"), matrix = ctx.getTransform(), sprites = [];
      c.setTransform(matrix);
      c.imageSmoothingEnabled = ctx.imageSmoothingEnabled;
      const sprite = this.sprite;
      this.sprite = function (context, key, x, y, size, alpha = 1, angle = 0) {
        if (method !== "path")
          return sprite.call(this, context, key, x, y, size, alpha, angle);
        const im = document.createElement("canvas");
        im.width = canvas.width;
        im.height = canvas.height;
        const ic = im.getContext("2d");
        ic.setTransform(context.getTransform());
        ic.globalAlpha = context.globalAlpha;
        ic.imageSmoothingEnabled = false;
        sprite.call(this, ic, key, x, y, size, alpha, angle);
        sprites.push({ canvas: im, key, x, y });
        return sprite.call(this, context, key, x, y, size, alpha, angle);
      };
      try { original.call(this, c, ...args); } finally { this.sprite = sprite; }
      probe.last = { canvas, matrix, sprites, method, args, id };
      if (!probe.suppress) original.call(this, ctx, ...args);
    };
  }
  const burst = proto.drawBurst;
  proto.drawBurst = function (ctx, b, ...rest) {
    const {key} = b, {x, y, diameter: size} = this.ringGeometry(ctx, b);
    {
      const matrix = ctx.getTransform(), scale = Math.hypot(matrix.a, matrix.b),
        side = Math.ceil(size * scale * 1.5) + 12,
        canvas = window.vcImpactCanvas ||= document.createElement("canvas");
      canvas.width = ctx.canvas.width; canvas.height = ctx.canvas.height;
      const c = canvas.getContext("2d");
      c.imageSmoothingEnabled = ctx.imageSmoothingEnabled;
      c.setTransform(matrix);
      this.clipContactCenters(c);
      burst.call(this, c, b, ...rest);
      const center = new DOMPoint(x, y).matrixTransform(matrix),
        left = Math.max(0, Math.floor(center.x - side / 2)),
        top = Math.max(0, Math.floor(center.y - side / 2)),
        w = Math.min(side, canvas.width - left), h = Math.min(side, canvas.height - top),
        data = c.getImageData(left, top, w, h).data;
      let loX = Infinity, hiX = -Infinity, loY = Infinity, hiY = -Infinity;
      for (let py = 0; py < h; py++) for (let px = 0; px < w; px++) {
        if (data[(py * w + px) * 4 + 3] < 250) continue;
        loX = Math.min(loX, px); hiX = Math.max(hiX, px);
        loY = Math.min(loY, py); hiY = Math.max(hiY, py);
      }
      window.vcContactRaster = { key, x: b.x, y: b.y, ringX: x, ringY: y, time: this.time,
        width: (hiX - loX + 1) / scale, height: (hiY - loY + 1) / scale };
    }
    return burst.call(this, ctx, b, ...rest);
  };
  window.measureVCPixels = () => {
    const probe = window.vcProbe, entry = probe.last, api = window.__waterTest,
      game = document.querySelector("#game"), composite = game.toDataURL();
    if (!entry) throw new Error("No actual VC raster draw");
    probe.suppress = true;
    api.step(0);
    const background = game.toDataURL(),
      bg = game.getContext("2d").getImageData(0, 0, game.width, game.height).data;
    probe.suppress = false;
    api.step(0);
    const { canvas, matrix, sprites, method, args, id } = entry,
      inverse = matrix.inverse(), scale = Math.hypot(matrix.a, matrix.b),
      data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data,
      luma = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
    let count = 0, colored = 0, satSum = 0, foreground = 0, ground = 0,
      minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity,
      radialMin = Infinity, radialMax = -Infinity;
    for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
      const i = (y * canvas.width + x) * 4;
      if (data[i + 3] < 250) continue;
      const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse);
      if (method === "drawNova") {
        const e = args[0], radius = Math.hypot(p.x - e.x, p.y - e.y);
        // Same V1-core wavefront-only color measurement, not the actor or interior dust.
        if (Math.abs(radius - e.radius) > 8) continue;
        radialMin = Math.min(radialMin, radius);
        radialMax = Math.max(radialMax, radius);
      }
      const max = Math.max(data[i], data[i + 1], data[i + 2]),
        sat = max ? (max - Math.min(data[i], data[i + 1], data[i + 2])) / max : 0;
      if (sat > .12) { colored++; satSum += sat; }
      count++;
      foreground += luma(data[i], data[i + 1], data[i + 2]);
      ground += luma(bg[i], bg[i + 1], bg[i + 2]);
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
    }
    let opaqueSpriteDiameter = null;
    if (method === "path") {
      const s = sprites.at(-1), dx = args[2].x - args[1].x, dy = args[2].y - args[1].y,
        length = Math.hypot(dx, dy) || 1,
        d = s.canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let lo = Infinity, hi = -Infinity;
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        if (d[(y * canvas.width + x) * 4 + 3] < 250) continue;
        const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse),
          n = (p.y * dx - p.x * dy) / length;
        lo = Math.min(lo, n); hi = Math.max(hi, n);
      }
      opaqueSpriteDiameter = hi - lo + 1 / scale;
    }
    return { id, method, count, saturation: satSum / Math.max(1, colored),
      colorFraction: colored / Math.max(1, count), contrast: Math.abs(foreground - ground) / count,
      foregroundLuma: foreground / count, backgroundLuma: ground / count,
      width: maxX - minX + 1 / scale, height: maxY - minY + 1 / scale,
      opaqueSpriteDiameter, radialMin, radialMax, spriteCount: sprites.length,
      composite, background, mask: canvas.toDataURL() };
  };
}
