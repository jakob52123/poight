// SPDX-License-Identifier: AGPL-3.0-or-later
// VB1 visual opt-in only. All contact, damage, stamina and cooldowns stay in gameplay.
window.PoightMeleeVB1 = class {
  static moves = {
    vinewhip: { shape: "whip", color: "green" },
    scratch: { shape: "scratch", color: "gold" },
    brickbreak: { shape: "fist", color: "gold", accent: "wall" },
    karatechop: { shape: "palm", color: "gold" },
    lick: { shape: "tongue", color: "pink" },
    wingattack: { shape: "gust", color: "gold" },
    metalclaw: { shape: "claw", color: "ice" },
    headbutt: { shape: "star", color: "gold" },
    return: { shape: "combo", color: "gold" },
    firepunch: { shape: "fist", color: "fire", accent: "ember" },
    absorb: { shape: "orb", color: "green", drain: true },
    leafblade: { shape: "cross", color: "green", accent: "leaf" },
    thunderpunch: { shape: "fist", color: "gold", accent: "bolt" },
    icepunch: { shape: "fist", color: "ice", accent: "ice" },
    drainpunch: { shape: "fist", color: "green", drain: true },
    reversal: { shape: "fist", color: "gold", accent: "blueorb" },
    crosschop: { shape: "palms", color: "gold" },
    poisonjab: { shape: "palm", color: "poison", accent: "poison" },
    shadowpunch: { shape: "fist", color: "ghost", accent: "trace" },
    peck: { shape: "tip", color: "gold" },
    drainingkiss: { shape: "heart", color: "pink", drain: true },
  };
  constructor(adapter) {
    this.adapter = adapter;
    this.reset();
  }
  reset() {
    this.poses = new WeakMap();
    this.activePoses = [];
    this.hits = [];
  }
  has(id) {
    // P6 owns Lick's continuous mouth-anchored tongue, including charge/recovery.
    return this.adapter.enabled && id !== "lick" && Object.hasOwn(window.PoightMeleeVB1.moves, id);
  }
  pose(p) {
    const attack = p.attack;
    if (!attack || !this.has(attack.id)) return { x: 0, y: 0 };
    const height = p.char.body.visibleSize[1];
    let instance = this.poses.get(attack);
    if (!instance) {
      const actor = { x: 0, y: 0, height },
        target = { x: height * 2, y: 0, height },
        windupMs = (attack.hitTime + (attack.move.contactDelay || 0)) * 1000;
      instance = this.adapter.engine.cast(attack.id, actor, target, { windupMs });
      if (!instance.move.events.some((e) => e.type === "actor" && e.role === "attacker")) {
        instance.cancel();
        const scene = this.adapter.engine.scene(actor, target, { impactMs: 400, windupMs });
        scene.other("contactattack");
        instance = scene.instance;
      }
      this.poses.set(attack, instance);
      this.activePoses.push({ actor: p, attack, instance });
    }
    if (instance.cancelled) return { x: 0, y: 0 };
    // Showdown's stage y/depth is a forward attack, not a world-space teleport.
    const sampled = this.adapter.boundedPose(instance, "attacker", attack.age * 1000),
      reach = Math.min(height / 2, Math.hypot(sampled.x, sampled.y)),
      lift = ["headbutt", "return"].includes(attack.id)
        ? Math.sin(Math.min(1, attack.age * 1000 / instance.impactMs) * Math.PI) * height * .08 : 0,
      forward = Math.sqrt(Math.max(0, reach * reach - lift * lift));
    const x = Math.cos(attack.aim) * forward, y = Math.sin(attack.aim) * forward - lift,
      gain = Math.min(1, height / 2 / (Math.hypot(x, y) || 1));
    return { x: x * gain, y: y * gain };
  }
  charge(ctx, p, m, api) {
    if (m.id !== "reversal" || !p.attack || p.attack.emitted) return;
    const height = p.char.body.visibleSize[1], pose = this.pose(p),
      x = p.x + pose.x, y = p.y + 14 - height / 2 - api.lift(p) + pose.y;
    for (let i = 0; i < 6; i++) {
      const a = i * Math.PI / 3 + p.attack.age * 8;
      this.stamp(ctx, "blueorb", "blue", x + Math.cos(a) * height * .6,
        y + Math.sin(a) * height * .5, Math.max(15, height * .32));
    }
  }
  impact(burst, target, source, m, api) {
    if (!this.has(m.id)) return;
    burst.vb1 = { ...window.PoightMeleeVB1.moves[m.id],
      height: target.char.body.visibleSize[1], sourceHeight: source.char.body.visibleSize[1],
      angle: source.attack?.aim ?? source.a,
      root: { x: source.x,
        y: source.y + 14 - source.char.body.visibleSize[1] / 2 - api.lift(source) },
    };
    if (burst.vb1.drain) this.hits.push({ ...burst, age: 0, life: .56 });
  }
  step(dt) {
    for (const hit of this.hits) hit.age += dt;
    this.hits = this.hits.filter((hit) => hit.age < hit.life);
    // Cancel only our sampled poses; external batches retain their instances.
    this.activePoses = this.activePoses.filter((entry) => {
      if (entry.actor.attack === entry.attack && entry.actor.hp > 0) return true;
      entry.instance.cancel();
      return false;
    });
    // Instances are sampled read-only; no engine callback can manufacture gameplay hits.
    this.adapter.engine.instances = this.adapter.engine.instances.filter((i) => !i.cancelled);
  }
  stamp(ctx, shape, color, x, y, length, angle = 0, alpha = 1) {
    const key = `vb1-${shape}-${color}`, mapping = this.adapter.engine.mapping.effects[key],
      size = length * mapping.width / Math.max(mapping.width, mapping.height);
    this.adapter.sprite(ctx, key, x, y, size,
      alpha, angle);
  }
  symbol(ctx, b) {
    if (!b.vb1) return;
    const v = b.vb1, t = b.age / .26, alpha = Math.min(1, (1 - t) * 2),
      size = v.height * .98, angle = v.angle, x = b.x, y = b.y,
      stamp = (shape, color, dx = 0, dy = 0, length = size, rotation = 0) =>
        this.stamp(ctx, shape, color, x + dx, y + dy, length, rotation, alpha);
    // Accents sit behind the main identifiable shape, never cover the fist/palm.
    if (["ember", "ice", "leaf", "poison", "blueorb"].includes(v.accent)) {
      for (let i = 0; i < 5; i++) {
        const a = i * Math.PI * 2 / 5 + t * 2, r = size * (.55 + t * .35),
          shape = v.accent === "poison" ? "orb" : v.accent,
          color = v.accent === "blueorb" ? "blue" : v.color;
        if (v.accent === "ice")
          this.adapter.sprite(ctx, "core-shard", x + Math.cos(a) * r,
            y + Math.sin(a) * r, Math.max(14, size * .40), alpha, a);
        else stamp(shape, color, Math.cos(a) * r, Math.sin(a) * r,
          Math.max(14, size * .42), a);
      }
    }
    if (v.accent === "bolt") stamp("bolt", "gold", 0, 0, size * 1.8);
    if (v.accent === "wall") {
      for (let i = 0; i < 4; i++) {
        const a = i * Math.PI / 2 + Math.PI / 4, r = size * (.7 + t);
        stamp("shard", "green", Math.cos(a) * r, Math.sin(a) * r, size * .5, a);
      }
    }
    if (v.accent === "trace") {
      for (let i = 3; i > 0; i--)
        this.stamp(ctx, "fist", "ghost", x - Math.cos(angle) * size * i * .28,
          y - Math.sin(angle) * size * i * .28, size, 0, alpha * (1 - i * .22));
    }
    if (v.shape === "scratch") {
      for (let i = -1; i <= 1; i++) stamp("scratch", v.color, i * size * .2, 0, size, -.5);
    } else if (v.shape === "claw") {
      for (const side of [-1, 1]) for (const i of [-1, 1])
        stamp("claw", v.color, side * size * .14, i * size * .16, size, side < 0 ? 0 : Math.PI / 2);
    } else if (v.shape === "gust") {
      for (const side of [-1, 1]) {
        stamp("gust", v.color, side * size * .48, 0, size);
        this.adapter.sprite(ctx, b.key, x + side * size * .48, y, size * .5, alpha);
      }
    } else if (v.shape === "palms") {
      stamp("cross", "gold", 0, 0, size * 1.25);
      for (const side of [-1, 1])
        stamp("palm", "gold", side * size * .22, 0, size, side * .72);
    } else if (v.shape === "combo") {
      for (let i = 0; i < 3; i++) {
        const a = i * Math.PI * 2 / 3 + t * 3;
        stamp("star", "gold", Math.cos(a) * size * .3,
          Math.sin(a) * size * .3, size * .9);
      }
    } else if (v.shape === "star" || v.shape === "tip") {
      stamp("star", "gold", 0, 0, size * (v.shape === "tip" ? .85 : 1.1),
        v.shape === "tip" ? angle : 0);
      if (v.shape === "tip") {
        // Emerald Peck has no beak sprite: an elongated sharp impact, not a new bird asset.
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(angle);
        ctx.fillStyle = "#ffff46";
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.moveTo(size * .82, 0);
        ctx.lineTo(-size * .40, -size * .18);
        ctx.lineTo(-size * .40, size * .18);
        ctx.fill();
        ctx.restore();
      }
    } else {
      stamp(v.shape, v.color, 0, 0, size, v.shape === "tongue" ? angle + Math.PI / 2 :
        v.shape === "palm" ? -.6 : v.shape === "whip" ? angle : 0);
      if (v.shape === "tongue") {
        // Emerald's Lick strip is square/jagged. Preserve that texture as the body,
        // but soften the tip and add a pink central crease so it reads as a tongue.
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(angle);
        ctx.globalAlpha = alpha;
        ctx.fillStyle = "#990035";
        ctx.beginPath();
        ctx.arc(size * .42, 0, size * .16, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ed3b93";
        ctx.lineWidth = Math.max(1, size * .045);
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(-size * .30, 0);
        ctx.lineTo(size * .46, 0);
        ctx.stroke();
        ctx.restore();
      }
    }
  }
  draw(ctx) {
    for (const b of this.hits) {
      const v = b.vb1, dx = v.root.x - b.x, dy = v.root.y - b.y,
        angle = Math.atan2(dy, dx), size = Math.max(15, v.sourceHeight * .32),
        arcRadius = Math.min(10, Math.hypot(dx, dy) * .18);
      for (let i = 0; i < 6; i++) {
        const t = Math.max(0, Math.min(1, (b.age - .035 - i * .018) / .40));
        if (b.age < .035 + i * .018) continue;
        const arc = Math.sin(t * Math.PI) * (i % 2 ? -arcRadius : arcRadius),
          x = b.x + dx * t - Math.sin(angle) * arc,
          y = b.y + dy * t + Math.cos(angle) * arc;
        this.stamp(ctx, "orb", "green", x, y, size, 0, t > .9 ? (1 - t) * 10 : 1);
        if (b.id === "drainingkiss")
          this.stamp(ctx, "heart", "pink", x, y - size * .6, size * .8, 0, 1 - t);
      }
    }
  }
};
