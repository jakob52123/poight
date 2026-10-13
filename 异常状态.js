"use strict";
// Combat RNG is injected; presentation never consumes random numbers.
window.PoightStatus = class {
  static definitions = Object.freeze({
    par: { name: "麻痹", text: "麻痹了！", duration: 5, immune: [13], color: "#f5d85c" },
    brn: { name: "烧伤", text: "烧伤了！", duration: 5, immune: [10], color: "#f08069" },
    frz: { name: "冰冻", text: "冻住了！", duration: 1.5, immune: [15], color: "#b6e9ff" },
    psn: { name: "中毒", text: "中毒了！", duration: 6, immune: [4, 9], color: "#ca8bde" },
  });
  constructor(api, assets) {
    this.api = api;
    this.tints = new WeakMap();
    this.frames = new WeakMap();
    this.visible = true;
    // Rasterize the eight label glyphs once at native pixel size, then nearest-neighbour blit.
    const definitions = window.PoightStatus.definitions;
    this.labels = Object.fromEntries(Object.entries(definitions).map(([id, d]) => {
      const c = document.createElement("canvas");
      c.width = 30;
      c.height = 14;
      const g = c.getContext("2d");
      g.font = "12px monospace";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillStyle = "#192b3b";
      g.fillText(d.name, 15, 7);
      const pixels = g.getImageData(0, 0, 30, 14);
      for (let i = 3; i < pixels.data.length; i += 4)
        pixels.data[i] = pixels.data[i] >= 96 ? 255 : 0;
      g.putImageData(pixels, 0, 0);
      return [id, c];
    }));
    this.assets = assets;
    this.images = {};
  }
  async load(loader) {
    if (!this.loading) this.loading = Promise.all(Object.entries(this.assets).map(
      async ([id, src]) => { this.images[id] = await loader(src); },
    )).catch(error => { this.loading = null; throw error; });
    return this.loading;
  }
  frozen(p) { return p?.status?.id === "frz"; }
  blocked(p) { return this.frozen(p) || (p?.status?.stiff || 0) > 1e-7; }
  speed(p) { return p.status?.id === "par" ? 0.6 : 1; }
  power(p, m) {
    return p.status?.id === "brn" && ["melee", "spin", "rush"].includes(m.kind) ? 0.6 : 1;
  }
  clear(p, fire = false) {
    if (this.frozen(p)) {
      p.freezeGrace = 2;
      p.statusThaw = { age: 0, fire, box: p.statusBox && { ...p.statusBox } };
    }
    p.status = null;
  }
  apply(p, source, id, move) {
    const d = window.PoightStatus.definitions[id];
    if (!d || p.hp <= 0 || p.status || this.api.protected(p) ||
      d.immune.some((t) => p.char.types.includes(t)) ||
      (id === "frz" && p.freezeGrace > 1e-7)) return false;
    p.status = { id, left: d.duration, age: 0, tick: 1, check: 1.5, stiff: 0,
      source, move, pose: { anim: p.anim, age: p.animAge, a: p.a } };
    this.api.notice(p, d.text, d.color);
    return true;
  }
  hit(p, source, m) {
    // Thaw is hit-dependent, not proc-dependent. Immunity/protect checked by damage().
    if (m.type === 10 && this.frozen(p)) this.clear(p, true);
    if (p.status || !m.statuses) return false;
    const roll = this.api.random() * 100;
    let sum = 0;
    for (const entry of m.statuses) {
      sum += entry.chance;
      if (roll < sum) return this.apply(p, source, entry.id, m.id);
    }
    return false;
  }
  tick(p, dt) {
    if (p.statusThaw && (p.statusThaw.age += dt) >= 0.3 - 1e-7) p.statusThaw = null;
    p.freezeGrace = Math.max(0, (p.freezeGrace || 0) - dt);
    const s = p.status;
    if (!s) return;
    const used = Math.min(dt, s.left);
    s.age += used;
    s.left = Math.max(0, s.left - dt);
    s.stiff = Math.max(0, s.stiff - dt);
    s.tick -= used;
    s.check -= used;
    if (s.id === "par" && s.check <= 1e-7) {
      s.check += 1.5;
      if (this.api.random() < 0.25) s.stiff = 0.5;
    }
    if (["brn", "psn"].includes(s.id) && s.tick <= 1e-7) {
      s.tick += 1;
      this.api.damage(p, s.source, p.maxHP * (s.id === "brn" ? 0.009 : 0.015),
        true, s.move);
    }
    if (s.left <= 1e-7) this.clear(p);
  }
  snapshot(p) {
    const s = p.status;
    return s ? { id: s.id, left: s.left, age: s.age, stiff: s.stiff,
      label: window.PoightStatus.definitions[s.id].name } : null;
  }
  sprite(p, image) {
    const id = p.status?.id;
    if (!id) return image;
    let cached = this.tints.get(image);
    if (!cached) this.tints.set(image, cached = {});
    if (!cached[id]) {
      const c = document.createElement("canvas");
      c.width = image.naturalWidth;
      c.height = image.naturalHeight;
      const g = c.getContext("2d");
      g.drawImage(image, 0, 0);
      if (id === "frz") {
        // Map every opaque sprite pixel into cyan-white, preserving luminance and alpha.
        const pixels = g.getImageData(0, 0, c.width, c.height);
        for (let i = 0; i < pixels.data.length; i += 4) {
          const l = (pixels.data[i] * 0.2126 + pixels.data[i + 1] * 0.7152 +
            pixels.data[i + 2] * 0.0722) / 255;
          pixels.data[i] = 35 + l * 170;
          pixels.data[i + 1] = 110 + l * 135;
          pixels.data[i + 2] = 160 + l * 95;
        }
        g.putImageData(pixels, 0, 0);
      } else {
        g.globalCompositeOperation = "source-atop";
        g.fillStyle = { par: "#ffdc4033", brn: "#ff452f38", psn: "#b445dd40" }[id];
        g.fillRect(0, 0, c.width, c.height);
      }
      cached[id] = c;
    }
    return cached[id];
  }
  filter(p) {
    return p.status?.id === "par"
      ? `brightness(${1 + 0.12 * Math.sin(p.status.age * 18)})` : "none";
  }
  bodyBox(p, image, d, row, col, x, y) {
    if (!p.status && !p.statusThaw) return;
    let frames = this.frames.get(image);
    if (!frames) this.frames.set(image, frames = {});
    const key = `${row}:${col}`;
    if (!frames[key]) {
      const c = document.createElement("canvas");
      c.width = d.frameWidth;
      c.height = d.frameHeight;
      const g = c.getContext("2d");
      g.drawImage(image, col * c.width, row * c.height, c.width, c.height,
        0, 0, c.width, c.height);
      const pixels = g.getImageData(0, 0, c.width, c.height).data;
      let left = c.width, top = c.height, right = 0, bottom = 0;
      for (let yy = 0; yy < c.height; yy++) for (let xx = 0; xx < c.width; xx++) {
        if (pixels[(yy * c.width + xx) * 4 + 3] < 96) continue;
        left = Math.min(left, xx);
        top = Math.min(top, yy);
        right = Math.max(right, xx + 1);
        bottom = Math.max(bottom, yy + 1);
      }
      frames[key] = { left, top, right, bottom };
    }
    const b = frames[key], scale = p.char.scale;
    p.statusBox = { x: x + b.left * scale, y: y + b.top * scale,
      width: (b.right - b.left) * scale, height: (b.bottom - b.top) * scale };
  }
  particle(ctx, id, frame, x, y, size) {
    const im = this.images[id];
    if (!im?.complete || !im.naturalWidth) return;
    // Keep Emerald's silhouettes/frames; brighten electric/fire cores and outline purple bubbles.
    this.particles ||= {};
    if (!this.particles[id]) {
      const make = (color) => {
        const c = document.createElement("canvas");
        c.width = im.width;
        c.height = im.height;
        const g = c.getContext("2d");
        g.drawImage(im, 0, 0);
        g.globalCompositeOperation = "source-in";
        g.fillStyle = color;
        g.fillRect(0, 0, c.width, c.height);
        return c;
      };
      this.particles[id] = { core: make({ par: "#fff240", brn: "#ffed40",
        psn: "#9518e8", crystal: "#4dffff" }[id]),
        edge: make(id === "brn" ? "#a82c08" : "#192c50") };
    }
    const source = this.particles[id], f = id === "brn" ? 32 : 16;
    const sy = (frame % Math.max(1, Math.floor(im.height / f))) * f;
    x = Math.round(x);
    y = Math.round(y);
    for (const [dx, dy] of [[-2, 0], [2, 0], [0, -2], [0, 2]])
      ctx.drawImage(source.edge, 0, sy, f, f, x + dx, y + dy, size, size);
    ctx.drawImage(source.core, 0, sy, f, f, x, y, size, size);
    if (id === "crystal") {
      ctx.save();
      ctx.globalAlpha *= 0.15;
      ctx.drawImage(im, 0, sy, f, f, x, y, size, size);
      ctx.restore();
    }
    if (id === "psn") {
      ctx.fillStyle = "#f6dbff";
      ctx.fillRect(x + size * 0.35, y + size * 0.3, 3, 3);
    }
  }
  draw(ctx, p, lift) {
    if (!this.visible || (!p.status && !p.statusThaw)) return;
    const s = p.status, b = p.statusBox;
    if (!b) return;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    if (s?.id === "frz") {
      const x = Math.floor(b.x - 4), y = Math.floor(b.y - 4);
      const w = Math.ceil(b.width + 8), h = Math.ceil(b.height + 8);
      // Solid cyan enclosure, 4 world-pixel margin, stepped pixel outline, three white facets.
      ctx.fillStyle = "#197fbd";
      ctx.fillRect(x + 2, y, w - 4, 2);
      ctx.fillRect(x + 2, y + h - 2, w - 4, 2);
      ctx.fillRect(x, y + 2, 2, h - 4);
      ctx.fillRect(x + w - 2, y + 2, 2, h - 4);
      ctx.save();
      ctx.globalAlpha *= 0.72;
      ctx.fillStyle = "#9fe8ff";
      ctx.fillRect(x + 2, y + 2, w - 4, h - 4);
      ctx.restore();
      // Original ice cube cracks provide extra internal detail without the old pink bubble.
      const cube = this.images.frz;
      if (cube?.complete) {
        ctx.save();
        ctx.globalAlpha *= 0.15;
        ctx.drawImage(cube, x + 2, y + 2, w - 4, h - 4);
        ctx.restore();
      }
      ctx.fillStyle = "#edffff";
      for (let line = 0; line < 3; line++) {
        const startX = x + 5 + line * w * 0.24;
        const startY = y + h * (0.15 + line * 0.22);
        for (let i = 0; i < Math.min(w * 0.26, h * 0.28); i += 2)
          ctx.fillRect(Math.round(startX + i), Math.round(startY + i), 3, 2);
      }
      // Four original ice crystals converge in exactly 0.2s, then pulse at the corners.
      const gap = Math.max(0, 1 - s.age / 0.2) * 26;
      for (let i = 0; i < 4; i++) {
        const dx = i % 2 ? 1 : -1, dy = i < 2 ? -1 : 1;
        this.particle(ctx, "crystal", 0,
          x + (dx > 0 ? w - 9 : -7) + dx * gap,
          y + (dy > 0 ? h - 9 : -7) + dy * gap,
          12 + Math.floor(1 + Math.sin(s.age * 12)));
      }
    } else if (s) {
      // Continuous readable satellites, with periodic ascent/pulse (no invisible half-cycle).
      for (let i = 0; i < 3; i++) {
        const size = s.id === "brn" ? 26 : 24;
        const x = i === 1 ? b.x + b.width / 2 - size / 2
          : i === 0 ? b.x - size + 3 : b.x + b.width - 3;
        const y = i === 1 ? b.y + b.height - 8
          : b.y + b.height * 0.55 - ((s.age * 22 + i * 13) % 22);
        this.particle(ctx, s.id, Math.floor(s.age * 12), x, y, size);
      }
    }
    if (p.statusThaw) {
      const thaw = p.statusThaw, t = thaw.age / 0.3, box = thaw.box || b;
      for (let i = 0; i < 8; i++) {
        const a = i * Math.PI / 4, radius = 8 + t * 42;
        this.particle(ctx, "crystal", 0,
          box.x + box.width / 2 + Math.cos(a) * radius - 6,
          box.y + box.height / 2 + Math.sin(a) * radius - 6 + t * t * 14,
          Math.max(4, Math.round(12 * (1 - t * 0.5))));
        if (thaw.fire) {
          ctx.fillStyle = "#ffc073";
          ctx.fillRect(Math.round(box.x + i * box.width / 8),
            Math.round(box.y - t * 30 - i % 3 * 5), 4, 4);
        }
      }
    }
    ctx.restore();
  }
  label(ctx, p, h) {
    const s = p.status;
    if (!s) return;
    const d = window.PoightStatus.definitions[s.id];
    const x = Math.round(h.x + h.width / 2 + 4 / h.sx), y = h.y - 8 / h.sy;
    ctx.save();
    ctx.fillStyle = "#243444";
    ctx.fillRect(x - 1 / h.sx, y - 1 / h.sy, 32 / h.sx, 19 / h.sy);
    ctx.fillStyle = d.color;
    ctx.fillRect(x, y, 30 / h.sx, 14 / h.sy);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.labels[s.id], x, y, 30 / h.sx, 14 / h.sy);
    ctx.fillStyle = d.color;
    ctx.fillRect(x, y + 16 / h.sy, 30 / h.sx * s.left / d.duration, 1 / h.sy);
    ctx.restore();
  }
};
