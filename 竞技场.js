/* Expanded arenas reuse the world's swept movement and bounded A* implementation. */
"use strict";
window.PoightArena = class PoightArena extends window.PoightWorld {
  static shakeFrame(ctx, canvas, camera, width, height, offset, screen) {
    if (!offset.x && !offset.y) return;
    const dx = offset.x * width / screen.width,
      dy = offset.y * height / screen.height,
      zoom = 1 + Math.max(Math.abs(dx) / (width / 2), Math.abs(dy) / (height / 2)) + 0.002;
    // The source canvas now contains a cropped viewport, not the whole arena.
    // Cover that exact screen rectangle at every shake phase, without exposing blank edges.
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, width, height);
    ctx.clip();
    ctx.translate(width / 2 + dx, height / 2 + dy);
    ctx.scale(zoom, zoom);
    ctx.translate(-width / 2, -height / 2);
    ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, width, height);
    ctx.restore();
  }
  static async load(scene, loader) {
    const image = await loader(scene.groundSrc);
    return new PoightArena(scene, image);
  }
  constructor(scene, image) {
    const cellSize = 10,
      columns = Math.ceil(scene.world.width / cellSize),
      rows = Math.ceil(scene.world.height / cellSize),
      empty = btoa("\0".repeat(columns * rows));
    super(
      {
        ...scene,
        cellSize,
        columns,
        rows,
        walkB64: empty,
        elevationB64: empty,
        behaviorB64: empty,
        areas: [],
        chunks: [{ x: 0, y: 0, w: scene.world.width, h: scene.world.height,
          groundSrc: scene.groundSrc }],
      },
      new Map([[scene.groundSrc, image]]),
    );
    const b = scene.bounds, { width: w, height: h } = scene.world;
    // Virtual walls clip all attacks at the battle boundary, not merely the image edge.
    this.walls = [
      { x: -w, y: -h, w: w * 3, h: b.top + h },
      { x: -w, y: b.bottom, w: w * 3, h: h * 2 },
      { x: -w, y: -h, w: b.left + w, h: h * 3 },
      { x: b.right, y: -h, w: w * 2, h: h * 3 },
    ];
    for (let row = 0; row < rows; row++)
      for (let col = 0; col < columns; col++)
        this.walk[row * columns + col] = this.freeAt(
          (col + 0.5) * cellSize,
          (row + 0.5) * cellSize,
          26, // largest current foot (20) + grid/waypoint clearance
        ) ? 1 : 0;
  }
  resetGrass() {
    super.resetGrass();
    this.lastPathVisited = 0;
  }
  blockers() {
    return [...this.data.collisionContract, ...this.walls];
  }
  drawGrass(ctx, actors) {
    const im = this.textures.get(this.data.groundSrc),
      sx = im.naturalWidth / this.data.world.width,
      sy = im.naturalHeight / this.data.world.height;
    // Re-use the actual painted grass immediately around each grounded foot, after actors.
    // No opaque full-region overlay: it would hide the entire character rather than the feet.
    for (const p of actors) {
      if (p.hp <= 0 || p.char.flightHeight || p.jumpHeight > 2) continue;
      const foot = window.PoightBodies.foot(p);
      for (const g of this.data.grassRegions) {
        if (p.x < g.x || p.x > g.x + g.width || p.y < g.y || p.y > g.y + g.height) continue;
        const x = Math.max(g.x, p.x - foot - 3),
          y = Math.max(g.y, p.y + 4),
          w = Math.min(g.x + g.width, p.x + foot + 3) - x,
          h = Math.min(g.y + g.height, p.y + 17) - y;
        if (w > 0 && h > 0) ctx.drawImage(im, x * sx, y * sy, w * sx, h * sy, x, y, w, h);
      }
    }
  }
  drawDebug(ctx) {
    ctx.save();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#ff375f";
    for (const o of this.data.collisionContract) ctx.strokeRect(o.x, o.y, o.w, o.h);
    ctx.strokeStyle = "#00eaff";
    const b = this.data.battleArea;
    ctx.strokeRect(b.x, b.y, b.width, b.height);
    ctx.strokeStyle = "#fff000";
    for (const g of this.data.grassRegions) ctx.strokeRect(g.x, g.y, g.width, g.height);
    ctx.restore();
  }
};
