"use strict";
window.PoightAim = class {
  constructor(api) {
    this.api = api;
    this.clock = 0;
    this.hold = null;
    this.mouse = null;
    this.rightHeld = false;
  }
  cancel() {
    const had = !!this.hold;
    this.hold = null;
    return had;
  }
  press(slot, pointer = null) {
    const a = this.api;
    const enabled = a.enabled();
    if (!pointer && (!this.rightHeld || !enabled)) {
      this.cancel();
      a.queue(slot, this.quickDirection(slot));
      return false;
    }
    if (!a.canAim(slot)) {
      a.rejectAim?.(slot);
      this.cancel();
      // Touch/pen requests, including busy-state buffers, belong to pointerup.
      // Keep this in hold so blur, death and round reset cancel it normally.
      if (pointer) this.hold = {
        slot, pointer, age: 0, angle: this.quickDirection(slot), active: false,
        deferred: true, dragged: false, aimEnabled: false,
      };
      else a.queue(slot, this.quickDirection(slot));
      return false;
    }
    a.prepare?.(slot);
    this.hold = {
      slot, age: 0, active: !pointer, angle: 0, pointer, drag: null,
      dragged: false, aimEnabled: enabled,
    };
    this.hold.angle = this.direction();
    return true;
  }
  quickDirection(slot) {
    const v = this.api.vector();
    return v.x || v.y ? Math.atan2(v.y, v.x) : this.api.auto(slot);
  }
  direction() {
    const a = this.api,
      h = this.hold,
      p = a.player();
    if (h.pointer && h.drag && Math.hypot(h.drag.x, h.drag.y) > 12)
      return Math.atan2(h.drag.y, h.drag.x);
    if (!h.pointer && this.mouse && this.clock - this.mouse.time <= 1) {
      const at = a.worldPoint(this.mouse.x, this.mouse.y);
      return Math.atan2(at.y - p.y, at.x - p.x);
    }
    const v = a.vector();
    return v.x || v.y ? Math.atan2(v.y, v.x) : a.auto(h.slot);
  }
  tick(dt) {
    this.clock += dt;
    const h = this.hold;
    if (!h || h.deferred) return;
    if (!this.api.canAim(h.slot)) {
      this.api.rejectAim?.(h.slot);
      this.cancel();
      return;
    }
    h.age += dt;
    h.active = h.aimEnabled && (!h.pointer || !!(h.drag && Math.hypot(h.drag.x, h.drag.y) > 12));
    h.dragged ||= h.active;
    h.angle = this.direction();
  }
  release(slot) {
    const h = this.hold;
    if (!h || h.slot !== slot) return;
    const angle = h.active ? this.direction() : this.quickDirection(slot);
    const cancelled = h.pointer && h.dragged && !h.active;
    this.hold = null;
    if (!cancelled) this.api.queue(slot, angle);
  }
  bind(button, slot) {
    let pointer = null;
    button.style.touchAction = "none";
    button.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      this.api.start();
      if (e.pointerType !== "touch" && e.pointerType !== "pen") {
        this.press(slot);
        this.api.focus();
        return;
      }
      pointer = e.pointerId;
      button.setPointerCapture(pointer);
      this.press(slot, { x: e.clientX, y: e.clientY });
    });
    button.addEventListener("pointermove", (e) => {
      if (e.pointerId !== pointer || !this.hold?.pointer) return;
      this.hold.drag = {
        x: e.clientX - this.hold.pointer.x,
        y: e.clientY - this.hold.pointer.y,
      };
      this.hold.active = this.hold.aimEnabled && Math.hypot(this.hold.drag.x, this.hold.drag.y) > 12;
      this.hold.dragged ||= this.hold.active;
    });
    button.addEventListener("pointerup", (e) => {
      if (e.pointerId !== pointer) return;
      e.preventDefault();
      this.release(slot);
      pointer = null;
      this.api.focus();
    });
    for (const event of ["pointercancel", "lostpointercapture"])
      button.addEventListener(event, () => {
        if (pointer !== null) this.cancel();
        pointer = null;
      });
    // Keyboard/assistive activation still supports a single automatic cast.
    button.addEventListener("click", (e) => {
      if (e.detail === 0) this.api.queue(slot);
    });
  }
  snapshot() {
    const h = this.hold;
    return h ? { slot: h.slot, active: h.active, age: h.age, angle: h.angle } : null;
  }
};

