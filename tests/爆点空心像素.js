// Observe production paint and the current native sprite, including the real camera shake.
() => {
  const probe = window.hollowProbe = { targetId: 6, enabled: true, ring: null };
  const canvas = (ctx, key) => {
    const c = probe[key] ||= document.createElement("canvas");
    if (c.width !== ctx.canvas.width || c.height !== ctx.canvas.height) {
      c.width = ctx.canvas.width; c.height = ctx.canvas.height;
    }
    const g = c.getContext("2d", { willReadFrequently: true });
    g.resetTransform(); g.clearRect(0, 0, c.width, c.height);
    g.setTransform(ctx.getTransform()); g.imageSmoothingEnabled = false;
    return [c, g];
  };
  const hero = window.PoightHeroVisuals.prototype, electrify = hero.electrify;
  hero.electrify = function (ctx, target, ...args) {
    if (probe.enabled && target.id === probe.targetId) {
      const [c, g] = canvas(ctx, "target");
      g.drawImage(...args);
      const [, , , , , x, y, w, h] = args, matrix = ctx.getTransform();
      const points = [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]
        .map(([px, py]) => new DOMPoint(px, py).matrixTransform(matrix));
      probe.targetBox = {
        x: Math.max(0, Math.floor(Math.min(...points.map(p => p.x)) - 32)),
        y: Math.max(0, Math.floor(Math.min(...points.map(p => p.y)) - 32)),
        right: Math.min(c.width, Math.ceil(Math.max(...points.map(p => p.x)) + 32)),
        bottom: Math.min(c.height, Math.ceil(Math.max(...points.map(p => p.y)) + 32)),
      };
    }
    return electrify.call(this, ctx, target, ...args);
  };
  const shake = window.PoightArena.shakeFrame;
  window.PoightArena.shakeFrame = function (ctx, c, ...args) {
    if (probe.enabled && probe.target) {
      const g = probe.target.getContext("2d");
      g.setTransform(ctx.getTransform());
      shake.call(this, g, probe.target, ...args);
    }
    return shake.call(this, ctx, c, ...args);
  };
  const captureRing = (ctx, b, diameter, paint) => {
    const [c, g] = canvas(ctx, "mask");
    paint(g);
    const matrix = ctx.getTransform(), center = new DOMPoint(b.ringX, b.ringY)
      .matrixTransform(matrix), pad = Math.ceil(diameter * Math.hypot(matrix.a, matrix.b) + 10);
    const x = Math.max(0, Math.floor(center.x - pad)), y = Math.max(0, Math.floor(center.y - pad));
    const w = Math.min(c.width - x, pad * 2), h = Math.min(c.height - y, pad * 2);
    const d = g.getImageData(x, y, w, h).data, bg = ctx.getImageData(x, y, w, h).data;
    const inv = matrix.inverse(), unit = 1 / Math.hypot(matrix.a, matrix.b);
    let lo = Infinity, hi = -Infinity, count = 0, chroma = 0, sat = 0, lum = 0, back = 0;
    let centerN = 0, centerClear = 0, radialMin = Infinity, radialMax = -Infinity;
    let contrastSum = 0, primaryPixels = 0, primaryLightness = 0;
    const primary = b.primaryColor?.match(/[0-9a-f]{2}/gi)?.map(v => parseInt(v, 16));
    for (let yy = 0; yy < h; yy++) for (let xx = 0; xx < w; xx++) {
      const i = (yy * w + xx) * 4;
      const q = new DOMPoint(x + xx + .5, y + yy + .5).matrixTransform(inv);
      const radius = Math.hypot(q.x - b.ringX, q.y - b.ringY);
      if (radius < diameter * .15) { centerN++; if (d[i + 3] === 0) centerClear++; }
      if (d[i + 3] < 250) continue;
      lo = Math.min(lo, q.x); hi = Math.max(hi, q.x);
      const max = Math.max(d[i], d[i + 1], d[i + 2]), min = Math.min(d[i], d[i + 1], d[i + 2]);
      const saturation = max ? (max - min) / max : 0;
      // White shock highlights have no hue; include them in contrast, not hue saturation.
      if (saturation > .12) { chroma++; sat += saturation; }
      if (radius < diameter * .54) {
        radialMin = Math.min(radialMin, radius); radialMax = Math.max(radialMax, radius);
        const foreground = .2126 * d[i] + .7152 * d[i + 1] + .0722 * d[i + 2],
          background = .2126 * bg[i] + .7152 * bg[i + 1] + .0722 * bg[i + 2];
        lum += foreground; back += background;
        // Bright band + mandated dark outline: opposite-signed contrasts must not cancel.
        contrastSum += Math.abs(foreground - background);
        if (primary && primary.every((v, k) => Math.abs(d[i + k] - v) <= 2)) {
          primaryPixels++; primaryLightness += (max + min) / 510;
        }
        count++;
      }
    }
    probe.ring = { id: b.id, age: b.age, height: b.height, count,
      diameter: hi - lo + unit, centerTransparent: centerClear / centerN,
      bandWidth: radialMax - radialMin + unit, saturation: sat / Math.max(1, chroma),
      contrast: contrastSum / Math.max(1, count),
      legacyAbsMeanContrast: Math.abs(lum - back) / Math.max(1, count),
      primaryPixels, primaryLightness: primaryLightness / Math.max(1, primaryPixels),
      ringLuminance: lum / Math.max(1, count), backgroundLuminance: back / Math.max(1, count) };
  };
  const core = window.PoightMoveAnimations.prototype, burst = core.drawBurst, lick = core.lick;
  core.drawBurst = function (ctx, b) {
    const geometry = this.ringGeometry?.(ctx, b) || {x:b.ringX,y:b.ringY,
      diameter: Math.max(b.size, b.height * 1.2) * (1 + b.age / .26 * .15)};
    const {diameter} = geometry;
    const light = this.ringIsLight ? this.ringIsLight(ctx, b, diameter / 2) : null;
    if (probe.enabled && probe.sampleRing !== false)
      captureRing(ctx, {...b, ringX:geometry.x, ringY:geometry.y,
        primaryColor: this.ringColor?.(b.type)}, diameter, g => {
        g.save();
        this.clipContactCenters(g);
        burst.call(this, g, b, light);
        g.restore();
      });
    return burst.call(this, ctx, b, light);
  };
  const paint = hero.paint;
  hero.paint = function (ctx, s, ...args) {
    if (probe.enabled && probe.sampleRing !== false && s.kind === "thunder" &&
      s.part === "ring" && this.core.ringBackdrop && s.ringX !== undefined) {
      const r = Math.max(Math.hypot(s.targetWidth || s.targetHeight, s.targetHeight) * .55,
        s.targetHeight * .60) + Math.min(.10, Math.max(0, s.since) * .4) * s.targetHeight;
      const light = this.core.ringBackdrop(ctx, s.ringX, s.ringY, r) < 157;
      const observed = { ...s, ringLight: light };
      captureRing(ctx, { id: s.id, ringX: s.ringX, ringY: s.ringY, height: s.targetHeight,
        age: Math.max(0, s.since), primaryColor: this.core.ringColor?.(13) },
        r * 2, g => {
          g.save();
          this.core.clipContactCenters(g);
          paint.call(this, g, observed, ...args);
          g.restore();
        });
      return paint.call(this, ctx, observed, ...args);
    }
    return paint.call(this, ctx, s, ...args);
  };
  core.lick = function (ctx, ...args) {
    if (probe.enabled && args[1].id === "lick") {
      const [c, g] = canvas(ctx, "tongue");
      lick.call(this, g, ...args);
      probe.tongue = c;
    }
    return lick.call(this, ctx, ...args);
  };
  window.measureHollow = () => {
    const c = probe.target, game = document.querySelector("#game");
    const b = probe.targetBox, w = b.right - b.x, h = b.bottom - b.y;
    const raw = c.getContext("2d").getImageData(b.x, b.y, w, h).data;
    const full = game.getContext("2d").getImageData(b.x, b.y, w, h).data;
    let target = 0, original = 0;
    for (let i = 0; i < raw.length; i += 4) {
      if (raw[i + 3] < 250) continue;
      target++;
      if ([0, 1, 2].every(k => Math.abs(raw[i + k] - full[i + k]) <= 8)) original++;
    }
    return { targetPixels: target, originalFraction: original / Math.max(1, target), ring: probe.ring };
  };
}
