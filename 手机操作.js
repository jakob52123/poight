"use strict";
// Input only: analog movement joins moveVector; all physics remain in movePet/translatePet.
window.PoightMobile = class {
  static touchDevice() {
    return matchMedia("(pointer: coarse)").matches ||
      (navigator.maxTouchPoints > 0 && !matchMedia("(pointer: fine)").matches);
  }
  constructor(api, mode, demo = false) {
    this.api = api;
    this.demo = demo;
    this.enabled = window.PoightMobile.touchDevice();
    this.controls = !demo && this.enabled && mode === "3";
    this.vector = { x: 0, y: 0 };
    this.pointerId = null;
    this.radius = 54;
    this.resume = false;
    document.documentElement.dataset.touchGame = String(this.enabled);
    this.overlay = document.createElement("div");
    this.overlay.id = "rotatePhone";
    this.overlay.setAttribute("popover", "manual");
    this.overlay.setAttribute("role", "alert");
    this.overlay.innerHTML = `<svg class="pixel-phone" viewBox="0 0 12 16"
      aria-hidden="true" shape-rendering="crispEdges">
      <path fill="#cab57f" d="M2 0h8v1h1v14h-1v1H2v-1H1V1h1Z"/>
      <path fill="#0b1628" d="M2 2h8v10H2Z"/>
      <path fill="#fff0ce" d="M5 13h2v1H5Z"/>
      </svg><h2>把手机横过来玩</h2><p>横屏后继续 · 对战已暂停</p>`;
    document.body.append(this.overlay);
    this.stick = document.createElement("div");
    this.stick.id = "mobileJoystick";
    this.stick.setAttribute("aria-hidden", "true");
    this.stick.innerHTML = "<i></i><span>移动</span>";
    document.getElementById("app").append(this.stick);
    const jump = document.getElementById("jumpButton");
    this.actions = document.createElement("div");
    this.actions.id = "mobileActions";
    this.dashButton = document.createElement("button");
    this.dashButton.id = "dashButton";
    this.dashButton.textContent = "闪";
    this.dashButton.setAttribute("aria-label", "朝摇杆方向闪避；停下时背离对手");
    this.actions.append(jump, this.dashButton);
    if (this.controls) this.actions.append(document.getElementById("diveButton"));
    document.getElementById("app").append(this.actions);
    this.dashButton.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || this.portrait) return;
      e.preventDefault();
      api.start();
      api.dash(this.vector);
    });
    this.dashButton.addEventListener("click", (e) => {
      if (e.detail === 0 && !this.portrait) api.dash(this.vector);
    });
    const canvas = document.getElementById("game");
    canvas.addEventListener("pointerdown", (e) => {
      const rect = canvas.getBoundingClientRect();
      if (!this.controls || this.portrait || e.pointerType !== "touch" ||
        this.pointerId !== null || e.clientX > rect.left + rect.width * 0.45) return;
      e.preventDefault();
      api.start();
      if (!api.playing()) return;
      this.pointerId = e.pointerId;
      this.origin = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
      this.stick.classList.add("held");
      this.stick.style.left = `${e.clientX}px`;
      this.stick.style.top = `${e.clientY}px`;
      this.move(e);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (e.pointerId === this.pointerId) this.move(e);
    });
    for (const event of ["pointerup", "pointercancel", "lostpointercapture"])
      canvas.addEventListener(event, (e) => {
        if (e.pointerId === this.pointerId) this.clear();
      });
    window.addEventListener("resize", () => this.orient());
    screen.orientation?.addEventListener("change", () => this.orient());
    new MutationObserver(() => this.orient(true)).observe(document.getElementById("setup"),
      { attributes: true, attributeFilter: ["open"] });
    document.getElementById("app").addEventListener("contextmenu", (e) => e.preventDefault());
    this.orient();
  }
  move(e) {
    const dx = e.clientX - this.origin.x, dy = e.clientY - this.origin.y,
      length = Math.hypot(dx, dy), ratio = Math.min(1, length / this.radius),
      gain = ratio <= 0.1 ? 0 : ratio;
    this.vector = { x: length ? dx / length * gain : 0, y: length ? dy / length * gain : 0 };
    this.stick.querySelector("i").style.transform =
      `translate(${length ? dx / length * ratio * this.radius : 0}px, ` +
      `${length ? dy / length * ratio * this.radius : 0}px)`;
  }
  clear() {
    this.pointerId = null;
    this.vector = { x: 0, y: 0 };
    this.stick.classList.remove("held");
    this.stick.removeAttribute("style");
    this.stick.querySelector("i").style.transform = "none";
  }
  orient(refresh = false) {
    this.portrait = !this.demo && this.enabled && innerHeight > innerWidth;
    if (this.portrait) {
      if (this.api.playing()) {
        this.resume = true;
        this.api.pause();
      }
      if (refresh && this.overlay.matches(":popover-open")) this.overlay.hidePopover();
      if (!this.overlay.matches(":popover-open")) this.overlay.showPopover();
    } else {
      if (this.overlay.matches(":popover-open")) this.overlay.hidePopover();
      if (this.resume) {
        this.resume = false;
        this.api.start();
      }
    }
  }
  async lockLandscape() {
    if (!this.enabled || this.demo) return;
    try { await screen.orientation?.lock("landscape"); } catch { /* Optional browser support. */ }
  }
  snapshot() {
    return { enabled: this.enabled, portrait: this.portrait, pointerId: this.pointerId,
      vector: { ...this.vector }, radius: this.radius };
  }
};
