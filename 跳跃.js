"use strict";
window.PoightJump = class {
  static parameters = Object.freeze({
    duration: 0.45,
    edge: 0.06,
    cost: 12,
    recovery: 0.15,
    cooldown: 0.6,
    speed: 0.7,
    height: 0.8,
  });
  constructor(api) {
    this.api = api;
    this.dust = [];
  }
  clear(p) {
    p.jump = null;
    p.jumpHeight = p.landLeft = p.jumpCool = 0;
  }
  reset() {
    this.dust = [];
  }
  blocked(p) {
    return !!(p?.jump || p?.landLeft > 1e-7);
  }
  airborne(p) {
    const c = window.PoightJump.parameters;
    return !!(p?.jump && p.jump.age >= c.edge - 1e-7 && p.jump.age < c.duration - c.edge - 1e-7);
  }
  canHit(p, move) {
    return !this.airborne(p) || move.hitsAirborne !== false;
  }
  start(p) {
    const a = this.api,
      c = window.PoightJump.parameters;
    if (
      !p ||
      !a.enabled(p) ||
      this.blocked(p) ||
      p.jumpCool > 1e-7 ||
      p.hp <= 0 ||
      p.attack ||
      p.dash ||
      p.hurt > 0 ||
      p.diveLeft > 0 ||
      !a.spend(p, c.cost)
    )
      return false;
    // Body.top measures the visible top relative to the footprint; +14 reaches the sprite foot.
    const peak = Math.max(1, (p.char.body?.top ?? 41) + 14) * c.height;
    p.jump = { age: 0, peak };
    p.jumpHeight = 0;
    p.jumps = (p.jumps || 0) + 1;
    a.reveal(p);
    a.cancel(p);
    this.puff(p);
    return true;
  }
  tick(p, dt) {
    const c = window.PoightJump.parameters;
    p.landLeft = Math.max(0, (p.landLeft || 0) - dt);
    p.jumpCool = Math.max(0, (p.jumpCool || 0) - dt);
    if (!p.jump) return;
    p.jump.age += dt;
    const t = Math.min(1, p.jump.age / c.duration);
    p.jumpHeight = 4 * t * (1 - t) * p.jump.peak;
    if (p.jump.age >= c.duration - 1e-7) {
      const overflow = Math.max(0, p.jump.age - c.duration);
      p.jump = null;
      p.jumpHeight = 0;
      p.landLeft = Math.max(0, c.recovery - overflow);
      p.jumpCool = Math.max(0, c.cooldown - overflow);
      this.api.cancel(p);
      this.puff(p);
    }
  }
  speed(p) {
    return p.jump ? window.PoightJump.parameters.speed : 1;
  }
  shadow(p) {
    return 1 - (0.4 * (p.jumpHeight || 0)) / (p.jump?.peak || 1);
  }
  puff(p) {
    this.dust.push({ x: p.x, y: p.y + 12, age: 0 });
  }
  step(dt) {
    for (const d of this.dust) d.age += dt;
    this.dust = this.dust.filter((d) => d.age < 0.24);
  }
  draw(ctx) {
    ctx.save();
    ctx.fillStyle = "#dfceb0";
    for (const d of this.dust) {
      const t = d.age / 0.24;
      ctx.globalAlpha = (1 - t) * 0.65;
      for (let i = 0; i < 7; i++) {
        const a = (i * Math.PI * 2) / 7;
        ctx.beginPath();
        ctx.ellipse(
          d.x + Math.cos(a) * (7 + t * 17),
          d.y + Math.sin(a) * (3 + t * 6) - t * 3,
          3 + t * 2,
          2,
          0,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
    }
    ctx.restore();
  }
  warning(shape, target, move) {
    return { ...shape, jumpSafe: this.airborne(target) && move.hitsAirborne === false };
  }
  // Shared telegraph geometry also covers melee, rush and generated ground/landing attacks.
  danger(p, source, tier, shapes, states, moves, bodies, clearLine) {
    const candidates = [];
    if (source.attack?.age >= tier.reaction)
      for (const s of shapes.filter((s) => s.id === source.attack.id && !s.aiming)) {
        if (s.support || s.remaining < 0.06 || s.remaining > 0.34) continue;
        let inside = false;
        if (s.rays)
          inside = s.rays.some((r) =>
            Number.isFinite(
              bodies.segment(
                p,
                r.x,
                r.y,
                r.x + Math.cos(r.angle) * r.length,
                r.y + Math.sin(r.angle) * r.length,
                s.radius,
              ),
            ),
          );
        else if (s.shape === "grid") inside = bodies.rect(p, s.x - 72, s.y - 72, 144, 144);
        else if (s.points) {
          const dx = p.x - source.x,
            dy = p.y - source.y;
          const dist = Math.hypot(dx, dy);
          inside =
            dist <= bodies.meleeRange(p, s.length, dx, dy, source) &&
            (s.shape === "ring" ||
              !dist ||
              (dx * Math.cos(s.angle) + dy * Math.sin(s.angle)) / dist > 0.42);
        } else inside = bodies.circle(p, s.x, s.y, s.radius);
        if (inside) candidates.push(moves[s.id]);
      }
    for (const e of states)
      if (
        e.owner === source &&
        !e.landed &&
        e.age >= tier.reaction &&
        ["lob", "target", "propagate"].includes(e.mode) &&
        e.life - e.age >= 0.06 &&
        e.life - e.age <= 0.34 &&
        bodies.circle(p, e.ex, e.ey, e.radius)
      )
        candidates.push(e.m);
    const m = candidates.find((m) => m.hitsAirborne === false);
    if (!m || !clearLine(source.x, source.y, p.x, p.y, 3)) return null;
    const dx = p.x - source.x,
      dy = p.y - source.y,
      d = Math.hypot(dx, dy) || 1;
    return { dx: -dy / d || 1, dy: dx / d, m };
  }
  tryAI(p, danger, tier, random) {
    return danger.m?.hitsAirborne === false && random() < 0.5 + tier.dodge * 0.25 && this.start(p);
  }
  bind(button, start) {
    Object.assign(button.style, {
      position: "fixed",
      left: "108px",
      bottom: "104px",
      zIndex: "12",
      minWidth: "48px",
      minHeight: "44px",
      borderRadius: "50%",
      touchAction: "none",
      pointerEvents: "auto",
    });
    button.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      start();
    });
    button.addEventListener("click", (e) => {
      if (e.detail === 0) start();
    });
  }
  snapshot(p) {
    return {
      jumping: !!p.jump,
      airborne: this.airborne(p),
      jumpHeight: p.jumpHeight || 0,
      jumpAge: p.jump?.age ?? null,
      jumpPeak: p.jump?.peak ?? 0,
      landing: p.landLeft || 0,
      jumpCooldown: p.jumpCool || 0,
      jumps: p.jumps || 0,
      shadowScale: this.shadow(p),
    };
  }
};
