/* Candidate ground-plane body model. Ellipse cores approximate silhouettes;
 * these are not pixel-perfect anatomy or jump/height volumes. No RNG evasion.
 */
"use strict";
window.PoightBodies = Object.freeze({
  row(a) {
    return ((Math.round((a - Math.PI / 2) / (Math.PI / 4)) % 8) + 8) % 8;
  },
  shape(p) {
    const q = p.char?.body?.hurtByDirection?.[this.row(p.a || 0)];
    return { rx: q?.[0] ?? 18, ry: q?.[1] ?? 18 };
  },
  foot(p) {
    return p.char?.body?.moveRadius ?? 18;
  },
  reach(p, dx, dy) {
    const s = this.shape(p),
      n = Math.hypot(dx, dy);
    return n > 1e-9 ? 1 / Math.hypot(dx / n / s.rx, dy / n / s.ry) : Math.min(s.rx, s.ry);
  },
  meleeRange(p, range, dx, dy, source) {
    return Math.max(
      1,
      range - 18 + this.reach(p, dx, dy) + (source ? this.reach(source, dx, dy) - 18 : 0),
    );
  },
  segment(p, ax, ay, bx, by, pad = 0) {
    const s = this.shape(p),
      rx = s.rx + Math.max(0, pad),
      ry = s.ry + Math.max(0, pad);
    const x = (ax - p.x) / rx,
      y = (ay - p.y) / ry,
      dx = (bx - ax) / rx,
      dy = (by - ay) / ry,
      c = x * x + y * y - 1;
    if (c <= 0) return 0;
    const a = dx * dx + dy * dy;
    if (a < 1e-18) return Infinity;
    const b = 2 * (x * dx + y * dy),
      disc = b * b - 4 * a * c;
    if (disc < 0) return Infinity;
    const t = (-b - Math.sqrt(Math.max(0, disc))) / (2 * a);
    return t >= 0 && t <= 1 ? t : Infinity;
  },
  circle(p, x, y, r) {
    return Number.isFinite(this.segment(p, x, y, x, y, r));
  },
  rect(p, x, y, w, h) {
    const s = this.shape(p),
      cx = Math.max(x, Math.min(x + w, p.x)),
      cy = Math.max(y, Math.min(y + h, p.y));
    return ((cx - p.x) / s.rx) ** 2 + ((cy - p.y) / s.ry) ** 2 <= 1;
  },
});
