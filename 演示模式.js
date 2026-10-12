"use strict";
// Recording policy only. Both actors use PoightBalanceTest and the live enemy AI.
window.PoightDemo = class {
  constructor(args) {
    const integer = (key, fallback, min, max) => {
      const value = Number(args.get(key));
      return args.has(key) && Number.isInteger(value) && value >= min && value <= max
        ? value
        : fallback;
    };
    this.enabled = args.get("demo") === "1";
    this.width = integer("w", 1920, 1, 8192);
    this.height = integer("h", 1080, 1, 8192);
    if (this.width * this.height > 16777216) {
      this.width = 1920;
      this.height = 1080;
    }
    this.fps = integer("fps", 0, 1, 240);
    this.seed = integer("seed", 1357911, -2147483648, 0xffffffff) >>> 0;
    const speed = Number(args.get("speed"));
    this.speed = args.has("speed") && speed >= 0.25 && speed <= 1 ? speed : 1;
    this.hideHUD = args.get("hud") === "0";
    this.bars = !this.hideHUD && args.get("bars") !== "0";
    this.loop = args.get("loop") !== "0";
    this.vs = args.get("vs") === "1";
    this.paused = args.get("paused") === "1";
    this.ready = false;
    this.frame = 0;
    this.round = 1;
    this.wait = 0;
    this.zoom = null;
    this.cameraMode = 2; // MX: default to the two-actor midpoint in both orientations.
    this.baseTitle = `${document.title} ${location.search}`;
    if (this.enabled) {
      document.documentElement.dataset.demo = "true";
      document.documentElement.dataset.demoHud = this.hideHUD ? "hidden" : "visible";
    }
  }
  profile(args, profile, byID, scenes, tiers, moves) {
    for (const [side, key, fallback] of [["player", "p1", 25], ["enemy", "p2", 6]]) {
      const id = Number(args.get(key));
      profile[side] = args.has(key) && byID.has(id) ? id : fallback;
      profile[side + "Moves"] = [...byID.get(profile[side]).defaultMoves];
    }
    profile.map = scenes.has(args.get("map")) ? args.get("map") : "arena-formal";
    profile.tier = tiers.some(t => t.id === args.get("tier")) ? args.get("tier") : "ultra";
    const list = (args.get("moves") || "").split(",");
    if (list.length >= 1 && list.length <= 4 && new Set(list).size === list.length &&
        list.every(id => moves[id] && byID.get(profile.player).learnset.includes(id))) {
      profile.playerMoves = list;
    }
    profile.shake = false;
    profile.holdAim = false;
  }
  // Only rank already legal, in-range choices. No changes to damage, resources,
  // reaction/poll/attack-gap, aiming, dodging or any difficulty coefficient.
  moveWeight(move, value) {
    if (!this.enabled || !Number.isFinite(value)) return value;
    if (!(move.damage > 0) || ["heal", "guard", "buff"].includes(move.kind)) return value;
    const spectacle = (move.hero || move.batch2 || move.r3 ? 18 : 0) +
      Math.min(24, (move.radius || 0) * 0.5) +
      (["beam", "nova", "zone", "rush"].includes(move.kind) ? 14 : 0);
    return value + move.damage * 0.6 + spectacle;
  }
  title() {
    if (this.enabled) document.title = this.baseTitle + (this.fps ? ` [frame=${this.frame}]` : "");
  }
  reset() {
    this.frame = 0;
    this.round = 1;
    this.wait = 0;
    this.zoom = null;
    this.title();
  }
  tick(api) {
    const dt = this.speed / (this.fps || 120);
    const phase = api.phase();
    if (phase === "versus") {
      this.wait += dt;
      if (this.wait + 1e-9 >= 1.6) {
        this.wait = 0;
        api.finishVS();
      }
    } else if (phase === "over") {
      if (this.loop) {
        this.wait += dt;
        if (this.wait + 1e-9 >= 3) {
          const frame = this.frame, round = this.round + 1;
          api.reset();
          this.frame = frame;
          this.round = round;
        }
      }
    } else {
      // Keep live collision/effects at <= 1/120s even with a low recording fps.
      const steps = Math.max(1, Math.ceil(dt * 120));
      for (let i = 0; i < steps; i++) api.update(dt / steps);
    }
    this.frame++;
    this.title();
  }
  key(event, api) {
    if (!this.enabled) return false;
    if (["Space", "KeyS", "KeyC"].includes(event.code)) {
      event.preventDefault();
      if (!event.repeat) {
        if (event.code === "Space") this.paused ? api.resume() : api.pause();
        if (event.code === "KeyS") this.speed = this.speed === 0.5 ? 1 : 0.5;
        if (event.code === "KeyC") this.cameraMode = (this.cameraMode + 1) % 3;
      }
    }
    return true;
  }
  fit(canvas) {
    const scale = Math.min(1, innerWidth / this.width, innerHeight / this.height);
    canvas.style.width = `${this.width * scale}px`;
    canvas.style.height = `${this.height * scale}px`;
    if (canvas.width !== this.width) canvas.width = this.width;
    if (canvas.height !== this.height) canvas.height = this.height;
  }
  // Nine-slice extension of the arena's own edge pixels. This is presentation
  // padding only: world dimensions, collision, bodies and AI remain untouched.
  drawGround(ctx, ground, x, y, width, height) {
    const slices = (start, span, extent) => {
      const end = start + span, parts = [];
      if (start < 0) parts.push([0, 1, 0, Math.min(end, 0) - start]);
      const lo = Math.max(0, start), hi = Math.min(extent, end);
      if (hi > lo) parts.push([lo, hi - lo, lo - start, hi - lo]);
      if (end > extent)
        parts.push([extent - 1, 1, Math.max(extent, start) - start, end - Math.max(extent, start)]);
      return parts;
    };
    for (const [sx, sw, dx, dw] of slices(x, width, ground.width))
      for (const [sy, sh, dy, dh] of slices(y, height, ground.height))
        if (dw > 0 && dh > 0) ctx.drawImage(ground, sx, sy, sw, sh, dx, dy, dw, dh);
  }
  camera(points, previous, world, dt, snap = false) {
    const minX = Math.min(...points.map(p => p.x)), maxX = Math.max(...points.map(p => p.x)),
      minY = Math.min(...points.map(p => p.y)), maxY = Math.max(...points.map(p => p.y)),
      dx = maxX - minX, dy = maxY - minY,
      clamp = (v, a, b) => Math.max(a, Math.min(b, v)),
      minZoom = Math.min(0.05, this.width * 0.68 / (world.width + 160),
        this.height * 0.68 / (world.height + 160)),
      target = clamp(Math.min(this.width * 0.68 / (dx + 160),
        this.height * 0.68 / (dy + 160)), minZoom, 4),
      k = snap || this.zoom === null ? 1 : 1 - Math.exp(-6 * dt);
    this.zoom = this.zoom === null ? target : this.zoom + (target - this.zoom) * k;
    this.zoom = clamp(Math.min(this.zoom, this.width * 0.76 / Math.max(1, dx),
      this.height * 0.76 / Math.max(1, dy)), minZoom, 4);
    const width = this.width / this.zoom, height = this.height / this.zoom;
    // Portrait always tracks the midpoint; landscape C switches focal actor.
    const focal = this.height > this.width || this.cameraMode === 2 ? points :
      points.slice(this.cameraMode * 2, this.cameraMode * 2 + 2);
    const tx = focal.reduce((sum, p) => sum + p.x, 0) / focal.length - width / 2,
      ty = focal.reduce((sum, p) => sum + p.y, 0) / focal.length - height / 2;
    // Clamp normal framing inside the world. An oversized portrait view centers
    // the smaller world in edge-texture padding rather than exposing the clear color.
    const bound = (value, span, extent) => span > extent
      ? (extent - span) / 2 : clamp(value, 0, extent - span);
    return { width, height, scale: this.zoom,
      x: bound(clamp(previous.x + (tx - previous.x) * k,
        maxX - width * 0.9, minX - width * 0.1), width, world.width),
      y: bound(clamp(previous.y + (ty - previous.y) * k,
        maxY - height * 0.9, minY - height * 0.1), height, world.height) };
  }
};
