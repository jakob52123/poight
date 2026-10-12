"use strict";
// Wall-clock feedback; no actor/projectile/AI clocks advance during hitstop.
window.PoightFeel = class {
  constructor() {
    this.reset();
  }
  reset() {
    this.remaining = 0;
    this.duration = 0;
    this.shakeLeft = 0;
    this.amplitude = 0;
    this.offset = { x: 0, y: 0 };
    this.pendingDash = null;
  }
  bufferDash(dx, dy) {
    if (this.remaining <= 0) return false;
    this.pendingDash = { dx, dy };
    return true;
  }
  flushDash(cast) {
    const pending = this.pendingDash;
    this.pendingDash = null;
    if (pending) cast(pending.dx, pending.dy);
  }
  hit(amount, effective, shake) {
    const heavy = amount >= 25 || effective >= 2;
    this.duration = Math.max(this.remaining, heavy ? 0.1 : 0.06);
    this.remaining = this.duration;
    this.amplitude = Math.max(this.amplitude, heavy ? 6 : 3);
    this.shakeLeft = 0.15;
    this.refresh(shake);
  }
  refresh(enabled) {
    const gain = enabled ? (this.amplitude * this.shakeLeft) / 0.15 : 0;
    const angle = (0.15 - this.shakeLeft) * 95 + Math.PI / 4;
    this.offset = { x: Math.cos(angle) * gain, y: Math.sin(angle) * gain };
  }
  tick(dt, enabled) {
    const frozen = Math.min(dt, this.remaining);
    this.remaining = Math.max(0, this.remaining - dt);
    this.shakeLeft = Math.max(0, this.shakeLeft - dt);
    if (!this.shakeLeft) this.amplitude = 0;
    this.refresh(enabled);
    return dt - frozen;
  }
  knockback(p, amount, dx, dy) {
    // Compressed body size, not raw mass: small bodies travel about twice as far.
    const size = Math.max(26, p.char.body?.nominalSize || 0);
    const distance = Math.min(40, ((8 + amount * 0.65) * 48) / size);
    const length = Math.hypot(dx, dy) || 1;
    // Replace rather than stack impulses: the remaining displacement cannot exceed 40px.
    p.vx = (dx / length) * distance * 13;
    p.vy = (dy / length) * distance * 13;
    return distance;
  }
  move(p, dt, translate) {
    const decay = Math.exp(-13 * dt);
    translate(p, (p.vx * (1 - decay)) / 13, (p.vy * (1 - decay)) / 13);
    p.vx *= decay;
    p.vy *= decay;
  }
  snapshot() {
    return {
      remaining: this.remaining,
      duration: this.duration,
      shakeLeft: this.shakeLeft,
      offset: { ...this.offset },
    };
  }
};