window.PoightTelegraph = {
  landing(p, m, angle, target, api) {
    const distance = Math.min(m.range, Math.hypot(target.x - p.x, target.y - p.y));
    const end = api.rayEnd(p.x, p.y, angle, distance, 5);
    return api.generated.has(m.id)
      ? end
      : {
          x: Math.max(api.bounds.left, Math.min(api.bounds.right, end.x)),
          y: Math.max(api.bounds.top, Math.min(api.bounds.bottom, end.y)),
        };
  },
  shape(p, m, angle, target, api) {
    const native = api.generated.has(m.id),
      B = api.bodies;
    const base = { id: m.id, kind: m.kind, x: p.x, y: p.y, angle, length: m.range || 0 };
    // Generated Agility is a real forward displacement, despite its data kind being buff.
    const movement = native && m.id === "agility";
    if (["shot", "beam", "rush", "fan"].includes(m.kind) || movement) {
      const projectile = m.kind === "shot" || m.kind === "fan" || (native && m.kind === "beam");
      const count = m.kind === "fan" ? m.count || 3 : 1;
      const rays = Array.from({ length: count }, (_, i) => {
        const a = angle + (i - (count - 1) / 2) * 0.16;
        const origin = projectile
          ? native
            ? api.origin(p, m, a)
            : {
                x: p.x + Math.cos(a) * 24,
                y: p.y + Math.sin(a) * 24,
              }
          : p;
        return { x: origin.x, y: origin.y, angle: a, length: m.range };
      });
      return {
        ...base,
        shape: m.kind === "fan" ? "fan" : "strip",
        rays,
        halfAngle: (count - 1) * 0.08,
        radius: projectile
          ? m.radius
          : movement
            ? B.foot(p)
            : m.kind === "rush"
              ? B.reach(p, -Math.sin(angle), Math.cos(angle)) + 4
              : 6,
        projectile,
      };
    }
    if (m.kind === "zone")
      return {
        ...base,
        ...(m.id === "thunder" && p.attack?.id === m.id
          ? p.attack.targetPoint : this.landing(p, m, angle, target, api)),
        shape: "circle",
        radius: native ? Math.min(m.radius || 50, 65) : m.radius,
      };
    if (m.kind === "nova" && api.animationEnabled !== false)
      return { ...base, shape: "ground-ring", radius: m.id === "earthquake" && native
        ? Math.hypot(72, 72) : m.range };
    if (m.id === "earthquake" && native) return { ...base, shape: "grid", width: 144, height: 144 };
    if (m.kind === "melee" || m.kind === "spin") {
      const halfAngle = m.kind === "spin" ? Math.PI : Math.acos(0.42);
      const points = Array.from({ length: 65 }, (_, i) => {
        const a = angle - halfAngle + (i / 64) * halfAngle * 2;
        const radius = B.meleeRange(target, m.range, Math.cos(a), Math.sin(a), p);
        return { x: p.x + Math.cos(a) * radius, y: p.y + Math.sin(a) * radius };
      });
      return { ...base, shape: m.kind === "spin" ? "ring" : "arc", halfAngle, points };
    }
    return {
      ...base,
      shape: "ring",
      radius: m.kind === "nova" ? m.range : Math.max(B.shape(p).rx, B.shape(p).ry) + 8,
      support: ["heal", "guard", "buff"].includes(m.kind),
    };
  },
  draw(ctx, shape, player, remaining, aiming = false, headBoxes = []) {
    const s = shape;
    ctx.save();
    ctx.fillStyle = player ? "#318eff" : "#ff414f";
    ctx.strokeStyle = remaining <= 0.1 && !aiming ? "#ffffff" : ctx.fillStyle;
    ctx.lineWidth = aiming ? 2.5 : 2;
    if (s.jumpSafe && !player) ctx.strokeStyle = "#a6adb5";
    ctx.setLineDash(s.jumpSafe && !player ? [6, 4] : []);
    if (s.shape === "ground-ring") {
      ctx.fillStyle = "#b98a38";
      ctx.strokeStyle = "#d6af62";
      ctx.setLineDash([7, 5]);
    }
    ctx.beginPath();
    if (s.shape === "strip") {
      const r = s.rays[0],
        ux = Math.cos(r.angle),
        uy = Math.sin(r.angle);
      ctx.moveTo(r.x - uy * s.radius, r.y + ux * s.radius);
      ctx.lineTo(r.x + ux * r.length - uy * s.radius, r.y + uy * r.length + ux * s.radius);
      ctx.lineTo(r.x + ux * r.length + uy * s.radius, r.y + uy * r.length - ux * s.radius);
      ctx.lineTo(r.x + uy * s.radius, r.y - ux * s.radius);
      ctx.closePath();
    } else if (s.shape === "fan") {
      const reach = Math.max(...s.rays.map((r) => Math.hypot(r.x - s.x, r.y - s.y)));
      ctx.moveTo(s.x, s.y);
      ctx.arc(s.x, s.y, s.length + reach, s.angle - s.halfAngle, s.angle + s.halfAngle);
      ctx.closePath();
    } else if (s.points) {
      if (s.shape === "arc") ctx.moveTo(s.x, s.y);
      else ctx.moveTo(s.points[0].x, s.points[0].y);
      for (const point of s.points) ctx.lineTo(point.x, point.y);
      ctx.closePath();
    } else if (s.shape === "grid") ctx.rect(s.x - 72, s.y - 72, s.width, s.height);
    else ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
    ctx.globalAlpha = s.shape === "ground-ring" ? 0.14 : 0.28;
    ctx.fill();
    ctx.globalAlpha = 0.9;
    ctx.stroke();
    if (s.shape === "grid") {
      ctx.beginPath();
      for (const n of [-24, 24]) {
        ctx.moveTo(s.x + n, s.y - 72);
        ctx.lineTo(s.x + n, s.y + 72);
        ctx.moveTo(s.x - 72, s.y + n);
        ctx.lineTo(s.x + 72, s.y + n);
      }
      ctx.stroke();
    }
    if (s.jumpSafe && !player) {
      ctx.fillStyle = "#dce0e4";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const text = "这招跳得过",
        metrics = ctx.measureText(text),
        width = Math.max(metrics.width, metrics.actualBoundingBoxLeft + metrics.actualBoundingBoxRight) + 4,
        height = Math.max(16, metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent + 4);
      let y = s.y + 40;
      // Place below the warning origin, then clear every actor's head-label envelope.
      while (headBoxes.some((b) =>
        s.x - width / 2 < b.x + b.width && s.x + width / 2 > b.x &&
        y - height / 2 < b.y + b.height && y + height / 2 > b.y
      )) y += height + 4;
      ctx.fillText(text, s.x, y);
    }
    ctx.restore();
  },
};
