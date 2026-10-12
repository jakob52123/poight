// SPDX-License-Identifier: AGPL-3.0-or-later
// VH: presentation only. Every point comes from the existing physics/landmark API.
window.PoightHeroVisuals = class {
  constructor(core) {
    this.core = core;
    this.reset();
  }
  reset() {
    this.ribbons = [];
    this.bursts = [];
    this.events = [];
    this.shocks = new Map();
  }
  uses(id, owner) {
    const caster = {
      thunderbolt: 25, quickattack: 25, irontail: 25, thunder: 25,
      flamethrower: 6, fireblast: 6, dragonclaw: 6, airslash: 6,
    }[id];
    return this.core.enabled && !!caster && (!owner || owner.id === caster);
  }
  prepare(b) {
    if (this.uses(b.m.id, b.owner) && b.originAnchor) b.heroRoot = { ...b.originAnchor };
  }
  texture(ctx, key, x, y, size, alpha = 1, angle = 0) {
    this.core.sprite(ctx, "hero-" + key, x, y, size, alpha, angle);
  }
  line(ctx, points, width, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = "miter";
    ctx.lineCap = "round";
    ctx.beginPath();
    points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.stroke();
  }
  local(ctx, x, y, radius, white, alpha) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
    g.addColorStop(0, white ? `rgba(255,255,235,${alpha})` : `rgba(12,8,30,${alpha})`);
    g.addColorStop(.45, white ? `rgba(255,255,235,${alpha * .6})` : `rgba(12,8,30,${alpha * .6})`);
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
  }
  // Five independent flames, upright in screen/world axes on ALL eight headings.
  fireCenters(x, y, size) {
    return [[0, -.46], [-.46, -.12], [.46, -.12], [-.36, .46], [.36, .46]]
      .map(([dx, dy]) => ({ x: x + dx * size, y: y + dy * size }));
  }
  fireGlyph(ctx, x, y, size, age, spread = 1, alpha = 1) {
    const points = this.fireCenters(x, y, size * spread);
    points.forEach(p => this.texture(ctx, "flame-rim", p.x, p.y, size * .39, alpha * .72));
    if (spread === 1) {
      const p = points.map(p => [p.x, p.y]);
      // Thin connecting strokes retain the ideograph; lobes remain widely separated.
      this.line(ctx, [p[1], [x, y - size * .12], p[2]], size * .09, "#ffeb17");
      this.line(ctx, [p[0], [x, y - size * .10], p[3]], size * .10, "#fff019");
      this.line(ctx, [[x, y - size * .10], p[4]], size * .10, "#fff019");
      this.line(ctx, [p[1], [x, y - size * .12], p[2]], size * .035, "#fff7bb");
      this.line(ctx, [p[0], [x, y - size * .10], p[3]], size * .035, "#fff7bb");
      this.line(ctx, [[x, y - size * .10], p[4]], size * .035, "#fff7bb");
    }
    points.forEach((p, i) => this.texture(ctx, "flame" + ((Math.floor(age * 24) + i) % 2),
      p.x, p.y, size * .29, alpha));
  }
  // This single real draw dispatch is also mirrored by the read-only raster acceptance probe.
  paint(ctx, s) {
    ctx.save();
    ctx.globalAlpha = s.alpha ?? 1;
    const { id, x, y, height: h, age = 0, angle = 0 } = s;
    const tick = Math.floor(age * 30);
    if (s.kind === "beam") {
      const dx = s.front.x - s.root.x, dy = s.front.y - s.root.y;
      const len = Math.hypot(dx, dy), a = Math.atan2(dy, dx), w = Math.max(14, h * .36);
      ctx.translate(s.root.x, s.root.y);
      ctx.rotate(a);
      if (id === "thunderbolt") {
        const pts = [[0, 0]], n = Math.max(2, Math.ceil(len / 11));
        for (let i = 1; i < n; i++)
          pts.push([i * len / n, Math.sin(i * 2.39 + tick * 1.71) * w * .48]);
        pts.push([len, 0]);
        this.line(ctx, pts, w + 12, "#ffda2838");
        this.line(ctx, pts, w + 4, "#ffe719");
        this.line(ctx, pts, w * .48, "#fffff5");
        for (let i = 1; i < n; i += 2) {
          const sign = (i + tick) % 3 ? 1 : -1;
          this.texture(ctx, "spark" + (tick % 2), i * len / n, sign * w * .5,
            w * .22, 1, -Math.PI / 2 + sign * .55);
        }
      } else {
        // Original red-orange fringe sits UNDER the opaque incandescent column.
        const n = Math.max(2, Math.ceil(len / 9));
        for (let i = 0; i <= n; i++) {
          const t = i / n;
          this.texture(ctx, "flame-rim", t * len, Math.sin(i * 2 + age * 35) * w * .18,
            w * (1.35 + t * .65), .45, Math.PI / 2);
        }
        // A continuous tapered body under the original, tumbling fire sprites.
        for (const [gain, color] of [[1.25, "#ff602730"], [1, "#ffeb18"], [.50, "#fff5d0"]]) {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.moveTo(0, -w * .5 * gain);
          ctx.lineTo(len, -w * .78 * gain);
          ctx.lineTo(len, w * .78 * gain);
          ctx.lineTo(0, w * .5 * gain);
          ctx.closePath();
          ctx.fill();
        }
        for (let i = 0; i <= n; i++) {
          const t = i / n, size = w * (1.05 + t * .55);
          this.texture(ctx, "flame" + ((i + tick) % 2), t * len,
            Math.sin(i * 2 + age * 35) * w * .18, size, 1, Math.PI / 2);
        }
        // Unbroken incandescent heart, not a series of disconnected fireballs.
        this.line(ctx, [[0, 0], [len, 0]], w * .42, "#fffbed");
      }
    } else if (s.kind === "projectile") {
      if (id === "fireblast") this.fireGlyph(ctx, x, y, Math.max(42, h * 1.05), age);
      else {
        ctx.translate(x, y);
        ctx.rotate(angle);
        const size = Math.max(30, h * .70);
        for (let i = 0; i < 3; i++)
          this.line(ctx, [[-size * (.7 + i * .12), (i - 1) * size * .24],
            [-size * .12, (i - 1) * size * .24]], 2, "#dcffffa0");
        // Source crescent spans horizontal; rotate so its tips flank the trajectory.
        this.texture(ctx, "wind", 0, 0, size, 1, -Math.PI / 2);
      }
    } else if (s.kind === "warning") {
      ctx.strokeStyle = "#ffe329";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.ellipse(x, y, s.radius, s.radius * .60, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      this.core.sprite(ctx, "core-impact--1", x, y - h * 3.5, 12 + 4 * Math.sin(age * 18));
    } else if (s.kind === "thunder") {
      const since = Math.max(0, s.since);
      if (s.part === "bolt" && since < .10) {
        // Invert the REAL camera transform: the channel enters from the visible top edge.
        const edge = new DOMPoint(ctx.canvas.width / 2, 0)
          .matrixTransform(ctx.getTransform().inverse());
        const top = Math.min(edge.y, y - h * 3), span = y - top, w = h * .30;
        const phase = Math.min(2, Math.floor(since * 30));
        ctx.globalAlpha *= phase === 1 ? .22 : 1; // bright / dark / bright, three 30Hz frames
        const offsets = [0, -.40, .34, -.56, .24, -.36, .42, -.18, 0];
        const pts = offsets.map((n, i) => [x + n * h, top + span * i / 8]);
        for (const [i, sign] of [[2, 1], [4, -1], [6, 1]]) {
          const [bx, by] = pts[i];
          const branch = [[bx, by], [bx + sign * h * .42, by + h * .30],
            [bx + sign * h * .31, by + h * .50], [bx + sign * h * .65, by + h * .80]];
          this.line(ctx, branch, 4, "#ffe529");
          this.line(ctx, branch, 1.5, "#fffff7");
        }
        this.line(ctx, pts, w + 8, "#ffeb4240");
        this.line(ctx, pts, w, "#ffe529");
        this.line(ctx, pts, w * .40, "#fffff7");
      }
      if (s.part === "ring") {
        const th = s.targetHeight, r = th * (.44 + Math.min(.10, since * .4));
        ctx.globalAlpha *= Math.min(1, (.35 - since) / .12);
        const points = Array.from({ length: 33 }, (_, i) => {
          const a = i * Math.PI / 16, rr = r + (i % 2 ? 1 : -1);
          return [x + Math.cos(a) * rr, y + Math.sin(a) * rr * .52];
        });
        this.line(ctx, points, 3, "#ffe529");
        this.line(ctx, points, 1, "#fffff7");
        for (let i = 0; i < 6; i++) {
          const a = i * Math.PI / 3 + .2, inner = th * .56, outer = th * .62;
          this.line(ctx, [[x + Math.cos(a) * inner, y + Math.sin(a) * inner * .52],
            [x + Math.cos(a) * outer, y + Math.sin(a) * outer * .52]], 1.5, "#fff6a0");
        }
      }
    } else if (s.kind === "rush") {
      ctx.translate(x, y);
      ctx.rotate(angle);
      for (let i = 0; i < 5; i++) {
        const n = (i - 2) * h * .16;
        this.line(ctx, [[-h * (1.3 + (i % 2) * .25), n], [-h * .12, n]],
          i === 2 ? 3 : 2, "#ffffff");
      }
    } else if (s.kind === "tail") {
      ctx.translate(x, y);
      ctx.rotate(angle + age * 6);
      for (const [w, color] of [[10, "#8393aa"], [8, "#e2f2ff"], [5, "#ffffff"]]) {
        ctx.strokeStyle = color;
        ctx.lineWidth = w;
        ctx.beginPath();
        ctx.arc(-h * .13, 0, h * .53, -.95, 1.35);
        ctx.stroke();
      }
    } else if (s.kind === "claw") {
      // Emerald's final claw_slash frame: three PARALLEL, separated diagonal cuts.
      // Screen-diagonal on all headings, like the original; no fuzzy aura over the victim.
      for (let i = 0; i < 3; i++) {
        if (age + 1e-6 < i * .04) continue;
        const n = (i - 1) * Math.max(18, h * .48);
        this.texture(ctx, "claw-strike", x - n / Math.SQRT2, y + n / Math.SQRT2,
          h * .90, 1);
      }
    } else if (s.kind === "contact") {
      const t = age / .28, size = s.size;
      if (["fireblast", "thunderbolt"].includes(id))
        this.local(ctx, x, y, h * 1.8, false, .48 * (1 - t));
      if (id === "fireblast") this.fireGlyph(ctx, x, y, Math.max(42, s.sourceHeight * 1.05),
        age, 1.05 + t * 1.3, 1 - t);
      if (id === "flamethrower") {
        for (let i = 0; i < 7; i++) {
          const a = i * Math.PI * 2 / 7, r = size * (.20 + t * .5);
          this.texture(ctx, "flame" + (i % 2), x + Math.cos(a) * r,
            y + Math.sin(a) * r, size * .62, 1 - t, a);
        }
      }
      if (id === "thunderbolt") {
        this.texture(ctx, "orb", x, y, size * .85, 1 - t);
        for (let i = 0; i < 6; i++) {
          const a = i * Math.PI / 3 + tick * .25, r = size * (.45 + t * .3);
          this.texture(ctx, "spark" + (i % 2), x + Math.cos(a) * r,
            y + Math.sin(a) * r, size * .075, 1 - t, a);
        }
      }
      if (id === "dragonclaw") this.paint(ctx, { ...s, kind: "claw",
        alpha: Math.min(1, (.28 - age) / .10) });
      if (["irontail", "quickattack"].includes(id)) {
        if (id === "quickattack") this.core.sprite(ctx, "core-impact--1", x, y, size, 1 - t);
        for (let i = 0; i < 8; i++) {
          const a = i * Math.PI / 4, r = size * (.2 + t * .6);
          this.line(ctx, [[x + Math.cos(a) * r, y + Math.sin(a) * r],
            [x + Math.cos(a) * (r + 6), y + Math.sin(a) * (r + 6)]], 2, "#f9ffff");
        }
      }
    }
    ctx.restore();
  }
  bullet(ctx, b, lift, api) {
    if (!this.uses(b.m.id, b.owner) || !b.heroRoot) return false;
    const angle = Math.atan2(b.uy, b.ux), beam = ["thunderbolt", "flamethrower"].includes(b.m.id);
    const fade = beam ? 1 : Math.max(0, 1 - b.age * b.speed / b.airDistance);
    const front = { x: b.x + (b.visualOffsetX || 0) * fade,
      y: b.y - 16 - lift + (b.visualOffset || 0) * fade };
    const root = b.owner.attack?.id === b.m.id ? api.anchor(b.owner, b.m, angle) : b.heroRoot;
    this.paint(ctx, { kind: beam ? "beam" : "projectile", id: b.m.id, root, front,
      ...front, height: b.owner.char.body.visibleSize[1], angle, age: b.age });
    return true;
  }
  projectileContact(b, point, lift, api, wall = false) {
    if (!this.uses(b.m.id, b.owner) || !b.heroRoot) return;
    const angle = Math.atan2(b.uy, b.ux), front = { x: point.x, y: point.y - 16 - lift };
    if (["thunderbolt", "flamethrower"].includes(b.m.id))
      this.ribbons.push({ kind: "beam", id: b.m.id, front,
        root: b.owner.attack?.id === b.m.id ? api.anchor(b.owner, b.m, angle) : b.heroRoot,
        height: b.owner.char.body.visibleSize[1], age: b.age, life: 0 });
    if (wall && b.m.id === "fireblast") this.wallBurst(front, b.owner.char.body.visibleSize[1]);
  }
  wallBurst(point, height) {
    this.bursts.push({ kind: "contact", id: "fireblast", ...point, age: 0,
      height, sourceHeight: height, size: height });
    this.events.push({ id: "fireblast", wall: true, ...point, time: this.core.time });
    this.events = this.events.slice(-64);
  }
  blockedOrigin(p, m, origin, api) {
    if (!this.uses(m.id, p) || m.id !== "fireblast") return;
    const dx = origin.x - p.x, dy = origin.y - p.y;
    const point = api.rayEnd(p.x, p.y, Math.atan2(dy, dx), Math.hypot(dx, dy), Math.min(m.radius, 7));
    this.wallBurst({ x: point.x, y: point.y - 16 - api.lift(p) }, p.char.body.visibleSize[1]);
  }
  impact(b, target, source, dx, dy) {
    if (!this.uses(b.id, source)) return;
    const event = { kind: "contact", ...b, height: target.char.body.visibleSize[1],
      sourceHeight: source.char.body.visibleSize[1], angle: Math.atan2(dy, dx) };
    this.bursts.push(event);
    if (["thunder", "dragonclaw"].includes(b.id)) b.heroContact = true;
    if (b.id === "thunder") this.shocks.set(target, 0);
    this.events.push({ id: b.id, x: b.x, y: b.y, time: this.core.time, wall: false });
    this.events = this.events.slice(-64);
  }
  sheen(ctx, p, anchor, api, age) {
    api.tailMask(ctx, p, anchor, g => {
      const r = p.char.body.visibleSize[1] * .38;
      const gradient = g.createLinearGradient(anchor.x - r, anchor.y - r,
        anchor.x + r, anchor.y + r);
      gradient.addColorStop(0, "#596980");
      gradient.addColorStop(.40 + .1 * Math.sin(age * 30), "#ffffff");
      gradient.addColorStop(1, "#a2b3cb");
      g.fillStyle = gradient;
      g.beginPath();
      g.arc(anchor.x, anchor.y, r, 0, Math.PI * 2);
      g.fill();
    });
  }
  charge(ctx, p, m, api) {
    if (!this.uses(m.id, p)) return false;
    const anchor = api.anchor(p, m, p.attack.aim), height = p.char.body.visibleSize[1];
    if (m.id === "thunder") this.paint(ctx, { kind: "warning", id: m.id,
      ...p.attack.targetPoint, height, radius: m.radius, age: p.attack.age });
    if (m.id === "irontail" && anchor) this.sheen(ctx, p, anchor, api, p.attack.age);
    if (m.id === "dragonclaw" && anchor)
      this.texture(ctx, "claw-strike", anchor.x, anchor.y, height * .22, .8);
    return true;
  }
  state(ctx, e, layer, api) {
    if (!this.uses(e.id, e.owner)) return false;
    if (e.id === "thunder") {
      const target = e.owner === api.player ? api.enemy : api.player;
      if (e.landed || layer === "above")
        this.paint(ctx, { kind: e.landed ? "thunder" : "warning", id: e.id,
          x: e.ex, y: e.ey, height: e.owner.char.body.visibleSize[1],
          targetHeight: target.char.body.visibleSize[1], radius: e.radius, age: e.age,
          part: layer === "below" ? "bolt" : "ring", since: e.age - (e.life - .35) });
      return true;
    }
    if (layer !== "above") return true;
    const p = e.owner, height = p.char.body.visibleSize[1];
    const anchor = api.anchor(p, e.m, e.a);
    if (anchor) e.drawAnchor = anchor; // Preserve the existing landmark audit verbatim.
    if (e.id === "quickattack") {
      this.paint(ctx, { kind: "rush", id: e.id, ...anchor, height, age: e.age, angle: e.a });
    } else if (e.id === "irontail") {
      this.sheen(ctx, p, anchor, api, e.age);
      this.paint(ctx, { kind: "tail", id: e.id, ...anchor, height, age: e.age, angle: e.a,
        alpha: Math.min(1, (e.life - e.age) / .08) });
    } else if (e.id === "dragonclaw") {
      // Short aura follows the claw. Full scars are created only at a successful contact.
      this.texture(ctx, "claw-strike", anchor.x, anchor.y, height * .22,
        Math.min(1, (e.life - e.age) / .08));
    }
    return true;
  }
  electrify(ctx, target, image, sx, sy, sw, sh, x, y, w, h) {
    const age = this.shocks.get(target);
    if (age === undefined || !(age < .035 || (age >= .075 && age < .11))) return;
    // Two white sweeps on the actual sprite alpha, never a solid flash hiding its colors.
    const canvas = (this.shockCanvas ||= document.createElement("canvas"));
    canvas.width = Math.ceil(w); canvas.height = Math.ceil(h);
    const c = canvas.getContext("2d");
    c.imageSmoothingEnabled = false;
    c.drawImage(image, sx, sy, sw, sh, 0, 0, w, h);
    c.globalCompositeOperation = "source-in";
    c.fillStyle = "#ffffff";
    c.fillRect(0, 0, w, h);
    c.globalCompositeOperation = "destination-in";
    c.beginPath();
    for (let i = -h; i < w; i += 16) {
      c.moveTo(i, 0); c.lineTo(i + 3, 0);
      c.lineTo(i + h + 3, h); c.lineTo(i + h, h); c.closePath();
    }
    c.fill();
    ctx.save();
    ctx.globalAlpha *= .9;
    ctx.drawImage(canvas, x, y);
    ctx.restore();
  }
  step(dt) {
    for (const [target, age] of this.shocks) {
      if (age + dt >= .35) this.shocks.delete(target);
      else this.shocks.set(target, age + dt);
    }
    for (const b of this.bursts) b.age += dt;
    for (const r of this.ribbons) r.life += dt;
    this.bursts = this.bursts.filter(b => b.age < .28);
    this.ribbons = this.ribbons.filter(r => r.life < .10);
  }
  draw(ctx) {
    for (const r of this.ribbons) this.paint(ctx, { ...r, alpha: 1 - r.life / .10 });
    for (const b of this.bursts) this.paint(ctx, b);
  }
};
