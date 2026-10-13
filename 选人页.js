/* S2 presentation/controller; roster and battle data stay owned by the game. */
"use strict";
window.PoightSelection = class {
  constructor(enabled, roster, changed) {
    this.enabled = enabled;
    this.group = "initial";
    this.cursors = {};
    if (!enabled) return;
    document.documentElement.dataset.selection = "S2";
    const dex = document.querySelector("#setup .dex"),
      toolbar = document.createElement("div"), groups = document.createElement("div"),
      search = document.createElement("div");
    toolbar.className = "roster-toolbar";
    groups.className = "group-tabs";
    groups.setAttribute("role", "tablist");
    groups.setAttribute("aria-label", "图鉴分组");
    const popular = roster.filter(c => c.id > 151).length;
    for (const [key, label] of [["initial", "初代 151"], ["popular", `人气精选 ${popular}`]]) {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.group = key; b.textContent = label;
      b.setAttribute("role", "tab"); b.setAttribute("aria-controls", "roster");
      b.onclick = () => {
        const cursor = dex.querySelector('.mon[data-cursor="true"]');
        if (cursor) this.cursors[this.group] = Number(cursor.dataset.id);
        this.group = key;
        for (const tab of groups.children) {
          tab.setAttribute("aria-selected", String(tab === b));
          tab.tabIndex = tab === b ? 0 : -1;
        }
        changed(this.cursors[key]);
        document.getElementById("roster").scrollTop = 0;
      };
      b.onkeydown = e => {
        e.stopPropagation();
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.code)) return;
        e.preventDefault(); e.stopPropagation();
        const next = e.code === "Home" ? groups.firstChild : e.code === "End" ? groups.lastChild :
          (b === groups.firstChild ? groups.lastChild : groups.firstChild);
        next.click(); next.focus();
      };
      b.setAttribute("aria-selected", String(key === this.group));
      b.tabIndex = key === this.group ? 0 : -1;
      groups.append(b);
    }
    search.className = "roster-search";
    const count = document.createElement("span"); count.id = "selectionCount";
    count.setAttribute("aria-live", "polite");
    search.append(count, document.getElementById("search"));
    toolbar.append(dex.querySelector(".side-tabs"), groups, search);
    dex.prepend(toolbar);
    this.tags = document.getElementById("typeChoices");
    this.tags.classList.add("type-tags"); this.tags.hidden = false;
    this.tags.addEventListener("keydown", e => e.stopPropagation());
    dex.querySelector(".filters").after(this.tags);
    this.groups = groups;
    const poll = now => { this.pollGamepad(now); requestAnimationFrame(poll); };
    requestAnimationFrame(poll);
  }
  matches(c) { return !this.enabled || (this.group === "initial" ? c.id <= 151 : c.id > 151); }
  count(n) {
    if (this.enabled) document.getElementById("selectionCount").textContent = `${this.group === "initial" ? "初代" : "精选"} ${n}`;
  }
  // Standard mapping: d-pad / left stick, A confirm, X swap side, LB/RB group.
  // Repeat only navigation; never repeated confirm. No battle input is injected.
  pollGamepad(now) {
    const setup = document.getElementById("setup");
    const pad = navigator.getGamepads?.()?.[0];
    if (!pad || !setup.open || setup.classList.contains("configuring") ||
        document.getElementById("scenePicker").open) { this.held = ""; return; }
    const pressed = i => pad.buttons[i]?.pressed;
    const code = pressed(12) || pad.axes[1] < -.55 ? "ArrowUp" :
      pressed(13) || pad.axes[1] > .55 ? "ArrowDown" :
      pressed(14) || pad.axes[0] < -.55 ? "ArrowLeft" :
      pressed(15) || pad.axes[0] > .55 ? "ArrowRight" :
      pressed(0) ? "Enter" : pressed(2) ? "Tab" : pressed(4) ? "LB" : pressed(5) ? "RB" : "";
    if (!code) { this.held = ""; return; }
    if (code === this.held && (!code.startsWith("Arrow") || now < this.repeatAt)) return;
    this.repeatAt = now + (code === this.held ? 110 : 300); this.held = code;
    if (code === "LB" || code === "RB") {
      this.groups.children[code === "LB" ? 0 : 1].click();
    } else {
      const grid = document.getElementById("roster");
      grid.dispatchEvent(new KeyboardEvent("keydown", { code, bubbles: true }));
    }
  }
};
