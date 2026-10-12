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
  load() {
    return (this.loading ||= this.engine.load());
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
      burst = { id: m.id, ...contact, age: 0,
        size: height * Math.max(.8, .6 + .4 * amount / 35),
        key: "core-impact-" + (this.engine.mapping.effects["core-impact-" + m.type] ? m.type : -1),
        heavy: amount >= 25 || mult >= 2, time: this.time, amount };
    this.hero.impact(burst, target, source, dx, dy);
    this.melee.impact(burst, target, source, m, api);
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
  step(dt) {
    this.hero.step(dt);
    this.time += dt;
    this.melee.step(dt);
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
    for (const r of this.ribbons)
      this.path(ctx, r.id, r.root, r.front, r.shotAge, 1 - r.age / .10, r.height);
    for (const b of this.bursts) {
      // VH revision: hollow electricity / separated scars replace only these two solid stars.
      if (b.heroContact) continue;
      const t = b.age / .26, alpha = 1 - t;
      if (b.id === "watergun" || b.id === "icebeam") {
        const ice = b.id === "icebeam";
        if (!ice) this.sprite(ctx, "core-splash", b.x, b.y, b.size * (1 + t), alpha);
        else this.glow(ctx, b.x, b.y, b.size, alpha * .5);
        for (let i = 0; i < 9; i++) {
          const a = i * Math.PI * 2 / 9, r = b.size * (.22 + t * .7);
          this.sprite(ctx, ice ? "core-shard" : "core-drop", b.x + Math.cos(a) * r,
            b.y + Math.sin(a) * r + (ice ? 0 : t * t * 12), ice ? 16 : 14, alpha, a);
        }
      }
      this.sprite(ctx, b.key, b.x, b.y, b.size * (b.vb1 ? 1.1 : 1), alpha);
      this.melee.symbol(ctx, b);
      if (b.heavy) {
        ctx.save();
        ctx.strokeStyle = "#ffffff";
        ctx.globalAlpha = alpha;
        ctx.lineWidth = 2;
        for (let i = 0; i < 12; i++) {
          const a = i * Math.PI / 6, r = b.size * (.6 + t * .4);
          ctx.beginPath();
          ctx.moveTo(b.x + Math.cos(a) * r, b.y + Math.sin(a) * r);
          ctx.lineTo(b.x + Math.cos(a) * (r + 5), b.y + Math.sin(a) * (r + 5));
          ctx.stroke();
        }
        ctx.restore();
      }
    }
    this.hero.draw(ctx);
    this.melee.draw(ctx);
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
