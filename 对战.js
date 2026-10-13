"use strict";
(() => {
  const evt = window.PoightEVT;
  const DATA = __GAME_DATA__,
    {
      roster: ROSTER,
      moves: MOVES,
      tiers: TIERS,
      types: TYPES,
      efficacy: EFFICACY,
      environment: DEFAULT_ENV,
      art: ART,
    } = DATA;
  const generated = new window.PoightR3GeneratedMoves(DATA.generatedFx || {}),
    bodies = window.PoightBodies,
    stealth = new window.PoightGrassStealth(),
    traversal = new window.PoightTraversal();
  for (const [id, d] of Object.entries(DATA.generatedFx || {}))
    if (MOVES[id]) Object.assign(MOVES[id], d.runtime);
  for (const [id, runtime] of Object.entries(DATA.revision3Moves || {}))
    if (MOVES[id]) Object.assign(MOVES[id], runtime);
  window.PoightFeelTiming(MOVES);
  const ALL_SCENES = DATA.environments || [DEFAULT_ENV],
    SCENES = ALL_SCENES.filter((s) => !s.entranceOnly),
    sceneByID = new Map(ALL_SCENES.map((s) => [s.id, s])),

    terrainByID = new Map((DATA.terrains || []).map((t) => [t.id, t]));
  let ENV = DEFAULT_ENV,
    sceneRevision = 0,
    terrain = null;
  const $ = (id) => document.getElementById(id),
    canvas = $("game"),
    ctx = canvas.getContext("2d", { alpha: false }),
    args = new URLSearchParams(location.search),
    manual = args.get("test") === "1",
    observe = args.get("observe") === "1";
  const animations = new window.PoightMoveAnimations(DATA.moveAnimations, args.get("anim") !== "old");
  generated.animations = animations;
  const matchAssets = window.PoightMatchAssets(animations, generated, MOVES);
  const demo = new window.PoightDemo(args);
  const battleHUD = new window.PoightBattleHUD(args.get("hud") || (demo.enabled ? "2" : null), DATA);
  const music = new window.PoightBattleMusic(initAudio, args, DATA.music);
  music.onDecision = (bgm) => evt.music(bgm);
  const gba = new window.PoightGBA(!demo.enabled && !args.has("hud"), {
    togglePause: () => phase === "paused" ? start() : pause(), playing: () => phase === "playing",
    resume: () => start(), setup: () => openSetup(), rematch: () => resetMatch(true),
    portrait: (el, id, side) => setPortrait(el, id, side), roster: DATA.gbaRoster,
  });
  if (gba.enabled) battleHUD.onMenuChange = (open) => { if (open) pause(); };
  const ui3 = gba.enabled && !window.PoightMobile.touchDevice() && matchMedia("(pointer: fine)").matches
    ? new window.PoightUI3(DATA) : null;
  const selectionUI = new window.PoightSelection(gba.enabled, ROSTER, (savedCursor) => {
    if (savedCursor != null) cursorID = savedCursor;
    pageIndex = 0;
    filteredRoster();
  });
  let mobile = null;
  const TAU = Math.PI * 2,
    WORLD = { ...ENV.world },
    B = { ...ENV.bounds };
  let obstacles = ENV.collisionContract;
  const CONFIG = {
    speed: 185,
    // B2: PV rapid-movement interval 0.30–0.433s; 255px ≈ 7.77 Pikachu heights.
    dashSpeed: 850,
    dashDuration: 0.30,
    dashProtection: 0.115,
    dashCooldown: 0.4,
    doubleTap: 0.25,
    regen: 25,
    regenDelay: 0.58,
    cost: { dash: 15 },
    radius: 18,
  };
  const byID = new Map(ROSTER.map((c) => [c.id, c])),
    clamp = (n, a, b) => Math.max(a, Math.min(b, n)),
    hypot = Math.hypot,
    lerp = (a, b, t) => a + (b - a) * t;
  const keys = new Set(),
    automaticHeld = new Set(),
    lastTap = {},
    moveKeys = ["KeyJ", "KeyK", "KeyL", "KeyI"],
    keyLabels = ["J", "K", "L", "I"],
    directionCodes = {
      KeyW: "up",
      ArrowUp: "up",
      KeyS: "down",
      ArrowDown: "down",
      KeyA: "left",
      ArrowLeft: "left",
      KeyD: "right",
      ArrowRight: "right",
    };
  let W = 960,
    H = 600,
    viewScale = 1,
    phase = "loading",
    elapsed = 0,
    matchSeconds = 0,
    frame = 0,
    player = null,
    enemy = null,
    bullets = [],
    effects = [],
    zones = [],
    floats = [],
    ghosts = [],
    hits = 0,
    taken = 0,
    outcome = null,
    queued = null,
    notice = "",
    noticeUntil = 0,
    aiEnabled = true,
    artReady = false,
    serial = 0,
    seed = 1357911,
    brain = null;
  const camera = { x: 0, y: 0 },
    arenaCamera = { x: 0, y: 0 },
    imageCache = new Map(),
    environmentImages = {},
    performanceSamples = [],
    actorHUD = new WeakMap();
  let profile = {
      player: 7,
      enemy: 4,
      playerMoves: [...byID.get(7).defaultMoves],
      enemyMoves: [...byID.get(4).defaultMoves],
      tier: DATA.defaultDifficulty,
      map: DEFAULT_ENV.id,
      shake: true,
      holdAim: true,
    },
    applySerial = 0;
  let sound = true,
    audio = null,
    assetError = "";
  let testTier = null;
  const balance = manual || demo.enabled ? new window.PoightBalanceTest({
    tiers: TIERS,
    multiplier: DATA.hpMultiplier,
    newBrain,
    reset: () => resetMatch(true),
    elapsed: () => elapsed,
    matchSeconds: () => matchSeconds,
    actors: () => [player, enemy],
    playing: () => phase === "playing",
    map: () => ENV.id,
    update,
    prepare(testSeed, aiTier, multiplier) {
      seed = testSeed >>> 0;
      profile.tier = aiTier;
      for (const p of [player, enemy]) p.hp = p.maxHP = Math.round(p.char.baseHP * multiplier);
    },
  }) : null;
  const environmentCache = new Map();
  async function loadEnvironment(id, point = null) {
    const env = sceneByID.get(id);
    if (!env) throw new Error("未知地图");
    if (!environmentCache.has(id))
      environmentCache.set(
        id,
        Promise.all([
          loadImage(env.groundSrc),
          loadImage(env.objectsSrc),
          env.type === "arena"
            ? window.PoightArena.load(env, loadImage)
            : env.terrainID
              ? window.PoightWorld.load(terrainByID.get(env.terrainID), loadImage)
              : null,
        ])
          .then(([ground, objects, world]) => ({ env, ground, objects, world }))
          .catch((e) => {
            environmentCache.delete(id);
            throw e;
          }),
      );
    const loaded = await environmentCache.get(id);
    const spawn = point || env.spawns.player;
    await loaded.world?.prepareView?.(spawn.x, spawn.y, W, H);
    return loaded;
  }
  function commitEnvironment(loaded) {
    // The latest completed selection commits artwork, collision, bounds and navigation together.
    if (terrain !== loaded.world) terrain?.release?.();
    ENV = loaded.env;
    terrain = loaded.world;
    if (terrain) terrain.capabilities = { ...ENV.capabilities };
    stealth.configure(ENV, terrain);
    Object.assign(WORLD, ENV.world);
    Object.assign(B, ENV.bounds);
    obstacles = ENV.collisionContract;
    environmentImages.ground = loaded.ground;
    environmentImages.objects = loaded.objects;
    prepareGround();
    navGrid = null;
    sceneRevision++;
    // New terrain must not stream at the previous scene's camera/player coordinates.
    resize(false);
  }
  async function traverseWarp(warp, current) {
    const job = applySerial;
    const loaded = await loadEnvironment(warp.destScene, warp);
    if (!current() || job !== applySerial) return false;
    // Check both safe landing positions before committing any part of the new scene.
    loaded.world.capabilities = { ...loaded.env.capabilities };
    const pp = {}, ep = {};
    if (!traversal.arrival(pp, loaded.world, warp.x, warp.y, bodies.foot(player)) ||
      !traversal.arrival(ep, loaded.world, warp.x, warp.y, bodies.foot(enemy),
        { ...pp, radius: bodies.foot(player) })) throw new Error("入口落点不可通行");
    clearInputs();
    bullets = []; zones = []; effects = []; floats = []; ghosts = [];
    generated.reset();
    brain = newBrain();
    for (const p of [player, enemy]) {
      p.attack = p.dash = null;
      jump.clear(p);
      p.vx = p.vy = p.motionX = p.motionY = 0;
      if (p.diveLeft > 0) traversal.surface(p);
    }
    Object.assign(player, pp);
    Object.assign(enemy, ep, { worldAbsent: true });
    commitEnvironment(loaded);
    terrain.resetGrass();
    camera.x = clamp(player.x - W / 2, 0, Math.max(0, WORLD.width - W));
    camera.y = clamp(player.y - H / 2, 0, Math.max(0, WORLD.height - H));
    announce(ENV.name + " · AI 将在 1 秒后跟进", 2);
    return true;
  }
  function toggleDive(p = player) {
    if (phase !== "playing" || statuses.blocked(p) || jump.blocked(p) ||
      !traversal.toggle(p, terrain)) return false;
    if (p === player) {
      queued = null;
      aim.cancel();
    }
    stealth.update(elapsed, player, enemy);
    generated.states = generated.states.filter((e) => e.owner !== p);
    return true;
  }
  function spawnActor(side, id, images, loadout) {
    const s = ENV.spawns[side];
    return makeActor(id, s.x, s.y, s.a, images, loadout, side === "player");
  }
  function rand() {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  }
  function setText(el, value) {
    const s = String(value);
    if (el.textContent !== s) el.textContent = s;
  }
  function announce(s, time = 1.5) {
    notice = s;
    noticeUntil = elapsed + time;
    setText($("status"), s);
  }
  function initAudio() {
    try {
      if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume().catch(() => {});
    } catch (_) {}
    return audio;
  }
  function tone(kind) {
    if (!sound || manual || !audio || audio.state !== "running") return;
    music.duckAlarm();
    try {
      const t = audio.currentTime,
        o = audio.createOscillator(),
        g = audio.createGain();
      o.type = kind === "hit" ? "square" : "triangle";
      const f =
        { shot: 810, hit: 210, dash: 480, heal: 620, guard: 350, win: 880, loss: 220 }[kind] || 470;
      o.frequency.setValueAtTime(f, t);
      o.frequency.exponentialRampToValueAtTime(
        kind === "heal" || kind === "win" ? f * 1.45 : f * 0.42,
        t + 0.09,
      );
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.025, t + 0.006);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.14);
      o.connect(g);
      g.connect(audio.destination);
      o.start(t);
      o.stop(t + 0.15);
      o.onended = () => {
        o.disconnect();
        g.disconnect();
      };
    } catch (_) {}
  }
  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("像素素材加载失败：" + src));
      im.src = src;
    });
  }
  const loadCharacterMetadata = window.PoightCharacterMetadata(DATA.characterPacks, ART, byID, loadImage);
  async function loadCharacter(id) {
    await loadCharacterMetadata(id);
    if (imageCache.has(id)) {
      const p = imageCache.get(id);
      imageCache.delete(id);
      imageCache.set(id, p);
      return p;
    }
    const files = ART[id],
      prom = Promise.all(
        Object.entries(files).map(async ([k, d]) => [k, await loadImage(d.src)]),
      ).then(Object.fromEntries);
    imageCache.set(id, prom);
    try {
      const loaded = await prom;
      pruneImages();
      return loaded;
    } catch (e) {
      imageCache.delete(id);
      throw e;
    }
  }
  function pruneImages() {
    for (const id of imageCache.keys()) {
      if (imageCache.size <= 6) break;
      if (id !== profile.player && id !== profile.enemy) imageCache.delete(id);
    }
  }
  function validateProfile(input) {
    const result = {
      player: Number(input.player),
      enemy: Number(input.enemy),
      tier: input.tier,
      shake: input.shake !== false,
      holdAim: input.holdAim !== false,
      map: ["forest", "courtyard", "coast"].includes(input.map)
        ? DEFAULT_ENV.id
        : (input.map ?? DEFAULT_ENV.id),
    };
    if (
      !byID.has(result.player) ||
      !byID.has(result.enemy) ||
      !TIERS.some((t) => t.id === result.tier) ||
      !sceneByID.has(result.map)
    )
      throw new Error("未知精灵、强度或地图");
    for (const side of ["player", "enemy"]) {
      const c = byID.get(result[side]),
        list = input[side + "Moves"];
      if (
        !Array.isArray(list) ||
        list.length < 1 ||
        list.length > 4 ||
        new Set(list).size !== list.length ||
        list.some((m) => !c.learnset.includes(m) || !MOVES[m])
      )
        throw new Error("配招须为1–4招，互不重复且在可学招式中");
      result[side + "Moves"] = [...list];
    }
    return result;
  }
  try {
    const saved = localStorage.getItem("pocket-arena-loadout-v1");
    if (saved && !demo.enabled) profile = validateProfile(JSON.parse(saved));
  } catch (_) {}
  function saveProfile() {
    if (demo.enabled) return;
    try {
      localStorage.setItem("pocket-arena-loadout-v1", JSON.stringify(profile));
    } catch (_) {}
  }
  const jump = new window.PoightJump({
    enabled: (p) => phase === "playing" && !traversal.pending && !p.worldAbsent &&
      !traversal.submerged(p, terrain) && !statuses.blocked(p),
    spend,
    reveal: (p) => stealth.event(p, "cast", elapsed),
    cancel: (p) => { if (p === player) { queued = null; aim.cancel(); feel.pendingDash = null; } },
  });
  const statuses = new window.PoightStatus({
    random: rand, protected: (p) => protectedNow(p) || p.shieldUntil > elapsed,
    damage: rawDamage,
    notice: (p, text, color) => float(text, p.x, headY(p, 12), color, p),
  }, DATA.statusAssets);
  const feel = new window.PoightFeel();
  const telegraph = window.PoightTelegraph;
  const aim = new window.PoightAim({
    enabled: () => profile.holdAim,
    player: () => player,
    canAim: (slot) => !castRefusal(slot),
    rejectAim: (slot) => rejectCast(slot, castRefusal(slot)),
    prepare: (slot) => {
      queued = null;
      blockedHeld.add(slot);
    },
    queue: (slot, angle = null) => queueAttack(slot, angle),
    auto: (slot) => aimAt(player, enemy, MOVES[player.moves[slot]]),
    vector: moveVector,
    start: () => {
      if (phase === "idle") start();
    },
    focus: () => canvas.focus({ preventScroll: true }),
    worldPoint: (x, y) => {
      const r = canvas.getBoundingClientRect();
      return {
        x: ((x - r.left - (ENV.type === "arena" ? 0 : feel.offset.x)) * W) / r.width +
          (ENV.type === "arena" ? camera.x : Math.round(camera.x)),
        y: ((y - r.top - (ENV.type === "arena" ? 0 : feel.offset.y)) * H) / r.height +
          (ENV.type === "arena" ? camera.y : Math.round(camera.y)),
      };
    },
  });
  function warningAPI() {
    return { bodies, generated, origin: releaseOrigin, rayEnd, bounds: B,
      animationEnabled: animations.enabled };
  }
  function warnings() {
    const result = [];
    for (const p of [player, enemy]) {
      if (!p || p.worldAbsent || traversal.submerged(p, terrain) || stealth.invisible(p)) continue;
      const a = p?.attack;
      if (a && !a.emitted && a.hitTime > 0 && a.age < a.hitTime)
        result.push({
          ...jump.warning(telegraph.shape(p, a.move || heroMove(p, MOVES[a.id]), a.aim,
            p === player ? enemy : player, warningAPI()),
            p === player ? enemy : player, MOVES[a.id]),
          player: p === player,
          remaining: a.hitTime - a.age,
          aiming: false,
        });
    }
    if (aim.hold?.active && !traversal.submerged(player, terrain))
      result.push({
        ...telegraph.shape(
          player, heroMove(player, MOVES[player.moves[aim.hold.slot]]),
          aim.hold.angle, enemy, warningAPI(),
        ),
        player: true,
        remaining: 1,
        aiming: true,
      });
    return result;
  }
  function clearInputs() {
    mobile?.clear();
    aim.cancel();
    feel.pendingDash = null;
    dashMemory = null;
    aim.rightHeld = false;
    keys.clear();
    automaticHeld.clear();
    queued = null;
    blockedHeld.clear();
    castNotices.clear();
    rejectedUntil.clear();
    for (const k of Object.keys(lastTap)) delete lastTap[k];
  }
  function newBrain() {
    return {
      mode: "观察",
      poll: 0,
      mx: 0,
      my: 0,
      orbit: 1,
      turnAt: 1.5,
      attackAfter: 0.7,
      dodgeAfter: 0,
      escapeUntil: 0,
      escapeX: 0,
      escapeY: 0,
      path: [],
      pathAt: 0,
      goalX: 0,
      goalY: 0,
      decisions: 0,
      dodgeDecisions: 0,
      pursuitDashes: 0,
      pathSearches: 0,
      casts: 0,
      defends: 0,
      heals: 0,
    };
  }
  function makeActor(id, x, y, a, images, loadout, isPlayer) {
    const char = byID.get(id);
    return {
      id,
      char,
      images,
      x,
      y,
      a,
      isPlayer,
      onBridge: terrain?.bridges?.layer(terrain.index(x, y)) ?? false,
      hp: char.hp,
      maxHP: char.hp,
      stamina: 100,
      rest: 0,
      speed: char.speed,
      moves: [...loadout],
      cool: Object.fromEntries(loadout.map((m) => [m, 0])),
      vx: 0,
      vy: 0,
      lastX: x,
      lastY: y,
      motionX: 0,
      motionY: 0,
      moving: false,
      immune: 0,
      hurt: 0,
      hurtAge: 0,
      attack: null,
      dash: null,
      dashCool: 0,
      ghostTime: 0,
      anim: "idle",
      animAge: 0,
      slow: 0,
      status: null,
      freezeGrace: 0,
      shield: 0,
      shieldUntil: 0,
      buffs: { speed: 0, power: 0 },
      shots: 0,
      splashes: 0,
      punches: 0,
      dodges: 0,
      evades: 0,
      spent: 0,
      damageTaken: 0,
      damageDealt: 0,
    };
  }
  function resetMatch(play = false) {
    if (!artReady || !player || !enemy) return;
    evt.quit(player, enemy); evt.replay();
    gba.reset();
    const pImages = player.images,
      eImages = enemy.images;
    music.setPlaying(false);
    music.prepared = false;
    if (play) music.prepareRound();
    phase = play ? "playing" : "idle";
    elapsed = 0;
    matchSeconds = 0;
    seed = demo.enabled ? demo.seed : 1357911;
    if (demo.enabled) { demo.reset(); frame = 0; }
    serial = 0;
    traversal.reset();
    terrain?.resetGrass();
    stealth.reset();
    generated.reset();
    jump.reset();
    feel.reset();
    performanceSamples.length = 0;
    clearInputs();
    bullets = [];
    effects = [];
    zones = [];
    floats = [];
    ghosts = [];
    hits = taken = 0;
    outcome = null;
    notice = "";
    noticeUntil = 0;
    aiEnabled = true;
    brain = newBrain();
    balance?.reset();
    player = spawnActor("player", profile.player, pImages, profile.playerMoves);
    enemy = spawnActor("enemy", profile.enemy, eImages, profile.enemyMoves);
    camera.x = clamp(player.x - W / 2, 0, Math.max(0, WORLD.width - W));
    camera.y = clamp(player.y - H / 2, 0, Math.max(0, WORLD.height - H));
    renderSkillButtons();
    if (demo.enabled) {
      balance.control(profile.tier);
      updateDemoCamera(0, true);
    } else if (ENV.type === "arena") resize();
    syncUI();
    if (play) evt.playing(profile, music.stream && !music.decided ? null : music.bgm);
  }
  async function applyProfile(input, play = true) {
    const next = validateProfile(input),
      job = ++applySerial;
    evt.quit(player, enemy);
    traversal.reset();
    clearInputs();
    phase = "loading";
    music.setPlaying(false);
    $("startBattle").disabled = true;
    setText($("setupMessage"), "正在加载精灵动作和场景…");
    $("setupMessage").classList.remove("error");
    try {
      const [p, e, environment] = await Promise.all([
        loadCharacter(next.player),
        loadCharacter(next.enemy),
        loadEnvironment(next.map),
        matchAssets.load(next, loadImage),
        statuses.load(loadImage),
        ...(gba.enabled ? [bwPortraits.preload(next.player), bwPortraits.preload(next.enemy)] : []),
      ]);
      if (job !== applySerial) {
        pruneImages();
        return false;
      }
      commitEnvironment(environment);
      assetError = "";
      profile = next;
      player = spawnActor("player", next.player, p, next.playerMoves);
      enemy = spawnActor("enemy", next.enemy, e, next.enemyMoves);
      artReady = true;
      resetMatch(play);
      await terrain?.prepareView?.(player.x, player.y, W, H);
      if (job !== applySerial) return false;
      draw();
      pruneImages();
      saveProfile();
      if (play && $("setup").open) $("setup").close();
      if (play) canvas.focus({ preventScroll: true });
      return true;
    } catch (err) {
      if (job === applySerial) {
        phase = player ? "paused" : "loading";
        assetError = err.message + "。请保留完整 assets 文件夹，然后重试。";
        setText($("status"), "素材文件未就位，保留上一张地图");
        setText($("setupMessage"), assetError);
        $("setupMessage").classList.add("error");
      }
      return false;
    } finally {
      if (job === applySerial) $("startBattle").disabled = false;
    }
  }
  function start() {
    if (
      !artReady ||
      mobile?.blockedPortrait ||
      $("setup").open ||
      $("scenePicker").open ||
      phase === "over" ||
      phase === "loading"
    )
      return;
    if (!music.prepared) music.prepareRound();
    phase = "playing";
    evt.playing(profile, music.stream && !music.decided ? null : music.bgm);
    clearInputs();
    if (demo.enabled) demo.paused = false;
    if (sound) initAudio();
    syncUI();
  }
  function pause() {
    if (demo.enabled) demo.paused = true;
    if (phase === "playing") {
      evt.pause();
      phase = "paused";
      clearInputs();
      syncUI();
    }
  }
  function finishMatch() {
    if (phase !== "playing" || (player.hp > 0 && enemy.hp > 0)) return;
    outcome = player.hp <= 0 ? (enemy.hp <= 0 ? "draw" : "loss") : "win";
    phase = "over";
    music.setPlaying(false);
    evt.finish(outcome, matchSeconds, player, hits, taken);
    clearInputs();
    bullets = [];
    zones = [];
    generated.states = [];
    for (const p of [player, enemy]) {
      p.attack = null;
      p.dash = null;
      p.vx = p.vy = 0;
      if (p.hp <= 0) {
        p.anim = "hurt";
        p.animAge = ART[p.id].hurt.totalDuration - 0.001;
      }
    }
    gba.finish(outcome, player, enemy, matchSeconds);
    tone(outcome === "win" ? "win" : "loss");
  }
  function mapObstacles(ax, ay, bx = ax, by = ay, pad = 0, upper) {
    return terrain ? terrain.blockers(ax, ay, bx, by, pad, upper) : obstacles;
  }
  function freeAt(x, y, r = 18, upper) {
    return (
      x >= B.left &&
      x <= B.right &&
      y >= B.top &&
      y <= B.bottom &&
      (terrain
        ? terrain.freeAt(x, y, r, upper)
        : obstacles.every(
            (o) => hypot(x - clamp(x, o.x, o.x + o.w), y - clamp(y, o.y, o.y + o.h)) >= r,
          ))
    );
  }
  function constrain(p) {
    const r = bodies.foot(p);
    if (terrain) {
      if (!freeAt(p.x, p.y, r, p.onBridge)) {
        const at = terrain.nearest(p.x, p.y, p.onBridge);
        if (at >= 0) {
          p.x = ((at % terrain.columns) + 0.5) * terrain.cell;
          p.y = (Math.floor(at / terrain.columns) + 0.5) * terrain.cell;
        }
      }
      return;
    }
    p.x = clamp(p.x, B.left, B.right);
    p.y = clamp(p.y, B.top, B.bottom);
    for (const o of obstacles) {
      const dx = p.x - clamp(p.x, o.x, o.x + o.w),
        dy = p.y - clamp(p.y, o.y, o.y + o.h),
        d = hypot(dx, dy);
      if (d >= r) continue;
      if (d > 0.001) {
        p.x += (dx / d) * (r - d);
        p.y += (dy / d) * (r - d);
      } else {
        const sides = [
          { v: Math.abs(p.x - o.x + r), x: o.x - r, y: p.y },
          { v: Math.abs(p.x - o.x - o.w - r), x: o.x + o.w + r, y: p.y },
          { v: Math.abs(p.y - o.y + r), x: p.x, y: o.y - r },
          { v: Math.abs(p.y - o.y - o.h - r), x: p.x, y: o.y + o.h + r },
        ].sort((a, b) => a.v - b.v);
        p.x = sides[0].x;
        p.y = sides[0].y;
      }
    }
  }
  function translatePet(p, dx, dy) {
    if (p.worldAbsent || traversal.pending) return;
    if (terrain) {
      const speed = traversal.speed(p, terrain);
      terrain.move(p, dx * speed, dy * speed, bodies.foot(p));
      return;
    }
    p.x += dx;
    constrain(p);
    p.y += dy;
    constrain(p);
  }
  function segmentBox(ax, ay, bx, by, o, pad = 0) {
    let lo = 0,
      hi = 1;
    for (const [p, d, min, max] of [
      [ax, bx - ax, o.x - pad, o.x + o.w + pad],
      [ay, by - ay, o.y - pad, o.y + o.h + pad],
    ]) {
      if (Math.abs(d) < 1e-9) {
        if (p < min || p > max) return Infinity;
      } else {
        let a = (min - p) / d,
          b = (max - p) / d;
        if (a > b) [a, b] = [b, a];
        lo = Math.max(lo, a);
        hi = Math.min(hi, b);
        if (lo > hi) return Infinity;
      }
    }
    return lo;
  }
  function clearLine(ax, ay, bx, by, pad = 5, upper) {
    return mapObstacles(ax, ay, bx, by, pad, upper).every(
      (o) => !Number.isFinite(segmentBox(ax, ay, bx, by, o, pad)),
    );
  }
  function rayEnd(x, y, a, range, pad = 5) {
    const ex = x + Math.cos(a) * range,
      ey = y + Math.sin(a) * range;
    let f = 1;
    for (const o of mapObstacles(x, y, ex, ey, pad))
      f = Math.min(f, segmentBox(x, y, ex, ey, o, pad));
    return { x: x + (ex - x) * Math.max(0, f - 0.002), y: y + (ey - y) * Math.max(0, f - 0.002) };
  }
  function segmentDistance(px, py, ax, ay, bx, by) {
    const dx = bx - ax,
      dy = by - ay,
      l = dx * dx + dy * dy,
      t = l ? clamp(((px - ax) * dx + (py - ay) * dy) / l, 0, 1) : 0;
    return hypot(px - ax - dx * t, py - ay - dy * t);
  }
  function demoCenters() {
    return [player, enemy].filter(Boolean).map(p => {
      const visual = window.PoightSeams.visual(p);
      return { x: visual.x, y: visual.y - (p.char.body?.top ?? 41) / 2 - flightHeight(p) };
    });
  }
  function renderRect() {
    return demo.enabled ? { width: demo.width, height: demo.height } : canvas.getBoundingClientRect();
  }
  function updateDemoCamera(dt, snap = false) {
    const points = [player, enemy].filter(Boolean).flatMap(p => {
      const visual = window.PoightSeams.visual(p), radius = bodies.shape(p).rx;
      return [{ x: visual.x - radius, y: headY(p) + visual.y - p.y },
        { x: visual.x + radius, y: visual.y + 14 + bodies.foot(p) }];
    });
    if (!points.length) return;
    const fit = demo.camera(points, camera, WORLD, dt, snap);
    W = fit.width; H = fit.height; viewScale = fit.scale;
    camera.x = fit.x; camera.y = fit.y;
    ctx.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
    ctx.imageSmoothingEnabled = false;
  }
  function updateCamera(dt) {
    if (demo.enabled) { updateDemoCamera(dt); return; }
    if (ENV.type === "arena") {
      Object.assign(camera, battleHUD.camera(camera, player, enemy, W, H, dt, WORLD));
      return;
    }
    const k = 1 - Math.exp(-10 * dt);
    const visual = window.PoightSeams.visual(player);
    camera.x = lerp(camera.x, clamp(visual.x - W / 2, 0, Math.max(0, WORLD.width - W)), k);
    camera.y = lerp(camera.y, clamp(visual.y - H / 2, 0, Math.max(0, WORLD.height - H)), k);
  }
  function resize(paint = true) {
    if (demo.enabled) {
      demo.fit(canvas);
      if (demo.zoom === null) updateDemoCamera(0, true);
      else ctx.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
      if (paint !== false && artReady) draw();
      return;
    }
    const r = canvas.getBoundingClientRect();
    viewScale = Math.max(
      1,
      Math.round(Math.min(r.width / 960, r.height / 600) * 4) / 4,
      r.width / WORLD.width,
      r.height / WORLD.height,
    );
    W = Math.max(1, Math.min(WORLD.width, Math.round(r.width / viewScale)));
    H = Math.max(1, Math.min(WORLD.height, Math.round(r.height / viewScale)));
    if (ENV.type === "arena") {
      const fit = battleHUD.viewport(r);
      viewScale = fit.scale;
      Object.assign(arenaCamera, { x: fit.x, y: fit.y });
      W = r.width / viewScale;
      H = r.height / viewScale;
    }
    const pixelRatio = Math.min(
      devicePixelRatio || 1,
      2,
      Math.sqrt(8388608 / Math.max(1, r.width * r.height)),
    );
    canvas.width = Math.max(1, Math.round(r.width * pixelRatio));
    canvas.height = Math.max(1, Math.round(r.height * pixelRatio));
    ctx.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
    ctx.imageSmoothingEnabled = false;
    camera.x = clamp(camera.x, 0, Math.max(0, WORLD.width - W));
    camera.y = clamp(camera.y, 0, Math.max(0, WORLD.height - H));
    if (paint !== false && (ENV.type === "arena" || (player && phase !== "playing"))) updateCamera(1);
    if (paint !== false && artReady) draw();
  }
  function moveVector() {
    let x =
        Number(keys.has("KeyD") || keys.has("ArrowRight")) -
        Number(keys.has("KeyA") || keys.has("ArrowLeft")),
      y =
        Number(keys.has("KeyS") || keys.has("ArrowDown")) -
        Number(keys.has("KeyW") || keys.has("ArrowUp")),
      l = hypot(x, y);
    if (!l && mobile?.controls) return mobile.vector;
    return { x: l ? x / l : 0, y: l ? y / l : 0 };
  }
  function spend(p, amount) {
    if (p.stamina + 1e-6 < amount) {
      if (p === player) announce("体力不足，缓一下");
      return false;
    }
    p.stamina = Math.max(0, p.stamina - amount);
    p.spent += amount;
    p.rest = CONFIG.regenDelay;
    return true;
  }
  function dash(p, dx, dy) {
    if (statuses.blocked(p) || jump.blocked(p) || traversal.pending || p.worldAbsent ||
      traversal.submerged(p, terrain)) return false;
    const length = hypot(dx, dy);
    if (!length || phase !== "playing" || p.hp <= 0 || p.dash || p.dashCool > 1e-6 || !spend(p, 15))
      return false;
    p.attack = null;
    p.hurt = 0;
    p.vx = p.vy = 0;
    p.dash = { age: 0, dx: dx / length, dy: dy / length };
    p.dashCool = CONFIG.dashCooldown;
    p.a = Math.atan2(dy, dx);
    p.dodges++;
    p.anim = "dash";
    p.animAge = 0;
    p.ghostTime = 0;
    if (p === player) {
      queued = null;
      aim.cancel();
    }
    tone("dash");
    return true;
  }
  let dashMemory = null;
  function requestDash(dx, dy) {
    if (feel.bufferDash(dx, dy)) return true;
    if (dash(player, dx, dy)) return true;
    if (phase === "playing" && player.hp > 0 && !player.dash &&
      (statuses.blocked(player) ||
        (player.dashCool > 0 && player.dashCool <= 0.08 + 1e-6))) {
      dashMemory = { dx, dy, until: inputClock + 0.08 };
      return true;
    }
    return false;
  }
  function rushDuration(m) {
    return m.range / (m.rushSpeed || 630);
  }
  function heroMove(p, m) {
    if (!m?.hero && !m?.limb && !m?.batch2 && !m?.r3) return m;
    const runtime = { ...m, range: Math.min(m.range, p.char.body.nominalSize * m.rangeBodies) };
    if (m.batch2) {
      const entries = p.char.moveAnchors || {};
      runtime.anchor = entries[m.anchor]
        ? m.anchor
        : ["mouth", "palms", "head", "cheek", "plant", "wing"].find((part) => entries[part]);
      runtime.animationRole = entries[runtime.anchor]?.role || "shoot";
    }
    return runtime;
  }
  function limbFacing(p, a) {
    const attack = p.attack;
    if (!attack?.move?.limb || !attack.emitted) return a;
    const age = Math.max(0, attack.age - attack.hitTime);
    if (attack.id === "rapidspin") return a + Math.floor(age / 0.055) * (Math.PI / 4);
    if (attack.id === "aquatail")
      return a + (Math.sin(Math.min(1, age / 0.38) * Math.PI) * Math.PI) / 2;
    return a;
  }
  function heroAnchor(p, m, a = p.a) {
    // Batch tables are opt-in; T5 hero anchors remain limited to #6/#25.
    const enabled = m.limb || m.batch2 || m.r3 || (m.hero && [6, 25].includes(p.id));
    const entries = p.char.moveAnchors;
    const entry = enabled && (m.r3 ? entries?.['r3-' + m.anchor] || entries?.[m.anchor]
      : entries?.[m.anchor]);

    if (!entry) return null;
    const role = entry.role,
      clip = ART[p.id][role],
      attack = p.attack,
      hit = clip.hitTime ?? clip.totalDuration * 0.5,
      time = attack
        ? attack.age < attack.hitTime
          ? (attack.age / Math.max(0.001, attack.hitTime)) * hit
          : hit +
            ((attack.age - attack.hitTime) / Math.max(0.001, attack.duration - attack.hitTime)) *
              (clip.totalDuration - hit)
        : p.animAge,
      row = directionRow(limbFacing(p, a)),
      frame = animationFrame(p.id, role, time),
      point = entry.points[row][frame],
      baseOffset = clip.bodyOffsets?.[row]?.[frame] || [0, 0],
      poseOffset = m.limb
        ? p.char.moveAnchors["r1-body"].poseOffsets[row][frame]
        : [0, 0],
      offset = [baseOffset[0] + poseOffset[0], baseOffset[1] + poseOffset[1]];
    const pointWorld = {
      x: p.x + (point[0] - clip.anchorX - offset[0]) * p.char.scale,
      y: p.y + 14 + (point[1] - clip.anchorY - offset[1]) * p.char.scale - flightHeight(p),
      role,
      row,
      frame,
      hidden: (entry.occludedRows || []).includes(row),
    };
    return m.r3 ? window.PoightRevision3.transform(pointWorld, p) : pointWorld;
  }
  function releaseOrigin(p, m, a) {
    const anchor = heroAnchor(p, m, a);
    if (anchor) {
      const reach = bodies.reach(p, Math.cos(a), Math.sin(a)),
        x = p.x + Math.cos(a) * reach,
        y = p.y + Math.sin(a) * reach;
      return {
        x,
        y,
        anchor,
        visualOffsetX: anchor.x - x,
        visualOffset: anchor.y - (y - 16 - visualLift(p)),
      };
    }
    if (m.hero || m.r3) {
      const reach = bodies.reach(p, Math.cos(a), Math.sin(a));
      return { x: p.x + Math.cos(a) * reach, y: p.y + Math.sin(a) * reach, visualOffset: 0 };
    }
    const row = directionRow(a),
      d = ART[p.id].shoot,
      point =
        p.id === 6 && ["flamethrower", "fireblast"].includes(m.id)
          ? [53, 27]
          : p.id === 7 && m.id === "watergun"
            ? [28, 16]
            : null;
    if (point && row === 6)
      return {
        x: p.x + (point[0] - d.anchorX) * p.char.scale,
        y: p.y,
        visualOffset:
          14 + (point[1] - d.anchorY) * p.char.scale - flightHeight(p) + 16 + visualLift(p),
      };
    if (m.id === "airslash")
      return {
        x: p.x - Math.cos(a) * 8 - Math.sin(a) * 18,
        y: p.y - Math.sin(a) * 8 + Math.cos(a) * 18,
        visualOffset: -20,
      };
    const reach = bodies.reach(p, Math.cos(a), Math.sin(a)) + 6;
    return { x: p.x + Math.cos(a) * reach, y: p.y + Math.sin(a) * reach, visualOffset: 0 };
  }
  const tailCanvas = document.createElement("canvas");
  tailCanvas.width = tailCanvas.height = 256;
  function heroTailMask(context, p, anchor, paint) {
    if (anchor.hidden) return;
    const g = tailCanvas.getContext("2d"),
      clip = ART[p.id][anchor.role],
      offset = clip.bodyOffsets?.[anchor.row]?.[anchor.frame] || [0, 0],
      scale = p.char.scale;
    g.clearRect(0, 0, 256, 256);
    g.save();
    g.translate(128 - p.x, 128 - p.y);
    paint(g);
    g.globalCompositeOperation = "destination-in";
    g.imageSmoothingEnabled = false;
    g.drawImage(
      p.images[anchor.role],
      anchor.frame * clip.frameWidth,
      anchor.row * clip.frameHeight,
      clip.frameWidth,
      clip.frameHeight,
      p.x - (clip.anchorX + offset[0]) * scale,
      p.y + 14 - (clip.anchorY + offset[1]) * scale - flightHeight(p),
      clip.frameWidth * scale,
      clip.frameHeight * scale,
    );
    g.restore();
    context.drawImage(tailCanvas, p.x - 128, p.y - 128);
  }
  function generatedAPI() {
    return {
      bodies,
      animations,
      moves: MOVES,
      player,
      enemy,
      damage,
      clearLine,
      rayEnd,
      move: translatePet,
      heal,
      lift: visualLift,
      projectileLift: (p, m) => visualLift(p) - (m.hitsAirborne === false ? p.jumpHeight || 0 : 0),
      bodyLift: flightHeight,
      elapsed: () => elapsed,
      tone,
      origin: releaseOrigin,
      landing: (p, m, angle, target) => telegraph.landing(p, m, angle, target, warningAPI()),
      anchor: heroAnchor,
      tailMask: heroTailMask,
      projectile: (b) => bullets.push({ id: ++serial, ...b }),
    };
  }
  function protectedNow(p) {
    return !!(
      (p.dash && p.dash.age < CONFIG.dashProtection) ||
      (p.attack &&
        MOVES[p.attack.id].phaseRush &&
        p.attack.age >= p.attack.hitTime &&
        p.attack.age < p.attack.hitTime + rushDuration(MOVES[p.attack.id]))
    );
  }
  function tier() {
    return TIERS.find((t) => t.id === (testTier || profile.tier));
  }
  function aimAt(p, target, m) {
    if (stealth.hidden(target)) return p.a;
    const lead =
      m.kind === "shot" || m.kind === "fan"
        ? Math.min(0.45, hypot(target.x - p.x, target.y - p.y) / m.speed) *
          (p === player ? 0.8 : tier().lead)
        : 0;
    let a = Math.atan2(
      clamp(target.y + target.motionY * lead, B.top, B.bottom) - p.y,
      clamp(target.x + target.motionX * lead, B.left, B.right) - p.x,
    );
    if (p === enemy) a += (rand() * 2 - 1) * tier().aimError;
    return a;
  }
  function beginAttack(p, id, target, manualAim = null) {
    if (statuses.blocked(p) || jump.blocked(p) || traversal.pending || p.worldAbsent || target.worldAbsent ||
      traversal.submerged(p, terrain)) return false;
    const m = heroMove(p, MOVES[id]);
    if (p === player && castRefusal(p.moves.indexOf(id))) return false;
    if (p === enemy && stealth.hidden(target)) return false;
    if (
      !m ||
      !p.moves.includes(id) ||
      phase !== "playing" ||
      p.hp <= 0 ||
      target.hp <= 0 ||
      p.attack ||
      p.dash ||
      p.hurt > 0 ||
      (p.cool[id] || 0) > 1e-6
    )
      return false;
    if (m.kind === "heal" && p.hp >= p.maxHP) {
      return false;
    }
    // Keep the AI's original range gate; only player input gains a clamped landing.
    if (p === enemy && id === "thunder" && hypot(target.x - p.x, target.y - p.y) > m.range)
      return false;
    if (!spend(p, m.cost)) return false;
    evt.cast(p === player ? "player" : "enemy", id);
    stealth.event(p, "cast", elapsed);
    const aim = manualAim ?? aimAt(p, target, m),
      rushTime = m.kind === "rush" ? rushDuration(m) : 0,
      streamHold = m.r3 && m.kind === "beam" ? Math.max(0, m.range / m.speed - m.recovery) : 0;
    p.attack = {
      id,
      move: m,
      targetPoint: manualAim !== null || (p === player && id === "thunder")
        ? telegraph.landing(p, m, aim, target, warningAPI())
        : { x: target.x, y: target.y },
      kind: m.kind,
      age: 0,
      aim,
      emitted: false,
      hitTime: m.windup,
      duration: m.windup + m.recovery + rushTime + streamHold,
      group: {
        id: ++serial,
        hit: new Set(),
        power: p.buffs.power > 0 ? 1.25 : 1,
        hp: p.hp / p.maxHP,
      },
    };
    if (m.fangs) window.PoightFangs.windup(generated, p, p.attack, target, generatedAPI());
    p.a = aim;
    p.cool[id] = m.cd;
    p.anim = m.animationRole ||
      (m.kind === "melee" || m.kind === "rush" || m.kind === "spin" ? "melee" : "shoot");
    p.animAge = 0;
    if (m.hero && m.windup === 0) {
      p.attack.emitted = true;
      impact(p, p.attack, target);
    }
    return true;
  }
  function effective(type, types) {
    return types.reduce((r, t) => r * (EFFICACY[type]?.[t] ?? 1), 1);
  }
  function float(text, x, y, color = "#fff7d5", actor = null, suffix = "") {
    actor ||= [player, enemy].find((p) => p && Math.abs(p.x - x) < 20);
    const recent = floats.filter((f) => f.actor === actor && f.age < 0.6),
      slot = recent.length ? Math.max(...recent.map((f) => f.slot)) + 1 : 0;
    floats.push({ text, x, y, age: 0, color, actor, suffix, slot });
    if (floats.length > 28) floats.shift();
  }
  function fx(kind, x, y, color, extra = {}) {
    effects.push({ kind, x, y, color, age: 0, life: 0.35, ...extra });
    if (effects.length > 120) effects.splice(0, effects.length - 120);
  }
  function particles(x, y, color, count = 12, contactGroup = null) {
    for (let i = 0; i < count; i++) {
      const a = rand() * TAU,
        s = 35 + rand() * 135;
      fx("particle", x, y, color, {
        vx: Math.cos(a) * s,
        vy: Math.sin(a) * s - 20,
        size: 2 + Math.floor(rand() * 4),
        life: 0.23 + rand() * 0.2,
        contactGroup,
      });
    }
  }
  function heal(p, amount, native = false) {
    const value = Math.min(amount, p.maxHP - p.hp);
    if (value <= 0) return;
    p.hp += value;
    balance?.record(p, p, "healing", "heal", value);
    float("+" + value, p.x, p.y - 57, "#e8ffbd");
    if (!native) fx("heal", p.x, p.y, "#b9eca0", { life: 0.7 });
    tone("heal");
  }
  function rawDamage(p, source, amount, dot = false, move = "unknown", multiplier = null,
    suffix = "") {
    const real = Math.min(p.hp, amount);
    p.hp = Math.max(0, p.hp - real);
    if (real > 0) stealth.event(p, "hit", elapsed);
    p.damageTaken += real;
    source.damageDealt += real;
    balance?.record(source, p, move, dot ? "dot" : "direct", real, multiplier);
    if (!dot) {
      if (source === player) hits++;
      else taken++;
    }
    float(
      "−" + (dot ? Number(real.toFixed(2)) : real),
      p.x + (rand() - 0.5) * 15,
      headY(p, 8),
      dot ? "#eac4f3" : "#fffbe3",
      p,
      suffix,
    );
    return real;
  }
  function damage(target, source, m, dx, dy, group, contactPoint = null) {
    if (!jump.canHit(target, m) || !traversal.canHit(target, m, terrain) ||
      source.worldAbsent) return false;
    // Only the authorized +120ms second crunch bite bypasses its OWN first hit's
    // 140ms hit immunity. Dodge/guard and immunity from any other hit still apply.
    const sameFangSequence = m.id === "crunch" && group.fangBite === 1 &&
      group.fangSequence === target.lastFangSequence;
    if (target.hp <= 0 || source.hp <= 0 || group.hit.has(target) ||
      (target.immune > 0 && !sameFangSequence)) return false;
    if (protectedNow(target)) {
      target.evades++;
      return false;
    }
    const mult = target.char.types.reduce(
      (v, t) => v * (m.waterEffective && t === 11 ? 2 : (EFFICACY[m.type]?.[t] ?? 1)),
      1,
    );
    group.hit.add(target);
    if (mult === 0) {
      float("无效", target.x, target.y - 52, "#eff0d9");
      return false;
    }
    stealth.event(target, "hit", elapsed);
    let amount = Math.max(
      1,
      Math.round(
        m.damage *
          mult *
          (source.char.types.includes(m.type) ? 1.1 : 1) *
          (group.power ?? (source.buffs.power > 0 ? 1.25 : 1)) *
          (m.execute && target.hp / target.maxHP <= 0.5 ? 1.6 : 1) *
          (m.hpScale ? 0.45 + 0.55 * (group.hp ?? source.hp / source.maxHP) : 1) *
          (m.lowHP ? 1 + 2 * (1 - (group.hp ?? source.hp / source.maxHP)) : 1) *
          (m.venom && target.status?.id === "psn" ? 1.6 : 1) * statuses.power(source, m),
      ),
    );
    amount *= m.hitFraction ?? 1;
    if (target.shield > 0 && target.shieldUntil > elapsed) {
      if (m.breakShield) {
        target.shield = 0;
        float("破盾", target.x, target.y - 70, "#ffddaa");
      } else {
        const absorbed = Math.min(target.shield, amount);
        target.shield -= absorbed;
        amount -= absorbed;
        fx("guard", target.x, target.y, "#e2ffc3", { life: 0.25 });
        float("格挡", target.x, target.y - 60, "#d7ffd0");
        if (!amount) return false;
      }
    }
    const real = rawDamage(
      target, source, amount, false, m.id, mult,
      mult >= 2 ? "效果拔群!" : mult < 1 ? "抵抗 · 效果不好" : "",
    );
    statuses.hit(target, source, m);
    target.immune = 0.14;
    target.lastFangSequence = group.fangSequence || null;
    target.hurt = m.kind === "melee" || m.kind === "spin" ? 0.2 : 0.13;
    target.hurtAge = 0;
    target.attack = null;
    if (!statuses.frozen(target)) {
      target.anim = "hurt";
      target.animAge = 0;
    }
    if (m.knockScale !== 0) feel.knockback(target, amount, dx, dy);
    feel.hit(amount, mult, profile.shake);
    animations.impact(target, source, m, amount, mult, dx, dy, contactPoint, generatedAPI());
    if (target === player) aim.cancel();
    if (m.slow) target.slow = Math.max(target.slow, m.slow);
    if (m.leech) heal(source, m.leech);
    if (m.r3 && real > 0) generated.returnFlow(source, target, m, generatedAPI());
    if (m.recoil) {
      const recoil = Math.min(source.hp, Math.max(1, Math.round(real * m.recoil)));
      source.hp -= recoil;
      source.damageTaken += recoil;
      balance?.record(source, source, m.id, "recoil", recoil);
      float("反伤 −" + recoil, source.x, source.y - 60, "#ffd1b0");
    }
    if (!generated.has(m.id) && !m.r3 && !animations.enabled) {
      // The enabled animation adapter already owns this contact's hollow burst.
      // Keep the classic particles/solid flash only in the explicit old-renderer mode.
      particles(target.x, target.y - 16 - visualLift(target), m.color, 12);
      fx("impact", target.x, target.y - 16 - visualLift(target), "#fff9df", { life: 0.15 });
    }
    tone("hit");
    return real > 0;
  }
  function impact(p, a, target) {
    const m = a.move || MOVES[a.id],
      ux = Math.cos(a.aim),
      uy = Math.sin(a.aim);
    if (m.kind === "splash") {
      p.splashes++;
      return; // 无命中、伤害、顿帧、击退或攻击音效。
    }
    if (m.cleanse) {
      p.slow = 0;
      statuses.clear(p);
      float("解除异常", p.x, p.y - 60, "#d9ffd3");
    }
    if (generated.emit(p, a, target, generatedAPI())) return;
    if (["shot", "fan"].includes(m.kind)) {
      const count = m.kind === "fan" ? m.count || 3 : 1;
      for (let i = 0; i < count; i++) {
        const angle = a.aim + (i - (count - 1) / 2) * 0.16,
          x = p.x + Math.cos(angle) * 24,
          y = p.y + Math.sin(angle) * 24;
        if (!clearLine(p.x, p.y, x, y, Math.min(m.radius, 7))) {
          particles(x, y - 16, m.color, 3);
          continue;
        }
        bullets.push({
          id: ++serial,
          x,
          y,
          ux: Math.cos(angle),
          uy: Math.sin(angle),
          speed: m.speed,
          range: m.range,
          age: 0,
          owner: p,
          m,
          group: a.group,
          airFrom: visualLift(p),
          airTo: generatedAPI().projectileLift(target, m),
          airDistance: Math.max(1, hypot(target.x - p.x, target.y - p.y) - 24),
        });
      }
      p.shots++;
      tone("shot");
    } else if (m.kind === "melee" || m.kind === "spin") {
      p.punches++;
      fx(m.kind === "spin" ? "spin" : "slash", p.x, p.y - 16, m.color, {
        a: a.aim,
        radius: m.range * 0.75,
        life: 0.24,
        contactGroup: a.group,
      });
      const dx = target.x - p.x,
        dy = target.y - p.y,
        d = hypot(dx, dy),
        dot = d ? (dx * ux + dy * uy) / d : 1;
      if (
        d <= bodies.meleeRange(target, m.range, dx, dy, p) &&
        (m.kind === "spin" || dot > 0.42) &&
        clearLine(p.x, p.y, target.x, target.y, 2)
      )
        damage(target, p, m, ux, uy, a.group);
      tone("hit");
    } else if (m.kind === "beam") {
      const end = rayEnd(p.x, p.y, a.aim, m.range, 5);
      fx("beam", p.x, p.y - 16, m.color, {
        ex: end.x,
        ey: end.y - 16,
        life: 0.22,
        width: m.damage > 30 ? 18 : 11,
        contactGroup: a.group,
      });
      if (
        Number.isFinite(bodies.segment(target, p.x, p.y, end.x, end.y, 6)) &&
        clearLine(p.x, p.y, target.x, target.y, 3)
      )
        damage(target, p, m, ux, uy, a.group);
      p.shots++;
      tone("shot");
    } else if (m.kind === "zone") {
      const end = telegraph.landing(p, m, a.aim, target, warningAPI());
      zones.push({
        x: clamp(end.x, B.left, B.right),
        y: clamp(end.y, B.top, B.bottom),
        m,
        owner: p,
        age: 0,
        delay: m.delay,
        group: a.group,
        radius: m.radius,
        alive: true,
      });
      tone("shot");
    } else if (m.kind === "nova") {
      fx("nova", p.x, p.y - 10, m.color,
        { radius: m.range, life: 0.45, contactGroup: a.group });
      if (bodies.circle(target, p.x, p.y, m.range) && clearLine(p.x, p.y, target.x, target.y, 3)) {
        const d = hypot(target.x - p.x, target.y - p.y) || 1;
        damage(target, p, m, (target.x - p.x) / d, (target.y - p.y) / d, a.group);
      }
      tone("shot");
    } else if (m.kind === "guard") {
      p.shield = m.damage;
      p.shieldUntil = elapsed + m.duration;
      fx("guard", p.x, p.y, m.color, { life: 0.35 });
      tone("guard");
    } else if (m.kind === "heal") heal(p, m.damage);
    else if (m.kind === "buff") {
      p.buffs[m.boost] = m.duration;
      float(m.name, p.x, p.y - 58, m.color);
      fx("power", p.x, p.y, m.color, { life: 0.6 });
      tone("heal");
    } else if (m.kind === "rush") tone("dash");
  }
  function baseUpdate(p, dt) {
    if (!statuses.frozen(p)) jump.tick(p, dt);
    p.lastX = p.x;
    p.lastY = p.y;
    p.moving = false;
    for (const id of p.moves) p.cool[id] = Math.max(0, (p.cool[id] || 0) - dt);
    p.dashCool = Math.max(0, p.dashCool - dt);
    p.immune = Math.max(0, p.immune - dt);
    if (p.hurt > 0) {
      p.hurt = Math.max(0, p.hurt - dt);
      p.hurtAge += dt;
    }
    p.slow = Math.max(0, p.slow - dt);
    for (const k of ["speed", "power"]) p.buffs[k] = Math.max(0, p.buffs[k] - dt);
    if (p.shieldUntil <= elapsed) p.shield = 0;
    const delay = p.rest;
    p.rest = Math.max(0, delay - dt);
    p.stamina = Math.min(100, p.stamina + Math.max(0, dt - delay) * CONFIG.regen);
    if (!statuses.blocked(p)) feel.move(p, dt, translatePet);
    statuses.tick(p, dt);
  }
  function movePet(p, dx, dy, dt) {
    if (statuses.blocked(p) || p.landLeft > 1e-7) return;
    if (p === player && phase === "playing" && (dx || dy || p.dash)) evt.firstInput();
    if (p.dash) {
      const d = p.dash,
        t = Math.max(0, Math.min(dt, CONFIG.dashDuration - d.age));
      translatePet(p, d.dx * CONFIG.dashSpeed * t, d.dy * CONFIG.dashSpeed * t);
      d.age += dt;
      p.ghostTime -= dt;
      if (p.ghostTime <= 0) {
        ghosts.push({
          x: p.x,
          y: p.y,
          a: p.a,
          age: 0,
          p,
          name: "dash",
          time: (d.age / CONFIG.dashDuration) * ART[p.id].dash.totalDuration,
        });
        p.ghostTime = 0.035;
      }
      if (d.age >= CONFIG.dashDuration) p.dash = null;
    } else if (
      p.attack?.kind === "rush" &&
      p.attack.age >= p.attack.hitTime &&
      p.attack.age < p.attack.hitTime + rushDuration(p.attack.move || MOVES[p.attack.id])
    ) {
      const a = p.attack,
        t = Math.max(0, Math.min(dt, a.hitTime + rushDuration(a.move || MOVES[a.id]) - a.age)),
        speed = (a.move || MOVES[a.id]).rushSpeed || 630;
      const ox = p.x,
        oy = p.y;
      translatePet(p, Math.cos(a.aim) * speed * t, Math.sin(a.aim) * speed * t);
      if ((a.move?.hero || a.move?.r3) && hypot(p.x - ox, p.y - oy) + 0.1 < speed * t) {
        a.duration = a.age + dt;
        generated.states = generated.states.filter((e) => e.group !== a.group);
      }
      p.ghostTime -= dt;
      if (p.ghostTime <= 0) {
        ghosts.push({ x: p.x, y: p.y, a: p.a, age: 0, p, name: "melee", time: 0.12,
          heroQuick: animations.hero.uses(a.id, p) && a.id === "quickattack" });
        p.ghostTime = 0.04;
      }
    } else if ((dx || dy) && p.attack?.kind !== "splash") {
      const speed =
        p.speed * jump.speed(p) * statuses.speed(p) *
        (p === player && aim.hold?.active ? 0.6 : 1) *
        (p.buffs.speed > 0 ? 1.3 : 1) *
        (p.slow > 0 || (p.hurt > 0 && p.hurtAge < 0.2) ? 0.65 : 1) *
        (p.attack
          ? p.attack.kind === "heal"
            ? 0.5
            : ["melee", "spin"].includes(p.attack.kind) || p.attack.move?.limb
              ? 0.75
              : 0.9
          : 1);
      translatePet(p, dx * speed * dt, dy * speed * dt);
      p.moving = true;
      if (!p.attack) p.a = Math.atan2(dy, dx);
    }
    constrain(p);
  }
  function updateAttack(p, target, dt) {
    if (!p.attack || statuses.blocked(p)) return;
    const a = p.attack,
      m = a.move || MOVES[a.id];
    a.age += dt;
    if (!a.emitted && a.age + 1e-9 >= a.hitTime) {
      a.emitted = true;
      impact(p, a, target);
    }
    if (
      m.kind === "rush" &&
      a.emitted &&
      (a.id !== "surf" || !m.r3 || generated.waveReached(p, target, m, a.aim, generatedAPI())) &&
      a.age < a.hitTime + rushDuration(m) &&
      Number.isFinite(
        bodies.segment(
          target,
          p.lastX,
          p.lastY,
          p.x,
          p.y,
          bodies.reach(p, -Math.sin(a.aim), Math.cos(a.aim)) + 4,
        ),
      ) &&
      clearLine(p.x, p.y, target.x, target.y, 2)
    )
      damage(target, p, m, Math.cos(a.aim), Math.sin(a.aim), a.group);
    if (a.age >= a.duration) {
      if (m.kind === "splash") {
        fx("splash", p.x, p.y + 13, "#9ce5ff", { life: 0.35 });
        float("但是什么也没有发生", p.x, headY(p, 12), "#e1f6ff", p);
      }
      p.attack = null;
    }
  }
  function animate(p, dt) {
    if (statuses.frozen(p)) {
      p.anim = p.status.pose.anim;
      p.animAge = p.status.pose.age;
      p.a = p.status.pose.a;
      p.motionX = p.motionY = 0;
      return;
    }
    let name = "idle",
      time = null;
    if (p.dash) {
      name = "dash";
      time = (p.dash.age / CONFIG.dashDuration) * ART[p.id].dash.totalDuration;
    } else if (p.hurt > 0) {
      name = "hurt";
      time = (p.hurtAge / (p.hurt + p.hurtAge)) * ART[p.id].hurt.totalDuration;
    } else if (p.attack) {
      name = p.attack.move?.animationRole ||
        (["melee", "rush", "spin"].includes(p.attack.kind) ? "melee" : "shoot");
      const a = p.attack,
        clip = ART[p.id][name],
        hit = clip.hitTime ?? clip.totalDuration * 0.5;
      time =
        a.age < a.hitTime
          ? (a.age / Math.max(0.001, a.hitTime)) * hit
          : hit +
            ((a.age - a.hitTime) / Math.max(0.001, a.duration - a.hitTime)) *
              (clip.totalDuration - hit);
    } else if (p.moving) name = "walk";
    if (name !== p.anim) {
      p.anim = name;
      p.animAge = 0;
    }
    p.animAge = time === null ? p.animAge + dt * (name === "walk" ? 1.5 : 1) : time;
    p.motionX = (p.x - p.lastX) / dt;
    p.motionY = (p.y - p.lastY) / dt;
  }
  const CELL = 40;
  let navGrid = null,
    navCols = 0,
    navRows = 0;
  function findPath(sx, sy, tx, ty, sourceLayer, targetLayer) {
    if (terrain) return terrain.findPath(sx, sy, tx, ty, sourceLayer, targetLayer);
    if (!navGrid) {
      navCols = Math.ceil(WORLD.width / CELL);
      navRows = Math.ceil(WORLD.height / CELL);
      navGrid = new Uint8Array(navCols * navRows);
      for (let y = 0; y < navRows; y++)
        for (let x = 0; x < navCols; x++)
          navGrid[y * navCols + x] = freeAt(x * CELL + CELL / 2, y * CELL + CELL / 2, 21) ? 1 : 0;
    }
    const point = (i) => ({
      x: (i % navCols) * CELL + CELL / 2,
      y: Math.floor(i / navCols) * CELL + CELL / 2,
    });
    const nearest = (x, y) => {
      let best = -1,
        d = Infinity;
      for (let i = 0; i < navGrid.length; i++)
        if (navGrid[i]) {
          const p = point(i),
            dd = (p.x - x) ** 2 + (p.y - y) ** 2;
          if (dd < d) {
            d = dd;
            best = i;
          }
        }
      return best;
    };
    const start = nearest(sx, sy),
      goal = nearest(tx, ty);
    if (start < 0 || goal < 0) return [];
    const count = navGrid.length,
      score = new Float64Array(count).fill(Infinity),
      parent = new Int32Array(count).fill(-1),
      closed = new Uint8Array(count),
      inOpen = new Uint8Array(count),
      open = [start];
    score[start] = 0;
    inOpen[start] = 1;
    const h = (i) =>
      hypot((i % navCols) - (goal % navCols), Math.floor(i / navCols) - Math.floor(goal / navCols));
    let found = false;
    while (open.length) {
      let bi = 0;
      for (let i = 1; i < open.length; i++)
        if (score[open[i]] + h(open[i]) < score[open[bi]] + h(open[bi])) bi = i;
      const at = open.splice(bi, 1)[0];
      inOpen[at] = 0;
      if (at === goal) {
        found = true;
        break;
      }
      closed[at] = 1;
      const x = at % navCols,
        y = Math.floor(at / navCols);
      for (const [dx, dy] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
        [1, 1],
        [-1, 1],
        [1, -1],
        [-1, -1],
      ]) {
        const nx = x + dx,
          ny = y + dy,
          ni = ny * navCols + nx;
        if (
          nx < 0 ||
          nx >= navCols ||
          ny < 0 ||
          ny >= navRows ||
          !navGrid[ni] ||
          closed[ni] ||
          (dx && dy && (!navGrid[y * navCols + nx] || !navGrid[ny * navCols + x]))
        )
          continue;
        const s = score[at] + (dx && dy ? Math.SQRT2 : 1);
        if (s < score[ni]) {
          score[ni] = s;
          parent[ni] = at;
          if (!inOpen[ni]) {
            open.push(ni);
            inOpen[ni] = 1;
          }
        }
      }
    }
    if (!found) return [];
    const path = [];
    for (let at = goal; at !== start && at >= 0; at = parent[at]) path.push(point(at));
    return path.reverse();
  }
  function navigateEnemy(tx, ty) {
    if (
      !terrain?.bridges?.navigation(enemy.x, enemy.y, tx, ty) &&
      !terrain?.seamLinks?.connects(enemy.x, enemy.y, tx, ty) &&
      clearLine(enemy.x, enemy.y, tx, ty, 23)
    ) {
      const d = hypot(tx - enemy.x, ty - enemy.y) || 1;
      return { x: (tx - enemy.x) / d, y: (ty - enemy.y) / d };
    }
    if (elapsed >= brain.pathAt || hypot(tx - brain.goalX, ty - brain.goalY) > 75) {
      const targetLayer = tx === player.x && ty === player.y ? player.onBridge : enemy.onBridge;
      brain.path = findPath(enemy.x, enemy.y, tx, ty, enemy.onBridge, targetLayer);
      brain.pathAt = elapsed + 0.65;
      brain.goalX = tx;
      brain.goalY = ty;
      brain.pathSearches++;
    }
    while (brain.path.length && (terrain?.waypointReached
      ? terrain.waypointReached(enemy, brain.path[0])
      : hypot(brain.path[0].x - enemy.x, brain.path[0].y - enemy.y) < 22))
      brain.path.shift();
    if (!brain.path.length) return { x: 0, y: 0 };
    if (ENV.type === "arena") {
      // A polling interval can travel farther than two 10px cells. Aim at the furthest
      // swept-clear waypoint rather than oscillating across a tiny already-passed cell.
      let ahead = 0;
      for (let i = 1; i < brain.path.length; i++) {
        const q = brain.path[i];
        if (hypot(q.x - enemy.x, q.y - enemy.y) > 120) break;
        if (clearLine(enemy.x, enemy.y, q.x, q.y, 26)) ahead = i;
      }
      brain.path.splice(0, ahead);
    }
    const goal = brain.path[0],
      d = hypot(goal.x - enemy.x, goal.y - enemy.y) || 1;
    return { x: (goal.x - enemy.x) / d, y: (goal.y - enemy.y) / d };
  }
  function available(p, id) {
    return (p.cool[id] || 0) <= 1e-6 && p.stamina >= MOVES[id].cost;
  }
  function dangerFor(p, t) {
    for (const b of bullets) {
      if (b.owner === p || b.age < t.reaction) continue;
      const dx = p.x - b.x,
        dy = p.y - b.y,
        along = dx * b.ux + dy * b.uy,
        cross = Math.abs(dx * b.uy - dy * b.ux);
      if (
        along > 0 &&
        along / b.speed < 0.3 &&
        cross < bodies.reach(p, -b.uy, b.ux) + b.m.radius + 3 &&
        clearLine(b.x, b.y, p.x, p.y, 3)
      )
        return { dx: -b.uy, dy: b.ux, projectile: true, m: b.m };
    }
    if (t.pressure >= 0.7)
      for (const z of zones)
        if (
          z.owner !== p &&
          z.age >= t.reaction &&
          z.delay - z.age < 0.4 &&
          bodies.circle(p, z.x, z.y, z.radius + 3)
        ) {
          const d = hypot(p.x - z.x, p.y - z.y) || 1;
          return { dx: (p.x - z.x) / d || 1, dy: (p.y - z.y) / d, m: z.m };
        }
    return jump.danger(p, p === player ? enemy : player, t, warnings(),
      generated.states, MOVES, bodies, clearLine);
  }
  function thinkEnemy(dt) {
    if (!aiEnabled || enemy.worldAbsent) {
      brain.mx = brain.my = 0;
      return;
    }
    if (
      stealth.think({
        player,
        enemy,
        brain,
        tier: profile.tier,
        navigate: navigateEnemy,
        reachable: (x, y) =>
          freeAt(x, y, bodies.foot(enemy), enemy.onBridge) &&
          (clearLine(enemy.x, enemy.y, x, y, bodies.foot(enemy), enemy.onBridge) ||
            findPath(enemy.x, enemy.y, x, y, enemy.onBridge, enemy.onBridge).length > 0),
      })
    )
      return;
    brain.poll -= dt;
    if (brain.poll > 0) return;
    const t = tier();
    brain.poll = t.poll;
    brain.decisions++;
    const dx = player.x - enemy.x,
      dy = player.y - enemy.y,
      d = hypot(dx, dy) || 1,
      ux = dx / d,
      uy = dy / d,
      line = clearLine(enemy.x, enemy.y, player.x, player.y, 7);
    brain.mx = brain.my = 0;
    if (statuses.blocked(enemy) || enemy.dash || enemy.hurt > 0 || jump.blocked(enemy)) return;
    if (elapsed > brain.turnAt) {
      brain.orbit = rand() < 0.5 ? 1 : -1;
      brain.turnAt = elapsed + 1.1 + rand() * 1.6;
    }
    const danger = dangerFor(enemy, t);
    if (traversal.tryAI(enemy, terrain, t.id, danger, rand)) {
      generated.states = generated.states.filter((e) => e.owner !== enemy);
      brain.mode = "潜水避招";
      return;
    }
    if (traversal.submerged(enemy, terrain)) {
      const nav = navigateEnemy(player.x, player.y);
      brain.mx = nav.x; brain.my = nav.y;
      return;
    }
    if (danger && elapsed >= brain.dodgeAfter && rand() < t.dodge) {
      if (jump.tryAI(enemy, danger, t, rand)) {
        brain.mode = "跳跃避招";
        brain.dodgeAfter = elapsed + 1.05;
        return;
      }
      let bx = danger.dx,
        by = danger.dy;
      const safe = (x, y) =>
        freeAt(enemy.x + x * 105, enemy.y + y * 105, 18, enemy.onBridge) &&
        clearLine(enemy.x, enemy.y, enemy.x + x * 105, enemy.y + y * 105, 20, enemy.onBridge);
      if (!safe(bx, by) && safe(-bx, -by)) {
        bx = -bx;
        by = -by;
      }
      if (safe(bx, by) && dash(enemy, bx, by)) {
        brain.dodgeDecisions++;
        brain.mode = "闪避反击";
        brain.dodgeAfter = elapsed + 0.5 + (1 - t.pressure) * 0.6;
        return;
      }
      const guard = enemy.moves.find((id) => MOVES[id].kind === "guard" && available(enemy, id));
      if (guard && t.pressure > 0.4 && beginAttack(enemy, guard, player)) {
        brain.defends++;
        brain.mode = "守住";
        return;
      }
    }
    if (enemy.attack) {
      brain.mx = -uy * brain.orbit * 0.4;
      brain.my = ux * brain.orbit * 0.4;
      return;
    }
    const retreat = enemy.stamina < t.reserve,
      hasMelee = enemy.moves.some((id) => ["melee", "rush", "spin"].includes(MOVES[id].kind)),
      engageDistance = Math.max(
        50,
        Math.min(
          175,
          Math.max(
            65,
            ...enemy.moves.map((id) =>
              ["guard", "heal", "buff"].includes(MOVES[id].kind) ? 0 : heroMove(enemy, MOVES[id]).range,
            ),
          ) * 0.72,
        ),
      );
    let mx = 0,
      my = 0;
    if (!line || d > 420) {
      const nav = navigateEnemy(player.x, player.y);
      mx = nav.x;
      my = nav.y;
      brain.mode = "绕路追击";
    } else if (retreat) {
      mx = -ux;
      my = -uy;
      brain.mode = "回体力";
    } else if (d > engageDistance || (hasMelee && d > 55 && t.pressure > 0.5)) {
      mx = ux * 0.9 - uy * brain.orbit * 0.22;
      my = uy * 0.9 + ux * brain.orbit * 0.22;
      brain.mode = player.hp < player.maxHP * 0.3 ? "追击收尾" : "压近";
    } else if (d < 65) {
      mx = -ux * 0.5 - uy * brain.orbit * 0.5;
      my = -uy * 0.5 + ux * brain.orbit * 0.5;
      brain.mode = "近身换招";
    } else {
      mx = -uy * brain.orbit;
      my = ux * brain.orbit;
      brain.mode = "侧移找角度";
    }
    let len = hypot(mx, my);
    if (len) {
      mx /= len;
      my /= len;
    }
    if (
      !freeAt(enemy.x + mx * 45, enemy.y + my * 45, 18, enemy.onBridge) ||
      !clearLine(enemy.x, enemy.y, enemy.x + mx * 45, enemy.y + my * 45, 20, enemy.onBridge)
    ) {
      const nav = navigateEnemy(player.x, player.y);
      mx = nav.x;
      my = nav.y;
    }
    brain.mx = mx;
    brain.my = my;
    if (
      d > 500 &&
      enemy.stamina > 60 &&
      t.pressure >= 0.7 &&
      rand() < t.pressure &&
      clearLine(enemy.x, enemy.y, enemy.x + mx * 108, enemy.y + my * 108, 22, enemy.onBridge) &&
      freeAt(enemy.x + mx * 108, enemy.y + my * 108, 18, enemy.onBridge) &&
      dash(enemy, mx, my)
    ) {
      brain.pursuitDashes++;
      brain.mode = "闪避追击";
      return;
    }
    if (elapsed < brain.attackAfter) return;
    let choice = null,
      best = -Infinity;
    for (const id of enemy.moves) {
      if (!available(enemy, id)) continue;
      const m = heroMove(enemy, MOVES[id]);
      let value = -Infinity;
      if (m.kind === "splash" && !retreat && !danger) value = 8;
      else if (m.kind === "heal" && enemy.hp < enemy.maxHP * 0.6 && (d > 155 || !line))
        value = 40 + (1 - enemy.hp / enemy.maxHP) * 40;
      else if (m.kind === "guard" && danger) value = 45 * t.pressure;
      else if (m.kind === "buff" && enemy.buffs[m.boost] <= 0 && d > 150) value = 12 * t.pressure;
      else if (line && !retreat && m.damage > 0 && !["guard", "heal", "buff"].includes(m.kind)) {
        const inRange = ["melee", "spin"].includes(m.kind)
          ? d <= bodies.meleeRange(player, m.range, dx, dy, enemy) * 0.92
          : m.kind === "nova"
            ? bodies.circle(player, enemy.x, enemy.y, m.range * 0.92)
            : m.kind === "rush"
              ? d < m.range + bodies.reach(player, dx, dy)
              : d < m.range * 0.94;
        if (inRange) {
          const mult = player.char.types.reduce(
              (v, type) =>
                v * (m.waterEffective && type === 11 ? 2 : (EFFICACY[m.type]?.[type] ?? 1)),
              1,
            ),
            power =
              m.damage *
              (m.execute && player.hp / player.maxHP <= 0.5 ? 1.6 : 1) *
              (m.venom && player.status?.id === "psn" ? 1.6 : 1) * statuses.power(enemy, m) *
              (m.lowHP ? 1 + 2 * (1 - enemy.hp / enemy.maxHP) : 1) *
              (m.hpScale ? 0.45 + (0.55 * enemy.hp) / enemy.maxHP : 1);
          value = mult ? (power * mult) / (0.5 + m.cd * 0.15) + rand() * 8 : -Infinity;
          if (!player.status && m.statuses) value += m.statuses.reduce((v, s) =>
            v + (window.PoightStatus.definitions[s.id].immune.some((t) =>
              player.char.types.includes(t)) ? 0 : s.chance * 0.1), 0);
          if (m.recoil && enemy.hp < power * mult * m.recoil) value -= 35 * t.pressure;
          if (m.kind === "zone" && t.pressure < 0.5) value -= 14;
          if (m.kind === "rush") value += t.pressure * 8;
          if (player.shield > 0 && m.breakShield) value += 35;
          if (player.hp <= power * mult) value += 24 * t.pressure;
        }
      }
      value = demo.moveWeight(m, value);
      if (value > best) {
        best = value;
        choice = id;
      }
    }
    if (choice && beginAttack(enemy, choice, player)) {
      brain.casts++;
      if (MOVES[choice].kind === "heal") brain.heals++;
      brain.attackAfter = elapsed + t.attackGap;
      brain.mode = MOVES[choice].kind === "heal" ? "回复" : MOVES[choice].name;
    }
  }
  function thinkTestPlayer(dt) {
    if (!balance?.playerTier) return;
    // Reuse the unchanged enemy policy, including aiming error and per-side brain.
    // Actor identity/isPlayer and projectile owners are never modified.
    const savedBrain = brain;
    [player, enemy] = [enemy, player];
    brain = balance.playerBrain;
    testTier = balance.playerTier;
    try {
      thinkEnemy(dt);
    } finally {
      balance.playerBrain = brain;
      brain = savedBrain;
      [player, enemy] = [enemy, player];
      testTier = null;
    }
  }
  function update(dt) {
    mobile?.orient();
    if (mobile?.blockedPortrait || !artReady || traversal.pending) return;
    if (phase === "playing") window.PoightFangs.presentationStep(generated, dt);
    if (phase === "playing") matchSeconds += dt;
    aim.tick(dt);
    dt = feel.tick(dt, profile.shake);
    if (phase !== "playing" || dt < 1e-8) return;
    inputClock += dt;
    feel.flushDash(requestDash);
    traversal.updateWarps(dt, player, enemy, terrain, traverseWarp, bodies.foot);
    if (traversal.pending) return;
    for (const p of [player, enemy]) traversal.tick(p, dt, terrain);
    // M4 hitstop subsumes B1's two-frame pause; do not stack two simulation clocks.
    generated.fangPause = 0;
    elapsed += dt;
    animations.step(dt);
    jump.step(dt);
    stealth.update(elapsed, player, enemy);
    if (stealth.hidden(player) && enemy.attack && !enemy.attack.emitted) enemy.attack = null;
    terrain?.updateGrass(dt, [player, enemy]);
    baseUpdate(player, dt);
    if (!enemy.worldAbsent) baseUpdate(enemy, dt);
    if (player.hp <= 0 || enemy.hp <= 0) {
      finishMatch();
      return;
    }
    if (dashMemory) {
      if (dashMemory.until < inputClock - 1e-6) dashMemory = null;
      else if (dash(player, dashMemory.dx, dashMemory.dy)) dashMemory = null;
    }
    if (queued && queued.until < inputClock - 1e-6) {
      rejectCast(queued.slot, castRefusal(queued.slot) || queued.reason);
      queued = null;
    }
    if (queued && beginAttack(player, player.moves[queued.slot], enemy, queued.angle)) {
      blockedHeld.delete(queued.slot);
      queued = null;
    }
    thinkTestPlayer(dt);
    thinkEnemy(dt);
    const v = balance?.playerTier
      ? { x: balance.playerBrain.mx, y: balance.playerBrain.my }
      : moveVector();
    movePet(player, v.x, v.y, dt);
    if (!enemy.worldAbsent) movePet(enemy, brain.mx, brain.my, dt);
    stealth.update(elapsed, player, enemy);
    updateAttack(player, enemy, dt);
    updateAttack(enemy, player, dt);
    generated.step(dt, generatedAPI());
    for (let i = bullets.length - 1; i >= 0; i--) {
      const b = bullets[i],
        ox = b.x,
        oy = b.y,
        dist = b.m.hero || b.m.batch2 || b.m.r3 ? Math.min(b.range, b.speed * dt) : b.speed * dt;
      b.x += b.ux * dist;
      b.y += b.uy * dist;
      b.range -= dist;
      b.age += dt;
      let blocked = Infinity;
      for (const o of mapObstacles(ox, oy, b.x, b.y, Math.min(b.m.radius, 7)))
        blocked = Math.min(blocked, segmentBox(ox, oy, b.x, b.y, o, Math.min(b.m.radius, 7)));
      const target = b.owner === player ? enemy : player,
        contact = jump.canHit(target, b.m) && traversal.canHit(target, b.m, terrain)
          ? bodies.segment(target, ox, oy, b.x, b.y, b.m.radius) : Infinity;
      if (Number.isFinite(contact) && contact < blocked) {
        const point = { x: lerp(ox, b.x, contact), y: lerp(oy, b.y, contact) },
          lift = lerp(b.airFrom || 0, b.airTo || 0,
            clamp((b.age * b.speed) / (b.airDistance || 1), 0, 1));
        animations.projectileContact(b, point, lift, generatedAPI());
        damage(target, b.owner, b.m, b.ux, b.uy, b.group,
          { x: point.x, y: point.y - 16 - lift });
        bullets.splice(i, 1);
        continue;
      }
      if (Number.isFinite(blocked)) {
        animations.hero.projectileContact(b,
          { x: lerp(ox, b.x, blocked), y: lerp(oy, b.y, blocked) },
          lerp(b.airFrom || 0, b.airTo || 0,
            clamp((b.age * b.speed) / (b.airDistance || 1), 0, 1)), generatedAPI(), true);
        if (!generated.has(b.m.id))
          particles(lerp(ox, b.x, blocked), lerp(oy, b.y, blocked) - 16, b.m.color, 4);
        bullets.splice(i, 1);
        continue;
      }
      if (b.m.batch2 && b.m.returning && !b.returned && b.range <= b.m.range / 2) {
        b.ux *= -1;
        b.uy *= -1;
        b.returned = true;
      }
      if (b.range <= 0 || b.x < 25 || b.x > WORLD.width - 25 || b.y < 45 || b.y > WORLD.height - 30)
        bullets.splice(i, 1);
    }
    for (let i = zones.length - 1; i >= 0; i--) {
      const z = zones[i];
      z.age += dt;
      if (z.age >= z.delay) {
        const target = z.owner === player ? enemy : player,
          dx = target.x - z.x,
          dy = target.y - z.y,
          d = hypot(dx, dy) || 1;
        if (bodies.circle(target, z.x, z.y, z.radius) && clearLine(z.x, z.y, target.x, target.y, 3))
          damage(target, z.owner, z.m, dx / d, dy / d, z.group);
        fx("nova", z.x, z.y - 10, z.m.color,
          { radius: z.radius, life: 0.5, contactGroup: z.group });
        particles(z.x, z.y - 16, z.m.color, 18, z.group);
        zones.splice(i, 1);
      }
    }
    for (let i = effects.length - 1; i >= 0; i--) {
      const e = effects[i];
      e.age += dt;
      if (e.kind === "particle") {
        e.x += e.vx * dt;
        e.y += e.vy * dt;
        e.vy += 140 * dt;
      }
      if (e.age >= e.life) effects.splice(i, 1);
    }
    for (let i = floats.length - 1; i >= 0; i--) {
      floats[i].age += dt;
      if (floats[i].age > 0.8) floats.splice(i, 1);
    }
    for (let i = ghosts.length - 1; i >= 0; i--) {
      ghosts[i].age += dt;
      if (ghosts[i].age > 0.16) ghosts.splice(i, 1);
    }
    stealth.update(elapsed, player, enemy);
    animate(player, dt);
    animate(enemy, dt);
    updateActorHUD(player);
    updateActorHUD(enemy);
    updateCamera(dt);
    finishMatch();
  }
  const ground = document.createElement("canvas"),
    groundCtx = ground.getContext("2d");
  function prepareGround() {
    ground.width = terrain ? environmentImages.ground.naturalWidth : WORLD.width;
    ground.height = terrain ? environmentImages.ground.naturalHeight : WORLD.height;
    groundCtx.imageSmoothingEnabled = false;
    groundCtx.drawImage(environmentImages.ground, 0, 0, ground.width, ground.height);
  }
  function directionRow(a) {
    return ((Math.round((a - Math.PI / 2) / (Math.PI / 4)) % 8) + 8) % 8;
  }
  function animationFrame(id, name, time) {
    const d = ART[id][name],
      loop = name === "idle" || name === "walk";
    let t = loop ? time % d.totalDuration : clamp(time, 0, Math.max(0, d.totalDuration - 0.000001));
    for (let i = 0; i < d.durations.length; i++) {
      if (t < d.durations[i]) return i;
      t -= d.durations[i];
    }
    return d.frames - 1;
  }
  function flightHeight(p) {
    if (traversal.swimming(p, terrain)) return p.jumpHeight || 0;
    const hop =
      p.attack?.kind === "splash"
        ? Math.sin(clamp((p.attack.age - p.attack.hitTime) /
          (p.attack.move || MOVES[p.attack.id]).recovery, 0, 1) * Math.PI) * 28
        : 0;
    return (
      (p.char.flightHeight && p.hp > 0
        ? p.char.flightHeight + Math.sin(elapsed * 4 + p.id) * 2
        : 0) + hop + (p.jumpHeight || 0)
    );
  }
  function visualLift(p) {
    return (p.jumpHeight || 0) + (p.char.flightHeight && p.hp > 0
      ? Math.max(0, flightHeight(p) - (p.jumpHeight || 0) - 30) : 0);
  }
  function headY(p, margin = 0) {
    if (traversal.submerged(p, terrain)) return p.y - 70 - margin;
    return p.y - (p.char.body?.top ?? 41) - flightHeight(p) - margin;
  }
  function spriteDraw(p, x = p.x, y = p.y, a = p.a, name = p.anim, time = p.animAge, alpha = 1) {
    const d = ART[p.id][name],
      im = p.images[name];
    if (!im || stealth.invisible(p)) return;
    const row = d.rows === 1 ? 0 : directionRow(limbFacing(p, a)),
      pose =
        p.attack?.emitted &&
        !p.char.moveAnchors?.[p.attack?.move?.anchor] &&
        row === 6 &&
        ((p.id === 6 && ["flamethrower", "fireblast"].includes(p.attack.id)) ||
          (p.id === 7 && p.attack.id === "watergun")),
      col = pose && name === "shoot" ? Math.min(5, d.frames - 1) : animationFrame(p.id, name, time),
      scale = p.char.scale,
      poseOffset = p.attack?.move?.limb && name === "melee"
        ? p.char.moveAnchors["r1-body"].poseOffsets[row][col]
        : [0, 0];
    ctx.save();
    const meleePose = animations.melee.pose(p);
    ctx.translate(meleePose.x, meleePose.y);
    const pose3 = window.PoightRevision3.pose(p);
    ctx.globalAlpha = alpha * stealth.alpha(p) * pose3.alpha;
    if (p.attack?.move?.r3) {
      const cx = x, cy = y - p.char.body.nominalSize * 0.38;
      ctx.translate(cx, cy - pose3.lift);
      ctx.rotate(pose3.angle);
      ctx.scale(1, pose3.squash);
      ctx.translate(-cx, -cy);
    }
    statuses.bodyBox(p, im, d, row, col,
      Math.round(x - (d.anchorX + (d.bodyOffsets?.[row]?.[col]?.[0] || 0) + poseOffset[0]) * scale),
      Math.round(y + 14 -
        (d.anchorY + (d.bodyOffsets?.[row]?.[col]?.[1] || 0) + poseOffset[1]) * scale -
        flightHeight(p)));
    ctx.filter = statuses.filter(p);
    if (!p.status && p.hurt > 0.08 && alpha === 1 && !animations.hero.shocks.has(p) &&
      !animations.colorGuard.has(p))
      ctx.filter = "brightness(1.65)";
    const frameArgs = [
      statuses.sprite(p, im),
      col * d.frameWidth,
      row * d.frameHeight,
      d.frameWidth,
      d.frameHeight,
      Math.round(x - (d.anchorX + (d.bodyOffsets?.[row]?.[col]?.[0] || 0) + poseOffset[0]) * scale),
      Math.round(
        y + 14 -
          (d.anchorY + (d.bodyOffsets?.[row]?.[col]?.[1] || 0) + poseOffset[1]) * scale -
          flightHeight(p),
      ),
      d.frameWidth * scale,
      d.frameHeight * scale,
    ];
    ctx.drawImage(...frameArgs);
    if (alpha === 1) {
      animations.captureContactFrame(ctx, p, d.contactBounds[row][col], ...frameArgs);
      animations.drawFrost(ctx, p, ...frameArgs);
      animations.hero.electrify(ctx, p, ...frameArgs);
    }
    ctx.restore();
  }
  function ring(x, y, r, color, width = 2, alpha = 1) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    for (let i = 0; i <= 24; i++) {
      const a = (i / 24) * TAU,
        px = Math.round(x + Math.cos(a) * r),
        py = Math.round(y + Math.sin(a) * r * 0.52);
      if (i) ctx.lineTo(px, py);
      else ctx.moveTo(px, py);
    }
    ctx.stroke();
    ctx.restore();
  }
  function petDraw(p) {
    const visual = window.PoightSeams.visual(p);
    ctx.save();
    ctx.translate(visual.x - p.x, visual.y - p.y);
    petDrawAt(p);
    ctx.restore();
  }
  function petDrawAt(p) {
    if (stealth.invisible(p)) return;
    if (!p.jump && traversal.drawActor(ctx, p, terrain, elapsed, bodies.foot(p),
      (y) => spriteDraw(p, p.x, y))) return;
    ctx.save();
    ctx.globalAlpha = stealth.alpha(p);
    const foot = bodies.foot(p),
      shape = bodies.shape(p);
    ctx.fillStyle = flightHeight(p) ? "#183a4938" : "#244f4932";
    ctx.beginPath();
    ctx.ellipse(Math.round(p.x), Math.round(p.y + 12),
      foot * jump.shadow(p), foot * 0.4 * jump.shadow(p), 0, 0, TAU);
    ctx.fill();
    ring(p.x, p.y + 13, foot + 5, p === player ? "#2f8dbe" : "#c78745", 2, 0.8);
    spriteDraw(
      p,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      p.hp <= 0 ? 0.42 : p.attack && MOVES[p.attack.id].phaseRush && protectedNow(p) ? 0.35 : 1,
    );
    if (p.shield > 0 && !generated.shown(p, "protect")) {
      ctx.save();
      ctx.fillStyle = "#d9ffbf24";
      ctx.strokeStyle = "#e0ffd2";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y - 12 - visualLift(p), Math.max(shape.rx, shape.ry) + 17, 0, TAU);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
    if (p.buffs.speed > 0 || p.buffs.power > 0)
      ring(p.x, p.y + 10, 29, p.buffs.power > 0 ? "#ffc576" : "#bdbcf7", 2, 0.65);
    if (p.slow > 0) {
      ctx.fillStyle = "#d3ffff";
      ctx.fillRect(p.x - 15, p.y + 5, 4, 6);
      ctx.fillRect(p.x + 11, p.y + 8, 4, 5);
    }
    statuses.draw(ctx, p, visualLift(p));
    ctx.restore();
  }
  // HUD state is presentation-only; combat resources and body geometry stay unchanged.
  function updateActorHUD(p) {
    let h = actorHUD.get(p);
    if (!h) {
      h = {
        hp: p.hp,
        trail: p.hp,
        damagedAt: -Infinity,
        stamina: p.stamina,
        spent: p.spent,
        spentAt: elapsed,
        alpha: 1,
        updatedAt: elapsed,
      };
      actorHUD.set(p, h);
    }
    if (p.hp < h.hp) {
      h.trail = Math.max(h.hp, hudTrail(p, h));
      h.damagedAt = elapsed;
    } else if (p.hp > h.hp) h.trail = Math.max(h.trail, p.hp);
    if (p.spent > h.spent || p.stamina < h.stamina) h.spentAt = elapsed;
    const dt = Math.max(0, elapsed - h.updatedAt),
      visible = p.stamina < 100 - 1e-6 || elapsed - h.spentAt < 1.5;
    h.alpha = clamp(h.alpha + ((visible ? 1 : -1) * dt) / 0.2, 0, 1);
    h.hp = p.hp;
    h.stamina = p.stamina;
    h.spent = p.spent;
    h.updatedAt = elapsed;
    return h;
  }
  function hudTrail(p, h) {
    return lerp(h.trail, p.hp, clamp((elapsed - h.damagedAt - 0.45) / 0.35, 0, 1));
  }
  function hudGeometry(p) {
    const r = renderRect(),
      sx = r.width / W,
      sy = r.height / H,
      h = updateActorHUD(p),
      x = p.x,
      y = headY(p, 10),
      width = 48 / sx,
      height = 6 / sy;
    return {
      x,
      y,
      width,
      height,
      sx,
      sy,
      ratio: p.hp / p.maxHP,
      trailRatio: hudTrail(p, h) / p.maxHP,
      color: p.hp / p.maxHP > 0.5 ? "#48d878" : p.hp / p.maxHP >= 0.2 ? "#f4cb48" : "#ef5b58",
      staminaY: battleHUD.mode === "2"
        ? y + (traversal.submerged(p, terrain) ? 16 : 9) / sy
        : p.y + 13 + (bodies.foot(p) + 5) * 0.52 + 5 / sy,
      staminaAlpha: battleHUD.mode === "2" ? 1 : h.alpha,
      oxygen: traversal.submerged(p, terrain) ? {
        x: x - width / 2, y: y + height / 2 + 4 / sy,
        width, height: 4 / sy, ratio: p.diveLeft / window.PoightTraversal.parameters.oxygen,
      } : null,
    };
  }
  function hudScreenBox(x, y, width, height) {
    const r = renderRect();
    return {
      x: ((x - (ENV.type === "arena" ? camera.x : Math.round(camera.x))) * r.width) / W,
      y: ((y - (ENV.type === "arena" ? camera.y : Math.round(camera.y))) * r.height) / H,
      width: (width * r.width) / W,
      height: (height * r.height) / H,
    };
  }
  function drawLabel(p) {
    if (demo.enabled && !demo.bars) return;
    if (p.worldAbsent || stealth.invisible(p)) return;
    const h = hudGeometry(p),
      left = h.x - h.width / 2,
      top = h.y - h.height / 2;
    ctx.save();
    ctx.fillStyle = "#182632";
    ctx.fillRect(left - 1 / h.sx, top - 1 / h.sy, h.width + 2 / h.sx, h.height + 2 / h.sy);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(left, top, h.width * h.trailRatio, h.height);
    ctx.fillStyle = h.color;
    ctx.fillRect(left, top, h.width * h.ratio, h.height);
    if (h.oxygen) {
      const o = h.oxygen;
      ctx.fillStyle = "#182632";
      ctx.fillRect(o.x - 1 / h.sx, o.y - 1 / h.sy, o.width + 2 / h.sx, o.height + 2 / h.sy);
      ctx.fillStyle = "#9ff3ff";
      ctx.fillRect(o.x, o.y, o.width * o.ratio, o.height);
    }
    const tagWidth = (gba.enabled ? (p === player ? 24 : 32) : (p === player ? 18 : 25)) / h.sx,
      tagHeight = gba.enabled ? 16 : 12;
    ctx.fillStyle = p === player ? "#246cb5" : "#b83d4c";
    ctx.fillRect(left - tagWidth - 2 / h.sx, h.y - tagHeight / 2 / h.sy, tagWidth, tagHeight / h.sy);
    ctx.font = `bold ${(gba.enabled ? 12 : 8) / h.sy}px system-ui`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(p === player ? "1P" : "CPU", left - tagWidth / 2 - 2 / h.sx, h.y);
    if (p === player && h.staminaAlpha > 0 && ["0", "2"].includes(battleHUD.mode)) {
      const overhead = battleHUD.mode === "2",
        width = overhead ? 48 : 36,
        height = overhead ? 6 : 3;
      ctx.globalAlpha = h.staminaAlpha;
      ctx.fillStyle = "#182632";
      ctx.fillRect(p.x - (width / 2 + 1) / h.sx, h.staminaY - 1 / h.sy,
        (width + 2) / h.sx, (height + 2) / h.sy);
      ctx.fillStyle = overhead ? "#ffd45e" : "#57ddd9";
      ctx.fillRect(p.x - width / 2 / h.sx, h.staminaY,
        width / h.sx * p.stamina / 100, height / h.sy);
      if (overhead) {
        ctx.font = `bold ${8 / h.sy}px system-ui`;
        ctx.fillText("SP", left - 12 / h.sx, h.staminaY + 3 / h.sy);
      }
    }
    ctx.globalAlpha = 1;
    statuses.label(ctx, p, h);
    battleHUD.drawHint(ctx, p, h, p.attack ? MOVES[p.attack.id] : null);
    ctx.restore();
  }
  function floatLayouts() {
    const r = renderRect(),
      sx = r.width / W,
      sy = r.height / H,
      occupied = [player, enemy].filter(Boolean).map((p) => {
        const h = hudGeometry(p);
        const height = battleHUD.mode === "2" && p === player
          ? (h.oxygen ? 31 : 24) : (h.oxygen ? 22 : 14);
        const pad = gba.enabled ? 36 : 29;
        return hudScreenBox(h.x - h.width / 2 - pad / sx, h.y - (gba.enabled ? 9 : 7) / sy,
          h.width + pad / sx, Math.max(height, gba.enabled ? 18 : height) / sy);
      }),
      layouts = [];
    const overlaps = (a, b) =>
      a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
    for (const f of floats) {
      ctx.font = `bold ${12 / sy}px system-ui`;
      const mainWidth = ctx.measureText(f.text).width;
      ctx.font = `bold ${(gba.enabled ? 12 : 9) / sy}px system-ui`;
      const suffixWidth = f.suffix ? ctx.measureText(f.suffix).width + 4 / sx : 0,
        width = mainWidth + suffixWidth,
        x = f.x + (f.slot ? (f.slot % 2 ? -10 : 10) / sx : 0),
        y = f.y - (f.age * 33 + f.slot * 22) / sy,
        box = hudScreenBox(x - width / 2 - 2 / sx, y - 9 / sy, width + 4 / sx, 18 / sy);
      // Reserve complete outlined boxes, including suffixes and both HP tags.
      while (occupied.some((b) => overlaps(box, b))) box.y -= 20;
      occupied.push(box);
      layouts.push({
        f,
        box,
        mainWidth,
        width,
        x: box.x / sx + Math.round(camera.x) + 2 / sx,
        y: (box.y + 9) / sy + Math.round(camera.y),
        sx,
        sy,
      });
    }
    return layouts;
  }
  function drawFloats() {
    ctx.save();
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.strokeStyle = "#182632";
    for (const q of floatLayouts()) {
      const f = q.f;
      ctx.globalAlpha = Math.min(1, (0.8 - f.age) * 4);
      ctx.lineWidth = 3 / q.sy;
      ctx.font = `bold ${12 / q.sy}px system-ui`;
      ctx.strokeText(f.text, q.x, q.y);
      ctx.fillStyle = f.color;
      ctx.fillText(f.text, q.x, q.y);
      if (f.suffix) {
        const x = q.x + q.mainWidth + 4 / q.sx;
        ctx.font = `bold ${(gba.enabled ? 12 : 9) / q.sy}px system-ui`;
        ctx.strokeText(f.suffix, x, q.y);
        ctx.fillStyle = f.suffix.includes("拔群") ? "#ffe16b" : "#cbd0d7";
        ctx.fillText(f.suffix, x, q.y);
      }
    }
    ctx.restore();
  }
  function drawBullet(b) {
    const lift = lerp(
      b.airFrom || 0,
      b.airTo || 0,
      clamp((b.age * b.speed) / (b.airDistance || 1), 0, 1),
    );
    if (generated.bullet(ctx, b, lift, generatedAPI())) return;
    const x = Math.round(b.x),
      y = Math.round(
        b.y -
          16 -
          lerp(b.airFrom || 0, b.airTo || 0, clamp((b.age * b.speed) / (b.airDistance || 1), 0, 1)),
      ),
      r = b.m.radius;
    ctx.save();
    for (let i = 4; i >= 1; i--) {
      ctx.globalAlpha = (1 - i / 5) * 0.7;
      ctx.fillStyle = b.m.color;
      const s = Math.max(2, r - i);
      ctx.fillRect(
        Math.round(x - b.ux * i * 6) - s / 2,
        Math.round(y - b.uy * i * 6) - s / 2,
        s,
        s,
      );
    }
    ctx.globalAlpha = 1;
    ctx.translate(x, y);
    if (b.m.type === 12) {
      ctx.rotate(Math.atan2(b.uy, b.ux) + b.age * 9);
      ctx.fillStyle = "#356947";
      ctx.fillRect(-r, -3, r * 2, 6);
      ctx.fillStyle = b.m.color;
      ctx.fillRect(-r + 2, -5, r * 2 - 4, 8);
      ctx.fillStyle = "#e9ffb5";
      ctx.fillRect(-r + 3, -1, r * 2 - 6, 2);
    } else if (b.m.type === 13) {
      ctx.fillStyle = b.m.color;
      ctx.rotate(b.age * 15);
      ctx.fillRect(-r, -3, r * 2, 6);
      ctx.fillRect(-3, -r, 6, r * 2);
      ctx.fillStyle = "#fffbe0";
      ctx.fillRect(-3, -3, 6, 6);
    } else if (b.m.type === 10) {
      ctx.fillStyle = "#b9553f";
      ctx.fillRect(-r, -r + 2, r * 2, r * 2 - 4);
      ctx.fillStyle = b.m.color;
      ctx.fillRect(-r + 2, -r, r * 2 - 4, r * 2);
      ctx.fillStyle = "#fff4a9";
      ctx.fillRect(-3, -3, 6, 5);
    } else {
      ctx.fillStyle = b.m.color;
      ctx.fillRect(-r, -r + 3, r * 2, r * 2 - 6);
      ctx.fillRect(-r + 3, -r, r * 2 - 6, r * 2);
      ctx.fillStyle = "#f8ffff";
      ctx.fillRect(-r + 3, -r + 3, Math.max(3, r - 1), 3);
      if (b.m.id === "bubble") {
        ctx.globalAlpha = 0.65;
        ctx.clearRect(0, 0, 0, 0);
        ctx.strokeStyle = "#e2ffff";
        ctx.lineWidth = 2;
        ctx.strokeRect(-r + 2, -r + 2, r * 2 - 4, r * 2 - 4);
      }
    }
    ctx.restore();
  }
  function drawZone(z) {
    const t = z.age / z.delay;
    ctx.save();
    ctx.fillStyle = z.owner === player ? "#5baed62b" : "#ef974a32";
    ctx.strokeStyle = z.owner === player ? "#b7efff" : "#ffe1a0";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.arc(z.x, z.y - 10, z.radius, 0, TAU);
    ctx.fill();
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(z.x, z.y - 10, z.radius * t, -Math.PI / 2, -Math.PI / 2 + TAU * t);
    ctx.stroke();
    ctx.fillStyle = z.owner === player ? "#f0fbff" : "#fff1ce";
    ctx.font = "bold 10px system-ui";
    ctx.textAlign = "center";
    ctx.fillText(z.m.name, z.x, z.y - 12);
    ctx.restore();
  }
  function drawEffect(e) {
    const t = e.age / e.life;
    ctx.save();
    if (e.contactGroup?.hit.size) animations.clipContactCenters(ctx, e.contactGroup.hit);
    ctx.globalAlpha = Math.max(0, 1 - t);
    ctx.fillStyle = e.color;
    ctx.strokeStyle = e.color;
    ctx.lineWidth = 3;
    if (e.kind === "particle") ctx.fillRect(Math.round(e.x), Math.round(e.y), e.size, e.size);
    else if (e.kind === "impact") {
      const r = 8 + t * 18;
      for (let i = 0; i < 8; i++) {
        const a = (i * TAU) / 8;
        ctx.fillRect(
          Math.round(e.x + Math.cos(a) * r) - 2,
          Math.round(e.y + Math.sin(a) * r) - 2,
          5,
          5,
        );
      }
    } else if (e.kind === "beam") {
      ctx.lineCap = "square";
      ctx.lineWidth = e.width * (1 - t * 0.5);
      ctx.beginPath();
      ctx.moveTo(e.x, e.y);
      ctx.lineTo(e.ex, e.ey);
      ctx.stroke();
      ctx.strokeStyle = "#ffffe9";
      ctx.lineWidth = Math.max(2, e.width * 0.35);
      ctx.stroke();
    } else if (e.kind === "slash" || e.kind === "spin") {
      const a = e.kind === "spin" ? TAU : e.a + 0.85;
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(
        e.x,
        e.y,
        e.radius * 0.65 + e.radius * 0.35 * t,
        e.kind === "spin" ? 0 : e.a - 0.85,
        a,
      );
      ctx.stroke();
      ctx.strokeStyle = "#fff9d5";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(
        e.x,
        e.y,
        e.radius * 0.65 + e.radius * 0.35 * t - 4,
        e.kind === "spin" ? 0 : e.a - 0.75,
        a,
      );
      ctx.stroke();
    } else if (e.kind === "nova") {
      ctx.lineWidth = 7 * (1 - t) + 1;
      ctx.beginPath();
      ctx.arc(e.x, e.y, 8 + e.radius * t, 0, TAU);
      ctx.stroke();
      ctx.globalAlpha = (1 - t) * 0.22;
      ctx.fill();
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * TAU;
        ctx.globalAlpha = 1 - t;
        ctx.fillRect(
          Math.round(e.x + Math.cos(a) * e.radius * t) - 3,
          Math.round(e.y + Math.sin(a) * e.radius * t) - 3,
          6,
          6,
        );
      }
    } else if (e.kind === "splash") {
      const r = 9 + t * 19;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(e.x, e.y, r, r * 0.35, 0, 0, TAU);
      ctx.stroke();
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * TAU;
        ctx.fillRect(
          Math.round(e.x + Math.cos(a) * r) - 1,
          Math.round(e.y + Math.sin(a) * r * 0.35 - Math.sin(t * Math.PI) * 7) - 1,
          2,
          3,
        );
      }
    } else if (e.kind === "heal") {
      for (let i = 0; i < 4; i++) {
        const x = e.x + Math.sin(i * 5) * 22,
          y = e.y - 10 - t * 50 + i * 7;
        ctx.fillRect(x - 5, y - 1, 10, 3);
        ctx.fillRect(x - 1, y - 5, 3, 10);
      }
    } else ring(e.x, e.y + 5, 22 + t * 27, e.color, 3, 1 - t);
    ctx.restore();
  }
  function drawMiniMap() {
    if (ENV.type === "arena" || gba.enabled) {
      battleHUD.drawArenaMap(ctx, ground, player, enemy, camera, W, H, WORLD,
        renderRect(), stealth.invisible(enemy), demo.enabled);
      return;
    }
    if (W < 550 || H < 400) return;
    const w = 116,
      h = 72,
      x = W - w - 15,
      y = H - h - 18,
      ww = WORLD.width,
      wh = WORLD.height;
    ctx.fillStyle = "#f7f8e4e8";
    ctx.fillRect(x - 4, y - 4, w + 8, h + 8);
    ctx.drawImage(ground, 0, 0, ground.width, ground.height, x, y, w, h);
    for (const o of obstacles) {
      ctx.fillStyle = o.type === "rock" ? "#94765d" : "#3d8158";
      ctx.fillRect(
        x + (o.x / ww) * w,
        y + (o.y / wh) * h,
        Math.max(2, (o.w / ww) * w),
        Math.max(2, (o.h / wh) * h),
      );
    }
    ctx.strokeStyle = "#fffbe2";
    ctx.lineWidth = 1;
    ctx.strokeRect(x + (camera.x / ww) * w, y + (camera.y / wh) * h, (W / ww) * w, (H / wh) * h);
    for (const [p, c] of [
      [player, "#117faa"],
      [enemy, "#c15e45"],
    ]) {
      if (p.worldAbsent || stealth.invisible(p)) continue;
      ctx.fillStyle = c;
      ctx.fillRect(Math.round(x + (p.x / ww) * w) - 2, Math.round(y + (p.y / wh) * h) - 2, 4, 4);
    }
  }
  function overlay(title, detail, sub = "") {
    $("matchOverlay").hidden = false;
    setText($("matchTitle"), title);
    setText($("matchDetail"), detail);
    setText($("matchHint"), sub);
    $("matchHint").hidden = !sub;
  }
  function draw() {
    if ($("setup").open || phase === "playing") $("matchOverlay").hidden = true;
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = "#73cda4";
    ctx.fillRect(0, 0, W, H);
    if (gba.enabled && phase === "versus" && ground.width) {
      const scale = Math.max(W / ground.width, H / ground.height) * 1.13;
      ctx.drawImage(ground, (W - ground.width * scale) / 2,
        (H - ground.height * scale) / 2, ground.width * scale, ground.height * scale);
      return;
    }
    const screen = renderRect(),
      cx = demo.enabled || ENV.type === "arena" ? camera.x : Math.round(camera.x) - (feel.offset.x * W) / screen.width,
      cy = demo.enabled || ENV.type === "arena" ? camera.y : Math.round(camera.y) - (feel.offset.y * H) / screen.height;
    if (terrain) {
      ctx.fillStyle = "#21453f";
      ctx.fillRect(0, 0, W, H);
      terrain.draw(ctx, cx, cy, W, H, "ground");
    } else if (environmentImages.ground) {
      if (demo.enabled && ENV.type === "arena") demo.drawGround(ctx, ground, cx, cy, W, H);
      else ctx.drawImage(ground, cx, cy, W, H, 0, 0, W, H);
    }
    if (player && enemy && artReady) {
      ctx.save();
      ctx.translate(-cx, -cy);
      for (const z of zones) drawZone(z);
      stealth.drawGenerated(generated, ctx, "below", visualLift, generatedAPI());
      jump.draw(ctx);
      for (const q of ghosts) {
        // Quick Attack contact ghosts fade immediately; release/flight trails are unchanged.
        const victim = q.p === player ? enemy : player;
        if (q.heroQuick && animations.colorGuard.has(victim)) continue;
        spriteDraw(q.p, q.x, q.y, q.a, q.name, q.time,
          (1 - q.age / 0.16) * (q.heroQuick ? 0.56 : 0.28));
      }
      for (const s of warnings())
        telegraph.draw(ctx, s, s.player, s.remaining, s.aiming,
          [player, enemy].filter(Boolean).map((p) => {
            const h = hudGeometry(p);
            return { x: h.x - h.width / 2 - (gba.enabled ? 36 : 29) / h.sx,
              y: h.y - (gba.enabled ? 9 : 7) / h.sy,
              width: h.width + (gba.enabled ? 37 : 30) / h.sx,
              height: (h.oxygen ? 22 : gba.enabled ? 18 : 14) / h.sy };
          }));
      for (const p of [player, enemy])
        if (p.attack)
          generated.charge(ctx, p, p.attack.move || MOVES[p.attack.id], visualLift(p), generatedAPI());
      const order = [
        { y: player.y + 15, type: 0, p: player },
        { y: enemy.y + 15, type: 0, p: enemy },
        ...ENV.sprites.map((s) => ({ y: s.z, type: 2, p: s })),
        ...bullets.map((b) => ({ y: b.y, type: 1, p: b })),
      ].sort((a, b) => a.y - b.y);
      for (const o of order) {
        if (o.type === 0) {
          ctx.save();
          ctx.translate(window.PoightFangs.shake(generated, o.p), 0);
          if (!terrain?.bridges?.above(o.p)) petDraw(o.p);
          ctx.restore();
        } else if (o.type === 1) drawBullet(o.p);
        else {
          const s = o.p;
          if (
            s.x + s.w * s.scale >= cx &&
            s.x <= cx + W &&
            s.y + s.h * s.scale >= cy &&
            s.y <= cy + H
          )
            ctx.drawImage(
              environmentImages.objects,
              s.sx,
              s.sy,
              s.w,
              s.h,
              s.x,
              s.y,
              s.w * s.scale,
              s.h * s.scale,
            );
        }
      }
      stealth.drawGenerated(generated, ctx, "above", visualLift, generatedAPI());
      if (terrain) {
        ctx.save();
        ctx.translate(cx, cy);
        terrain.draw(ctx, cx, cy, W, H, "over");
        ctx.restore();
        // Original bridge metatiles live in the over layer; deck actors draw above it.
        for (const p of [player, enemy].sort((a, b) => a.y - b.y))
          if (terrain.bridges?.above(p)) petDraw(p);
        terrain.drawGrass(ctx, [player, enemy]);
        if (manual && args.get("arenaDebug") === "1") terrain.drawDebug?.(ctx);
      }
      stealth.draw(ctx, [player, enemy], elapsed);
      for (const e of effects) drawEffect(e);
      animations.draw(ctx);
      for (const p of [player, enemy]) drawLabel(p);
      if (!demo.enabled || !demo.hideHUD) drawFloats();
      ctx.restore();
      if (ENV.darkness) {
        ctx.fillStyle = `rgba(5, 10, 28, ${ENV.darkness})`;
        ctx.fillRect(0, 0, W, H);
      }
      if (!demo.enabled || !demo.hideHUD) drawMiniMap();
      if ((!demo.enabled || !demo.hideHUD) && ENV.type === "arena" && !stealth.invisible(enemy))
        battleHUD.drawEdge(ctx, enemy, camera, W, H, screen);
      if (
        ENV.type !== "arena" &&
        phase === "playing" && !enemy.worldAbsent &&
        !stealth.invisible(enemy) &&
        (enemy.x - cx < 0 || enemy.x - cx > W || enemy.y - cy < 0 || enemy.y - cy > H)
      ) {
        const ex = clamp(enemy.x - cx, 18, W - 18),
          ey = clamp(enemy.y - cy, 110 / viewScale, H - 110 / viewScale),
          a = Math.atan2(enemy.y - player.y, enemy.x - player.x);
        ctx.save();
        ctx.translate(ex, ey);
        ctx.rotate(a);
        ctx.fillStyle = "#b96346";
        ctx.beginPath();
        ctx.moveTo(11, 0);
        ctx.lineTo(-7, -7);
        ctx.lineTo(-7, 7);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
    }
    if (!demo.enabled && ENV.type === "arena")
      window.PoightArena.shakeFrame(ctx, canvas, camera, W, H, feel.offset, screen);
    if (!$("setup").open && (!demo.enabled || !demo.hideHUD)) {
      if (phase === "loading")
        overlay(
          assetError ? "素材文件未就位" : "准备像素动作…",
          assetError ? "请保留完整 assets 文件夹，在选角页重试。" : "只加载本场精灵",
        );
      else if (phase === "paused")
        overlay(
          "已暂停",
          `你的血量 ${Math.ceil(player.hp)} / ${player.maxHP}　 ·　对手 ${Math.ceil(enemy.hp)} / ${enemy.maxHP}`,
          "点场地继续 · Esc 继续",
        );
      else if (phase === "idle")
        overlay("准备好了。", "方向键移动 · J K L I 出招", "点场地开打 · 左上角换精灵 / 配招");
      else if (phase === "over" && gba.enabled) gba.showResult(outcome);
      else if (phase === "over")
        overlay(
          outcome === "win" ? "你赢了！" : outcome === "loss" ? "再来一局？" : "平局",
          `你的血量 ${player.hp} / ${player.maxHP}　 ·　对手 ${enemy.hp} / ${enemy.maxHP}`,
          player.id === 129 || enemy.id === 129
            ? "鲤鱼王尽力了。"
            : "点场地再战 · R 重新准备 · 换精灵试试别的打法",
        );
    }
  }
  let skillButtons = [];
  function moveDescription(m) {
    const first =
      m.kind === "heal"
        ? "回复 " + m.damage
        : m.kind === "guard"
          ? "护盾 " + m.damage
          : m.kind === "buff"
            ? m.boost === "speed"
              ? "移速 +30%"
              : "伤害 +25%"
            : "威力 " + m.damage;
    const category = {
      shot: "直线弹道",
      fan: "散射",
      melee: "近身",
      rush: "突进",
      spin: "环扫",
      beam: "直线光束",
      zone: "延迟范围",
      nova: "周身范围",
      guard: "格挡",
      heal: "回复",
      buff: "强化",
      splash: "原地跳跃 · 无伤害",
    }[m.kind];
    const extra = m.recoil
      ? " · 命中反伤"
      : m.phaseRush
        ? " · 突进时虚化"
        : m.leech
          ? " · 吸血"
          : m.cleanse
            ? " · 清异常"
            : m.execute
              ? " · 对残血增伤"
              : m.lowHP
                ? " · 自身残血增伤"
                : m.hpScale
                  ? " · 满血更强"
                  : m.waterEffective
                    ? " · 克制水系"
                    : m.venom
                      ? " · 对中毒增伤"
                      : m.statuses
                        ? " · " + m.statuses.map((s) =>
                          `${window.PoightStatus.definitions[s.id].name} ${Number(s.chance.toFixed(1))}%`
                        ).join(" / ")
                        : m.slow
                          ? " · 减速"
                          : "";
    return `${category} · ${first} · CD ${gba.enabled ? Number(m.cd.toFixed(2)) : m.cd}s · 体力 ${m.cost}${extra}`;
  }
  function renderSkillButtons() {
    $("skills").parentElement.style.setProperty("--skill-count", player.moves.length);
    $("skills").replaceChildren();
    skillButtons = player.moves.map((id, i) => {
      const m = MOVES[id],
        button = document.createElement("button");
      button.className = "skill";
      button.id = ["water", "melee", "skill3", "skill4"][i];
      button.style.setProperty("--move", m.color);
      button.title = m.name + "：" + moveDescription(m);
      button.setAttribute("aria-label", keyLabels[i] + " " + m.name + "，" + moveDescription(m));
      const k = document.createElement("kbd"),
        name = document.createElement("strong"),
        small = document.createElement("small");
      k.textContent = keyLabels[i];
      name.textContent = m.name;
      button.append(k, name, small);
      if (gba.enabled) {
        const cd = document.createElement("span");
        cd.className = "gba-cd";
        button.append(cd);
      }
      aim.bind(button, i);
      $("skills").append(button);
      return { button, small, id };
    });
    ui3?.bind(skillButtons);
  }
  function syncUI() {
    if (player) music.setHealth(player.hp / player.maxHP);
    music.setPlaying(phase === "playing");
    traversal.syncButton(player, terrain, phase === "playing");
    if (mobile?.controls && traversal.button) {
      traversal.button.textContent = traversal.submerged(player, terrain) ? "浮" : "潜";
    }
    if (!player || !enemy) return;
    battleHUD.sync(player, enemy);
    gba.sync(player, enemy, matchSeconds, terrain?.area(player.x, player.y)?.name || ENV.name, phase);
    for (const s of skillButtons) {
      const m = MOVES[s.id],
        left = player.cool[s.id] || 0;
      s.button.style.setProperty("--cool", clamp(left / m.cd, 0, 1).toFixed(3));
      s.button.classList.toggle("active", player.attack?.id === s.id);
      s.button.classList.toggle("cooling", left > 0);
      s.button.classList.toggle("insufficient", player.stamina < m.cost);
      s.button.classList.toggle("cast-rejected", (rejectedUntil.get(s.id) || 0) > aim.clock);
      setText(
        s.small,
        gba.enabled ? "能量 " + m.cost :
          left > 0.01 ? "CD " + (Math.ceil(left * 10) / 10).toFixed(1) + "s" : "体力 " + m.cost,
      );
      if (gba.enabled) setText(s.button.querySelector(".gba-cd"), (Math.ceil(left * 10) / 10).toFixed(1));
    }
    ui3?.sync(player, enemy, matchSeconds, phase, skillButtons);
    setText($("tierLabel"), tier().name);
    setText(
      $("sceneButton"),
      "地图 · " + (terrain?.area(player.x, player.y)?.name || ENV.name) + " ▾",
    );
    setText(
      $("status"),
      traversal.error ? "入口加载失败，离开后重试：" + traversal.error :
      traversal.pending ? "正在进入场景…" : elapsed < noticeUntil
        ? notice
        : phase === "playing"
          ? "AI · " + brain.mode
          : phase === "paused"
            ? "已暂停"
            : phase === "over"
              ? "本局结束 · 点击场地再战"
              : phase === "loading"
                ? "准备动作中…"
                : "准备好了 · 点场地开打",
    );
  }
  let activeMoveSlot = 0,
    draft = null,
    editingSide = "player",
    pageIndex = 0,
    filtered = ROSTER,
    setupReturnPhase = "idle",
    cursorID = null,
    versusTimer = null;
  const PAGE_SIZE = ROSTER.length; // R200: one scrollable grid, including keyboard/gamepad navigation.
  const bwPortraits = window.PoightPortraits(DATA.portraits, loadImage);
  function setPortrait(el, id, side) {
    bwPortraits.set(el, id, side);
  }
  function animatePortraits(now) {
    bwPortraits.animate(now);
  }
  function renderFighterDetails(side) {
    const mon = byID.get(draft[side]),
      types = $(side + "PickTypes"),
      moves = $(side + "PickMoves");
    types.className = "fighter-types";
    types.replaceChildren();
    for (const t of mon.types) {
      const badge = document.createElement("span");
      badge.className = "type-tag";
      badge.style.setProperty("--type", TYPES[t][1]);
      badge.textContent = TYPES[t][0];
      types.append(badge);
    }
    moves.replaceChildren();
    for (const id of draft[side + "Moves"]) {
      const move = MOVES[id],
        chip = document.createElement("span");
      chip.style.setProperty("--move-color", TYPES[move.type][1]);
      chip.textContent = move.name;
      moves.append(chip);
    }
  }
  function setupKeyboard(e) {
    if (
      e.isComposing ||
      e.metaKey ||
      e.ctrlKey ||
      e.altKey ||
      /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) ||
      e.target.isContentEditable ||
      !$("loadoutPanel").hidden ||
      (!selectionUI.enabled && !$("typeChoices").hidden) ||
      $("scenePicker").open
    )
      return;
    const deltas = {
      ArrowLeft: -1,
      KeyA: -1,
      ArrowRight: 1,
      KeyD: 1,
      ArrowUp: -1,
      KeyW: -1,
      ArrowDown: 1,
      KeyS: 1,
    };
    if (e.code === "Tab") {
      e.preventDefault();
      $(editingSide === "player" ? "chooseEnemy" : "choosePlayer").click();
      $("roster").querySelector(`[data-id="${cursorID}"]`)?.focus({ preventScroll: true });
    } else if (e.code === "Home" || e.code === "End") {
      e.preventDefault();
      const list = [...$("roster").querySelectorAll(".mon")];
      const next = e.code === "Home" ? list[0] : list.at(-1);
      if (!next) return;
      cursorID = Number(next.dataset.id);
      for (const b of list) b.dataset.cursor = String(b === next);
      next.focus({ preventScroll: true });
      next.scrollIntoView({ block: "nearest", inline: "nearest" });
    } else if (e.code in deltas) {
      e.preventDefault();
      const list = [...$("roster").querySelectorAll(".mon")];
      if (!list.length) return;
      const cols = getComputedStyle($("roster")).gridTemplateColumns.split(" ").length,
        vertical = ["ArrowUp", "KeyW", "ArrowDown", "KeyS"].includes(e.code),
        index = Math.max(
          0,
          list.findIndex((b) => b.dataset.id === String(cursorID)),
        ),
        next = list[clamp(index + deltas[e.code] * (vertical ? cols : 1), 0, list.length - 1)];
      cursorID = Number(next.dataset.id);
      for (const b of list) b.dataset.cursor = String(b === next);
      next.focus({ preventScroll: true });
      next.scrollIntoView({ block: "nearest", inline: "nearest" });
    } else if (["Enter", "KeyJ"].includes(e.code)) {
      e.preventDefault();
      $("roster").querySelector(`[data-id="${cursorID}"]`)?.click();
    }
  }
  // R200 selection-only standard gamepad support; the existing keyboard handler
  // remains the single navigation path, including focus and nearest-row scrolling.
  let padKey = "", padRepeatAt = 0;
  function selectionGamepad(now) {
    if (!selectionUI.enabled && $("setup").open && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "")) {
      const pad = [...(navigator.getGamepads?.() || [])].find(p => p?.connected);
      const pressed = n => pad?.buttons[n]?.pressed;
      const key = pressed(0) ? "Enter" : pressed(4) || pressed(5) ? "Tab" :
        pressed(12) || pad?.axes[1] < -.55 ? "ArrowUp" :
        pressed(13) || pad?.axes[1] > .55 ? "ArrowDown" :
        pressed(14) || pad?.axes[0] < -.55 ? "ArrowLeft" :
        pressed(15) || pad?.axes[0] > .55 ? "ArrowRight" : "";
      if (key && (key !== padKey || (now >= padRepeatAt && key.startsWith("Arrow")))) {
        $("roster").dispatchEvent(new KeyboardEvent("keydown", { code: key, bubbles: true, cancelable: true }));
        padRepeatAt = now + (key === padKey ? 130 : 300);
      }
      padKey = key;
    } else padKey = "";
    requestAnimationFrame(selectionGamepad);
  }
  requestAnimationFrame(selectionGamepad);
  requestAnimationFrame(animatePortraits);
  function iconStyle(el, id) {
    const index = DATA.iconOrder.indexOf(id);
    el.style.backgroundPosition = `-${(index % DATA.iconColumns) * 48}px -${Math.floor(index / DATA.iconColumns) * 48}px`;
  }
  function setTypePicker(open) {
    if (selectionUI.enabled) return;
    $("typeChoices").hidden = !open;
    $("typeFilterToggle").setAttribute("aria-expanded", String(open));
    if (open) {
      const box = $("typeFilterToggle").getBoundingClientRect(),
        panel = $("typeChoices");
      panel.style.left =
        clamp(box.right - panel.offsetWidth, 12, innerWidth - panel.offsetWidth - 12) + "px";
      panel.style.top = clamp(box.bottom + 8, 12, innerHeight - panel.offsetHeight - 12) + "px";
      panel.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true });
    }
  }
  function setTypeFilter(id) {
    $("typeFilter").value = id;
    setText($("typeFilterToggle"), (id ? TYPES[id][0] + "属性" : "全部属性") + " ▾");
    for (const b of $("typeChoices").children)
      b.setAttribute("aria-pressed", String(b.dataset.type === String(id)));
  }
  function filteredRoster() {
    const term = $("search")
        .value.trim()
        .toLowerCase()
        .replace(/^#/, "")
        .replace(/^0+(?=\d)/, ""),
      type = Number($("typeFilter").value),
      gen = Number($("generationFilter").value),
      bounds = [0, 151, 251, 386, 493, 649, 721, 809, 905, 1025];
    filtered = ROSTER.filter(
      (c) =>
        (!term ||
          (/^\d+$/.test(term) ? c.id === Number(term) : c.name.toLowerCase().includes(term))) &&
        (!type || c.types.includes(type)) &&
        (!gen || (c.id > bounds[gen - 1] && c.id <= bounds[gen])) &&
        selectionUI.matches(c),
    );
    pageIndex = clamp(pageIndex, 0, Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1));
    renderRoster();
  }
  function renderRoster() {
    const grid = $("roster"),
      fragment = document.createDocumentFragment(),
      scroll = grid.scrollTop,
      visible = selectionUI.enabled ? filtered : filtered.slice(pageIndex * PAGE_SIZE, (pageIndex + 1) * PAGE_SIZE);
    if (!visible.some((c) => c.id === cursorID)) cursorID = visible[0]?.id ?? null;
    for (const c of visible) {
      const button = document.createElement("button");
      button.className = "mon";
      if (gba.enabled) button.style.setProperty("--tile", TYPES[c.types[0]][1]);
      button.dataset.id = c.id;
      button.dataset.cursor = String(cursorID === c.id);
      button.dataset.player = String(draft.player === c.id);
      button.dataset.enemy = String(draft.enemy === c.id);
      button.setAttribute("aria-pressed", String(draft[editingSide] === c.id));
      button.setAttribute("aria-label", `#${String(c.id).padStart(3, "0")} ${c.name}`);
      const number = document.createElement("small"),
        icon = document.createElement("span"),
        name = document.createElement("b");
      number.textContent = String(c.id).padStart(3, "0");
      icon.className = "mon-icon";
      icon.setAttribute("aria-hidden", "true");
      iconStyle(icon, c.id);
      if (gba.enabled) {
        const n = DATA.iconOrder.indexOf(c.id);
        icon.style.backgroundPosition = `-${n % 10 * 44}px -${Math.floor(n / 10) * 44}px`;
      }
      name.textContent = c.name;
      button.append(number, icon, name);
      button.addEventListener("click", () => {
        cursorID = c.id;
        draft[editingSide] = c.id;
        draft[editingSide + "Moves"] = [...c.defaultMoves];
        renderRoster();
        renderSelection();
        grid.querySelector(`[data-id="${c.id}"]`)?.focus({ preventScroll: true });
      });
      fragment.append(button);
    }
    if (!filtered.length) {
      const empty = document.createElement("p");
      empty.className = "empty-results";
      empty.textContent = "没有找到。试试名称、编号，或清除筛选。";
      fragment.append(empty);
    }
    grid.replaceChildren(fragment);
    grid.dataset.count = visible.length;
    grid.dataset.expectedCount = visible.length;
    grid.scrollTop = scroll;
    selectionUI.count(filtered.length);
    setText($("filterCount"), `${filtered.length} 只符合条件`);
    setText(
      $("pageLabel"),
      `${pageIndex + 1} / ${Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))}`,
    );
    $("previousPage").disabled = pageIndex === 0;
    $("nextPage").disabled = (pageIndex + 1) * PAGE_SIZE >= filtered.length;
  }
  function renderSelection() {
    const c = byID.get(draft[editingSide]);
    $("setup").dataset.side = editingSide;
    for (const [side, prefix] of [
      ["player", "player"],
      ["enemy", "enemy"],
    ]) {
      const mon = byID.get(draft[side]);
      setPortrait($(prefix + "Portrait"), mon.id, side);
      setText($(prefix + "PickName"), mon.name);
      renderFighterDetails(side);
      const b = mon.body;
      setText(
        $(prefix + "Body"),
        `${b.dimensionMode === "coiled-length" ? "身长" : "身高"} ${b.heightMeters} m · ${b.weightKg} kg\n移速 ${mon.speed}`,
      );
    }
    $("pickPlayerPanel").setAttribute("aria-pressed", String(editingSide === "player"));
    $("pickEnemyPanel").setAttribute("aria-pressed", String(editingSide === "enemy"));
    setText(
      $("pickInstruction"),
      editingSide === "player"
        ? "正在给你选精灵 · 点中间头像切换"
        : "正在给电脑选精灵 · 点中间头像切换",
    );
    setText(
      $("loadoutTitle"),
      editingSide === "player" ? "你的配招（1–4招）" : "电脑配招（1–4招）",
    );
    setText($("draftPlayerName"), byID.get(draft.player).name);
    setText($("draftEnemyName"), byID.get(draft.enemy).name);
    $("choosePlayer").setAttribute("aria-pressed", String(editingSide === "player"));
    $("chooseEnemy").setAttribute("aria-pressed", String(editingSide === "enemy"));
    iconStyle($("selectedIcon"), c.id);
    setText(
      $("selectedNumber"),
      `#${String(c.id).padStart(3, "0")} / ${editingSide === "player" ? "你的搭档" : "AI 对手"}`,
    );
    setText($("selectedName"), c.name);
    $("selectedStats").replaceChildren();
    for (const text of [
      "HP " + c.hp,
      "移速 " + c.speed + " px/s",
      (c.body.dimensionMode === "coiled-length" ? "身长 " : "身高 ") + c.body.heightMeters + " m",
      c.body.weightKg + " kg",
      ...(c.nativeFloatOrBob ? ["原生浮动"] : []),
    ]) {
      const d = document.createElement("div");
      d.textContent = text;
      $("selectedStats").append(d);
    }
    $("selectedTypes").replaceChildren();
    for (const t of c.types) {
      const el = document.createElement("span");
      el.className = "type-tag";
      el.style.setProperty("--type", TYPES[t][1]);
      el.textContent = TYPES[t][0];
      $("selectedTypes").append(el);
    }
    renderMoveCards(c);
    for (const b of $("difficulty").children)
      b.setAttribute("aria-pressed", String(b.dataset.tier === draft.tier));
    const t = TIERS.find((t) => t.id === draft.tier);
    setText($("difficultyDescription"), t.description);
    setText(
      $("selectionSummary"),
      `${byID.get(draft.player).name}  VS  ${byID.get(draft.enemy).name}　·　${t.name}　·　${sceneByID.get(draft.map).name}`,
    );
  }
  function renderMoveCards(c) {
    const equipped = draft[editingSide + "Moves"];
    activeMoveSlot = clamp(activeMoveSlot, 0, equipped.length - 1);
    $("addMoveSlot").disabled = equipped.length >= Math.min(4, c.learnset.length);
    $("removeMoveSlot").disabled = equipped.length <= 1;
    $("moveSlots").style.setProperty("--slot-count", equipped.length);
    $("movesPlayer").setAttribute("aria-pressed", String(editingSide === "player"));
    $("movesEnemy").setAttribute("aria-pressed", String(editingSide === "enemy"));
    $("moveSlots").replaceChildren();
    for (let slot = 0; slot < equipped.length; slot++) {
      const m = MOVES[equipped[slot]],
        b = document.createElement("button"),
        k = document.createElement("kbd"),
        name = document.createElement("strong"),
        type = document.createElement("small");
      b.className = "move-slot";
      b.id = "moveChoice" + slot;
      b.dataset.move = m.id;
      b.setAttribute("aria-pressed", String(slot === activeMoveSlot));
      b.style.setProperty("--move-color", m.color);
      k.textContent = keyLabels[slot];
      name.textContent = m.name;
      type.textContent = TYPES[m.type][0];
      b.append(k, name, type);
      b.onclick = () => {
        activeMoveSlot = slot;
        renderMoveCards(c);
        $("moveChoice" + slot).focus({ preventScroll: true });
      };
      $("moveSlots").append(b);
    }
    setText(
      $("moveHint"),
      `正在替换 ${keyLabels[activeMoveSlot]} · ${MOVES[equipped[activeMoveSlot]].name}，点下方招式即可装备`,
    );
    const scroll = $("moveCatalog").scrollTop;
    $("moveCatalog").replaceChildren();
    for (const id of c.learnset) {
      const m = MOVES[id],
        at = equipped.indexOf(id),
        b = document.createElement("button"),
        header = document.createElement("span"),
        name = document.createElement("strong"),
        badge = document.createElement("small"),
        desc = document.createElement("span");
      b.className = "move-card";
      b.dataset.move = id;
      b.style.setProperty("--move-color", m.color);
      b.disabled = at >= 0 && at !== activeMoveSlot;
      b.setAttribute("aria-pressed", String(at === activeMoveSlot));
      name.textContent = m.name;
      badge.textContent = at >= 0 ? keyLabels[at] + " · 已装备" : TYPES[m.type][0];
      header.append(name, badge);
      desc.textContent = moveDescription(m);
      b.append(header, desc);
      b.onclick = () => {
        if (equipped.some((v, i) => i !== activeMoveSlot && v === id)) return;
        equipped[activeMoveSlot] = id;
        evt.change(editingSide + "Moves", [...equipped]);
        renderFighterDetails(editingSide);
        renderMoveCards(c);
        $("moveCatalog").querySelector(`[data-move="${id}"]`).focus({ preventScroll: true });
        setText(
          $("moveHint"),
          `${keyLabels[activeMoveSlot]} 已装备「${m.name}」 · 可继续点击其他槽位配置`,
        );
      };
      $("moveCatalog").append(b);
    }
    $("moveCatalog").scrollTop = scroll;
  }
  function resizeLoadout(add) {
    const c = byID.get(draft[editingSide]),
      equipped = draft[editingSide + "Moves"];
    if (add && equipped.length < 4) {
      const id = c.learnset.find((id) => !equipped.includes(id));
      if (id) equipped.push(id);
    } else if (!add && equipped.length > 1) equipped.pop();
    evt.change(editingSide + "Moves", [...equipped]);
    renderFighterDetails(editingSide);
    renderMoveCards(c);
  }
  function setLoadoutOpen(open) {
    $("loadoutPanel").hidden = !open;
    $("setup").classList.toggle("configuring", open);
    $("toggleLoadout").setAttribute("aria-expanded", String(open));
    setText($("toggleLoadout"), open ? "完成配招 ✓" : "配招 / AI 强度");
    if (open) {
      renderMoveCards(byID.get(draft[editingSide]));
      $("moveChoice" + activeMoveSlot).focus({ preventScroll: true });
    } else $("toggleLoadout").focus({ preventScroll: true });
  }
  function openSetup() {
    if (gba.locked()) return;
    evt.quit(player, enemy); evt.replay(true);
    clearTimeout(versusTimer);
    $("vsScreen").hidden = true;
    if (phase === "versus") phase = "idle";
    setLoadoutOpen(false);
    setupReturnPhase = phase === "playing" ? "paused" : phase;
    pause();
    clearInputs();
    draft = structuredClone(profile);
    editingSide = "player";
    cursorID = draft.player;
    pageIndex = 0;
    $("search").value = "";
    setTypeFilter("");
    setTypePicker(false);
    $("generationFilter").value = "";
    setText($("setupMessage"), "角色动画按需加载，不把整本图鉴一次性解码。");
    $("setupMessage").classList.remove("error");
    filteredRoster();
    renderSelection();
    if (!$("setup").open) $("setup").showModal();
    evt.selection();
  }
  function closeSetup() {
    if (!player) {
      // Preserve first-open X/Esc: cancel the draft and prepare the saved/default
      // match on this explicit action, never as a hidden selection-page preload.
      if (phase !== "loading") applyProfile(profile, false).then(ok => {
        if (ok) {
          setupReturnPhase = "idle";
          closeSetup();
        }
      });
      return;
    }
    if (phase === "loading") {
      ++applySerial;
      $("startBattle").disabled = false;
      phase = player ? "paused" : "loading";
    }
    if ($("setup").open) $("setup").close();
    if (phase !== "over" && phase !== "loading")
      phase =
        setupReturnPhase === "over" ? "over" : setupReturnPhase === "idle" ? "idle" : "paused";
    canvas.focus({ preventScroll: true });
  }
  async function launchBattle() {
    evt.launch(draft, byID, { map: DEFAULT_ENV.id, tier: DATA.defaultDifficulty });
    if (!(await applyProfile(draft, false))) return;
    if ($("setup").open) $("setup").close();
    clearInputs();
    phase = "versus";
    // applyProfile has awaited both characters and all match artwork. Only now stream BGM.
    music.prepareRound();
    for (const [side, prefix] of [
      ["player", "vsPlayer"],
      ["enemy", "vsEnemy"],
    ]) {
      setPortrait($(prefix + "Icon"), profile[side], side);
      setText($(prefix + "Name"), byID.get(profile[side]).name);
    }
    setText($("vsTier"), tier().name + " · " + ENV.name);
    $("vsScreen").hidden = false;
    $("vsContinue").focus({ preventScroll: true });
    clearTimeout(versusTimer);
    versusTimer = setTimeout(
      finishVersus,
      matchMedia("(prefers-reduced-motion: reduce)").matches ? 600 : 1600,
    );
  }
  function finishVersus() {
    if (phase !== "versus") return;
    clearTimeout(versusTimer);
    $("vsScreen").hidden = true;
    start();
    canvas.focus({ preventScroll: true });
  }
  let sceneFromSetup = false,
    pendingScene = DEFAULT_ENV.id,
    sceneReturnPhase = "idle",
    sceneBusy = false,
    sceneSelectSerial = 0;
  function renderSceneCards() {
    $("sceneCards").replaceChildren();
    const current = sceneByID.get(pendingScene),
      easterEgg = current?.type !== "arena" ? current : SCENES.find((s) => s.terrainID);
    const menuScenes = [...SCENES.filter((s) => s.type === "arena"), easterEgg].filter(Boolean);
    for (const scene of menuScenes) {
      const b = document.createElement("button"),
        image = document.createElement("img"),
        name = document.createElement("strong"),
        description = document.createElement("small"),
        state = document.createElement("span");
      b.className = "scene-card";
      b.dataset.scene = scene.id;
      b.setAttribute("aria-pressed", String(scene.id === pendingScene));
      b.disabled = sceneBusy;
      image.src = scene.previewSrc;
      image.alt = scene.name + "全景";
      image.width = 400;
      image.height = 250;
      name.textContent = scene.type === "arena" ? scene.name : "丰缘大地图 · 彩蛋";
      description.textContent = scene.type === "arena"
        ? scene.description
        : "丰缘 49 连图＋琉璃市 · 游泳／潜水 · 当前起点：" + scene.name;
      state.className = "scene-selected";
      state.textContent =
        scene.id === pendingScene
          ? "✓ 已选择"
          : scene.id === profile.map
            ? "当前对战地图"
            : "点击选择";
      b.append(image, name, description, state);
      b.onclick = () => {
        pendingScene = scene.id;
        renderSceneCards();
        $("sceneCards").querySelector(`[data-scene="${scene.id}"]`).focus({ preventScroll: true });
      };
      $("sceneCards").append(b);
    }
    const starts = document.createElement("select");
    starts.id = "hoennStart";
    starts.setAttribute("aria-label", "丰缘城市起点");
    starts.disabled = sceneBusy;
    for (const scene of SCENES.filter((s) => s.terrainID && !s.entranceOnly)) {
      const option = document.createElement("option");
      option.value = scene.id;
      option.textContent = scene.name + (scene.id === "emerald-sootopoliscity" ? "（独立场景）" : "");
      starts.append(option);
    }
    starts.value = easterEgg.id;
    starts.onchange = () => {
      pendingScene = starts.value;
      renderSceneCards();
    };
    $("sceneCards").append(starts);
    $("applyScene").disabled = sceneBusy;
    setText(
      $("applyScene"),
      sceneBusy
        ? "加载中…"
        : sceneFromSetup
          ? "选用此地图"
          : pendingScene === profile.map
            ? "保持当前地图"
            : "切换并重新开局",
    );
  }
  function openScenePicker(fromSetup = false) {
    if (phase === "loading") return;
    sceneFromSetup = fromSetup;
    sceneReturnPhase = phase === "playing" ? "paused" : phase;
    pause();
    clearInputs();
    pendingScene = fromSetup ? draft.map : profile.map;
    sceneBusy = false;
    setText(
      $("sceneHint"),
      fromSetup
        ? "选择后随阵容一起开局。这里只改待选地图，不重置当前对局。"
        : "局中换场会重新开局：双方血量、体力、招式冷却与场上飞行物全部重置。取消则保留原对局。",
    );
    setText(
      $("sceneMessage"),
      "正规场与自然场整场一屏。丰缘大地图保留原版连接；全员游泳、潜水，可进森林和隧道。琉璃市独立选址，不含水下与剧情。",
    );
    $("sceneMessage").classList.remove("error");
    renderSceneCards();
    $("scenePicker").showModal();
    $("sceneCards").querySelector('[aria-pressed="true"]').focus({ preventScroll: true });
  }
  function closeScenePicker() {
    ++sceneSelectSerial;
    if (sceneBusy) {
      ++applySerial;
      $("startBattle").disabled = false;
      phase = sceneReturnPhase;
    }
    sceneBusy = false;
    $("applyScene").disabled = false;
    if ($("scenePicker").open) $("scenePicker").close();
    syncUI();
    (sceneFromSetup ? $("setupMapButton") : canvas).focus({ preventScroll: true });
  }
  async function confirmScene() {
    if (sceneBusy) return;
    if (sceneFromSetup) {
      draft.map = pendingScene;
      evt.change("map", pendingScene);
      renderSelection();
      closeScenePicker();
      return;
    }
    if (pendingScene === profile.map) {
      closeScenePicker();
      return;
    }
    evt.setting("map", pendingScene);
    const run = ++sceneSelectSerial;
    sceneBusy = true;
    renderSceneCards();
    setText($("sceneMessage"), "正在准备新地图；完成前保留旧对局，可取消。");
    $("sceneMessage").classList.remove("error");
    const ok = await applyProfile({ ...profile, map: pendingScene }, false);
    if (run !== sceneSelectSerial) return;
    sceneBusy = false;
    if (ok) {
      closeScenePicker();
      announce("已切换到" + ENV.name + " · 点场地开打", 4);
    } else {
      renderSceneCards();
      setText($("sceneMessage"), "切换失败，未改动旧地图和对局。" + assetError);
      $("sceneMessage").classList.add("error");
    }
  }
  function prepareUI() {
    jump.bind($("jumpButton"), () => {
      if (phase === "idle") start();
      jump.start(player);
      canvas.focus({ preventScroll: true });
    });
    for (const [id, key, label] of [
      ["shakeSetting", "shake", "震屏"],
      ["aimSetting", "holdAim", "按住瞄准"],
    ]) {
      const render = () => {
        setText($(id), label + "：" + (profile[key] ? "开" : "关"));
        $(id).setAttribute("aria-pressed", String(profile[key]));
      };
      render();
      $(id).onclick = () => {
        profile[key] = !profile[key];
        evt.setting(key, profile[key]);
        if (key === "holdAim") clearInputs();
        feel.refresh(profile.shake);
        saveProfile();
        render();
      };
    }
    $("sceneButton").onclick = () => openScenePicker(false);
    $("setupMapButton").onclick = () => openScenePicker(true);
    $("closeScene").onclick = closeScenePicker;
    $("cancelScene").onclick = closeScenePicker;
    $("applyScene").onclick = confirmScene;
    $("scenePicker").addEventListener("cancel", (e) => {
      e.preventDefault();
      closeScenePicker();
    });
    $("pickPlayerPanel").onclick = () => {
      $("choosePlayer").click();
    };
    $("pickEnemyPanel").onclick = () => {
      $("chooseEnemy").click();
    };
    $("toggleLoadout").onclick = () => setLoadoutOpen($("loadoutPanel").hidden);
    $("addMoveSlot").onclick = () => resizeLoadout(true);
    $("removeMoveSlot").onclick = () => resizeLoadout(false);
    $("closeMoves").onclick = () => setLoadoutOpen(false);
    $("movesPlayer").onclick = () => {
      editingSide = "player";
      renderRoster();
      renderSelection();
      $("movesPlayer").focus();
    };
    $("movesEnemy").onclick = () => {
      editingSide = "enemy";
      renderRoster();
      renderSelection();
      $("movesEnemy").focus();
    };
    $("vsContinue").onclick = finishVersus;
    $("vsBack").onclick = openSetup;
    $("setup").addEventListener("keydown", setupKeyboard);
    $("vsScreen").addEventListener("click", finishVersus);
    document.documentElement.style.setProperty("--icons", `url("${DATA.icons}")`);
    setText($("rosterCount"), ROSTER.length);
    setText($("moveCount"), Object.keys(MOVES).length);
    for (const [id, t] of [["", ["全部属性", "#b3c9dc"]], ...Object.entries(TYPES)]) {
      const b = document.createElement("button");
      b.dataset.type = id;
      b.textContent = t[0];
      b.style.setProperty("--type-color", t[1]);
      b.setAttribute("aria-pressed", String(id === ""));
      b.onclick = () => {
        setTypeFilter(id);
        pageIndex = 0;
        filteredRoster();
        setTypePicker(false);
        if (selectionUI.enabled) {
          $("typeChoices").querySelector(`[data-type="${id}"]`)?.focus({ preventScroll: true });
        } else $("typeFilterToggle").focus({ preventScroll: true });
      };
      $("typeChoices").append(b);
    }
    $("typeFilterToggle").onclick = () => setTypePicker($("typeChoices").hidden);
    document.addEventListener("pointerdown", (e) => {
      if (!e.target.closest(".type-picker")) setTypePicker(false);
    });
    for (const t of TIERS) {
      const b = document.createElement("button"),
        ball = document.createElement("i");
      b.dataset.tier = t.id;
      ball.className = "ball " + t.id;
      ball.setAttribute("aria-hidden", "true");
      b.append(ball, document.createTextNode(t.name));
      b.addEventListener("click", () => {
        draft.tier = t.id;
        evt.change("tier", t.id);
        renderSelection();
      });
      $("difficulty").append(b);
    }
    $("choosePlayer").onclick = () => {
      editingSide = "player";
      renderRoster();
      renderSelection();
    };
    $("chooseEnemy").onclick = () => {
      editingSide = "enemy";
      renderRoster();
      renderSelection();
    };
    $("randomEnemy").onclick = () => {
      const c = ROSTER[Math.floor(Math.random() * ROSTER.length)];
      draft.enemy = c.id;
      evt.change("random", c.id);
      draft.enemyMoves = [...c.defaultMoves];
      renderSelection();
      renderRoster();
    };
    $("defaultMoves").onclick = () => {
      draft[editingSide + "Moves"] = [...byID.get(draft[editingSide]).defaultMoves];
      evt.change(editingSide + "Moves", draft[editingSide + "Moves"]);
      renderSelection();
    };
    for (const id of ["search", "typeFilter", "generationFilter"])
      $(id).addEventListener(id === "search" ? "input" : "change", () => {
        pageIndex = 0;
        filteredRoster();
      });
    $("previousPage").onclick = () => {
      pageIndex--;
      renderRoster();
    };
    $("nextPage").onclick = () => {
      pageIndex++;
      renderRoster();
    };
    $("startBattle").onclick = launchBattle;
    $("setupButton").onclick = openSetup;
    $("closeSetup").onclick = closeSetup;
    $("setup").addEventListener("cancel", (e) => {
      e.preventDefault();
      if (!selectionUI.enabled && !$("typeChoices").hidden) {
        setTypePicker(false);
        $("typeFilterToggle").focus();
      } else if (!$("loadoutPanel").hidden) setLoadoutOpen(false);
      else closeSetup();
    });
    $("help").onclick = () => {
      const hidden = !$("helpPanel").hidden;
      $("helpPanel").hidden = hidden;
      $("help").setAttribute("aria-expanded", String(!hidden));
      if (!hidden) pause();
    };
    $("reset").onclick = () => {
      resetMatch();
      $("helpPanel").hidden = true;
      $("help").setAttribute("aria-expanded", "false");
      canvas.focus({ preventScroll: true });
    };
    $("sound").onclick = () => {
      sound = !sound;
      evt.setting("sound", sound);
      setText($("sound"), "声音：" + (sound ? "开" : "关"));
      $("sound").setAttribute("aria-pressed", String(sound));
      if (sound) initAudio();
      canvas.focus({ preventScroll: true });
    };
    $("fullscreen").onclick = async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else if (document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen({ navigationUI: "hide" });
          await mobile?.lockLandscape();
        }
        else announce("浏览器未开放全屏；画面已铺满窗口", 4);
      } catch (_) {
        announce("全屏未获允许；画面仍铺满窗口", 4);
      }
      canvas.focus({ preventScroll: true });
    };
    document.addEventListener("fullscreenchange", () => {
      const on = !!document.fullscreenElement;
      evt.setting("fullscreen", on);
      $("fullscreen").setAttribute("aria-pressed", String(on));
      setText($("fullscreen"), on ? "退出全屏 ⛶" : "全屏 ⛶");
      resize();
    });
  }
  // Feedback uses wall time; bounded skill/dodge memory uses actionable time.
  let inputClock = 0;
  const blockedHeld = new Set(),
    castNotices = new Map(),
    rejectedUntil = new Map();
  function castRefusal(slot) {
    const id = player?.moves[slot],
      m = id && heroMove(player, MOVES[id]);
    if (
      !m || phase !== "playing" || player.hp <= 0 || enemy.hp <= 0 ||
      traversal.pending || player.worldAbsent || enemy.worldAbsent ||
      traversal.submerged(player, terrain) || jump.blocked(player) || statuses.blocked(player)
    ) return { code: "busy" };
    if (m.kind === "heal" && player.hp >= player.maxHP) return { code: "full", text: "血量已满" };
    const left = player.cool[id] || 0;
    if (left > 1e-6)
      return { code: "cool", text: `冷却 ${(Math.ceil(left * 10) / 10).toFixed(1)} 秒` };
    if (player.stamina + 1e-6 < m.cost) return { code: "stamina", text: "体力不足" };
    if (player.attack || player.dash || player.hurt > 0) return { code: "busy" };
    return null;
  }
  function rejectCast(slot, reason) {
    if (!reason || phase !== "playing") return;
    const id = player.moves[slot],
      button = skillButtons[slot]?.button;
    rejectedUntil.set(id, aim.clock + 0.28);
    if (button) {
      button.classList.remove("cast-rejected");
      void button.offsetWidth;
      button.classList.add("cast-rejected");
      button.dataset.rejections = String(Number(button.dataset.rejections || 0) + 1);
    }
    if (!reason.text || aim.clock - (castNotices.get(reason.code) ?? -Infinity) < 0.8) return;
    castNotices.set(reason.code, aim.clock);
    float(reason.text, player.x, headY(player, 24), "#ffb9b0", player);
  }
  function queueAttack(slot, angle = null) {
    if (!player?.moves[slot] || jump.blocked(player)) return;
    if (phase === "idle") start();
    if (phase === "playing") {
      blockedHeld.add(slot);
      const reason = castRefusal(slot);
      if (reason && reason.code !== "busy") {
        rejectCast(slot, reason);
        return;
      }
      queued = { slot, angle, until: inputClock + 0.12, reason };
      if (feel.remaining <= 1e-8 && beginAttack(player, player.moves[slot], enemy, angle))
        queued = null;
    }
  }
  window.addEventListener(
    "keydown",
    (e) => {
      if (
        e.isComposing ||
        e.metaKey ||
        e.ctrlKey ||
        e.altKey ||
        /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) ||
        e.target.isContentEditable ||
        $("setup").open ||
        $("scenePicker").open
      )
        return;
      if (demo.key(e, { pause, resume: resumeDemo })) return;
      if (phase === "versus") {
        if (e.code === "Enter") {
          e.preventDefault();
          finishVersus();
        } else if (e.code === "Escape") {
          e.preventDefault();
          openSetup();
        }
        return;
      }
      const dir = directionCodes[e.code],
        slot = moveKeys.indexOf(e.code);
      if (dir) {
        e.preventDefault();
        if (phase === "idle") start();
        if (phase !== "playing") return;
        const held = Object.keys(directionCodes).some(
          (k) => directionCodes[k] === dir && keys.has(k),
        );
        keys.add(e.code);
        if (!e.repeat && !held) {
          const tapTime = manual || (demo.enabled && demo.fps) ? aim.clock : performance.now() / 1000,
            last = lastTap[dir];
          if (last !== undefined && tapTime - last >= 0.025 && tapTime - last <= CONFIG.doubleTap) {
            const v = moveVector(),
              fallback = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[dir];
            const dx = v.x || v.y ? v.x : fallback[0],
              dy = v.x || v.y ? v.y : fallback[1];
            requestDash(dx, dy);
            delete lastTap[dir];
          } else lastTap[dir] = tapTime;
        }
      } else if (slot >= 0 && player?.moves[slot]) {
        e.preventDefault();
        if (phase === "idle") start();
        if (phase === "playing") {
          keys.add(e.code);
          if (!e.repeat && !aim.press(slot)) automaticHeld.add(slot);
        }
      } else if (e.code === "ShiftLeft" || e.code === "ShiftRight") {
        e.preventDefault();
        if (!e.repeat) {
          if (phase === "idle") start();
          const v = moveVector(),
            away = Math.atan2(player.y - enemy.y, player.x - enemy.x);
          requestDash(v.x || v.y ? v.x : Math.cos(away),
            v.x || v.y ? v.y : Math.sin(away));
        }
      } else if (e.code === "Space") {
        e.preventDefault();
        if (!e.repeat) {
          if (phase === "idle") start();
          jump.start(player);
        }
      } else if (e.code === "KeyC" && !e.repeat) {
        e.preventDefault();
        toggleDive();
      } else if (e.code === "KeyR" && !e.repeat) {
        e.preventDefault();
        resetMatch();
      } else if (e.code === "Escape" && !e.repeat) {
        e.preventDefault();
        if (aim.cancel()) return;
        if (phase === "paused") start();
        else pause();
      }
    },
    { passive: false },
  );
  window.addEventListener("keyup", (e) => {
    if (demo.enabled) return;
    keys.delete(e.code);
    const slot = moveKeys.indexOf(e.code);
    if (slot >= 0) {
      aim.release(slot);
      automaticHeld.delete(slot);
      // An expired press must not turn back into a held-key cast on the same frame.
      if (!queued || queued.slot !== slot) blockedHeld.delete(slot);
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (demo.enabled) return;
    if (e.pointerType !== "touch")
      aim.mouse = { x: e.clientX, y: e.clientY, time: aim.clock };
  });
  window.addEventListener("pointerdown", (e) => {
    if (demo.enabled) return;
    if (sound) initAudio();
    if (e.button === 2 && phase === "playing") {
      aim.rightHeld = true;
      e.preventDefault();
    }
  });
  window.addEventListener("pointerup", (e) => {
    if (e.button === 2) {
      if (aim.hold && !aim.hold.pointer) aim.release(aim.hold.slot);
      aim.rightHeld = false;
    }
  });
  window.addEventListener("keydown", () => { if (sound) initAudio(); });
  window.addEventListener("contextmenu", (e) => {
    if (aim.rightHeld || e.target === canvas) e.preventDefault();
  });
  window.addEventListener("blur", pause);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause();
  });
  window.addEventListener("resize", resize);
  new ResizeObserver(resize).observe(canvas);
  window.visualViewport?.addEventListener("resize", resize);
  canvas.addEventListener("pointerdown", () => {
    if (demo.enabled) return;
    canvas.focus({ preventScroll: true });
    if ($("helpPanel").hidden === false) {
      $("helpPanel").hidden = true;
      $("help").setAttribute("aria-expanded", "false");
    }
    if (phase === "over") resetMatch(true);
    else if (phase !== "playing") start();
  });
  function snapshot() {
    const pState = (p) =>
      p
        ? {
            id: p.id,
            name: p.char.name,
            ...jump.snapshot(p),
            headY: headY(p),
            flightHeight: flightHeight(p),
            visualLift: visualLift(p),
            speed: p.speed,
            onBridge: !!p.onBridge,
            seamVisualPosition: window.PoightSeams.visual(p),
            swimming: traversal.swimming(p, terrain),
            diving: traversal.submerged(p, terrain),
            oxygen: p.diveLeft || 0,
            diveCooldown: p.diveCool || 0,
            worldAbsent: !!p.worldAbsent,
            traversalSpeed: traversal.speed(p, terrain),
            scale: p.char.scale,
            body: { ...p.char.body, hurt: bodies.shape(p), labelY: headY(p, 20) },
            x: p.x,
            y: p.y,
            a: p.a,
            hp: p.hp,
            maxHP: p.maxHP,
            stamina: p.stamina,
            stealth: stealth.snapshot(p),
            spent: p.spent,
            damageTaken: p.damageTaken,
            damageDealt: p.damageDealt,
            moves: [...p.moves],
            cool: { ...p.cool },
            dashCool: p.dashCool,
            dashing: !!p.dash,
            protected: protectedNow(p),
            anim: p.anim,
            animFrame: animationFrame(p.id, p.anim, p.animAge),
            direction: directionRow(limbFacing(p, p.a)),
            shots: p.shots,
            splashes: p.splashes,
            punches: p.punches,
            dodges: p.dodges,
            evades: p.evades,
            shield: p.shield,
            slow: p.slow,
            status: statuses.snapshot(p),
            statusLabel: statuses.snapshot(p)?.label || null,
            freezeGrace: p.freezeGrace,
            statusBlocked: statuses.blocked(p),
            buffs: { ...p.buffs },
            attack: p.attack
              ? {
                  id: p.attack.id,
                  kind: p.attack.kind,
                  age: p.attack.age,
                  aim: p.attack.aim,
                  duration: p.attack.duration,
                  emitted: p.attack.emitted,
                  hitTime: p.attack.hitTime,
                  range: p.attack.move?.range,
                  targetPoint: p.attack.targetPoint,
                  anchor: heroAnchor(p, p.attack.move || MOVES[p.attack.id]),
                }
              : null,
          }
        : null;
    const sorted = [...performanceSamples].sort((a, b) => a - b);
    return {
      phase,
      hpMultiplier: DATA.hpMultiplier,
      balance: balance?.state() || null,
      outcome,
      elapsed,
      matchSeconds,
      frame,
      artReady,
      generated: generated.stats(),
      animation: animations.snapshot(),
      feel: feel.snapshot(),
      aim: aim.snapshot(),
      queued: queued ? { slot: queued.slot, remaining: Math.max(0, queued.until - inputClock) } : null,
      dashMemory: dashMemory ? { remaining: Math.max(0, dashMemory.until - inputClock) } : null,
      sound,
      music: music.snapshot(),
      warnings: warnings(),
      world: { ...WORLD },
      environment: {
        id: ENV.id,
        name: ENV.name,
        type: ENV.type || "world",
        variant: ENV.variant || null,
        grassRegions: ENV.grassRegions || [],
        bounds: { ...B },
        spawns: ENV.spawns,
        groundSrc: ENV.groundSrc,
        objectsSrc: ENV.objectsSrc,
        spriteCount: ENV.sprites.length,
        revision: sceneRevision,
        navGridBuilt: !!navGrid || !!terrain,
        area: terrain?.area(player?.x || 0, player?.y || 0)?.id || null,
        terrain: terrain?.stats() || null,
        capabilities: { ...ENV.capabilities },
        warpPending: traversal.pending,
        warpError: traversal.error,
        followIn: traversal.follow,
      },
      viewport: { width: W, height: H, scale: viewScale },
      camera: { ...camera },
      arenaView: ENV.type === "arena" ? { edge: battleHUD.edge || null,
        minimap: battleHUD.minimap || null, smoothing: ctx.imageSmoothingEnabled } : null,
      mobile: mobile?.snapshot(),
      hud: {
        variant: battleHUD.mode,
        tagFont: gba.enabled ? 12 : 8,
        suffixFont: gba.enabled ? 12 : 9,
        actors: [player, enemy].filter(Boolean).map((p) => {
          const h = hudGeometry(p);
          return {
            side: p === player ? "player" : "enemy",
            ...h,
            box: hudScreenBox(h.x - h.width / 2, h.y - h.height / 2, h.width, h.height),
            oxygen: h.oxygen ? {
              ratio: h.oxygen.ratio,
              box: hudScreenBox(h.oxygen.x, h.oxygen.y, h.oxygen.width, h.oxygen.height),
            } : null,
            stamina:
              p === player
                ? ["1", "3"].includes(battleHUD.mode)
                  ? { alpha: 1, source: "dom", box: battleHUD.staminaBox() }
                  : {
                    alpha: h.staminaAlpha,
                    box: battleHUD.mode === "2"
                      ? hudScreenBox(p.x - 24 / h.sx, h.staminaY, 48 / h.sx, 6 / h.sy)
                      : hudScreenBox(p.x - 18 / h.sx, h.staminaY, 36 / h.sx, 3 / h.sy),
                  }
                : null,
          };
        }),
        floats: floatLayouts().map(({ f, box }) => ({
          text: f.text,
          suffix: f.suffix,
          slot: f.slot,
          age: f.age,
          side: f.actor === player ? "player" : "enemy",
          box,
        })),
      },
      profile: structuredClone(profile),
      obstacles,
      hits,
      taken,
      player: pState(player),
      enemy: pState(enemy),
      ai: brain
        ? {
            mode: brain.mode,
            lastSeen: stealth.lastSeen ? { ...stealth.lastSeen } : null,
            searchGoal: stealth.searchGoal ? { ...stealth.searchGoal } : null,
            retreat: stealth.retreat ? { ...stealth.retreat } : null,
            decisions: brain.decisions,
            dodgeDecisions: brain.dodgeDecisions,
            pursuitDashes: brain.pursuitDashes,
            pathSearches: brain.pathSearches,
            casts: brain.casts,
            defends: brain.defends,
            heals: brain.heals,
          }
        : null,
      bullets: bullets.map((b) => ({
        id: b.id,
        x: b.x,
        y: b.y,
        ux: b.ux,
        uy: b.uy,
        age: b.age,
        range: b.range,
        speed: b.speed,
        radius: b.m.radius,
        sx: b.sx,
        sy: b.sy,
        maxRange: b.m.range,
        originAnchor: b.originAnchor,
        variant: b.variant,
        returned: b.returned,
        visualOffsetX: b.visualOffsetX,
        visualOffset: b.visualOffset,
        move: b.m.id,
        owner: b.owner === player ? "player" : "enemy",
      })),
      zones: zones.map((z) => ({ x: z.x, y: z.y, age: z.age, radius: z.radius, delay: z.delay })),
      effects: effects.length,
      effectKinds: effects.map((e) => e.kind),
      floats: floats.map((f) => ({ ...f })),
      ghosts: ghosts.length,
      heroGhosts: ghosts.filter(q => q.heroQuick).map(q => ({
        x: q.x, y: q.y, age: q.age, alpha: (1 - q.age / .16) * .56,
      })),
      held: [...keys],
      rosterCount: ROSTER.length,
      moveCount: Object.keys(MOVES).length,
      cachedCharacters: [...imageCache.keys()],
      timing: {
        cpuP95Ms: sorted[Math.floor(sorted.length * 0.95)] || 0,
        cpuMaxMs: sorted.at(-1) || 0,
        frameSamples: sorted.length,
      },
      config: CONFIG,
    };
  }
  let last = performance.now(),
    accumulator = 0;
  function loop(now) {
    const t = performance.now(),
      dt = Math.min(0.25, Math.max(0, (now - last) / 1000));
    if (phase === "playing") evt.frame(now - last);
    last = now;
    if (demo.enabled) {
      if (demo.ready && !demo.paused) {
        if (demo.fps) advanceDemoFrame();
        else {
          accumulator = Math.min(0.25, accumulator + dt);
          while (accumulator + 1e-9 >= 1 / 120) {
            advanceDemoFrame(false);
            accumulator -= 1 / 120;
          }
          syncUI();
          draw();
        }
      }
    } else if (!manual) {
      accumulator = Math.min(0.25, accumulator + dt);
      while (accumulator >= 1 / 120) {
        update(1 / 120);
        accumulator -= 1 / 120;
      }
      syncUI();
    }
    if (!demo.enabled) {
      // Finish-hit presentation runs on wall time, never AI/physics/input or resource clocks.
      if (phase === "over" && gba.locked()) {
        animations.step(dt);
        for (const e of effects) {
          e.age += dt;
          if (e.kind === "particle") { e.x += e.vx * dt; e.y += e.vy * dt; e.vy += 140 * dt; }
        }
        effects = effects.filter(e => e.age < e.life);
        for (const f of floats) f.age += dt;
        floats = floats.filter(f => f.age <= 0.8);
        ghosts = [];
      }
      draw();
      frame++;
    }
    performanceSamples.push(performance.now() - t);
    if (performanceSamples.length > 240) performanceSamples.shift();
    requestAnimationFrame(loop);
  }
  function resumeDemo() {
    demo.paused = false;
    accumulator = 0;
    if (phase === "paused") start();
  }
  function advanceDemoFrame(paint = true) {
    demo.tick({ phase: () => phase, update, reset: () => resetMatch(true),
      finishVS: finishVersus });
    // Camera fitting also covers hit-stop, KO and other early-return updates.
    updateDemoCamera(0);
    frame = demo.frame;
    if (paint) { syncUI(); draw(); }
  }
  if (demo.enabled) window.__demo = {
    get ready() { return demo.ready; },
    get frame() { return demo.frame; },
    get paused() { return demo.paused; },
    get speed() { return demo.speed; },
    get round() { return demo.round; },
    get cameraMode() { return demo.cameraMode; },
    pause() { pause(); },
    resume() { resumeDemo(); },
    reset() { resetMatch(true); accumulator = 0; if (demo.paused) pause(); draw(); },
    step(n = 1) {
      if (!demo.ready || !demo.paused) throw new Error("demo.step requires a ready, paused match");
      if (!Number.isSafeInteger(n) || n < 0 || n > 100000) throw new Error("invalid frame count");
      try {
        for (let i = 0; i < n; i++) {
          if (phase === "paused") phase = "playing";
          advanceDemoFrame();
          if (phase === "playing") phase = "paused";
        }
      } finally {
        demo.paused = true;
        if (phase === "playing") phase = "paused";
      }
      return demo.frame;
    },
    snapshot() {
      const s = snapshot();
      // No wall-clock CPU timings, cache statistics or DOM-dependent HUD geometry.
      return { frame: demo.frame, fps: demo.fps || 120, seed, phase,
        round: demo.round, speed: demo.speed, cameraMode: demo.cameraMode,
        bars: demo.bars, hideHUD: demo.hideHUD, environment: ENV.id, tier: profile.tier,
        casts: { player: balance.playerBrain?.casts || 0, enemy: brain.casts },
        elapsed, matchSeconds, outcome, hits, taken,
        player: s.player, enemy: s.enemy, ai: s.ai,
        bullets: s.bullets, zones: s.zones, effects: s.effectKinds,
        camera: { ...camera, zoom: demo.zoom, width: W, height: H },
        canvas: { width: canvas.width, height: canvas.height },
        centers: demoCenters().map(p => ({ ...p, nx: (p.x - camera.x) / W,
          ny: (p.y - camera.y) / H })) };
    },
  };
  if (manual || observe) window.__waterTest = { snapshot };
  if (manual)
    Object.assign(window.__waterTest, {
      statusTest: {
        seed: (value) => { seed = value >>> 0; },
        visual(side) {
          const p = side === "enemy" ? enemy : player;
          draw();
          const shown = canvas.toDataURL();
          statuses.visible = false;
          try { draw(); } finally { statuses.visible = true; }
          const base = canvas.toDataURL();
          draw();
          const sx = canvas.width / W, sy = canvas.height / H;
          const b = p.statusBox;
          return { shown, base, box: b && {
            x: (b.x - camera.x) * sx, y: (b.y - camera.y) * sy,
            width: b.width * sx, height: b.height * sy },
            thaw: p.statusThaw && { age: p.statusThaw.age, fire: p.statusThaw.fire } };
        },
        apply(side, id, move = "status-test") {
          const p = side === "enemy" ? enemy : player;
          return statuses.apply(p, p === player ? enemy : player, id, move);
        },
        clear(side) {
          const p = side === "enemy" ? enemy : player;
          statuses.clear(p);
          p.freezeGrace = p.immune = p.hurt = 0;
        },
        types(side, types) {
          const p = side === "enemy" ? enemy : player;
          p.char = { ...p.char, types };
        },
        freshHit(side, id) {
          const p = side === "enemy" ? enemy : player;
          p.hp = p.maxHP;
          p.immune = p.hurt = 0;
          p.attack = p.dash = p.status = p.statusThaw = null;
          p.freezeGrace = 0;
          const hit = damage(p, p === player ? enemy : player, MOVES[id], 1, 0,
            { hit: new Set() });
          return { hit, status: statuses.snapshot(p), hp: p.hp };
        },
        move(side, dx, dy, dt) {
          movePet(side === "enemy" ? enemy : player, dx, dy, dt);
        },
        queue: queueAttack,
      },
      autopilot: (tier = profile.tier) => balance.control(tier),
      simulate: (options) => balance.run(options),
      catalog: () => ({
        roster: ROSTER.map((c) => ({ ...c })),
        moves: MOVES,
        tiers: TIERS,
        art: ART,
        efficacy: EFFICACY,
        scenes: SCENES,
        terrains: DATA.terrains || [],
        warpScenes: ALL_SCENES.filter((s) => s.entranceOnly),
      }),
      step(seconds, render = true) {
        if (!Number.isFinite(seconds) || seconds < 0 || seconds > 120)
          throw new Error("step out of bounds");
        for (let left = seconds; left > 1e-8; ) {
          const dt = Math.min(left, 1 / 120);
          update(dt);
          left -= dt;
        }
        if (render) {
          syncUI();
          draw();
        }
      },
      async select(input) {
        return applyProfile(input, true);
      },
      reset(play = true) {
        if ($("setup").open) $("setup").close();
        resetMatch(play);
      },
      start,
      arrange(setup) {
        if (typeof setup.ai === "boolean") aiEnabled = setup.ai;
        for (const [key, p] of [
          ["player", player],
          ["enemy", enemy],
        ])
          if (p && setup[key]) {
            if (Number.isFinite(setup[key].x) || Number.isFinite(setup[key].y))
              p.onBridge = setup[key].onBridge ?? terrain?.bridges?.layer(terrain.index(
                setup[key].x ?? p.x, setup[key].y ?? p.y,
              )) ?? false;
            for (const k of ["x", "y", "a", "hp", "stamina", "hurt", "hurtAge", "slow"])
              if (Number.isFinite(setup[key][k]))
                p[k] =
                  k === "hp"
                    ? clamp(setup[key][k], 0, p.maxHP)
                    : k === "stamina"
                      ? clamp(setup[key][k], 0, 100)
                      : setup[key][k];
            constrain(p);
          }
        if (setup.clearProjectiles) {
          bullets = [];
          zones = [];
        }
        if (setup.tier && TIERS.some((t) => t.id === setup.tier)) profile.tier = setup.tier;
        stealth.update(elapsed, player, enemy);
        syncUI();
        draw();
      },
      grassRegions(regions) {
        stealth.configure({ grassRegions: regions }, null);
        stealth.update(elapsed, player, enemy);
        syncUI();
        draw();
      },
      equip(side, ids) {
        if (
          !Array.isArray(ids) ||
          ids.length < 1 ||
          ids.length > 4 ||
          ids.some((id) => !MOVES[id]) ||
          new Set(ids).size !== ids.length
        )
          throw new Error("bad moves");
        const p = side === "enemy" ? enemy : player;
        p.moves = [...ids];
        p.cool = Object.fromEntries(ids.map((id) => [id, 0]));
        if (p === player) renderSkillButtons();
      },
      cast(side, id) {
        return beginAttack(
          side === "enemy" ? enemy : player,
          id,
          side === "enemy" ? player : enemy,
        );
      },
      dash(side, dx, dy) {
        return dash(side === "enemy" ? enemy : player, dx, dy);
      },
      injectWater(spec) {
        const owner = spec.owner === "player" ? player : enemy,
          m = MOVES[spec.move || "watergun"];
        bullets.push({
          id: ++serial,
          x: spec.x,
          y: spec.y,
          ux: spec.ux,
          uy: spec.uy,
          speed: spec.speed || m.speed,
          range: spec.range || 700,
          age: 0,
          owner,
          m,
          group: { id: serial, hit: new Set() },
        });
      },
      jump: (side = "player") => jump.start(side === "enemy" ? enemy : player),
      injectMoveHit(side, id) {
        const target = side === "enemy" ? enemy : player;
        return damage(target, target === player ? enemy : player, MOVES[id], 1, 0,
          { hit: new Set() });
      },
      dive: (side = "player") => toggleDive(side === "enemy" ? enemy : player),
      feedbackHit(amount = 10, mult = 1) {
        feel.hit(amount, mult, profile.shake);
      },
      testDamage(side = "enemy", amount = 10, dx = 1, dy = 0) {
        const target = side === "enemy" ? enemy : player;
        return damage(
          target, side === "enemy" ? player : enemy,
          { id: "test", damage: amount, kind: "shot", type: -1, color: "#fff" },
          dx, dy, { hit: new Set() },
        );
      },
      // Test-only capability isolation hook; no production menu grants these flags.
      capabilities(value) {
        ENV = { ...ENV, capabilities: { ...value } };
        if (terrain) terrain.capabilities = { ...value };
        for (const p of [player, enemy]) traversal.tick(p, 0, terrain);
        syncUI();
      },
      injectLimbBoundary(spec) {
        const m = heroMove(player, MOVES[spec.move]);
        if (!m?.limb) throw new Error("R1 attached moves only");
        const group = { id: ++serial, hit: new Set(), power: 1, hp: 1 },
          attack = {
            id: m.id,
            move: m,
            group,
            aim: spec.aim,
            emitted: true,
            age: m.windup,
            hitTime: m.windup,
            duration: m.windup + m.recovery,
          },
          probe = { ...player, x: spec.x, y: spec.y, attack };
        generated.emit(probe, { id: m.id, move: m, group, aim: spec.aim }, enemy, generatedAPI());
      },
      heroAnchor: (side, id) => heroAnchor(side === "enemy" ? enemy : player, MOVES[id]),
      effective,
      freeAt,
      clearLine,
      findPath,
      assetProbe() {
        const result = [];
        for (const [name, d] of Object.entries(ART[player.id])) {
          const im = player.images[name],
            c = document.createElement("canvas");
          c.width = d.frameWidth;
          c.height = d.frameHeight;
          const g = c.getContext("2d", { willReadFrequently: true });
          g.imageSmoothingEnabled = false;
          for (const row of new Set([0, Math.min(4, d.rows - 1), d.rows - 1]))
            for (const f of new Set([0, Math.floor(d.frames / 2), d.frames - 1])) {
              g.clearRect(0, 0, c.width, c.height);
              g.drawImage(
                im,
                f * d.frameWidth,
                row * d.frameHeight,
                d.frameWidth,
                d.frameHeight,
                0,
                0,
                c.width,
                c.height,
              );
              const pixels = g.getImageData(0, 0, c.width, c.height).data;
              let visible = 0;
              for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) visible++;
              result.push({
                name,
                row,
                frame: f,
                visible,
                sizeOK:
                  im.naturalWidth === d.frames * d.frameWidth &&
                  im.naturalHeight === d.rows * d.frameHeight,
              });
            }
        }
        return result;
      },
      async preload(id) {
        await loadCharacter(id);
        pruneImages();
        return true;
      },
      render: draw,
    });
  evt.bind(() => [player, enemy]);
  prepareUI();
  traversal.bindButton(() => { toggleDive(); syncUI(); canvas.focus({ preventScroll: true }); });
  mobile = new window.PoightMobile({
    start: () => { if (phase !== "playing") start(); },
    pause,
    playing: () => phase === "playing",
    dash: (v) => {
      if (!player || phase !== "playing") return;
      const away = Math.atan2(player.y - enemy.y, player.x - enemy.x);
      requestDash(v.x || v.y ? v.x : Math.cos(away),
        v.x || v.y ? v.y : Math.sin(away));
    },
  }, battleHUD.mode, demo.enabled);
  resize();
  requestAnimationFrame(loop);
  (async () => {
    // The privileged regression fixture supports synchronous arbitrary equip/cast and
    // direct raster probes, so explicitly preload its full library. Real navigation,
    // observe mode, demo mode and ?test=1&lazy=1 always use match-scoped assets.
    if (manual && args.get("lazy") !== "1")
      await Promise.all([generated.load(loadImage), animations.load(),
        ...ROSTER.map(c => loadCharacterMetadata(c.id))]);
    if (!manual && !demo.enabled) {
      phase = "selection";
      openSetup();
      return;
    }
    if (demo.enabled) {
      profile.shake = false;
      profile.holdAim = false;
      battleHUD.debug = false;
      sound = false;
      demo.profile(args, profile, byID, sceneByID, TIERS, MOVES);
    }
    const ok = await applyProfile(profile, demo.enabled);
    if (ok && demo.enabled) {
      if (demo.vs) {
        phase = "versus";
        for (const [side, prefix] of [["player", "vsPlayer"], ["enemy", "vsEnemy"]]) {
          setPortrait($(prefix + "Icon"), profile[side], side);
          setText($(prefix + "Name"), byID.get(profile[side]).name);
        }
        setText($("vsTier"), tier().name + " · " + ENV.name);
        $("vsScreen").hidden = false;
      }
      demo.ready = true;
      accumulator = 0;
      last = performance.now();
      if (demo.paused) pause();
      demo.title();
      draw();
    } else if (ok && manual) {
      if ($("setup").open) $("setup").close();
    } else {
      openSetup();
      if (!ok) {
        setText($("setupMessage"), assetError);
        $("setupMessage").classList.add("error");
      }
    }
  })();
})();
