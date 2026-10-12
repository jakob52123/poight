/* Pixel-art rush and directional impact effects. Drawing only; no game state. */
(function (root) {
  'use strict';

  const TAU = Math.PI * 2;
  const clamp01 = v => Math.max(0, Math.min(1, v));
  const smooth = t => { t = clamp01(t); return t * t * (3 - 2 * t); };
  const fract = n => n - Math.floor(n);
  function rand(seed, index) {
    return fract(Math.sin((Number(seed) || 0) * 127.1 + index * 311.7) * 43758.5453);
  }
  function polygon(ctx, points, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(Math.round(points[0]), Math.round(points[1]));
    for (let i = 2; i < points.length; i += 2) ctx.lineTo(Math.round(points[i]), Math.round(points[i + 1]));
    ctx.closePath();
    ctx.fill();
  }
  function feather(ctx, x, y, angle, length, width, color) {
    const ca = Math.cos(angle), sa = Math.sin(angle), px = -sa, py = ca;
    polygon(ctx, [x, y, x + ca * length * .58 + px * width,
      y + sa * length * .58 + py * width, x + ca * length,
      y + sa * length, x + ca * length * .58 - px * width,
      y + sa * length * .58 - py * width], color);
  }

  function drawRush(ctx, opt) {
    const x = opt.x, y = opt.y, angle = opt.angle || 0;
    const age = Math.max(0, opt.age || 0), windup = Math.max(.001, opt.windup || .001);
    const duration = Math.max(windup + .001, opt.duration || windup + .2);
    const dash = clamp01((age - windup) / (duration - windup));
    const charging = age < windup;
    const strength = charging ? smooth(age / windup) : 1 - dash * .42;
    const seed = opt.seed || 0;
    ctx.save();
    ctx.translate(Math.round(x), Math.round(y));
    ctx.rotate(angle);
    ctx.globalAlpha = charging ? .58 + strength * .42 : Math.max(.18, 1 - dash * .65);

    if (charging) {
      // Two angular blue-white wings gather behind the fighter.
      const spread = 7 + strength * 15, reach = 13 + strength * 13;
      polygon(ctx, [-5, -2, -reach, -spread - 5, -reach + 4, -spread + 2, -2, -5, 3, -3], '#48aeea');
      polygon(ctx, [-5, 2, -reach, spread + 5, -reach + 4, spread - 2, -2, 5, 3, 3], '#48aeea');
      polygon(ctx, [-3, -2, -reach + 4, -spread + 1, -11, -2, 2, -1], '#e7faff');
      polygon(ctx, [-3, 2, -reach + 4, spread - 1, -11, 2, 2, 1], '#e7faff');
      // A compact, stable pixel core; no full-screen flashes.
      ctx.fillStyle = '#dffaff';
      ctx.fillRect(-2, -2, 5, 4);
      ctx.fillStyle = '#72dcff';
      ctx.fillRect(-7, -1, 4, 2);
      for (let i = 0; i < 3; i++) {
        const side = i % 2 ? 1 : -1;
        const xx = -10 - i * 5;
        const yy = side * (4 + rand(seed, i) * (3 + strength * 5));
        ctx.fillStyle = i === 0 ? '#c8f5ff' : '#70cfff';
        ctx.fillRect(Math.round(xx), Math.round(yy), 3, 2);
      }
    } else {
      // Broad swept wings and a short, tapered feather wake.
      const spread = 12 + 11 * (1 - dash), reach = 30 + 10 * (1 - dash);
      polygon(ctx, [-3, -3, -reach, -spread - 7, -reach + 7, -spread + 3, -13, -4, 2, -2], '#248bd0');
      polygon(ctx, [-3, 3, -reach, spread + 7, -reach + 7, spread - 3, -13, 4, 2, 2], '#248bd0');
      polygon(ctx, [-6, -2, -reach + 4, -spread + 2, -18, -3, 3, -1], '#b8efff');
      polygon(ctx, [-6, 2, -reach + 4, spread - 2, -18, 3, 3, 1], '#b8efff');
      // Keep the trail bounded to a dozen small marks per frame.
      for (let i = 0; i < 7; i++) {
        const back = 12 + i * 5 + rand(seed, i) * 5;
        const side = (rand(seed, i + 20) - .5) * (9 + i * 1.4);
        const size = i < 2 ? 4 : 3;
        ctx.fillStyle = i % 3 === 0 ? '#e9fbff' : (i % 2 ? '#61caff' : '#329ee2');
        ctx.fillRect(Math.round(-back), Math.round(side), size, size - 1);
      }
      ctx.fillStyle = '#f4ffff';
      ctx.fillRect(-3, -2, 8, 4);
      ctx.fillStyle = '#7de1ff';
      ctx.fillRect(3, -1, 5, 2);
    }
    ctx.restore();
  }

  function drawImpact(ctx, opt) {
    const x = opt.x, y = opt.y, angle = opt.angle || 0;
    const age = Math.max(0, opt.age || 0), life = Math.max(.001, opt.life || .001);
    const t = clamp01(age / life), fade = 1 - t, seed = opt.seed || 0;
    ctx.save();
    ctx.translate(Math.round(x), Math.round(y));
    ctx.rotate(angle);
    ctx.globalAlpha = fade;
    // Directional starburst with long forward lances and shorter rear shards.
    const reach = 17 + 12 * t;
    polygon(ctx, [4, -4, reach, -2, reach + 5, 0, reach, 2, 4, 4, -4, 3, -8, 0], '#45b8eb');
    polygon(ctx, [5, -2, reach - 2, -1, reach + 1, 0, reach - 2, 1, 5, 2, 0, 0], '#f2ffff');
    for (let i = 0; i < 8; i++) {
      const a = TAU * i / 8 + (rand(seed, i) - .5) * .22;
      const dist = 7 + t * 13 + rand(seed, i + 30) * 6;
      const len = 5 + rand(seed, i + 50) * 7;
      feather(ctx, Math.round(Math.cos(a) * dist), Math.round(Math.sin(a) * dist), a,
        len * fade + 2, 1.5 + rand(seed, i + 70) * 1.5, i % 3 ? '#64cfff' : '#e8fbff');
    }
    ctx.fillStyle = '#f8ffff';
    ctx.fillRect(-3, -3, 7, 6);
    ctx.fillStyle = '#a9edff';
    ctx.fillRect(-6, -1, 3, 2);
    ctx.restore();
  }

  root.PocketFX = { drawRush, drawImpact };
})(typeof window !== 'undefined' ? window : globalThis);
