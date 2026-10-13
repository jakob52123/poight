"use strict";
window.PoightEVT = (() => {
  const P = performance, q = new URLSearchParams(location.search), start = P.now();
  const on = navigator.doNotTrack !== "1" && !navigator.globalPrivacyControl &&
    (q.get("track") === "1" || (location.protocol !== "file:" &&
      !["localhost", "localhost", "localhost", "localhost"].includes(location.hostname) &&
      !["demo", "observe", "test"].some(k => q.get(k) === "1")));
  const uuid = () => crypto.randomUUID?.() ||
    "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
      (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  let did = uuid(), born = Date.now(), rv = false, count = 0, games = 0;
  if (on) try {
    const old = localStorage.getItem("poight.evt.device");
    if (/^[\da-f]{8}(-[\da-f]{4}){3}-[\da-f]{12}$/i.test(old || "")) {
      born = +localStorage.getItem("poight.evt.first") || born; did = old; rv = true;
    } else {
      localStorage.setItem("poight.evt.device", did);
      localStorage.setItem("poight.evt.first", String(born));
    }
  } catch (_) {}
  const sid = uuid(), last = new Map(), images = new Set(), errors = new Set();
  const ua = navigator.userAgent, dt = /iPad|Tablet/i.test(ua) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/.test(ua)) ? "tablet" :
    /Mobile|Android|iPhone/i.test(ua) ? "phone" : "desktop";
  const utf8 = new TextEncoder(), time = () => Math.round(P.now() - start);
  const round = n => Math.round(n * 10) / 10, hp = p => p ? round(p.hp / p.maxHP * 100) : 0;
  const kb = () => round(P.getEntriesByType("resource").filter(r =>
    !r.name.includes("/e?")).reduce((n, r) => n + r.transferSize,
    P.getEntriesByType("navigation")[0]?.transferSize || 0) / 1024);
  function emit(e, p = {}, t = time()) {
    if (!on || count >= 300 || P.now() - (last.get(e) ?? -1e9) < 1000) return;
    try {
      const data = utf8.encode(JSON.stringify(p));
      const encoded = btoa(String.fromCharCode(...data)).replace(/\+/g, "-")
        .replace(/\//g, "_").replace(/=+$/, "");
      const args = new URLSearchParams({ v: "1", e, d: did, s: sid,
        t: String(t), b: "__EVT_BUILD__", p: encoded });
      if (utf8.encode("/e?" + args).length > 600) return;
      count++; last.set(e, P.now());
      const img = new Image(); images.add(img);
      img.onload = img.onerror = () => images.delete(img);
      img.src = "/e?" + args;
    } catch (_) {}
  }
  let b = null, click = null, ended = null, input = "keyboard", ready = false, actors = null;
  function launch(p, roster, def) {
    if (!on) return;
    click = { t: time(), kb: kb() }; ended = null;
    emit("battle_start_click", { a: p.player, c: p.enemy, m: p.map, l: p.tier,
      x: p.playerMoves, y: p.enemyMoves, z: p.map === def.map && p.tier === def.tier &&
        ["player", "enemy"].every(s => p[s + "Moves"].join() ===
          roster.get(p[s]).defaultMoves.join()) });
    emit("pick", { s: "player", n: p.player }, click.t);
    const t = click.t, c = p.enemy;
    setTimeout(() => emit("pick", { s: "enemy", n: c }, t), 1050);
  }
  function playing(p, bgm = "orig") {
    if (!on || b) return;
    b = { t: time(), p: structuredClone(p), u: [p.playerMoves.map(() => 0),
      p.enemyMoves.map(() => 0)], n: 0, ms: 0, lm: 0, ln: 0 };
    b.ready = { ms: click ? b.t - click.t : 0,
      kb: click ? round(kb() - click.kb) : 0 };
    if (bgm) music(bgm);
    click = null;
  }
  function music(bgm) {
    if (!b?.ready) return;
    emit("battle_ready", { ...b.ready, bgm }); b.ready = null;
  }
  function firstInput() {
    if (!b || b.input) return;
    b.input = true; emit("first_input", { ms: time() - b.t, i: input });
  }
  function cast(side, id) {
    if (!b) return;
    const n = side === "player" ? 0 : 1, i = b.p[side + "Moves"].indexOf(id);
    if (i >= 0) b.u[n][i]++;
    if (!n) firstInput();
  }
  function frame(ms) {
    if (!b || document.hidden || ms <= 0) return;
    b.n++; b.ms += ms; b.lm += ms; b.ln++;
    if (b.lm < 1000) return;
    b.ls = b.ln / b.lm < .04 ? (b.ls || 0) + b.lm : 0;
    if (!b.low && b.ls >= 3000) {
      b.low = true; emit("perf_low", { f: round(1000 * b.ln / b.lm), dt });
    }
    b.lm = b.ln = 0;
  }
  function finish(r, sec, p, hit, hurt) {
    if (!b) return;
    emit("battle_end", { r: r === "loss" ? "lose" : r, sec: round(sec), h: hp(p),
      hit, hurt, ev: p.dodges, u: b.u, f: b.ms ? round(b.n * 1000 / b.ms) : 0,
      pa: !!b.paused });
    b = null; games++; ended = time();
  }
  function quit(p, c) {
    if (!b) return;
    emit("quit", { sec: round((time() - b.t) / 1000), a: hp(p), c: hp(c) }); b = null;
  }
  function replay(change = false) {
    if (ended === null) return;
    emit(change ? "change_pokemon" : "rematch", { ms: time() - ended }); ended = null;
  }
  function error(message, file = "", line = 0) {
    let m = String(message).replace(/(https?:\/\/[^\s?#)]+)[?#][^\s)]*/g, "$1")
      .replace(/[\w.+-]+@[\w.-]+\.[a-z]+/gi, "[redacted]").slice(0, 120);
    while (utf8.encode(m).length > 180) m = m.slice(0, -1);
    if (errors.has(m)) return;
    errors.add(m);
    emit("error", { m, f: file.split(/[?#]/)[0].split("/").pop().slice(0, 20), l: +line || 0 });
  }
  const listen = window.addEventListener.bind(window);
  listen("error", e => error(e.message, e.filename, e.lineno));
  listen("unhandledrejection", e =>
    error(e.reason instanceof Error ? e.reason.message : "Unhandled rejection"));
  listen("keydown", e => {
    if (!/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) input = "keyboard";
  }, true);
  listen("pointerdown", e => {
    input = e.pointerType === "touch" ? "touch" : "keyboard";
  }, true);
  function end(close = false) {
    setTimeout(() => {
      if (close && b && actors) quit(...actors());
      emit("session_end", { ms: time(), n: games });
    });
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden) end(); });
  listen("pagehide", () => end(true));
  document.querySelectorAll(".setup-credit a").forEach((a, i) =>
    a.addEventListener("click", () => emit("link_click", { to: i ? "source" : "tribute" })));
  let ref = "direct";
  try { if (document.referrer) ref = new URL(document.referrer).hostname.slice(0, 100); } catch (_) {}
  const source = k => /^(github|github\.com|douyin|tiktok|direct|video|share)$/i.test(q.get(k) || "")
    ? q.get(k).toLowerCase() : q.has(k) ? "other" : "";
  emit("page_view", { ref, src: source("from"), utm: source("utm_source"), dt,
    w: innerWidth, h: innerHeight, o: innerWidth > innerHeight ? "landscape" : "portrait",
    lang: navigator.language.slice(0, 16), sa: matchMedia("(display-mode: standalone)").matches ||
      !!navigator.standalone, rv, days: Math.max(0, Math.floor((Date.now() - born) / 86400000)) });
  return { emit, launch, playing, music, cast, frame, finish, quit, replay, firstInput,
    pause() { if (b) { b.paused = true; b.ls = b.lm = b.ln = 0; } },
    bind(fn) { actors = fn; },
    change(k, v) { emit("loadout_change", { k, v }); },
    setting(k, v) { emit("setting", { k, v }); },
    selection() {
      if (!on || ready) return;
      if (!document.querySelector("#setup").open || document.querySelector("#startBattle").disabled ||
        document.querySelectorAll("#roster .mon").length !== Number(document.querySelector("#roster").dataset.expectedCount) ||
        ![...document.querySelectorAll("#playerPortrait,#enemyPortrait")].every(n => n.dataset.frame)) {
        requestAnimationFrame(() => this.selection()); return;
      }
      ready = true; emit("select_ready", { ms: Math.round(P.now()), kb: kb() });
    },
  };
})();
