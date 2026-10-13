// SPDX-License-Identifier: AGPL-3.0-or-later
// Physics is authoritative. This adapter never owns damage values, range or collision shapes.
window.PoightMoveAnimations = class {
  constructor(bundle, enabled = true) {
    this.enabled = enabled;
    this.engine = new window.PoightAnimationEngine(bundle.data, bundle.mapping);
    this.loading = null;
    this.hero = new window.PoightHeroVisuals(this);
    this.melee = new window.PoightMeleeVB1(this);
    this.reset();
  }
  load(ids = null, extraEffects = []) {
    return this.engine.load(ids, extraEffects);
  }
  reset() {
    this.hero.reset();
    this.engine.clear();
    this.melee?.reset();
    this.bursts = [];
    this.ribbons = [];
    this.releases = [];
    this.contacts = [];
    this.frost = new Map();
    this.colorGuard = new Map();
    this.contactFrames = new Map();
    this.time = 0;
  }
  uses(id) {
    return this.enabled && ["watergun", "icebeam", "earthquake"].includes(id);
  }
  anchor(p, m, angle, api) {
    const entries = p.char.moveAnchors || {},
      part = entries["r3-mouth"] ? "r3-mouth" : "mouth";
    return api.anchor(p, { ...m, r3: false, batch2: true, anchor: part }, angle);
  }
  prepare(b, api) {
    this.hero.prepare(b);
    if (!this.uses(b.m.id)) return b;
    const root = this.anchor(b.owner, b.m, Math.atan2(b.uy, b.ux), api);
    if (!root) throw new Error("Missing animation mouth anchor: " + b.owner.id);
    b.originAnchor = { ...root };
    b.coreRoot = { ...root };
    b.visualOffsetX = root.x - b.x;
    b.visualOffset = root.y - (b.y - 16 - b.airFrom);
    b.coreShot = this.engine.createShot(b.m.id,
      { ...root, height: b.owner.char.body.visibleSize[1] },
      { x: b.x, y: b.y, height: 48 }, { fx: b.m.id === "watergun" ? "core-water" : "core-ice" });
    this.releases.push({ id: b.m.id, x: root.x, y: root.y, anchor: { ...root },
      physical: { x: b.x, y: b.y }, time: this.time });
    this.releases = this.releases.slice(-32);
    return b;
  }
  front(b, lift) {
    const travel = Math.hypot(b.x - b.sx, b.y - b.sy),
      fade = Math.max(0, 1 - travel / Math.max(1, b.airDistance - 36));
    return { x: b.x + (b.visualOffsetX || 0) * fade,
      y: b.y - 16 - lift + (b.visualOffset || 0) * fade };
  }
  sprite(ctx, key, x, y, size, alpha = 1, angle = 0) {
    const m = this.engine.mapping.effects[key];
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    this.engine.drawEffect(ctx, key,
      { x: 0, y: 0, z: 0, scale: size / m.width, xscale: 1, yscale: 1, opacity: alpha },
      this.time * 1000, "core", 1);
    ctx.restore();
  }
  glow(ctx, x, y, radius, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
    g.addColorStop(0, "#e6ffff");
    g.addColorStop(.3, "#65dcffb0");
    g.addColorStop(1, "#54cfff00");
    ctx.fillStyle = g;
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
    ctx.restore();
  }
  readable(height) {
    return { bead: Math.max(14, height * .30), beam: Math.max(10, height * .25) };
  }
  path(ctx, id, root, front, age, alpha = 1, height = 48) {
    const dx = front.x - root.x, dy = front.y - root.y,
      length = Math.hypot(dx, dy), angle = Math.atan2(dy, dx),
      sizes = this.readable(height);
    if (id === "icebeam") {
      // Continuous ice-blue core, with tiled Emerald crystals, NOT a stretched fireball.
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineCap = "round";
      for (const [width, color] of [
        [sizes.beam + 10, "#18c7ff60"], [sizes.beam + 4, "#60ffff"],
        [sizes.beam, "#f2ffff"],
      ]) {
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(root.x, root.y);
        ctx.lineTo(front.x, front.y);
        ctx.stroke();
      }
      ctx.restore();
      const n = Math.max(1, Math.ceil(length / 23));
      for (let i = 0; i <= n; i++) {
        const t = i / n, wobble = Math.sin(i * 2.2 + age * 28) * 2;
        this.sprite(ctx, "core-ice", root.x + dx * t - Math.sin(angle) * wobble,
          root.y + dy * t + Math.cos(angle) * wobble,
          Math.max(22 + (i % 2) * 6, sizes.beam * 1.5), alpha, angle);
      }
      // Keep the luminous core unbroken even across the crystal tiles.
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = "#f2ffff";
      ctx.lineWidth = Math.max(4, sizes.beam * .65);
      ctx.beginPath();
      ctx.moveTo(root.x, root.y);
      ctx.lineTo(front.x, front.y);
      ctx.stroke();
      ctx.restore();
      this.glow(ctx, root.x, root.y, 15, alpha * .7);
      this.glow(ctx, front.x, front.y, 16, alpha * .65);
    } else {
      // Discrete, curved water bead train; every bead stays behind the physical head.
      const count = 6, size = Math.max(sizes.bead, length / (count - 1) + 2);
      for (let i = 0; i < count; i++) {
        const t = i / (count - 1), arc = -Math.sin(t * Math.PI) * 7;
        this.sprite(ctx, "core-water", root.x + dx * t - Math.sin(angle) * arc,
          root.y + dy * t + Math.cos(angle) * arc, size, alpha, angle);
      }
      if (age < .1) this.glow(ctx, root.x, root.y, 12, alpha * (1 - age / .1));
    }
  }
  bullet(ctx, b, lift, api) {
    if (this.hero.bullet(ctx, b, lift, api)) return true;
    if (!this.uses(b.m.id) || !b.coreShot) return false;
    const front = this.front(b, lift),
      root = b.m.id === "icebeam" && b.owner.attack?.id === b.m.id
        ? this.anchor(b.owner, b.m, Math.atan2(b.uy, b.ux), api) : b.coreRoot;
    b.coreShot.update(front, this.time * 1000);
    this.path(ctx, b.m.id, root, front, b.age, 1, b.owner.char.body.visibleSize[1]);
    return true;
  }
  projectileContact(b, point, lift, api) {
    this.hero.projectileContact(b, point, lift, api);
    if (!this.uses(b.m.id) || !b.coreShot) return;
    const front = { x: point.x, y: point.y - 16 - lift },
      root = b.m.id === "icebeam" && b.owner.attack?.id === b.m.id
        ? this.anchor(b.owner, b.m, Math.atan2(b.uy, b.ux), api) : b.coreRoot;
    b.coreShot.hit(front, this.time * 1000);
    this.ribbons.push({ id: b.m.id, root, front, age: 0, shotAge: b.age,
      height: b.owner.char.body.visibleSize[1] });
    this.ribbons = this.ribbons.slice(-32);
  }
  impact(target, source, m, amount, mult, dx, dy, point, api) {
    if (!this.enabled) return;
    const height = target.char.body.visibleSize[1],
      length = Math.hypot(dx, dy) || 1,
      reach = api.bodies.reach(target, dx, dy),
      contact = point || { x: target.x - dx / length * reach * .6,
        y: target.y + 14 - height / 2 - api.lift(target) - dy / length * reach * .6 },
      burst = { id: m.id, type: m.type, ...contact, age: 0,
        ringX: target.x, ringY: target.y + 14 - height / 2 - api.lift(target),
        height,
        size: height * Math.max(.8, .6 + .4 * amount / 35),
        key: "core-impact-" + (this.engine.mapping.effects["core-impact-" + m.type] ? m.type : -1),
        heavy: amount >= 25 || mult >= 2, time: this.time, amount };
    Object.defineProperty(burst, 'ringTarget', { value: target });
    this.hero.impact(burst, target, source, dx, dy);
    this.melee.impact(burst, target, source, m, api);
    // Presentation-only stencil: covers the existing contact/recovery layers, never hit clocks.
    this.colorGuard.set(target, .6);
    if (m.id === "icebeam") this.frost.set(target, .3);
    this.bursts.push(burst);
    this.bursts = this.bursts.slice(-64);
    this.contacts.push({ ...burst });
    this.contacts = this.contacts.slice(-64);
  }
  nova(common, target, api) {
    // Keep M4's square eligibility, including corner/body overlap, but defer the hit.
    const shapes = target.char.body.hurtByDirection,
      rx = Math.max(...shapes.map((s) => s[0])),
      ry = Math.max(...shapes.map((s) => s[1])),
      maxRadius = Math.hypot(72 + rx, 72 + ry);
    return { ...common, mode: "core-nova", life: .6, radius: 0,
      maxRadius, previousGap: Infinity, contactRadius: null, targetDistance: null };
  }
  stepNova(e, target, api) {
    const dx = target.x - e.x, dy = target.y - e.y, distance = Math.hypot(dx, dy);
    e.radius = e.maxRadius * Math.min(1, e.age / .45);
    if (e.radius >= distance && e.previousGap > 0 &&
      api.bodies.rect(target, e.x - 72, e.y - 72, 144, 144) &&
      api.clearLine(e.x, e.y, target.x, target.y, 3)) {
      e.contactRadius = e.radius;
      e.targetDistance = distance;
      e.contacted = !!api.damage(target, e.owner, e.m, dx / (distance || 1),
        dy / (distance || 1), e.group, { x: target.x, y: target.y });
    }
    e.previousGap = distance - e.radius;
  }
  drawNova(ctx, e) {
    const alpha = Math.min(1, (.6 - e.age) / .15), r = e.radius;
    ctx.save();
    ctx.globalAlpha = alpha;
    // A world-space circular ground front, not a screen-space squash: radius = hit clock.
    // M6b 授权外观修正：只加深地震前景，保持双场地亮度差 >=60。
    ctx.strokeStyle = "#251204";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(e.x, e.y, Math.max(0, r), 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = "#b87828";
    ctx.lineWidth = 1;
    ctx.stroke();
    for (let i = 0; i < 20; i++) {
      const a = i * Math.PI / 10, ux = Math.cos(a), uy = Math.sin(a);
      this.sprite(ctx, "core-dust", e.x + ux * r, e.y + uy * r, 18, alpha * .75, a);
      ctx.strokeStyle = "#493012";
      ctx.beginPath();
      ctx.moveTo(e.x + ux * r * .6, e.y + uy * r * .6);
      ctx.lineTo(e.x + ux * r * .8 - uy * 4, e.y + uy * r * .8 + ux * 4);
      ctx.lineTo(e.x + ux * r, e.y + uy * r);
      ctx.stroke();
    }
    ctx.restore();
  }
  drawFrost(ctx, target, image, sx, sy, sw, sh, x, y, w, h) {
    const life = this.frost.get(target);
    if (!life) return;
    // Alpha-silhouette outline of the CURRENT actor frame, never a rectangular box.
    const canvas = (this.frostCanvas ||= document.createElement("canvas"));
    canvas.width = Math.ceil(w) + 8;
    canvas.height = Math.ceil(h) + 8;
    const c = canvas.getContext("2d");
    c.imageSmoothingEnabled = false;
    for (const [dx, dy] of [[-2, 0], [2, 0], [0, -2], [0, 2]])
      c.drawImage(image, sx, sy, sw, sh, 4 + dx, 4 + dy, w, h);
    c.globalCompositeOperation = "source-in";
    c.fillStyle = "#e5ffff";
    c.fillRect(0, 0, canvas.width, canvas.height);
    c.globalCompositeOperation = "destination-out";
    c.drawImage(image, sx, sy, sw, sh, 4, 4, w, h);
    ctx.save();
    ctx.globalAlpha *= Math.min(1, life / .08);
    ctx.drawImage(canvas, x - 4, y - 4);
    ctx.restore();
  }
  captureContactFrame(ctx, target, nativeBounds, ...args) {
    // Same alpha>=128 pixel bounds as runtime sampling, packed losslessly at build time.
    // file:// images may be drawable but not readable under Chromium's origin policy.
    const [left, top, right, bottom] = nativeBounds;
    this.contactFrames.set(target, { args, matrix: ctx.getTransform(),
      bounds: { left, top, right, bottom } });
  }
  clipContactCenters(ctx, targets = this.colorGuard.keys()) {
    // Used ONLY for successful-hit contact/recovery paint. Actors, terrain, charge and
    // live projectiles never enter this stencil. Zero alpha also prevents stacked teeth.
    const transform = ctx.getTransform();
    for (const target of targets) {
      const frame = this.contactFrames.get(target);
      if (!frame || !this.colorGuard.has(target)) continue;
      const { args, bounds: b, matrix } = frame, [, , , sw, sh, x, y, w, h] = args;
      const cx = x + (b.left + b.right) / 2 * w / sw,
        cy = y + (b.top + b.bottom) / 2 * h / sh,
        shape = window.PoightBodies.shape(target);
      ctx.resetTransform();
      ctx.beginPath();
      ctx.rect(0, 0, ctx.canvas.width, ctx.canvas.height);
      ctx.setTransform(matrix);
      ctx.ellipse(cx, cy, Math.max(shape.rx * .90, (b.right - b.left) * w / sw * .45),
        Math.max(shape.ry * .90, (b.bottom - b.top) * h / sh * .45), 0, 0, Math.PI * 2);
      ctx.clip("evenodd");
    }
    ctx.setTransform(transform);
  }
  step(dt) {
    this.hero.step(dt);
    this.time += dt;
    this.melee.step(dt);
    for (const [target, life] of this.colorGuard) {
      if (life <= dt) this.colorGuard.delete(target);
      else this.colorGuard.set(target, life - dt);
    }
    for (const [target, life] of this.frost) {
      if (life <= dt) this.frost.delete(target);
      else this.frost.set(target, life - dt);
    }
    for (const b of this.bursts) b.age += dt;
    for (const r of this.ribbons) r.age += dt;
    this.bursts = this.bursts.filter((b) => b.age < .26);
    this.ribbons = this.ribbons.filter((r) => r.age < .10);
    this.engine.shots = this.engine.shots.filter((s) => this.time * 1000 - s.time < 1000);
  }
  draw(ctx) {
    ctx.save();
    this.clipContactCenters(ctx);
    for (const r of this.ribbons)
      this.path(ctx, r.id, r.root, r.front, r.shotAge, 1 - r.age / .10, r.height);
    for (const b of this.bursts) {
      // VH revision: hollow electricity / separated scars replace only these two solid stars.
      if (b.heroContact) continue;
      this.drawBurst(ctx, b);
      this.melee.symbol(ctx, b);
    }
    this.hero.draw(ctx);
    this.melee.draw(ctx);
    ctx.restore();
  }
  ringGeometry(ctx, b) {
    let x = b.ringX, y = b.ringY, diameter = Math.max(b.size, b.height * 1.2);
    const frame = this.contactFrames.get(b.ringTarget);
    if (frame) {
      const { args, bounds: box, matrix } = frame, [, , , sw, sh, bx, by, w, h] = args,
        cx = bx + (box.left + box.right) / 2 * w / sw,
        cy = by + (box.top + box.bottom) / 2 * h / sh,
        shape = window.PoightBodies.shape(b.ringTarget),
        rx = Math.max(shape.rx * .90, (box.right - box.left) * w / sw * .45),
        ry = Math.max(shape.ry * .90, (box.bottom - box.top) * h / sh * .45),
        transform = ctx.getTransform().inverse().multiply(matrix),
        center = new DOMPoint(cx, cy).matrixTransform(transform),
        axisX = new DOMPoint(cx + rx, cy).matrixTransform(transform),
        axisY = new DOMPoint(cx, cy + ry).matrixTransform(transform);
      x = center.x; y = center.y;
      diameter = Math.max(diameter, 2 * (Math.max(Math.hypot(axisX.x - x, axisX.y - y),
        Math.hypot(axisY.x - x, axisY.y - y)) + 6));
    }
    return { x, y, diameter: diameter * (1 + b.age / .26 * .15) };
  }
  drawBurst(ctx, b) {
    // Follow the actual current silhouette outside the P6 stencil, including hurt poses.
    // Physical contact coordinates and the hit clock stay intact.
    const t = b.age / .26, { x, y, diameter } = this.ringGeometry(ctx, b),
      r = diameter / 2, width = Math.min(3, diameter * .065),
      color = this.ringColor(b.type), shock = [1, 2, 9, -1].includes(b.type);
    ctx.save();
    ctx.globalAlpha *= Math.min(1, (.26 - b.age) / .08);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineJoin = "round";
    const outline = (offset) => {
      ctx.beginPath();
      for (let i = 0; i <= 64; i++) {
        const a = i * Math.PI / 32,
          wobble = b.type === 13 ? (i % 2 ? 1 : -1) * width * .45
            : b.type === 11 ? Math.sin(a * 9 + t * 3) * width * .35 : 0,
          rr = r - width / 2 + wobble + offset;
        const px = x + Math.cos(a) * rr, py = y + Math.sin(a) * rr;
        if (i) ctx.lineTo(px, py);
        else ctx.moveTo(px, py);
      }
      ctx.closePath();
    };
    // Exactly one screen pixel on the OUTSIDE, none added inside the transparent center.
    const pixel = 1 / Math.hypot(ctx.getTransform().a, ctx.getTransform().b);
    outline(pixel / 2);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = width + pixel;
    ctx.stroke();
    outline(0);
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
    // Broken white crests/highlights, not a solid disk: attribute ink remains continuous
    // underneath. Long alternating segments preserve saturated pigment between crests.
    ctx.save();
    const crestDash = [r * Math.PI * .75, r * Math.PI * .25],
      crestRatio = (r - width / 2 + pixel / 2) / (r - width / 2);
    ctx.setLineDash(crestDash.map(v => v * crestRatio));
    ctx.lineDashOffset = -t * r * .3 * crestRatio;
    outline(pixel / 2);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = width + 1 + pixel;
    ctx.stroke();
    outline(0);
    ctx.setLineDash(crestDash);
    ctx.lineDashOffset = -t * r * .3;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = width + 1; // White fringe is achromatic; outside ink stays exactly one pixel.
    ctx.stroke();
    ctx.restore();
    // Outer-only motifs: never place a shard, leaf, spark or glow in the transparent center.
    for (let i = 0; i < 10; i++) {
      const a = i * Math.PI / 5 + .15, ca = Math.cos(a), sa = Math.sin(a),
        inner = r + width, outer = inner + Math.max(3, diameter * .09) * (1 + t);
      ctx.strokeStyle = color;
      ctx.lineWidth = shock ? 1.2 : width * .65;
      ctx.beginPath();
      ctx.moveTo(x + ca * inner, y + sa * inner);
      if (b.type === 12 || b.type === 15) {
        ctx.lineTo(x + ca * (inner + outer) / 2 - sa * width,
          y + sa * (inner + outer) / 2 + ca * width);
        ctx.lineTo(x + ca * outer, y + sa * outer);
        ctx.lineTo(x + ca * (inner + outer) / 2 + sa * width,
          y + sa * (inner + outer) / 2 - ca * width);
        ctx.closePath();
      } else if ([4, 8, 14].includes(b.type)) {
        ctx.arc(x, y, outer, a, a + .25);
      } else {
        ctx.lineTo(x + ca * outer, y + sa * outer);
      }
      ctx.stroke();
    }
    ctx.restore();
  }
  ringColor(type) {
    // All primary pigments have HSL L>=60%; white/ivory, blue foam and bright violet.
    const colors = { 1: '#fff340', 2: '#ff8f40', 3: '#4fbaff', 4: '#ed40ff',
      5: '#ffd440', 6: '#ffd440', 7: '#b0ff40', 8: '#d640ff', 9: '#4fbaff',
      10: '#ffb240', 11: '#4fc3ff', 12: '#b0ff40', 13: '#ffe440',
      14: '#ff40dd', 15: '#4fefff', 16: '#a640ff', 17: '#d640ff', 18: '#ff40dd' };
    return colors[type] || colors[1];
  }
  ringBackdrop(ctx, x, y, r) {
    if (this.backdropReadbackBlocked) return 160;
    const matrix = ctx.getTransform(), points = [];
    let left = ctx.canvas.width - 1, top = ctx.canvas.height - 1, right = 0, bottom = 0;
    for (let i = 0; i < 64; i++) {
      const a = i * Math.PI / 32,
        q = new DOMPoint(x + Math.cos(a) * r, y + Math.sin(a) * r).matrixTransform(matrix),
        px = Math.max(0, Math.min(ctx.canvas.width - 1, Math.round(q.x))),
        py = Math.max(0, Math.min(ctx.canvas.height - 1, Math.round(q.y)));
      points.push([px, py]);
      left = Math.min(left, px); right = Math.max(right, px);
      top = Math.min(top, py); bottom = Math.max(bottom, py);
    }
    const width = right - left + 1;
    let pixels;
    try {
      pixels = ctx.getImageData(left, top, width, bottom - top + 1).data;
    } catch (error) {
      if (error.name !== "SecurityError") throw error;
      // Preserve offline playback; only blocked backdrop readback uses the dark saturated ink.
      this.backdropReadbackBlocked = true;
      return 160;
    }
    return points.reduce((sum, [px, py]) => {
      const n = ((py - top) * width + px - left) * 4;
      return sum + .2126 * pixels[n] + .7152 * pixels[n + 1] + .0722 * pixels[n + 2];
    }, 0) / points.length;
  }
  lick(ctx, p, m, age, api, charging = false) {
    if (!this.enabled || m.id !== "lick") return false;
    const a = p.attack?.aim ?? p.a, h = p.char.body.visibleSize[1],
      root = api.anchor(p, m, a) || this.anchor(p, m, a, api) ||
        { x: p.x, y: p.y - h * .45 - api.lift(p) },
      target = p === api.player ? api.enemy : api.player,
      tip = { x: target.x, y: target.y + 14 - target.char.body.visibleSize[1] / 2 -
        api.lift(target) },
      reach = Math.min(m.range, Math.hypot(tip.x - root.x, tip.y - root.y)),
      angle = Math.atan2(tip.y - root.y, tip.x - root.x),
      contact = m.contactDelay || .10, hold = contact + .04,
      // Sample the EXISTING release/contact/recovery clocks; do not change any hit tick.
      extension = charging ? .5 * Math.min(1, age / p.attack.hitTime)
        : age <= contact ? .5 + .5 * Math.min(1, age / contact)
          : Math.max(0, 1 - Math.max(0, age - hold) / Math.max(.01, m.recovery - hold)),
      length = Math.max(56, reach) * extension, width = Math.min(3, h * .06);
    ctx.save();
    ctx.translate(root.x, root.y);
    ctx.rotate(angle);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(length * .32, -width * .8, length * .70, width * .8, length * .86, 0);
    ctx.bezierCurveTo(length * 1.08, -width * .7, length * .98, -width * 1.5,
      length * .88, -width * .9);
    ctx.strokeStyle = "#70002b";
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.strokeStyle = "#d8106a";
    ctx.lineWidth = width * .65;
    ctx.stroke();
    ctx.restore();
    return root;
  }
  // Melee opt-in: never apply raw contactattack actor coordinates to game state.
  boundedPose(instance, role, elapsed) {
    const actor = instance.actors[role], sampled = instance.snapshot(elapsed).actors[role],
      dx = sampled.x - actor.x, dy = sampled.y - actor.y,
      length = Math.hypot(dx, dy), limit = actor.height / 2,
      gain = Math.min(1, limit / (length || 1)) *
        Math.max(0, 1 - Math.max(0, elapsed - instance.impactMs) / 120);
    return { x: dx * gain, y: dy * gain };
  }
  snapshot() {
    return { enabled: this.enabled, loaded: this.engine.images.size,
      releases: this.releases, contacts: this.contacts, bursts: this.bursts,
      hero: { events: this.hero.events, bursts: this.hero.bursts },
      ribbons: this.ribbons, frost: [...this.frost.values()], time: this.time,
      meleeReturns: this.melee.hits };
  }
};
