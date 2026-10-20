/* REKORD web app — runs as PWA on Mac, Windows, Linux, iPhone, Android. No build step, no CDN, works offline on the LAN. */
"use strict";

// ================================================================ helpers
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = $("#view");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const debounce = (fn, ms = 400) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const IS_LOCAL = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname); // this computer (not a phone in the Wi-Fi)
const IS_MOBILE = /iPhone|iPad|Android/i.test(navigator.userAgent);
const gbFmt = (n) => (n || 0).toLocaleString("de-AT", { maximumFractionDigits: 1 }) + " GB";
const UNKNOWN = "Nicht erkannte Stimme", UNKNOWN_COLOR_JS = "#8A877F";  // all voices REKORD doesn't know – one entry, never "Sprecher 1, 2, 3"
const LECTURER = "Vortragende Person", AUDIENCE = "Publikum";  // „Vorlesung“: the main voice and everyone else
const unnamed = (n) => n === UNKNOWN || n === LECTURER || n === AUDIENCE || /^Sprecher \d+$/.test(n || "");  // voices still to be named
const initials = (n) => n === UNKNOWN || n === AUDIENCE ? "?" : (n || "?").replace(/^Sprecher\s*/, "S").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

function fmtTime(t) {
  t = Math.max(0, Math.floor(t || 0));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
const fmtDur = (t) => (t >= 3600 ? `${Math.floor(t / 3600)} h ${Math.round((t % 3600) / 60)} min` : t >= 60 ? `${Math.round(t / 60)} min` : `${Math.round(t)} s`);
const fmtDate = (ts, o = { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) => new Date(ts * 1000).toLocaleString("de-AT", o);

function toast(msg, ms = 2600) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), ms);
}

// token: kept after pairing so websockets and the iOS home-screen app keep working
(function keepToken() {
  const u = new URL(location.href);
  const tok = u.searchParams.get("token");
  if (tok) {
    try { localStorage.setItem("rekord.token", tok); } catch (e) {}
    // phones keep it in the address: iOS starts home-screen apps without Safari's storage
    if (!IS_MOBILE) {
      u.searchParams.delete("token");
      history.replaceState(null, "", u.pathname + u.hash);
    }
  }
})();
const token = () => { try { return localStorage.getItem("rekord.token") || ""; } catch (e) { return ""; } };

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token()) headers["X-Rekord-Token"] = token();
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, { ...opts, headers });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r;
}

// streams text from the LLM endpoints; error marker from server = "\0ERROR:"
async function streamText(path, body, onChunk) {
  const r = await api(path, { method: "POST", json: body });
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let all = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    all += dec.decode(value, { stream: true });
    const errAt = all.indexOf("\u0000ERROR:");
    if (errAt >= 0) throw new Error(all.slice(errAt + 7));
    onChunk(all);
  }
  return all;
}

function wsUrl(path) {
  const u = new URL(path, location.href);
  u.protocol = location.protocol === "https:" ? "wss:" : "ws:";
  if (token()) u.searchParams.set("token", token());
  return u.toString();
}

// ================================================================ dialogs
const dlg = $("#dlg"), dlgBody = $("#dlg-body");
function dialog(html, onOpen) {
  return new Promise((resolve) => {
    dlgBody.innerHTML = html;
    dlg.returnValue = "";
    dlg.onclose = () => resolve(dlg.returnValue);
    dlg.showModal();
    onOpen && onOpen(dlgBody);
    const first = $("input,textarea,select", dlgBody);
    first && setTimeout(() => first.focus(), 30);
  });
}
async function promptText(title, value = "", label = "", extra = "") {
  const r = await dialog(`<h2>${esc(title)}</h2>${label ? `<label class="muted">${esc(label)}</label>` : ""}
    <input type="text" id="dlg-in" value="${esc(value)}">${extra}
    <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok" id="dlg-ok">OK</button></div>`,
  (b) => { $("#dlg-in", b).addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); dlg.close("ok"); } }); });
  return r === "ok" ? $("#dlg-in").value.trim() : null;
}
async function confirmBox(title, text, okLabel = "Löschen") {
  const r = await dialog(`<h2>${esc(title)}</h2><p class="muted">${esc(text)}</p>
    <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">${esc(okLabel)}</button></div>`);
  return r === "ok";
}

// ================================================================ per-device preferences (theme, accent, mic …)
const DEVICE_DEFAULTS = { theme: "system", accent: "#FF5A1F", density: "comfortable", micId: "", echoCancellation: true, noiseSuppression: true,
  autoGainControl: true, inputMode: "mic", liveDetect: true, participants: [], guests: 0, wakeLock: true, autoscroll: true, rate: 1, detailTab: "summary" };
const prefs = (() => { try { return { ...DEVICE_DEFAULTS, ...JSON.parse(localStorage.getItem("rekord.device") || "{}") }; } catch (e) { return { ...DEVICE_DEFAULTS }; } })();
function setPref(k, v) {
  prefs[k] = v;
  try { localStorage.setItem("rekord.device", JSON.stringify(prefs)); } catch (e) {}
  if (["theme", "accent", "density"].includes(k)) applyLook();
}
function applyLook() {
  const root = document.documentElement;
  let t = prefs.theme;
  if (t === "system") t = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  root.dataset.theme = t;
  root.dataset.density = prefs.density;
  root.style.setProperty("--accent", prefs.accent);
  const onAccent = luminance(prefs.accent) > 0.45 ? "#0B0B0C" : "#FFFFFF";
  root.style.setProperty("--on-accent", onAccent);
  $('meta[name="theme-color"]').content = t === "light" ? "#F6F5F2" : "#0B0B0C";
}
function luminance(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
matchMedia("(prefers-color-scheme: light)").addEventListener("change", applyLook);
applyLook();

// ================================================================ global state: status + job events
const state = { status: null, recordings: null, current: null, templates: null };
const listeners = new Set();
function onEvent(fn) { listeners.add(fn); return () => listeners.delete(fn); }

let seenVersion = null;
async function refreshStatus() {
  try {
    state.status = await api("/api/status");
    const s = state.status;
    if (seenVersion && s.version !== seenVersion) { location.reload(); return; }  // REKORD was updated → its new interface
    if (!seenVersion) {
      seenVersion = s.version;
      const up = s.update || {};
      if (up.just_updated && localStorage.getItem("rekord-updated") !== s.version) {
        localStorage.setItem("rekord-updated", s.version);
        setTimeout(() => toast(`REKORD wurde auf ${s.version} aktualisiert ✓`, 5000), 800);
      }
    }
    const busy = s.jobs_pending > 0 || s.live.length > 0;
    const dl = s.models.find((m) => m.progress && m.progress.state === "downloading");
    $("#engine-status").innerHTML = `
      <div title="${!s.ready ? "Die Sprachmodelle werden einmalig geladen" : "Alles läuft auf diesem Computer"}"><span class="dot ${s.models_missing ? "err" : !s.ready ? "busy" : busy ? "busy" : "ok"}"></span><b>${s.models_missing ? "Laufwerk mit Modellen fehlt"
        : !s.ready ? (s.storage_chosen === false ? "Speicherort wählen" : "Modelle werden geladen") : busy ? "Arbeitet …" : "Bereit · lokal"}</b></div>
      ${dl ? `<div>${esc(dl.name)} ${Math.round((dl.progress.done / dl.progress.total) * 100)} %</div>` : ""}
      ${s.ai_ready ? `<div>KI: ${esc(s.provider_name)}${s.model ? ` · ${esc(s.model)}` : ""}</div>`
        : `<div><a href="#/settings?s=ai" style="color:var(--accent)">KI verbinden →</a></div>`}
      ${s.update && s.update.available ? `<div><a href="#/settings?s=data" style="color:var(--accent)">Update auf ${esc(s.update.latest)} →</a></div>` : ""}`;
  } catch (e) {
    $("#engine-status").innerHTML = `<span class="dot err"></span><b>Hub nicht erreichbar</b>`;
  }
}
setInterval(refreshStatus, 5000);

(function events() {
  let ws;
  const connect = () => {
    ws = new WebSocket(wsUrl("/ws/events"));
    ws.onmessage = (m) => { const ev = JSON.parse(m.data); listeners.forEach((fn) => fn(ev)); };
    ws.onclose = () => setTimeout(connect, 2500);
  };
  connect();
})();

// ================================================================ router
const routes = [
  [/^#?\/?$/, () => viewLibrary()],
  [/^#\/live/, () => viewLive()],
  [/^#\/r\/([a-f0-9]+)/, (m) => viewDetail(m[1])],
  [/^#\/ask/, () => viewAsk()],
  [/^#\/people/, () => viewPeople()],
  [/^#\/templates/, () => viewTemplates()],
  [/^#\/settings/, () => viewSettings()],
];
let cleanup = null;
// listeners on long-lived elements (view, document) are registered here and removed on every navigation
let disposers = [];
function listen(target, type, fn, opts) {
  target.addEventListener(type, fn, opts);
  disposers.push(() => target.removeEventListener(type, fn, opts));
}
async function route() {
  if (cleanup) { try { cleanup(); } catch (e) {} cleanup = null; }
  disposers.splice(0).forEach((d) => d());
  const h = location.hash || "#/";
  const nav = h.startsWith("#/live") ? "live" : h.startsWith("#/ask") ? "ask" : h.startsWith("#/people") ? "people"
    : h.startsWith("#/templates") ? "templates" : h.startsWith("#/settings") ? "settings" : "library";
  $$(".nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === nav));
  $("#fab").classList.toggle("hide", nav === "live" || nav === "settings" || h.startsWith("#/r/") || !!liveSession);
  if (state.status && state.status.storage_missing) { viewMissing(state.status.storage_missing); return; }
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) { view.scrollTop = 0; await fn(m); return; }
  }
  viewLibrary();
}
window.addEventListener("hashchange", route);
const qs = () => new URLSearchParams((location.hash.split("?")[1]) || "");

// ================================================================ first start: pick an AI in one click
async function onboarding(box) {
  const st = state.status || (await api("/api/status").catch(() => null));
  if (!box || !st || st.ai_ready || st.provider === "none") { if (box) box.innerHTML = ""; return; }
  const oll = await api("/api/ollama").catch(() => null);
  const busy = oll && ["installing", "starting", "pulling"].includes(oll.setup.state);
  box.innerHTML = `<div class="card onboard">
    <div class="eyebrow">Noch ein Schritt</div>
    <h2 style="margin:4px 0 6px">KI für Protokolle, To-dos und Mind Maps</h2>
    <p class="muted" style="margin-top:0">Aufnehmen, Transkript und Sprecher-Erkennung laufen schon. Für Zusammenfassungen eine KI wählen – jederzeit änderbar unter Einstellungen → KI.</p>
    <div class="provider-grid">
      <button class="prov" data-ob="local"><b>Lokal · gratis</b><small>Ein Klick. REKORD lädt Ollama und ein passendes Modell${oll ? ` (${esc(oll.default)})` : ""}. Nichts verlässt den Computer.</small></button>
      <button class="prov" data-ob="anthropic"><b>Claude</b><small>Beste Qualität. API-Key einfügen, fertig.</small></button>
      <button class="prov" data-ob="openai"><b>ChatGPT</b><small>API-Key einfügen, fertig.</small></button>
    </div>
    <div id="ob-prog" style="margin-top:12px"></div>
    <button class="btn ghost sm" data-ob="none" style="margin-top:8px">Ohne KI weiter</button></div>`;
  const prog = $("#ob-prog", box);
  $$("[data-ob]", box).forEach((b) => b.onclick = async () => {
    const k = b.dataset.ob;
    if (k === "local") {
      if (!IS_LOCAL && !(oll && oll.installed)) { toast("Die lokale KI wird am Computer eingerichtet – dort REKORD öffnen.", 5000); return; }
      b.disabled = true;
      try { await api("/api/ollama/setup", { method: "POST", json: {} }); } catch (e) { toast(e.message, 5000); b.disabled = false; return; }
      localSetupProgress(prog, () => setTimeout(() => refreshStatus().then(() => onboarding(box)), 2500));
      return;
    }
    await api("/api/settings", { method: "PUT", json: { llm: { provider: k } } });
    await refreshStatus();
    if (k === "none") { box.innerHTML = ""; toast("Ohne KI – jederzeit unter Einstellungen → KI änderbar."); return; }
    location.hash = "#/settings?s=ai&key=1";
  });
  if (busy) localSetupProgress(prog, () => setTimeout(() => refreshStatus().then(() => onboarding(box)), 2500));
}

// progress of "Lokal einrichten": install Ollama → start → download model → ready
function localSetupProgress(el, onDone) {
  let stopped = false;
  const tick = async () => {
    if (stopped || !el.isConnected) return;
    let o;
    try { o = await api("/api/ollama"); } catch (e) { setTimeout(tick, 2000); return; }
    const su = o.setup, pr = su.model ? o.pulls[su.model] || {} : {};
    const pct = su.state === "installing" && su.total ? su.done / su.total : su.state === "pulling" && pr.total ? pr.done / pr.total : 0;
    if (su.state === "error") { el.innerHTML = `<div style="color:#EF4444">✗ ${esc(su.error)}</div>`; return; }
    if (su.state === "done") { el.innerHTML = `<div style="color:#22C55E">✓ Lokale KI bereit · ${esc(su.model)}</div>`; toast("Lokale KI ist bereit."); onDone && onDone(o); return; }
    const extra = su.state === "installing" && su.total ? ` · ${gbFmt(su.done / 1e9)} von ${gbFmt(su.total / 1e9)}`
      : su.state === "pulling" && pr.total ? ` · ${gbFmt(pr.done / 1e9)} von ${gbFmt(pr.total / 1e9)}` : "";
    el.innerHTML = `<div class="muted" style="font-size:14px">${esc(su.step || "…")}${extra}</div>
      <div class="progress" style="width:100%"><i style="width:${Math.round(pct * 100)}%"></i></div>
      <div class="muted" style="font-size:12px;margin-top:4px">Läuft im Hintergrund weiter – du kannst REKORD schon benutzen.</div>`;
    setTimeout(tick, 1000);
  };
  tick();
  return () => { stopped = true; };
}

// ================================================================ LIBRARY
async function viewLibrary() {
  let q = "", folder = null;
  view.innerHTML = `<div class="page">
    <div class="row"><span class="eyebrow">Alles lokal · nichts verlässt dein Gerät</span></div>
    <h1 class="big">Aufnahmen<span class="acc">.</span></h1>
    <div class="row">
      <label class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input type="search" id="q" placeholder="Suchen in Titeln und allem, was gesagt wurde …"></label>
      <label class="btn"><svg viewBox="0 0 24 24"><path d="M12 16V4M6 10l6-6 6 6M4 20h16"/></svg>Importieren
        <input type="file" id="file" accept="audio/*,video/*,.m4a,.mp3,.wav,.webm,.ogg,.opus,.flac,.mp4,.mov" multiple hidden></label>
      <a class="btn primary" href="#/live"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5" fill="currentColor"/></svg>Aufnehmen</a>
    </div>
    <div id="onboard"></div>
    <div id="folders" class="row" style="margin-top:14px"></div>
    <div class="drop" id="drop">Audio- oder Videodateien hierher ziehen – Sprachmemos, Zoom-Aufnahmen, Diktiergerät …</div>
    <div id="list"></div></div>`;

  const load = async () => {
    const data = await api(`/api/recordings?q=${encodeURIComponent(q)}${folder !== null ? `&folder=${encodeURIComponent(folder)}` : ""}`);
    state.recordings = data.items;
    renderFolders(data.folders);
    renderList(data.items);
  };
  const renderFolders = (fs) => {
    $("#folders").innerHTML = fs.length ? `<div class="seg"><button data-f="" class="${folder === null ? "on" : ""}">Alle</button>${fs.map((f) =>
      `<button data-f="${esc(f)}" class="${folder === f ? "on" : ""}">${esc(f)}</button>`).join("")}</div>` : "";
    $$("#folders button").forEach((b) => b.onclick = () => { folder = b.dataset.f || null; load(); });
  };
  const renderList = (items) => {
    if (!items.length) {
      $("#list").innerHTML = q ? `<div class="empty"><h2>Nichts gefunden.</h2><p>Andere Wörter probieren – die Suche durchsucht auch die Transkripte.</p></div>`
        : `<div class="empty"><h2>Noch keine Aufnahmen.</h2><p>Drück den roten Knopf. REKORD erkennt live, wer spricht,<br>und schreibt dir danach Protokoll, To-dos und Mind Map.</p></div>`;
      return;
    }
    $("#list").innerHTML = `<div class="rec-list">${items.map(recRow).join("")}</div>`;
  };
  const recRow = (r) => {
    const d = new Date(r.created_at * 1000);
    const st = r.status === "done" ? "" : r.status === "error" ? `<span class="badge err">Fehler</span>`
      : r.status === "recording" ? `<span class="badge acc">● Live</span>` : `<span class="badge acc">${esc(r.stage || "In Warteschlange")}</span>`;
    return `<a class="rec" href="#/r/${r.id}" data-id="${r.id}">
      <div class="rec-date"><b>${d.getDate()}</b><span>${d.toLocaleString("de-AT", { month: "short" })}</span></div>
      <div><div class="rec-title">${esc(r.title)}</div>
        <div class="rec-meta">${fmtDate(r.created_at, { hour: "2-digit", minute: "2-digit" })} · ${fmtDur(r.duration || 0)} ${st}
          ${(r.speakers || []).slice(0, 5).map((n) => `<span class="chip" style="--c:${n.color}"><i></i>${esc(n.name)}</span>`).join("")}
          ${r.folder ? `<span class="badge">${esc(r.folder)}</span>` : ""}</div>
        ${["queued", "processing"].includes(r.status) ? `<div class="progress"><i style="width:${Math.round((r.progress || 0) * 100)}%"></i></div>` : ""}
      </div>
      <div class="muted">${r.language ? r.language.toUpperCase() : ""}</div></a>`;
  };

  onboarding($("#onboard"));
  $("#q").addEventListener("input", debounce((e) => { q = e.target.value.trim(); load(); }, 250));
  $("#file").addEventListener("change", (e) => upload([...e.target.files]));
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach((t) => listen(view, t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => listen(view, t, (e) => { e.preventDefault(); if (t === "drop" || e.target === drop) drop.classList.remove("over"); }));
  listen(view, "drop", (e) => { const fs = [...(e.dataTransfer?.files || [])]; if (fs.length) upload(fs); });

  async function upload(files) {
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    toast(`${files.length} Datei(en) werden hochgeladen …`);
    try { await api("/api/recordings", { method: "POST", body: fd }); toast("Importiert – Verarbeitung läuft."); load(); }
    catch (e) { toast("Import fehlgeschlagen: " + e.message); }
  }

  const reload = debounce(load, 300);
  cleanup = onEvent((ev) => {
    if (ev.type === "progress" && state.recordings) {
      const el = $(`.rec[data-id="${ev.id}"]`);
      if (el) {
        const bar = $(".progress i", el); if (bar) bar.style.width = Math.round(ev.progress * 100) + "%";
        const b = $(".badge.acc", el); if (b) b.textContent = ev.stage;
        return;
      }
    }
    reload();
  });
  await load();
}

// ================================================================ AUDIO CAPTURE (shared by live + enroll)
const WORKLET = `
class Down16k extends AudioWorkletProcessor {
  constructor() { super(); this.ratio = sampleRate / 16000; this.pos = 0; this.buf = new Int16Array(1600); this.n = 0; this.prev = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    // fractional-step linear resampler with a light box filter (anti-alias good enough for speech)
    while (this.pos < ch.length) {
      const i = Math.floor(this.pos), f = this.pos - i;
      const a = i > 0 ? ch[i - 1] * 0.25 + ch[i] * 0.5 + (ch[i + 1] ?? ch[i]) * 0.25 : ch[i];
      const b = ch[i + 1] ?? ch[i];
      const s = Math.max(-1, Math.min(1, a * (1 - f) + b * f));
      this.buf[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.n === this.buf.length) { this.port.postMessage(this.buf.buffer, [this.buf.buffer]); this.buf = new Int16Array(1600); this.n = 0; }
      this.pos += this.ratio;
    }
    this.pos -= ch.length;
    return true;
  }
}
registerProcessor("down16k", Down16k);`;

class Capture {
  constructor({ onPcm, onLevel }) { this.onPcm = onPcm; this.onLevel = onLevel; this.streams = []; }
  async start(mode = prefs.inputMode) {
    const constraints = { audio: { deviceId: prefs.micId ? { exact: prefs.micId } : undefined, channelCount: 1,
      echoCancellation: prefs.echoCancellation, noiseSuppression: prefs.noiseSuppression, autoGainControl: prefs.autoGainControl } };
    let mic;
    try { mic = await navigator.mediaDevices.getUserMedia(constraints); }
    catch (e) {
      if (prefs.micId) { delete constraints.audio.deviceId; mic = await navigator.mediaDevices.getUserMedia(constraints); }
      else throw e;
    }
    this.streams.push(mic);
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (this.ctx.state === "suspended") await this.ctx.resume();
    const url = URL.createObjectURL(new Blob([WORKLET], { type: "text/javascript" }));
    await this.ctx.audioWorklet.addModule(url);
    this.node = new AudioWorkletNode(this.ctx, "down16k");
    this.node.port.onmessage = (e) => { if (e.data instanceof ArrayBuffer && this.onPcm) this.onPcm(e.data); };
    const mix = this.ctx.createGain();
    this.ctx.createMediaStreamSource(mic).connect(mix);
    if (mode === "mic+system") {
      // calls: capture the other side (Zoom/Teams/Meet tab or system audio) and mix it with your mic
      try {
        const sys = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: { echoCancellation: false, noiseSuppression: false }, systemAudio: "include" });
        if (sys.getAudioTracks().length) {
          this.streams.push(sys);
          this.ctx.createMediaStreamSource(new MediaStream(sys.getAudioTracks())).connect(mix);
        } else toast("Kein Systemton freigegeben – nur Mikrofon.");
        sys.getVideoTracks().forEach((t) => t.stop());
      } catch (e) { toast("Systemton abgelehnt – nur Mikrofon."); }
    }
    mix.connect(this.node);
    if (this.onLevel) this.meter(mix);
    const mute = this.ctx.createGain(); mute.gain.value = 0;
    this.node.connect(mute).connect(this.ctx.destination);
    this.mediaStream = mic;
  }
  // Level meter: dBFS from an AnalyserNode, read once per frame. Rises instantly, falls back smoothly,
  // so it can't get stuck at a peak (and doesn't depend on worklet messages, which WebKit throttles).
  meter(source) {
    const an = this.ctx.createAnalyser();
    an.fftSize = 2048;
    source.connect(an);
    const buf = new Float32Array(an.fftSize);
    let shown = 0;
    const tick = () => {
      if (!this.ctx) return;
      an.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const db = 20 * Math.log10(Math.sqrt(sum / buf.length) + 1e-9);
      const v = Math.max(0, Math.min(1, (db + 60) / 54));   // -60 dB → 0 %, -6 dB → 100 %
      shown = v > shown ? v : shown * 0.9 + v * 0.1;         // fast attack, smooth release
      this.onLevel(shown);
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }
  stop() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.streams.forEach((s) => s.getTracks().forEach((t) => t.stop()));
    this.streams = [];
    if (this.ctx) this.ctx.close().catch(() => {});
    this.ctx = null;
  }
}

async function listMics() {
  try {
    let devs = await navigator.mediaDevices.enumerateDevices();
    if (!devs.some((d) => d.kind === "audioinput" && d.label)) {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach((t) => t.stop());
      devs = await navigator.mediaDevices.enumerateDevices();
    }
    return devs.filter((d) => d.kind === "audioinput");
  } catch (e) { return []; }
}

// ================================================================ LIVE
let liveSession = null; // survives navigation; recording keeps running in the background

function viewLive() {
  view.innerHTML = `<div class="page">
    <div class="row"><span class="eyebrow">Live · Sprecher-Erkennung in Echtzeit</span><span class="spacer"></span>
      <div class="seg" id="mode"><button data-m="mic" title="Alle sitzen im Raum – das Mikrofon reicht">Vor Ort</button><button data-m="mic+system" title="Teams, Zoom, Meet … – der Ton des Calls wird mit aufgenommen">Online</button><button data-m="lecture" title="Eine Person trägt vor, Fragen aus dem Hörsaal werden gesammelt">Vorlesung</button></div>${tip("meeting")}</div>
    <h1 class="big" style="margin-bottom:16px"><input id="title" class="det-title" style="background:none;border:0;width:100%;padding:0;font:inherit;letter-spacing:inherit"
      placeholder="Meeting ${new Date().toLocaleDateString("de-AT")}"></h1>
    <div class="live">
      <section class="stage">
        <div class="stage-top"><span class="rec-pill" id="pill"><i></i>BEREIT</span><span class="spacer"></span><span class="timer" id="timer">00:00</span></div>
        <div class="now">
          <div class="now-ring" id="ring"><b id="ring-i">·</b></div>
          <div class="now-name unknown" id="now-name">Wer spricht?</div>
          <div class="now-sub" id="now-sub">Starte die Aufnahme – REKORD zeigt dir live, wer gerade redet.</div>
        </div>
        <div class="level" style="margin:0 0 18px"><i id="lvl"></i></div>
        <div class="controls">
          <button class="ctl star" id="hl" title="Moment markieren (H)" disabled><svg viewBox="0 0 24 24"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></svg></button>
          <button class="rec-btn" id="rec" title="Start/Stopp (Leertaste)"><i></i></button>
          <button class="ctl" id="pause" title="Pause" disabled><svg viewBox="0 0 24 24"><path d="M9 5v14M15 5v14"/></svg></button>
        </div>
      </section>
      <aside>
        <div id="setup"></div>
        <div class="eyebrow" style="margin-bottom:10px">Im Raum${tip("room")}</div>
        <div class="roster" id="roster"><div class="muted">Stimmen erscheinen hier. Tipp auf eine unbekannte Stimme, um ihr einen Namen zu geben – REKORD erkennt sie ab dann immer.</div></div>
        <div class="eyebrow" style="margin:22px 0 10px">Mitschrift</div>
        <div class="feed" id="feed"></div>
      </aside>
    </div></div>`;

  $$("#mode button").forEach((b) => {
    b.classList.toggle("on", b.dataset.m === prefs.inputMode);
    b.onclick = () => { setPref("inputMode", b.dataset.m); $$("#mode button").forEach((x) => x.classList.toggle("on", x === b)); };
  });

  const ui = {
    render() {
      const s = liveSession;
      const on = !!s && !s.stopping;
      $("#rec").classList.toggle("on", on);
      $("#hl").disabled = !on; $("#pause").disabled = !on;
      $("#pill").className = "rec-pill" + (on && !s.paused ? " on" : "");
      $("#pill").lastChild.textContent = !s ? "BEREIT" : s.stopping ? "SPEICHERT" : s.paused ? "PAUSE" : s.offline ? "AUFNAHME (OFFLINE)" : "LIVE";
      $("#title").disabled = on;
      const su = $("#setup"); if (su) su.classList.toggle("hidden", !!s);
      if (s) { $("#title").value = s.title; this.roster(); this.feed(); this.now(s.now); }
    },
    now(n) {
      const ring = $("#ring"); if (!ring) return;
      if (!n) { $("#now-name").textContent = liveSession ? "…" : "Wer spricht?"; ring.style.setProperty("--c", "var(--fg3)"); $("#ring-i").textContent = "·"; return; }
      ring.style.setProperty("--c", n.color || "var(--fg3)");
      $("#ring-i").textContent = n.silence ? "·" : initials(n.name);
      const nm = $("#now-name");
      nm.textContent = n.silence ? "Stille" : n.name;
      nm.classList.toggle("unknown", !n.known || n.silence);
      $("#now-sub").textContent = n.silence ? "" : n.known ? `erkannt · ${Math.round((n.score || 0) * 100)} % Übereinstimmung`
        : n.key == null ? "Noch nicht zugeordnet" : "Antippen rechts („Im Raum“), um sie zu benennen";
    },
    roster() {
      const s = liveSession; if (!s || !$("#roster")) return;
      if (!s.speakers.length) return;
      const total = s.speakers.reduce((a, b) => a + (b.talk || 0), 0) || 1;
      $("#roster").innerHTML = s.speakers.map((p) => p.waiting ? `<div class="who" style="--c:${p.color};opacity:.55;cursor:default">
        <span class="avatar">${esc(initials(p.name))}</span><span><div class="who-name">${esc(p.name)}</div><div class="who-sub">dabei · noch nicht gesprochen</div></span><span></span></div>`
        : `<button class="who ${s.now && !s.now.silence && s.now.key === p.key ? "talking" : ""}" data-key="${p.key}" data-known="${p.known ? 1 : 0}" style="--c:${p.color}">
        <span class="avatar">${esc(initials(p.name))}</span><span><div class="who-name">${esc(p.name)}</div>
        <div class="who-sub">${p.known ? "erkannt" : p.voices > 1 ? `${p.voices} Stimmen · tippen benennt die zuletzt gehörte` : "tippen zum Benennen"} · ${fmtTime(p.talk || 0)}</div><div class="bar"><i style="width:${Math.round(((p.talk || 0) / total) * 100)}%"></i></div></span>
        <span class="muted">${Math.round(((p.talk || 0) / total) * 100)}%</span></button>`).join("");
      $$("#roster button.who").forEach((b) => b.onclick = async () => {
        const key = Number(b.dataset.key);
        const cur = s.speakers.find((x) => x.key === key);
        const name = await promptText("Wer ist das?", cur && cur.known ? cur.name : "", "Name eingeben – die Stimme wird gespeichert und ab jetzt automatisch erkannt.");
        if (name && s.ws && s.ws.readyState === 1) { s.ws.send(JSON.stringify({ type: "name_speaker", key, name })); toast(`${name} gemerkt.`); }
      });
    },
    feed() {
      const s = liveSession, el = $("#feed"); if (!s || !el) return;
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      el.innerHTML = s.lines.slice(-200).map((l) => `<div class="line" style="--c:${l.color}"><i></i><div><b>${esc(l.name)}</b><span class="t">${fmtTime(l.start)}</span>
        <p>${esc(l.text || "…")}</p></div></div>`).join("") || `<div class="muted">${s.offline ? "Offline-Aufnahme: Transkript nach dem Hochladen." : "Warte auf den ersten Satz …"}</div>`;
      if (nearBottom) el.scrollTop = el.scrollHeight;
    },
  };
  liveUI = ui;
  ui.render();
  renderSetup();

  $("#rec").onclick = () => (liveSession ? stopLive() : beginRecording($("#title").value.trim()));
  $("#hl").onclick = () => { highlightLive(); const b = $("#hl"); b.classList.add("flash"); setTimeout(() => b.classList.remove("flash"), 400); };
  $("#pause").onclick = () => togglePauseLive();
  const keys = (e) => {
    if (e.target.matches("input,textarea")) return;
    if (e.code === "Space") { e.preventDefault(); $("#rec").click(); }
    if (e.key === "h" || e.key === "H") $("#hl").click();
  };
  document.addEventListener("keydown", keys);
  const tick = setInterval(() => { if (liveSession && $("#timer")) $("#timer").textContent = fmtTime(liveSession.elapsed()); }, 250);
  cleanup = () => { document.removeEventListener("keydown", keys); clearInterval(tick); liveUI = null; };
  if (qs().get("autostart") === "1" && !liveSession) beginRecording("");
}
let liveUI = null;

// "Wer ist dabei?" — asked before EVERY recording: how many people talk, who of them REKORD knows.
// With the headcount REKORD separates exactly that many voices; known people are matched only against each other.
// online: the call's sound – natively on this computer (any app: Teams, Zoom …), otherwise via the browser's tab sharing
const callNative = () => IS_LOCAL && !!(state.status && state.status.capture && state.status.capture.system_audio);
const callBrowser = () => !!navigator.mediaDevices?.getDisplayMedia && !IS_MOBILE;
function callHint() {
  if (callNative()) return `<span style="color:#22C55E">✓</span> REKORD nimmt den Ton des Calls direkt am Computer auf – auch wenn Teams oder Zoom als App läuft. Mit Kopfhörern am saubersten.`
    + (/Mac/.test(navigator.platform) ? " Beim ersten Mal fragt macOS nach „Bildschirm- & Systemaudioaufnahme“ – erlauben." : "");
  if (callBrowser()) return "Beim Start fragt der Browser, was geteilt wird: den Tab mit dem Call wählen und <b>Audio teilen</b> anhaken.";
  return esc((state.status && state.status.capture && state.status.capture.reason) || "Call-Ton geht hier nicht – nur Mikrofon.");
}

async function beginRecording(title) {
  if (liveSession) return;
  if (await askParticipants()) startLive(title);
}

async function askParticipants() {
  let people = [];
  try { people = (await api("/api/profiles")).items; } catch (e) {}
  const ids = new Set(prefs.participants.filter((id) => people.some((p) => p.id === id)));
  let total = prefs.whoTotal ? Math.max(prefs.whoTotal, ids.size) : 0;  // 0 = not answered yet
  let meeting = prefs.inputMode === "mic+system" || prefs.inputMode === "lecture" ? prefs.inputMode : "mic";
  const lecture = () => meeting === "lecture";
  for (;;) {
    const r = await dialog(`<h2>Wer ist dabei?${tip("who")}</h2>
      <div><b>Wo findet das Meeting statt?</b>${tip("meeting")}</div>
      <div class="seg" id="w-meet" style="align-self:flex-start;flex-wrap:wrap"><button type="button" data-v="mic">Vor Ort</button><button type="button" data-v="mic+system">Online (Teams, Zoom, Meet …)</button><button type="button" data-v="lecture">Vorlesung</button></div>
      <div id="w-meet-hint" class="muted" style="font-size:13px;margin-top:-4px"></div>
      <p class="muted" style="margin:0" id="w-why">Damit REKORD weiß, wie viele Stimmen es trennen muss – und wen es schon kennt.</p>
      <div class="who-q" id="w-count"><div><b>Wie viele sprechen?</b>${tip("total")}<div class="muted" style="font-size:13px">dich mitgezählt</div></div>
        <div class="stepper"><button type="button" class="btn icon" id="w-minus" aria-label="weniger">−</button><b id="w-total">–</b>
        <button type="button" class="btn icon" id="w-plus" aria-label="mehr">+</button></div></div>
      <div class="row" id="w-quick" style="gap:6px">${[1, 2, 3, 4, 5, 6, 8].map((n) => `<button type="button" class="btn sm" data-n="${n}">${n}</button>`).join("")}</div>
      ${people.length ? `<div><b>Wer davon ist bekannt?</b>${tip("known")}<div class="row" id="w-ppl" style="gap:8px;margin-top:8px">${people.map((p) =>
        `<button type="button" class="chip" data-id="${p.id}" style="--c:${p.color};cursor:pointer"><i></i>${esc(p.name)}</button>`).join("")}</div></div>`
        : `<p class="muted" style="margin:0">Noch niemand angelernt – alle zählen als neu.</p>`}
      <div id="w-sum" class="who-sum"></div>
      <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok" id="w-ok">● Aufnahme starten</button></div>`,
    (b) => {
      const draw = () => {
        $$("#w-meet button", b).forEach((x) => x.classList.toggle("on", x.dataset.v === meeting));
        $("#w-meet-hint", b).innerHTML = meeting === "mic" ? "Alle im Raum – das Mikrofon reicht."
          : lecture() ? `Eine Person trägt vor, Fragen aus dem Hörsaal sammelt REKORD unter „Publikum“. Mitzählen musst du nicht. Mikro Richtung Vortrag.${tip("lecture")}` : callHint();
        $("#w-count", b).style.display = $("#w-quick", b).style.display = lecture() ? "none" : "";
        $("#w-why", b).textContent = lecture() ? "Ist die vortragende Person schon bekannt? Dann antippen – sonst einfach starten." : "Damit REKORD weiß, wie viele Stimmen es trennen muss – und wen es schon kennt.";
        $("#w-total", b).textContent = total || "–";
        $$("#w-quick [data-n]", b).forEach((x) => x.classList.toggle("primary", Number(x.dataset.n) === total));
        $$("#w-ppl [data-id]", b).forEach((x) => {
          const on = ids.has(Number(x.dataset.id));
          x.style.cssText = `--c:${x.style.getPropertyValue("--c")};cursor:pointer;` + (on ? "background:var(--fg);color:var(--bg);border-color:var(--fg)" : "");
        });
        const fresh = total - ids.size;
        const names = people.filter((p) => ids.has(p.id)).map((p) => esc(p.name));
        $("#w-sum", b).innerHTML = lecture() ? (names.length ? `<b>Vortrag</b>: ${names.join(", ")} · alle anderen: Publikum` : `<b>Vortrag</b>: wird an der Stimme erkannt · alle anderen: Publikum`)
          : !total ? `<span style="color:var(--accent)">Wähle oben, wie viele ihr seid.</span>`
          : `<b>${total} ${total === 1 ? "Person" : "Personen"}</b>: ${[names.join(", "), fresh ? `${fresh} neu${tip("newpeople")}` : ""].filter(Boolean).join(" + ")}
             ${fresh ? `<div class="muted" style="font-size:13px;margin-top:4px">Neue Stimmen landen unter „${UNKNOWN}“. Besser: jetzt kurz einsprechen lassen – dann erkennt REKORD sie mit Namen.</div>
             <button type="button" class="btn sm" id="w-intro" style="margin-top:8px">🎙 ${fresh === 1 ? "Neue Person" : `${fresh} neue Personen`} jetzt einsprechen</button>${tip("intro")}`
             : `<div class="muted" style="font-size:13px;margin-top:4px">Geschlossene Runde: jede Stimme wird einer dieser Personen zugeordnet.</div>`}`;
        $("#w-ok", b).disabled = !total && !lecture();
        const intro = $("#w-intro", b);
        if (intro) intro.onclick = () => { b.closest("dialog").close("intro"); };
      };
      $$("#w-meet button", b).forEach((x) => x.onclick = () => { meeting = x.dataset.v; draw(); });
      $("#w-minus", b).onclick = () => { total = Math.max(ids.size || 1, (total || 1) - 1); draw(); };
      $("#w-plus", b).onclick = () => { total = Math.min(30, (total || 0) + 1); draw(); };
      $$("#w-quick [data-n]", b).forEach((x) => x.onclick = () => { total = Math.max(Number(x.dataset.n), ids.size); draw(); });
      $$("#w-ppl [data-id]", b).forEach((x) => x.onclick = () => {
        const pid = Number(x.dataset.id);
        if (ids.has(pid)) ids.delete(pid); else { ids.add(pid); total = Math.max(total, ids.size); }
        draw();
      });
      b.addEventListener("keydown", (e) => { if (e.key === "Enter" && (total || lecture())) { e.preventDefault(); b.closest("dialog").close("ok"); } });
      draw();
    });
    if (r === "intro") {  // each new person reads their own text, then counts as known
      const fresh = total - ids.size;
      for (let i = 0; i < fresh; i++) {
        const prof = await enrollDialog({ intro: true, step: fresh > 1 ? `${i + 1} von ${fresh}` : "" });
        if (!prof) break;
        ids.add(prof.id);
        if (!people.some((p) => p.id === prof.id)) people.push(prof);
      }
      continue;
    }
    if (r !== "ok" || (!total && !lecture())) return false;
    setPref("participants", [...ids]);
    setPref("inputMode", meeting);
    if (!lecture()) {
      setPref("guests", Math.max(0, total - ids.size));
      setPref("whoTotal", total);
    }
    return true;
  }
}

// the live page shows who was announced; changing it = the same question
async function renderSetup() {
  const box = $("#setup"); if (!box) return;
  let people = [];
  try { people = (await api("/api/profiles")).items; } catch (e) {}
  const known = people.filter((p) => prefs.participants.includes(p.id));
  const total = prefs.whoTotal ? Math.max(prefs.whoTotal, known.length) : 0;
  box.innerHTML = `<div class="card" style="margin-bottom:22px">
    <div class="eyebrow" style="margin-bottom:10px">Wer ist dabei?${tip("who")}</div>
    ${total ? `<div><b>${total} ${total === 1 ? "Person" : "Personen"}</b>${known.length ? ": " + known.map((p) => `<span class="chip" style="--c:${p.color}"><i></i>${esc(p.name)}</span>`).join(" ") : ""}
      ${total - known.length ? ` + ${total - known.length} neu` : ""}</div>
      <div class="muted" style="font-size:12.5px;margin-top:6px">Wird beim Start nochmal bestätigt.</div>`
    : `<div class="muted">Fragt REKORD beim Start: wie viele ihr seid und wer schon bekannt ist.</div>`}
    <div class="row" style="margin-top:12px;gap:8px"><button class="btn sm" id="who-edit">Festlegen</button>
      <button class="btn sm" id="intro">🎙 Vorstellungsrunde</button>${tip("intro")}</div></div>`;
  $("#who-edit").onclick = async () => { await askParticipants(); renderSetup(); };
  $("#intro").onclick = async () => {
    const prof = await enrollDialog({ intro: true });
    if (prof) { setPref("participants", [...new Set([...prefs.participants, prof.id])]); setPref("whoTotal", Math.max(prefs.whoTotal || 0, prefs.participants.length)); renderSetup(); }
  };
}

async function startLive(title) {
  const s = liveSession = { title: title || `Meeting ${new Date().toLocaleString("de-AT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`,
    speakers: [], lines: [], now: null, paused: false, offline: false, highlights: [], t0: Date.now(), pausedMs: 0, pausedAt: 0, chunks: [],
    participants: [...prefs.participants], guests: prefs.guests,
    elapsed() { return ((this.pausedAt || Date.now()) - this.t0 - this.pausedMs) / 1000; } };
  liveUI && liveUI.render();
  const useWs = prefs.liveDetect;
  try {
    s.capture = new Capture({
      // until the hub confirms the session (first start loads the models) audio is kept here – nothing gets lost
      onPcm: (buf) => { if (s.paused) return; if (s.started && !s.offline && s.ws && s.ws.readyState === 1) s.ws.send(buf); else s.chunks.push(buf); },
      onLevel: (v) => { const l = $("#lvl"); if (l) l.style.width = v * 100 + "%"; const r = $("#ring"); if (r) r.style.setProperty("--lvl", v.toFixed(2)); },
    });
    s.online = prefs.inputMode === "mic+system";
    s.native = s.online && callNative();
    await s.capture.start(s.online && !s.native && callBrowser() ? "mic+system" : "mic");
  } catch (e) {
    liveSession = null; liveUI && liveUI.render();
    toast("Mikrofon nicht verfügbar: " + e.message, 5000);
    return;
  }
  if (prefs.wakeLock && navigator.wakeLock) { try { s.wake = await navigator.wakeLock.request("screen"); } catch (e) {} }
  const goOffline = () => { s.offline = true; liveUI && liveUI.render(); };
  if (!useWs) { goOffline(); return; }
  s.ws = new WebSocket(wsUrl("/ws/live"));
  s.ws.binaryType = "arraybuffer";
  s.ws.onopen = () => s.ws.send(JSON.stringify({ type: "start", sample_rate: 16000, title: s.title, participants: s.participants, guests: s.guests,
    meeting: s.online ? "online" : prefs.inputMode === "lecture" ? "lecture" : "person", call_audio: !!s.native }));
  s.ws.onerror = () => { if (!s.started) { toast("Hub nicht erreichbar – nehme offline auf."); goOffline(); } };
  setTimeout(() => {  // hub too slow to answer: keep recording, evaluate afterwards
    if (liveSession === s && !s.started && !s.offline && !s.stopping) { toast("Live-Erkennung startet nicht – nehme trotzdem auf, Auswertung danach.", 5000); goOffline(); try { s.ws.close(); } catch (e) {} }
  }, 45000);
  s.ws.onclose = () => { if (!s.stopping && s.started) { toast("Verbindung verloren – Aufnahme wird lokal fortgesetzt."); goOffline(); } };
  s.ws.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.type === "started") {
      s.started = true; s.id = ev.id;
      if (s.native) toast(ev.call_audio ? "Call-Ton läuft – die anderen im Call werden mit aufgenommen." : `Nur Mikrofon: ${(ev.notes || []).join(" ")}`, ev.call_audio ? 3500 : 9000);
      if (!s.offline) { s.chunks.splice(0).forEach((b) => s.ws.send(b)); }  // what was said while the hub got ready
    }
    else if (ev.type === "error") { toast(ev.error, 6000); goOffline(); }
    else if (ev.type === "speaking") { s.now = ev; liveUI && (liveUI.now(ev), liveUI.roster()); }
    else if (ev.type === "silence") { s.now = { silence: true }; liveUI && liveUI.now(s.now); }
    else if (ev.type === "segment") {
      s.lines.push(ev);
      const sp = s.speakers.find((x) => x.key === ev.key); if (sp) sp.talk = (sp.talk || 0) + (ev.end - ev.start);
      liveUI && (liveUI.feed(), liveUI.roster());
    } else if (ev.type === "speakers") {
      const talk = Object.fromEntries(s.speakers.map((x) => [x.key, x.talk]));
      s.speakers = ev.items.map((x) => ({ ...x, talk: Math.max(x.talk || 0, talk[x.key] || 0) }));
      s.lines.forEach((l) => { const sp = s.speakers.find((x) => x.key === l.key); if (sp) { l.name = sp.name; l.color = sp.color; } });
      liveUI && (liveUI.roster(), liveUI.feed());
    } else if (ev.type === "stopped") { s.savedId = ev.id; }
  };
}

function highlightLive() {
  const s = liveSession; if (!s) return;
  s.highlights.push(s.elapsed());
  if (s.ws && s.ws.readyState === 1) s.ws.send(JSON.stringify({ type: "highlight" }));
  toast("★ Moment markiert");
}
function togglePauseLive() {
  const s = liveSession; if (!s) return;
  s.paused = !s.paused;
  if (s.paused) s.pausedAt = Date.now(); else { s.pausedMs += Date.now() - s.pausedAt; s.pausedAt = 0; }
  if (s.ws && s.ws.readyState === 1) s.ws.send(JSON.stringify({ type: s.paused ? "pause" : "resume" }));
  liveUI && liveUI.render();
}
async function stopLive() {
  const s = liveSession; if (!s || s.stopping) return;
  s.stopping = true; liveUI && liveUI.render();
  s.capture.stop();
  if (s.wake) s.wake.release().catch(() => {});
  if ((s.offline || !s.started) && s.chunks.length) {
    // upload what we captured as WAV
    const wav = pcmToWav(s.chunks);
    const fd = new FormData();
    fd.append("files", new File([wav], "aufnahme.wav", { type: "audio/wav" }));
    fd.append("title", s.title);
    fd.append("source", "record");
    fd.append("highlights", JSON.stringify(s.highlights));
    if (s.participants.length || prefs.inputMode === "lecture") fd.append("participants", JSON.stringify({ ids: s.participants, guests: s.guests,
      meeting: prefs.inputMode === "lecture" ? "lecture" : s.online ? "online" : "person" }));
    try { const r = await api("/api/recordings", { method: "POST", body: fd }); s.savedId = r.items[0].id; }
    catch (e) { downloadBlob(wav, `${s.title}.wav`); toast("Hub nicht erreichbar – WAV wurde heruntergeladen.", 6000); }
  } else if (s.ws && s.ws.readyState === 1) {
    s.ws.send(JSON.stringify({ type: "stop" }));
    for (let i = 0; i < 300 && !s.savedId; i++) await sleep(100);
  }
  liveSession = null;
  if (s.savedId) { toast("Gespeichert – Feinschliff läuft im Hintergrund."); location.hash = `#/r/${s.savedId}`; }
  else liveUI && liveUI.render();
}
function pcmToWav(chunks) {
  const len = chunks.reduce((a, c) => a + c.byteLength, 0);
  const b = new DataView(new ArrayBuffer(44 + len));
  const w = (o, s) => [...s].forEach((c, i) => b.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); b.setUint32(4, 36 + len, true); w(8, "WAVEfmt "); b.setUint32(16, 16, true); b.setUint16(20, 1, true); b.setUint16(22, 1, true);
  b.setUint32(24, 16000, true); b.setUint32(28, 32000, true); b.setUint16(32, 2, true); b.setUint16(34, 16, true); w(36, "data"); b.setUint32(40, len, true);
  let o = 44; for (const c of chunks) { new Uint8Array(b.buffer, o, c.byteLength).set(new Uint8Array(c)); o += c.byteLength; }
  return new Blob([b.buffer], { type: "audio/wav" });
}
function downloadBlob(blob, name) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
window.addEventListener("beforeunload", (e) => { if (liveSession) { e.preventDefault(); e.returnValue = ""; } });

// ================================================================ DETAIL
async function viewDetail(id) {
  let rec;
  try { rec = await api(`/api/recordings/${id}`); } catch (e) { view.innerHTML = `<div class="page empty"><h2>Aufnahme nicht gefunden.</h2><a class="btn" href="#/">Zurück</a></div>`; return; }
  state.current = rec;
  if (!state.templates) state.templates = (await api("/api/templates")).items;
  const tab0 = qs().get("tab") || prefs.detailTab;
  view.innerHTML = `<div class="page">
    <div class="row"><a class="btn ghost sm" href="#/"><svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>Aufnahmen</a><span class="spacer"></span>
      <button class="btn sm" id="more"><svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg></button></div>
    <h1 class="det-title" id="dtitle" contenteditable="plaintext-only" spellcheck="false">${esc(rec.title)}</h1>
    <div class="rec-meta" id="dmeta"></div>
    <div id="dprog"></div>
    <div class="player" id="player">
      <div class="wave" id="wave"><canvas></canvas></div>
      <div class="timeline" id="tl"></div>
      <div class="player-ctl">
        <button class="btn ghost icon sm" id="back15" title="-15 s"><svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 3-6.2M4 4v4h4"/></svg></button>
        <button class="play" id="play"><svg viewBox="0 0 24 24" id="play-ico"><path d="M8 5v14l11-7z"/></svg></button>
        <button class="btn ghost icon sm" id="fwd15" title="+15 s"><svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-3-6.2M20 4v4h-4"/></svg></button>
        <span class="ptime" id="ptime">00:00 / ${fmtTime(rec.duration)}</span><span class="spacer"></span>
        <button class="btn sm" id="rate" title="Wiedergabe-Tempo">${prefs.rate}×</button>
      </div>
      <audio id="audio" preload="metadata" src="/api/recordings/${id}/audio"></audio>
    </div>
    <div class="spk-bar" id="spk"></div>
    <div id="naming"></div>
    <div class="tabs" id="tabs">
      <button data-tab="summary" title="Protokoll, To-dos, Entscheidungen – mit Vorlagen">Zusammenfassung</button><button data-tab="transcript" title="Alles, was gesagt wurde – wer, wann, was">Transkript</button>
      <button data-tab="mindmap" title="Die Themen als Landkarte">Mind Map</button><button data-tab="ask" title="Fragen nur zu dieser Aufnahme">Fragen</button><button data-tab="notes" title="Eigene Notizen und Ordner">Notizen</button><button data-tab="export" title="Als Datei speichern oder kopieren">Export</button>
    </div>
    <div id="tab"></div></div>`;

  const audio = $("#audio");
  audio.playbackRate = prefs.rate;
  const segs = () => rec.segments;
  const spk = (sid) => rec.speakers.find((s) => s.id === sid) || { name: "?", color: "var(--fg3)" };
  const seek = (t) => { audio.currentTime = t; if (audio.paused) audio.play().catch(() => {}); };
  listen(view, "click", (e) => {
    const a = e.target.closest("a.tsl,[data-seek]");
    if (a) { e.preventDefault(); seek(Number(a.dataset.t ?? a.dataset.seek)); }
  });

  // ---------- header
  $("#dtitle").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); e.target.blur(); } });
  $("#dtitle").addEventListener("blur", async (e) => {
    const t = e.target.textContent.trim();
    if (t && t !== rec.title) { rec.title = t; await api(`/api/recordings/${id}`, { method: "PATCH", json: { title: t } }); toast("Titel gespeichert"); }
  });
  const renderMeta = () => {
    $("#dmeta").innerHTML = `${fmtDate(rec.created_at)} · ${fmtDur(rec.duration || 0)} ${rec.language ? "· " + rec.language.toUpperCase() : ""}
      ${rec.folder ? `<span class="badge">${esc(rec.folder)}</span>` : ""} ${(rec.highlights || []).length ? `<span class="badge acc">★ ${rec.highlights.length}</span>` : ""}`;
    const p = $("#dprog");
    if (["queued", "processing", "recording"].includes(rec.status)) {
      p.innerHTML = `<div class="card" style="margin-top:14px"><div class="row"><span class="dot busy"></span><b id="pstage">${esc(rec.stage || "In Warteschlange")}</b>
        <span class="spacer"></span><span class="muted" id="ppct">${Math.round((rec.progress || 0) * 100)} %</span></div>
        <div class="progress" style="width:100%"><i id="pbar" style="width:${Math.round((rec.progress || 0) * 100)}%"></i></div>
        <div class="muted" style="font-size:13px;margin-top:8px">Sprecher trennen → Personen erkennen → transkribieren → zusammenfassen. Läuft komplett auf diesem Rechner.</div></div>`;
    } else if (rec.status === "error") {
      p.innerHTML = `<div class="card" style="margin-top:14px;border-color:#EF4444"><b>Verarbeitung fehlgeschlagen.</b> <span class="muted">${esc(rec.error)}</span>
        <button class="btn sm" id="retry" style="margin-left:8px">Nochmal</button></div>`;
      $("#retry").onclick = async () => { await api(`/api/recordings/${id}/reprocess`, { method: "POST" }); toast("Neu gestartet"); };
    } else p.innerHTML = "";
  };
  renderMeta();

  // ---------- speakers
  const talk = () => {
    const t = {};
    segs().forEach((s) => { t[s.speaker_id] = (t[s.speaker_id] || 0) + s.end - s.start; });
    return t;
  };
  const renderSpeakers = () => {
    const t = talk(), total = Object.values(t).reduce((a, b) => a + b, 0) || 1;
    $("#spk").innerHTML = rec.speakers.map((s) => `<button class="spk-card" data-sid="${s.id}" style="--c:${s.color}">
      <span class="avatar">${esc(initials(s.name))}</span><span><b>${esc(s.name)}</b><br><small>${Math.round(((t[s.id] || 0) / total) * 100)} % · ${
      s.profile_id ? `erkannt${s.match_score && s.match_score < 1 ? " " + Math.round(s.match_score * 100) + " %" : ""}` : (s.voices > 1 ? `${s.voices} Stimmen` : "nicht erkannt")}</small></span></button>`).join("");
    $$("#spk .spk-card").forEach((b) => b.onclick = () => editSpeaker(Number(b.dataset.sid)));
    drawTimeline();
    renderNaming();
  };

  // ---------- "Wer ist das?" right after a recording: name the unknown voice once → recognized from then on
  const INTRO_RE = /(?:^|[\s,.;:!?])(?:[Hh]ier (?:ist|spricht)|[Mm]ein Name ist|[Ii]ch heiße|[Tt]his is|[Mm]y name is|[Ii]ch bin(?: der| die)?)\s+([A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)/g;
  const NOT_NAMES = new Set(["Ich", "Heute", "Hier", "Jetzt", "Gerade", "Auch", "Noch", "Mal", "Eigentlich", "Okay", "Der", "Die", "Das", "Ein", "Eine", "Team"]);
  let knownNames = [];
  const suggestName = (lines) => {
    for (const sg of lines) {
      for (const m of (sg.text || "").matchAll(INTRO_RE)) {
        const name = m[1], weak = /ich bin/i.test(m[0]);
        if (NOT_NAMES.has(name)) continue;
        if (!weak || knownNames.some((k) => k.toLowerCase() === name.toLowerCase())) return name;  // "ich bin X" only for known names
      }
    }
    return "";
  };
  let playUntil = null;
  audio.addEventListener("timeupdate", () => { if (playUntil != null && audio.currentTime >= playUntil) { audio.pause(); playUntil = null; } });
  const playSample = (lines) => {
    const mine = [...lines].sort((a, b) => (b.end - b.start) - (a.end - a.start));
    if (!mine.length) return;
    audio.currentTime = mine[0].start; playUntil = Math.min(mine[0].end, mine[0].start + 8); audio.play().catch(() => {});
  };
  async function renderNaming() {
    const box = $("#naming"); if (!box) return;
    const unknown = rec.status === "done" ? rec.speakers.filter((x) => !x.profile_id && unnamed(x.name)) : [];
    let later = false; try { later = sessionStorage.getItem("rekord.namelater." + id) === "1"; } catch (e) {}
    if (!unknown.length || later) { box.innerHTML = ""; return; }
    if (!knownNames.length) { try { knownNames = (await api("/api/profiles")).items.map((x) => x.name); } catch (e) {} }
    // one row per unknown voice: a bucket with several people is listed voice by voice (by when they first spoke)
    const rows = [];
    for (const x of unknown) {
      const lines = segs().filter((g) => g.speaker_id === x.id);
      const byVoice = {};
      lines.forEach((g) => { const v = g.voice ?? "one"; (byVoice[v] = byVoice[v] || []).push(g); });
      const groups = Object.values(byVoice).sort((a, b) => a[0].start - b[0].start);
      groups.forEach((g) => rows.push({ sid: x.id, lines: g, single: groups.length === 1 }));
    }
    box.innerHTML = `<div class="card naming"><div class="row"><b>Wer ist das?</b>${tip("naming")}<span class="spacer"></span><button class="btn ghost sm" id="nm-later">Später</button></div>
      <p class="muted" style="margin:4px 0 10px">${rows.length > 1 ? `${rows.length} Stimmen hat REKORD nicht erkannt.` : "Eine Stimme hat REKORD nicht erkannt."} Anhören, Namen eingeben, <b>Merken</b> – ab der nächsten Aufnahme wird sie automatisch erkannt.</p>
      ${rows.map((r, k) => `<div class="nm-row" style="--c:${UNKNOWN_COLOR_JS}"><span class="avatar">?</span>
          <button type="button" class="btn sm icon" data-play="${k}" title="Anhören">▶</button>
          <span class="nm-who"><b>Ab ${fmtTime(r.lines[0].start)} · ${r.lines.length} ${r.lines.length === 1 ? "Satz" : "Sätze"}</b><small>„${esc((r.lines[0].text || "").slice(0, 80))}“</small></span>
          <input type="text" data-name="${k}" placeholder="Name" value="${esc(suggestName(r.lines))}" list="nm-list" autocomplete="off">
          <button type="button" class="btn primary sm" data-save="${k}">Merken</button></div>`).join("")}
      <datalist id="nm-list">${knownNames.map((n) => `<option value="${esc(n)}">`).join("")}</datalist></div>`;
    $("#nm-later").onclick = () => { try { sessionStorage.setItem("rekord.namelater." + id, "1"); } catch (e) {} box.innerHTML = ""; };
    $$("#naming [data-play]").forEach((b) => b.onclick = () => playSample(rows[Number(b.dataset.play)].lines));
    $$("#naming [data-save]").forEach((b) => b.onclick = async () => {
      const r = rows[Number(b.dataset.save)], name = $(`#naming [data-name="${b.dataset.save}"]`).value.trim();
      if (!name) { toast("Namen eingeben"); return; }
      b.disabled = true;
      try {
        if (r.single) await api(`/api/speakers/${r.sid}`, { method: "PATCH", json: { name, remember: true } });
        else await api(`/api/segments/${r.lines[0].id}/assign`, { method: "POST", json: { name, remember: true, whole_voice: true } });
        toast(`${name}: Stimme gemerkt ✓`); await reload();
      } catch (e) { toast(e.message, 6000); b.disabled = false; }
    });
    $$("#naming [data-name]").forEach((inp) => inp.addEventListener("keydown", (e) => { if (e.key === "Enter") $(`#naming [data-save="${inp.dataset.name}"]`).click(); }));
  }

  // ---------- "Wer sagt das?" for a single line – sorts out the unknown voices one sentence at a time
  async function assignLine(segId) {
    const sg = segs().find((x) => x.id === segId); if (!sg) return;
    const cur = spk(sg.speaker_id);
    if (!knownNames.length) { try { knownNames = (await api("/api/profiles")).items.map((x) => x.name); } catch (e) {} }
    const sameVoice = sg.voice != null ? segs().filter((x) => x.speaker_id === sg.speaker_id && x.voice === sg.voice).length : 1;
    const names = [...new Set([...rec.speakers.filter((x) => x.name !== UNKNOWN && !/^Sprecher \d+$/.test(x.name)).map((x) => x.name), ...knownNames])].filter((n) => n !== cur.name);
    const r = await dialog(`<h2>Wer sagt das?</h2>
      <blockquote class="read-text" style="font-size:15px">„${esc(sg.text)}“</blockquote>
      <div class="row"><button type="button" class="btn sm" id="al-play">▶ Anhören</button><span class="muted">${fmtTime(sg.start)} · jetzt: ${esc(cur.name)}</span></div>
      ${names.length ? `<div class="row" style="gap:8px">${names.map((n) => `<button type="button" class="btn sm" data-pick="${esc(n)}">${esc(n)}</button>`).join("")}</div>` : ""}
      <input type="text" id="al-name" placeholder="…oder neuer Name" autocomplete="off">
      ${sameVoice > 1 ? `<label class="row"><input type="checkbox" id="al-all-voice" checked> Alle ${sameVoice} Sätze dieser Stimme</label>` : ""}
      <label class="row"><input type="checkbox" id="al-rem" checked> Stimme dabei lernen${tip("remember")}</label>
      <div><button type="button" class="btn ghost sm" id="al-all">Alle Sätze von „${esc(cur.name)}“ umbenennen …</button></div>
      <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Zuordnen</button></div>`,
    (b) => {
      $("#al-play", b).onclick = () => { audio.currentTime = sg.start; playUntil = sg.end; audio.play().catch(() => {}); };
      $$("[data-pick]", b).forEach((x) => x.onclick = () => { $("#al-name", b).value = x.dataset.pick; b.closest("dialog").close("ok"); });
      $("#al-all", b).onclick = () => b.closest("dialog").close("all");
    });
    if (r === "all") { editSpeaker(sg.speaker_id); return; }
    const name = r === "ok" && $("#al-name").value.trim();
    if (!name) return;
    try {
      await api(`/api/segments/${segId}/assign`, { method: "POST", json: { name, remember: $("#al-rem").checked, whole_voice: !!($("#al-all-voice") && $("#al-all-voice").checked) } });
      toast($("#al-rem").checked ? `${name} ✓ – Stimme gelernt` : `${name} ✓`);
      await reload(true);
    } catch (e) { toast(e.message, 6000); }
  }
  async function editSpeaker(sid) {
    const s = rec.speakers.find((x) => x.id === sid);
    const others = rec.speakers.filter((x) => x.id !== sid);
    const r = await dialog(`<h2>Sprecher</h2>
      <label class="muted">Name</label><input type="text" id="sp-name" value="${esc(s.name)}">
      ${s.voices > 1 ? `<p class="muted" style="margin:0">Hier stecken ${s.voices} verschiedene Stimmen. Zum Lernen im Transkript einzelne Sätze antippen und zuordnen.</p>`
        : `<label class="row"><input type="checkbox" id="sp-rem" ${s.profile_id || unnamed(s.name) ? "checked" : ""}> Stimme merken – in Zukunft automatisch erkennen${tip("remember")}</label>`}
      ${others.length ? `<label class="muted">Oder zusammenführen mit (falls doppelt erkannt)</label>
        <select id="sp-merge"><option value="">—</option>${others.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join("")}</select>` : ""}
      <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Speichern</button></div>`,
    (b) => { $("#sp-name", b).select(); if (unnamed(s.name)) $("#sp-name", b).value = ""; });
    if (r !== "ok") return;
    const merge = $("#sp-merge") && $("#sp-merge").value;
    if (merge) {
      await api(`/api/recordings/${id}/speakers/merge`, { method: "POST", json: { source: sid, target: Number(merge) } });
      toast("Zusammengeführt");
    } else {
      const name = $("#sp-name").value.trim();
      const remember = !!($("#sp-rem") && $("#sp-rem").checked);
      try {
        await api(`/api/speakers/${sid}`, { method: "PATCH", json: { name, remember } });
        toast(remember ? `${name}: Stimme gespeichert ✓` : "Umbenannt");
      } catch (e) { toast(e.message, 5000); }
    }
    await reload();
  }

  // ---------- player
  const canvas = $("#wave canvas");
  function drawWave() {
    const dpr = devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const c = canvas.getContext("2d"); c.scale(dpr, dpr);
    const peaks = rec.peaks || [];
    const cs = getComputedStyle(document.documentElement);
    const played = (audio.currentTime || 0) / (rec.duration || 1);
    const n = Math.min(peaks.length, Math.floor(w / 3)) || 1;
    for (let i = 0; i < n; i++) {
      const p = peaks.length ? peaks[Math.floor((i / n) * peaks.length)] : 0.05;
      const bh = Math.max(2, p * (h - 4));
      c.fillStyle = i / n < played ? cs.getPropertyValue("--accent") : cs.getPropertyValue("--line2");
      c.fillRect(i * (w / n), (h - bh) / 2, Math.max(1, w / n - 1.2), bh);
    }
  }
  function drawTimeline() {
    const d = rec.duration || 1;
    $("#tl").innerHTML = segs().map((s) => `<i style="left:${(s.start / d) * 100}%;width:${((s.end - s.start) / d) * 100}%;--c:${spk(s.speaker_id).color}"></i>`).join("")
      + (rec.highlights || []).map((h) => `<span class="hl-mark" style="left:${(h / d) * 100}%">★</span>`).join("");
  }
  const seekFromEvent = (e, el) => { const r = el.getBoundingClientRect(); seek(((e.clientX - r.left) / r.width) * (rec.duration || audio.duration || 0)); };
  $("#wave").onclick = (e) => seekFromEvent(e, $("#wave"));
  $("#tl").onclick = (e) => seekFromEvent(e, $("#tl"));
  $("#play").onclick = () => (audio.paused ? audio.play() : audio.pause());
  $("#back15").onclick = () => (audio.currentTime = Math.max(0, audio.currentTime - 15));
  $("#fwd15").onclick = () => (audio.currentTime = audio.currentTime + 15);
  $("#rate").onclick = () => {
    const rates = [1, 1.25, 1.5, 1.75, 2];
    const next = rates[(rates.indexOf(prefs.rate) + 1) % rates.length];
    audio.playbackRate = next; setPref("rate", next); $("#rate").textContent = next + "×";
  };
  audio.onplay = audio.onpause = () => {
    $("#play-ico").innerHTML = audio.paused ? '<path d="M8 5v14l11-7z"/>' : '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>';
  };
  let lastActive = null;
  audio.ontimeupdate = () => {
    $("#ptime").textContent = `${fmtTime(audio.currentTime)} / ${fmtTime(rec.duration || audio.duration)}`;
    drawWave();
    const t = audio.currentTime;
    const cur = segs().find((s) => t >= s.start && t < s.end + 0.3);
    if (cur && cur.id !== lastActive) {
      lastActive = cur.id;
      $$(".tseg.active").forEach((x) => x.classList.remove("active"));
      const el = $(`.tseg[data-id="${cur.id}"]`);
      if (el) { el.classList.add("active"); if (prefs.autoscroll && !audio.paused) el.scrollIntoView({ block: "center", behavior: "smooth" }); }
    }
  };
  const ro = new ResizeObserver(() => drawWave()); ro.observe(canvas);

  // ---------- tabs
  const tabs = { summary: tabSummary, transcript: tabTranscript, mindmap: tabMindmap, ask: tabAsk, notes: tabNotes, export: tabExport };
  let currentTab = tabs[tab0] ? tab0 : "summary";
  const showTab = (t) => {
    currentTab = t; setPref("detailTab", t);
    $$("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
    tabs[t]();
  };
  $$("#tabs button").forEach((b) => b.onclick = () => showTab(b.dataset.tab));

  function tabTranscript() {
    const hl = rec.highlights || [];
    if (!segs().length) { $("#tab").innerHTML = `<div class="empty"><p>${rec.status === "done" ? "Keine Sprache erkannt." : "Transkript entsteht gerade …"}</p></div>`; return; }
    $("#tab").innerHTML = `<div class="row" style="margin-bottom:12px">
        <label class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input type="search" id="tfind" placeholder="Im Transkript suchen"></label>
        <button class="btn sm" id="frep">Suchen & Ersetzen</button>
        <label class="row muted" style="font-size:13px"><input type="checkbox" id="ascroll" ${prefs.autoscroll ? "checked" : ""}> Mitscrollen</label></div>
      <div class="seg-list" id="segs">${segs().map((s) => {
        const p = spk(s.speaker_id);
        const isHl = hl.some((h) => h >= s.start - 2 && h <= s.end + 2);
        return `<div class="tseg${isHl ? " hl" : ""}" data-id="${s.id}" style="--c:${p.color}">
          <div class="spk"><button data-sid="${s.speaker_id}" title="Wer sagt das? – antippen zum Zuordnen">${esc(p.name)}</button><span class="ts" data-seek="${s.start}">${fmtTime(s.start)}${isHl ? " ★" : ""}</span></div>
          <div class="tx" contenteditable="plaintext-only" spellcheck="false" data-id="${s.id}">${esc(s.text)}</div></div>`;
      }).join("")}</div>`;
    $$("#segs .spk button").forEach((b) => b.onclick = () => assignLine(Number(b.closest(".tseg").dataset.id)));
    $$("#segs .tx").forEach((el) => {
      el.addEventListener("blur", async () => {
        const s = segs().find((x) => x.id === Number(el.dataset.id));
        const t = el.textContent.trim();
        if (s && t !== s.text) { s.text = t; await api(`/api/segments/${s.id}`, { method: "PATCH", json: { text: t } }); toast("Gespeichert"); }
      });
    });
    $("#ascroll").onchange = (e) => setPref("autoscroll", e.target.checked);
    $("#tfind").addEventListener("input", debounce((e) => {
      const q = e.target.value.trim().toLowerCase();
      $$("#segs .tseg").forEach((row) => {
        const s = segs().find((x) => x.id === Number(row.dataset.id));
        row.classList.toggle("hidden", !!q && !s.text.toLowerCase().includes(q) && !spk(s.speaker_id).name.toLowerCase().includes(q));
        const tx = $(".tx", row);
        tx.innerHTML = q ? esc(s.text).replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), (m) => `<mark>${m}</mark>`) : esc(s.text);
      });
    }, 150));
    $("#frep").onclick = async () => {
      const r = await dialog(`<h2>Suchen & Ersetzen</h2><input type="text" id="f1" placeholder="Suchen (z. B. falsch erkannter Name)">
        <input type="text" id="f2" placeholder="Ersetzen durch"><label class="row"><input type="checkbox" id="f3" checked> Auch Sprechernamen</label>
        <label class="row"><input type="checkbox" id="f4"> Dauerhaft ins Vokabular übernehmen (künftige Aufnahmen)</label>
        <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Alle ersetzen</button></div>`);
      if (r !== "ok" || !$("#f1").value) return;
      const find = $("#f1").value, replace = $("#f2").value;
      const res = await api(`/api/recordings/${id}/find_replace`, { method: "POST", json: { find, replace, speakers: $("#f3").checked } });
      if ($("#f4").checked) {
        const s = await api("/api/settings");
        await api("/api/settings", { method: "PUT", json: { vocabulary: [...(s.vocabulary || []), { from: find, to: replace }] } });
      }
      toast(`${res.changed} Stellen ersetzt`); reload();
    };
  }

  function renderMd(el, content, sumId) {
    el.innerHTML = MD.render(content);
    if (sumId) $$('input[type="checkbox"][data-line]', el).forEach((cb) => cb.onchange = async () => {
      const s = rec.summaries.find((x) => x.id === sumId);
      s.content = MD.toggleTask(s.content, Number(cb.dataset.line));
      cb.closest("li").classList.toggle("done", cb.checked);
      await api(`/api/summaries/${sumId}`, { method: "PATCH", json: { content: s.content } });
    });
  }

  function tplOptions(sel = "auto") {
    const byCat = {};
    state.templates.filter((t) => t.id !== "mindmap").forEach((t) => (byCat[t.category] = byCat[t.category] || []).push(t));
    return Object.entries(byCat).map(([c, ts]) => `<optgroup label="${esc(c)}">${ts.map((t) => `<option value="${t.id}" ${t.id === sel ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</optgroup>`).join("");
  }

  function tabSummary() {
    const list = rec.summaries.filter((s) => s.template_id !== "mindmap");
    const noAi = state.status && !state.status.ai_ready;
    $("#tab").innerHTML = `<div class="row" style="margin-bottom:16px">
        <select id="tpl" style="max-width:340px">${tplOptions()}</select>
        <button class="btn primary" id="gen" ${!segs().length ? "disabled" : ""}>Zusammenfassen</button>
        <span class="muted" style="font-size:13px">Mehrere Vorlagen = mehrere Blickwinkel auf dasselbe Gespräch. <a href="#/templates">Vorlagen verwalten →</a></span></div>
      ${noAi ? `<div class="card" style="margin-bottom:14px"><b>${esc(state.status.ai_problem || "Keine KI verbunden")}.</b> <a href="#/settings?s=ai">Claude, ChatGPT oder lokal (Ollama) verbinden →</a>
        <div class="muted" style="font-size:13px">Transkript und Sprecher funktionieren auch ohne KI.</div></div>` : ""}
      <div id="sums">${list.length ? "" : `<div class="empty" style="padding:40px"><p>${segs().length ? "Noch keine Zusammenfassung. Vorlage wählen und los." : "Wartet auf das Transkript …"}</p></div>`}</div>`;
    const box = $("#sums");
    list.forEach((s) => box.appendChild(sumCard(s)));
    $("#gen").onclick = () => generate($("#tpl").value);
  }
  function sumCard(s) {
    const el = document.createElement("div");
    el.className = "card sum-card";
    el.innerHTML = `<div class="sum-head"><span class="eyebrow">${esc(s.title)}</span><span class="muted" style="font-size:12px">${s.model ? esc(s.model) + " · " : ""}${fmtDate(s.created_at)}</span>
      <span class="spacer"></span><button class="btn ghost sm icon" data-a="copy" title="Kopieren"><svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4H4v12h4"/></svg></button>
      <button class="btn ghost sm icon" data-a="edit" title="Bearbeiten"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg></button>
      <button class="btn ghost sm icon" data-a="del" title="Löschen"><svg viewBox="0 0 24 24"><path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/></svg></button></div><div class="md"></div>`;
    renderMd($(".md", el), s.content, s.id);
    $('[data-a="copy"]', el).onclick = () => { navigator.clipboard.writeText(s.content); toast("Kopiert (Markdown)"); };
    $('[data-a="del"]', el).onclick = async () => { if (await confirmBox("Zusammenfassung löschen?", s.title)) { await api(`/api/summaries/${s.id}`, { method: "DELETE" }); reload(); } };
    $('[data-a="edit"]', el).onclick = async () => {
      const r = await dialog(`<h2>${esc(s.title)}</h2><textarea id="ed" style="min-height:50vh;font-family:var(--mono);font-size:13px">${esc(s.content)}</textarea>
        <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Speichern</button></div>`);
      if (r === "ok") { s.content = $("#ed").value; await api(`/api/summaries/${s.id}`, { method: "PATCH", json: { content: s.content } }); renderMd($(".md", el), s.content, s.id); }
    };
    return el;
  }
  async function generate(tid, target) {
    const tpl = state.templates.find((t) => t.id === tid);
    const box = target || $("#sums");
    if (!target) { const empty = $(".empty", box); if (empty) empty.remove(); }
    const el = document.createElement("div");
    el.className = "card sum-card";
    el.innerHTML = `<div class="sum-head"><span class="eyebrow">${esc(tpl ? tpl.name : tid)}</span><span class="dot busy" style="margin-left:6px"></span></div><div class="md streaming"></div>`;
    if (!target) box.prepend(el);
    const btn = $("#gen"); if (btn) btn.disabled = true;
    try {
      await streamText(`/api/recordings/${id}/summaries`, { template_id: tid }, (txt) => { if (!target) $(".md", el).innerHTML = MD.render(txt); });
      await reload(true);
      return true;
    } catch (e) {
      $(".md", el).classList.remove("streaming");
      $(".md", el).innerHTML = `<p style="color:#EF4444"><b>Fehler:</b> ${esc(e.message)}</p><p><a href="#/settings?s=ai">KI-Einstellungen prüfen →</a></p>`;
      return false;
    } finally { if (btn) btn.disabled = false; }
  }

  function tabMindmap() {
    const mm = rec.summaries.find((s) => s.template_id === "mindmap");
    $("#tab").innerHTML = `<div class="row" style="margin-bottom:14px"><button class="btn ${mm ? "" : "primary"}" id="mmgen" ${!segs().length ? "disabled" : ""}>${mm ? "Neu erstellen" : "Mind Map erstellen"}</button>
      ${mm ? `<button class="btn" id="mmsvg">SVG speichern</button><button class="btn" id="mmpng">PNG speichern</button>` : ""}</div>
      <div class="mindmap" id="mm">${mm ? "" : `<div class="empty"><p>Die KI baut aus dem Gespräch eine Mind Map.</p></div>`}</div>`;
    if (mm) $("#mm").innerHTML = mindmapSvg(MD.outline(mm.content));
    $("#mmgen").onclick = async () => {
      $("#mmgen").disabled = true; $("#mm").innerHTML = `<div class="empty"><span class="dot busy"></span> Mind Map entsteht …</div>`;
      const ok = await generate("mindmap", document.createElement("div"));
      if (ok) { showTab("mindmap"); } else { $("#mm").innerHTML = `<div class="empty"><p>Fehler – KI-Einstellungen prüfen.</p></div>`; $("#mmgen").disabled = false; }
    };
    if (mm) {
      $("#mmsvg").onclick = () => downloadBlob(new Blob([$("#mm").innerHTML], { type: "image/svg+xml" }), `${rec.title} – Mind Map.svg`);
      $("#mmpng").onclick = () => {
        const svg = $("#mm svg"), img = new Image();
        img.onload = () => {
          const c = document.createElement("canvas"); c.width = svg.width.baseVal.value * 2; c.height = svg.height.baseVal.value * 2;
          const x = c.getContext("2d"); x.fillStyle = getComputedStyle(document.body).getPropertyValue("--card"); x.fillRect(0, 0, c.width, c.height); x.scale(2, 2); x.drawImage(img, 0, 0);
          c.toBlob((b) => downloadBlob(b, `${rec.title} – Mind Map.png`));
        };
        img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(svg));
      };
    }
  }

  function tabAsk() {
    $("#tab").innerHTML = `<div class="chat" id="chat"></div>
      <div class="suggest" id="sugg">${["Was wurde entschieden?", "Welche To-dos habe ich?", "Wer hat was zugesagt?", "Gab es Widersprüche oder offene Fragen?",
        "Schreib eine kurze Mail an alle Teilnehmer."].map((q) => `<button>${q}</button>`).join("")}</div>
      <form class="composer" id="cf"><textarea id="cq" rows="1" placeholder="Frag etwas zu dieser Aufnahme …"></textarea><button class="btn primary icon" style="height:48px;width:48px">
      <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form>`;
    chatUI(`/api/chat/${id}`, `/api/recordings/${id}/ask`);
  }

  function tabNotes() {
    $("#tab").innerHTML = `<p class="muted">Eigene Notizen. Fließen in Zusammenfassungen ein.</p>
      <textarea id="notes" style="min-height:300px">${esc(rec.notes || "")}</textarea>
      <div class="row" style="margin-top:12px"><label class="muted">Ordner</label><input type="text" id="folder" value="${esc(rec.folder || "")}" placeholder="z. B. Voltage, Coffee Club, Uni" style="max-width:320px"></div>`;
    const save = debounce(async () => { rec.notes = $("#notes").value; await api(`/api/recordings/${id}`, { method: "PATCH", json: { notes: rec.notes } }); toast("Notizen gespeichert", 1200); }, 800);
    $("#notes").addEventListener("input", save);
    $("#folder").addEventListener("change", async (e) => { rec.folder = e.target.value.trim(); await api(`/api/recordings/${id}`, { method: "PATCH", json: { folder: rec.folder } }); renderMeta(); });
  }

  function tabExport() {
    const f = [["md", "Markdown", "Zusammenfassungen + Transkript – für Notion, Obsidian"], ["docx", "Word", "Zum Weiterschicken"], ["txt", "Text", "Transkript pur"],
      ["srt", "SRT", "Untertitel mit Sprechern"], ["vtt", "WebVTT", "Untertitel fürs Web"], ["json", "JSON", "Alle Daten, maschinenlesbar"]];
    $("#tab").innerHTML = `<div class="grid">${f.map(([k, n, d]) => `<a class="card tpl" href="/api/recordings/${id}/export/${k}" download><b>${n}</b><div class="muted">${d}</div></a>`).join("")}
      <button class="card tpl" id="cpy" style="text-align:left"><b>In Zwischenablage</b><div class="muted">Markdown kopieren</div></button>
      <button class="card tpl" id="prt" style="text-align:left"><b>PDF</b><div class="muted">Über Drucken → Als PDF sichern</div></button>
      <a class="card tpl" href="/api/recordings/${id}/audio" download><b>Audio</b><div class="muted">Originalaufnahme</div></a></div>`;
    $("#cpy").onclick = async () => { const r = await api(`/api/recordings/${id}/export/md`); navigator.clipboard.writeText(await r.text()); toast("Kopiert"); };
    $("#prt").onclick = () => { showTab("summary"); setTimeout(() => print(), 300); };
  }

  // ---------- more menu
  $("#more").onclick = async () => {
    const r = await dialog(`<h2>Aufnahme</h2>
      <button class="btn" value="reprocess">Neu verarbeiten (andere Einstellungen/Modell)</button>
      <button class="btn" value="reid">Personen neu erkennen</button>
      <button class="btn" value="title">Umbenennen</button>
      <button class="btn danger" value="delete">Löschen</button>
      <button class="btn ghost" value="cancel">Abbrechen</button>`);
    if (r === "reprocess") { await api(`/api/recordings/${id}/reprocess`, { method: "POST" }); toast("Wird neu verarbeitet …"); reload(); }
    if (r === "reid") { const x = await api(`/api/recordings/${id}/reidentify`, { method: "POST" }); toast(`${x.renamed} Person(en) erkannt`); reload(); }
    if (r === "title") { const t = await promptText("Titel", rec.title); if (t) { await api(`/api/recordings/${id}`, { method: "PATCH", json: { title: t } }); reload(); } }
    if (r === "delete" && await confirmBox("Aufnahme löschen?", "Audio, Transkript und Zusammenfassungen werden endgültig entfernt.")) {
      await api(`/api/recordings/${id}`, { method: "DELETE" }); toast("Gelöscht"); location.hash = "#/";
    }
  };

  async function reload(keepTab) {
    rec = await api(`/api/recordings/${id}`);
    state.current = rec;
    $("#dtitle").textContent = rec.title;
    renderMeta(); renderSpeakers(); drawWave();
    if (keepTab !== false) showTab(currentTab);
  }

  const off = onEvent((ev) => {
    if (ev.id !== id) return;
    if (ev.type === "progress") {
      if ($("#pbar")) { $("#pbar").style.width = Math.round(ev.progress * 100) + "%"; $("#pstage").textContent = ev.stage; $("#ppct").textContent = Math.round(ev.progress * 100) + " %"; }
      else { rec.status = "processing"; rec.stage = ev.stage; rec.progress = ev.progress; renderMeta(); }
    }
    if (["done", "summary_done", "error", "queued"].includes(ev.type)) reload();
    if (ev.type === "summary_started" && currentTab === "summary") toast("Zusammenfassung wird erstellt …");
  });
  cleanup = () => { off(); ro.disconnect(); audio.pause(); };

  renderSpeakers();
  showTab(currentTab);
  const t = Number(qs().get("t"));
  if (t) { audio.currentTime = t; showTab("transcript"); }
}

// ================================================================ chat (per recording + global)
async function chatUI(historyPath, askPath) {
  const box = $("#chat");
  const add = (role, content) => {
    const el = document.createElement("div");
    el.className = "msg " + role;
    if (role === "assistant") { el.innerHTML = `<div class="md">${MD.render(content)}</div>`; } else el.textContent = content;
    box.appendChild(el);
    return el;
  };
  try { (await api(historyPath)).items.forEach((m) => add(m.role, m.content)); } catch (e) {}
  if (box.children.length) $("#sugg") && $("#sugg").classList.add("hidden");
  const ta = $("#cq");
  ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(200, ta.scrollHeight) + "px"; });
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#cf").requestSubmit(); } });
  $$("#sugg button").forEach((b) => b.onclick = () => { ta.value = b.textContent; $("#cf").requestSubmit(); });
  $("#cf").onsubmit = async (e) => {
    e.preventDefault();
    const q = ta.value.trim(); if (!q) return;
    ta.value = ""; ta.style.height = "auto";
    $("#sugg") && $("#sugg").classList.add("hidden");
    add("user", q);
    const el = add("assistant", "");
    const md = $(".md", el); md.classList.add("streaming");
    el.scrollIntoView({ block: "end" });
    try { await streamText(askPath, { question: q }, (t) => { md.innerHTML = MD.render(t); }); }
    catch (err) { md.innerHTML = `<p style="color:#EF4444">${esc(err.message)}</p>`; }
    md.classList.remove("streaming");
    el.scrollIntoView({ block: "end", behavior: "smooth" });
  };
}

// ================================================================ ASK EVERYTHING
async function viewAsk() {
  view.innerHTML = `<div class="page narrow">
    <div class="row"><span class="eyebrow">Über alle Aufnahmen</span><span class="spacer"></span><button class="btn ghost sm" id="clr">Verlauf leeren</button></div>
    <h1 class="big">Frag dein<br>Gedächtnis<span class="acc">.</span></h1>
    <div class="chat" id="chat"></div>
    <div class="suggest" id="sugg">${["Was hat Lisa letzte Woche zum Budget gesagt?", "Welche To-dos sind noch offen?", "Wann haben wir über den Headliner gesprochen?",
      "Fass meine Meetings dieser Woche zusammen."].map((q) => `<button>${q}</button>`).join("")}</div>
    <form class="composer" id="cf"><textarea id="cq" rows="1" placeholder="Was wurde wann von wem gesagt …"></textarea>
      <button class="btn primary icon" style="height:48px;width:48px"><svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form></div>`;
  $("#clr").onclick = async () => { await api("/api/chat/global", { method: "DELETE" }); viewAsk(); };
  chatUI("/api/chat/global", "/api/ask");
}

// ================================================================ PEOPLE
async function viewPeople() {
  const data = await api("/api/profiles");
  view.innerHTML = `<div class="page">
    <div class="row"><span class="eyebrow">Stimmabdrücke · bleiben auf diesem Gerät${tip("people")}</span></div>
    <h1 class="big">Personen<span class="acc">.</span></h1>
    <p class="muted" style="max-width:640px">REKORD erkennt Menschen an ihrer Stimme – live im Meeting und in jeder Aufnahme. Neue Person: im Live-Modus auf die unbekannte Stimme tippen,
      im Transkript auf den Sprecher klicken – oder hier eine Sprachprobe aufnehmen.</p>
    <div class="row" style="margin:18px 0 22px"><button class="btn primary" id="enroll">Person einsprechen</button></div>
    <div class="grid" id="people">${data.items.length ? data.items.map((p) => `<div class="card person" style="--c:${p.color}">
      <span class="avatar">${esc(initials(p.name))}</span><div style="flex:1;min-width:0"><b style="font:800 18px var(--display)">${esc(p.name)}</b>
      <div class="muted" style="font-size:13px">${p.recordings} Aufnahme(n) · ${p.samples} Stimmproben</div></div>
      <button class="btn ghost sm icon" data-edit="${p.id}"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg></button></div>`).join("")
      : `<div class="muted">Noch niemand angelernt.</div>`}</div></div>`;
  $$("[data-edit]").forEach((b) => b.onclick = async () => {
    const p = data.items.find((x) => x.id === Number(b.dataset.edit));
    const r = await dialog(`<h2>${esc(p.name)}</h2><label class="muted">Name</label><input type="text" id="pn" value="${esc(p.name)}">
      <label class="muted">Farbe</label><input type="color" id="pc" value="${p.color}" style="width:60px;height:40px;border:0;background:none">
      <div class="row"><button class="btn danger" value="delete">Stimmabdruck löschen</button><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Speichern</button></div>`);
    if (r === "ok") await api(`/api/profiles/${p.id}`, { method: "PATCH", json: { name: $("#pn").value.trim(), color: $("#pc").value } });
    if (r === "delete" && await confirmBox(`${p.name} vergessen?`, "Der Stimmabdruck wird gelöscht. Bestehende Transkripte behalten den Namen.")) await api(`/api/profiles/${p.id}`, { method: "DELETE" });
    viewPeople();
  });
  $("#enroll").onclick = async () => { await enrollDialog(); viewPeople(); };
}

// Every person reads their OWN text (~50 s): long enough for a solid voiceprint, varied sounds, numbers, questions.
const READ_POOL = [
  "Heute früh habe ich zuerst einen starken Kaffee getrunken und dann in Ruhe meine Nachrichten gelesen.",
  "Auf dem Weg zur Arbeit fahre ich meistens mit dem Fahrrad, außer es regnet in Strömen.",
  "Wusstest du, dass manche Schnecken bis zu drei Jahre am Stück schlafen können?",
  "Für das Sommerfest brauchen wir noch Getränke, Tische, Stühle und eine ordentliche Lautsprecheranlage.",
  "Wenn ich ehrlich bin, finde ich lange Besprechungen ohne Tagesordnung ziemlich anstrengend.",
  "Der Zug nach Zürich fährt um siebzehn Uhr zweiunddreißig von Gleis vier ab.",
  "Könnten wir das Budget bis Freitag noch einmal gemeinsam durchgehen?",
  "Im Herbst färben sich die Blätter gelb, orange und tiefrot, und die Luft riecht nach Regen.",
  "Mein Lieblingsessen ist eine Pizza mit Pilzen, Paprika und extra viel Käse.",
  "Ich glaube, wir sollten zuerst die wichtigsten Aufgaben verteilen und danach über Details sprechen.",
  "Gestern Abend war das Konzert so laut, dass mir heute noch die Ohren klingeln.",
  "Bitte schick mir die Unterlagen per E-Mail, dann schaue ich sie mir am Wochenende an.",
  "Zwölf Zwerge zogen zwanzig Zentner Zucker quer durch den Zoo.",
  "Fischers Fritz fischt frische Fische, frische Fische fischt Fischers Fritz.",
  "Das Wetter in den Bergen kann sich innerhalb einer Stunde komplett ändern.",
  "Wie viele Leute erwarten wir eigentlich beim nächsten Workshop?",
  "Ehrlich gesagt hätte ich nie gedacht, dass das Projekt so schnell fertig wird!",
  "Unsere Nachbarin hat einen kleinen Hund, der jeden Morgen pünktlich um sechs Uhr bellt.",
  "Für die Präsentation brauche ich noch drei Folien mit Zahlen und eine kurze Zusammenfassung.",
  "Am liebsten verbringe ich meine Freizeit draußen, am See oder irgendwo in den Bergen.",
  "Kannst du mir kurz erklären, wie das neue Programm eigentlich funktioniert?",
  "Die Rechnung über vierhundertneunundachtzig Euro ist schon letzte Woche bezahlt worden.",
  "Manchmal ist es besser, eine Pause zu machen und später mit frischem Kopf weiterzuarbeiten.",
  "Quer über den Platz lief ein junger Mann mit einem riesigen Strauß Sonnenblumen.",
  "Wir treffen uns am Dienstag um halb zehn im großen Besprechungsraum im dritten Stock.",
  "Hast du schon gehört, dass die Bibliothek ab nächster Woche auch sonntags geöffnet hat?",
  "Die Technik für den Abend besteht aus zwei Mikrofonen, einem Mischpult und vier Boxen.",
  "Jeder im Team sollte genau wissen, wer für welche Aufgabe verantwortlich ist.",
  "Bei schönem Wetter grillen wir im Garten, bei schlechtem kochen wir eine große Suppe.",
  "Vielleicht sollten wir den Termin um eine Woche verschieben, damit wirklich alle dabei sein können.",
  "Xaver übt jeden Abend Saxophon, sehr zur Freude seiner Nachbarn im Erdgeschoss.",
  "Ich bin gespannt, was die Kundinnen und Kunden zu unserem Vorschlag sagen werden.",
  "Achtung, die Brücke über den Fluss ist wegen Bauarbeiten bis Ende Juli gesperrt.",
  "Ob wir das schaffen? Ich denke schon, wenn wir uns die Arbeit gut aufteilen.",
];
const READ_POOL_EN = [
  "This morning I had a strong coffee first and then read my messages in peace.",
  "Most days I ride my bike to work, unless it is pouring with rain.",
  "Did you know that some snails can sleep for up to three years?",
  "For the summer party we still need drinks, tables, chairs and a decent sound system.",
  "To be honest, I find long meetings without an agenda pretty exhausting.",
  "The train to Zurich leaves at five thirty-two from platform four.",
  "Could we go through the budget together once more before Friday?",
  "In autumn the leaves turn yellow, orange and deep red, and the air smells of rain.",
  "My favourite food is a pizza with mushrooms, peppers and lots of extra cheese.",
  "I think we should split up the most important tasks first and talk about details later.",
  "The concert last night was so loud that my ears are still ringing today.",
  "Please send me the documents by email and I will look at them over the weekend.",
  "She sells seashells by the seashore, and the shells she sells are surely seashells.",
  "The weather in the mountains can change completely within a single hour.",
  "How many people are we actually expecting at the next workshop?",
  "Honestly, I never thought the project would be finished this quickly!",
  "Our neighbour has a little dog that barks every morning at exactly six o'clock.",
  "For the presentation I still need three slides with numbers and a short summary.",
  "Can you quickly explain how the new software actually works?",
  "The invoice for four hundred and eighty-nine euros was paid last week.",
  "Sometimes it is better to take a break and come back later with a fresh mind.",
  "We meet on Tuesday at half past nine in the big meeting room on the third floor.",
  "The technical setup for the evening is two microphones, a mixing desk and four speakers.",
  "Everyone on the team should know exactly who is responsible for which task.",
  "Maybe we should move the date by a week so that really everyone can be there.",
  "I am curious what our customers will say about our proposal.",
];
function readingText(name, variant = 0, lang = state.language || "de") {
  if (lang === "en") return readingTextFrom(READ_POOL_EN, name, variant,
    (who) => `Hi, my name is ${who}. I am reading this text in my normal voice so that REKORD can recognise me in meetings.`,
    "Finally I count slowly to ten: one, two, three, four, five, six, seven, eight, nine, ten.");
  return readingTextFrom(READ_POOL, name, variant,
    (who) => `Hallo, ich heiße ${who}. Ich lese diesen Text jetzt in meiner normalen Stimme vor, damit REKORD mich in Meetings erkennt.`,
    "Zum Schluss zähle ich langsam bis zehn: eins, zwei, drei, vier, fünf, sechs, sieben, acht, neun, zehn.");
}
function readingTextFrom(POOL, name, variant, open, close) {
  const key = (name || "").trim().toLowerCase() + "#" + variant;
  let h = 2166136261;
  for (const ch of key) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
  const pool = POOL.map((t, i) => [((h ^ Math.imul(i + 1, 2654435761)) >>> 0) % 100003, t]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
  return [open((name || "").trim() || "…"), ...pool.slice(0, 7), close].join(" ");
}

const ENROLL_TARGET = 45, ENROLL_MIN = 25;  // seconds of speech
// "Einfach reden lassen": ideas if the person doesn't know what to say (only shown on request)
const TALK_IDEAS = {
  de: ["Erzähl, was du heute schon gemacht hast.", "Was ist dein Lieblingsessen – und wie kocht man es?", "Beschreib den Weg von dir zuhause zur Arbeit oder Uni.",
    "Was war dein letzter Urlaub – wo, mit wem, was war das Beste?", "Woran arbeitest du gerade, und was ist dabei schwierig?", "Erklär einem Kind, was du beruflich machst oder studierst.",
    "Welches Buch, welche Serie oder welcher Film hat dich zuletzt beeindruckt?", "Was würdest du mit einem freien Tag machen?", "Erzähl von einem Konzert oder Event, das du nie vergisst."],
  en: ["Tell what you have done today so far.", "What is your favourite food – and how do you cook it?", "Describe your way from home to work or university.",
    "Where did you go on your last holiday, and what was the best part?", "What are you working on right now, and what is hard about it?", "Explain to a child what you do or study.",
    "Which book, series or film impressed you lately?", "What would you do with a free day?", "Tell about a concert or event you will never forget."],
};

// counts the seconds in which someone really speaks (pauses don't count), from the microphone level
function speechMeter(stream, onTick) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});  // browsers start audio only after a click – this is one
  const an = ctx.createAnalyser(); an.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(an);
  const buf = new Float32Array(an.fftSize);
  let floor = 0.02, speech = 0, wall = 0, lastVoice = -1;
  const t = setInterval(() => {
    an.getFloatTimeDomainData(buf);
    let sum = 0; for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length);
    floor = rms < floor ? rms : floor * 1.002;  // background noise level, follows slowly upwards
    if (rms > Math.max(0.006, floor * 2)) lastVoice = wall;
    const talking = lastVoice >= 0 && wall - lastVoice <= 0.4;  // short gaps between words still count as talking
    if (talking) speech += 0.1;
    wall += 0.1;
    onTick({ speech, wall, level: Math.min(1, rms * 8), talking });
  }, 100);
  return () => { clearInterval(t); ctx.close().catch(() => {}); };
}

async function enrollDialog(opts = {}) {
  let rec, chunks = [], stopMeter = null, secs = 0, stream, variant = 0, mode = prefs.enrollMode || "read", idea = -1;
  let recordings = [], voices = [], pickedVoice = null, player = null, playUntil = 0;
  try { state.language = (await api("/api/settings")).language; } catch (e) {}
  const lang = state.language === "en" ? "en" : "de";
  const title = opts.intro ? `Vorstellungsrunde${opts.step ? " · " + opts.step : ""}` : "Person einsprechen";
  const r = await dialog(`<h2>${title}${tip("intro")}</h2>
    <input type="text" id="en-name" placeholder="Name der Person" value="${esc(opts.name || "")}" autocomplete="off">
    <div><b>Wie soll REKORD die Stimme lernen?</b>${tip("enrollmode")}</div>
    <div class="seg" id="en-mode" style="align-self:flex-start;flex-wrap:wrap">
      <button type="button" data-m="read">Text vorlesen</button><button type="button" data-m="free">Einfach reden lassen</button><button type="button" data-m="recording">Aus Aufnahme lernen</button></div>
    <div id="en-live">
      <div id="en-read"><p class="muted" style="margin:0 0 6px">${opts.intro ? "Mikro zur Person. Sie liest ihren eigenen Text vor" : "Lies diesen Text vor"} – ganz normal, wie im Meeting (ca. ${ENROLL_TARGET} Sekunden):</p>
        <blockquote id="en-text" class="read-text"></blockquote>
        <div class="row"><button type="button" class="btn ghost sm" id="en-other">↻ Anderer Text</button></div></div>
      <div id="en-free"><p class="muted" style="margin:0 0 6px">Die Person redet einfach – über irgendwas, so lange sie will. Kein Text, nichts vorlesen.
        Passt auch, wenn jemand gerade sowieso redet, z. B. der Prof am Anfang der Vorlesung: Mikro in seine Richtung, Aufnahme starten.
        Kurze Zwischenrufe anderer lässt REKORD weg.</p>
        <div class="row"><button type="button" class="btn ghost sm" id="en-idea">💬 Gesprächsidee</button></div>
        <blockquote id="en-idea-text" class="read-text" style="display:none"></blockquote></div>
      <div class="row" style="margin-top:8px"><button type="button" class="btn primary" id="en-rec">● Aufnahme starten</button><span class="timer" id="en-t">0 s</span>
        <span class="lvl" style="flex:1;max-width:160px;height:8px;border-radius:4px;background:var(--line,#ddd);overflow:hidden"><i id="en-lvl" style="display:block;height:100%;width:0%;background:var(--accent)"></i></span></div>
      <div class="progress" style="width:100%"><i id="en-bar" style="width:0%"></i></div>
      <div class="muted" id="en-hint" style="font-size:13px">Gezählt wird nur, wenn wirklich gesprochen wird. Mindestens ${ENROLL_MIN} Sekunden – je länger, desto sicherer.</div>
      <details><summary class="muted" style="cursor:pointer">…oder eine Datei mit nur dieser Person</summary><input type="file" id="en-file" accept="audio/*,video/*"></details>
    </div>
    <div id="en-recording">
      <p class="muted" style="margin:0 0 6px">Die Stimme aus einer fertigen Aufnahme nehmen – z. B. den Prof aus der Vorlesung. Aufnahme wählen, Stimme anhören, auswählen.</p>
      <select id="en-recsel"><option value="">Aufnahme wählen …</option></select>
      <div id="en-voices" style="display:flex;flex-direction:column;gap:6px;margin-top:8px"></div>
      <audio id="en-audio" preload="none"></audio>
    </div>
    <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok" id="en-ok" disabled>Stimme speichern</button></div>`,
  (b) => {
    const text = () => { $("#en-text", b).textContent = readingText($("#en-name", b).value, variant); };
    const ready = () => {
      const named = !!$("#en-name", b).value.trim();
      $("#en-ok", b).disabled = !named || (mode === "recording" ? pickedVoice === null : !(secs >= ENROLL_MIN || $("#en-file", b).files.length));
    };
    const stopRec = () => { if (rec && rec.state === "recording") rec.stop(); };
    const drawVoices = () => {
      $("#en-voices", b).innerHTML = voices.length ? voices.map((v, k) => `<label class="nm-row" style="--c:${esc(v.color)};cursor:pointer">
          <input type="radio" name="en-v" value="${k}" ${pickedVoice === k ? "checked" : ""}>
          <button type="button" class="btn sm icon" data-play="${k}" title="Anhören">▶</button>
          <span class="nm-who"><b>${esc(v.known ? v.name : v.name === UNKNOWN || v.name === AUDIENCE ? `Stimme ab ${fmtTime(v.first)}` : v.name)} · ${Math.round(v.seconds)} s</b>
          <small>„${esc(v.text)}“</small></span></label>`).join("")
        : `<span class="muted">${$("#en-recsel", b).value ? "Keine Stimmen in dieser Aufnahme." : ""}</span>`;
      $$("#en-voices [data-play]", b).forEach((x) => x.onclick = (e) => {
        e.preventDefault();
        const v = voices[Number(x.dataset.play)], [a, z] = v.samples[0];
        player.currentTime = a; playUntil = Math.min(z, a + 8); player.play().catch(() => {});
      });
      $$("#en-voices input[name=en-v]", b).forEach((x) => x.onchange = () => {
        pickedVoice = Number(x.value);
        const v = voices[pickedVoice];
        if (!$("#en-name", b).value.trim() && v.known) $("#en-name", b).value = v.name;
        ready();
      });
    };
    const setMode = async (m) => {
      stopRec();
      mode = m; setPref("enrollMode", m);
      $$("#en-mode button", b).forEach((x) => x.classList.toggle("on", x.dataset.m === m));
      $("#en-live", b).style.display = m === "recording" ? "none" : "";
      $("#en-read", b).style.display = m === "read" ? "" : "none";
      $("#en-free", b).style.display = m === "free" ? "" : "none";
      $("#en-recording", b).style.display = m === "recording" ? "" : "none";
      $("#en-ok", b).textContent = m === "recording" ? "Stimme lernen" : "Stimme speichern";
      if (m === "recording" && !recordings.length) {
        try { recordings = (await api("/api/recordings")).items.filter((x) => x.status === "done"); } catch (e) {}
        $("#en-recsel", b).innerHTML = `<option value="">${recordings.length ? "Aufnahme wählen …" : "Noch keine fertige Aufnahme"}</option>`
          + recordings.map((x) => `<option value="${x.id}">${esc(x.title)} · ${fmtDate(x.created_at)}</option>`).join("");
      }
      ready();
    };
    player = $("#en-audio", b);
    player.ontimeupdate = () => { if (playUntil && player.currentTime >= playUntil) { player.pause(); playUntil = 0; } };
    text(); setMode(mode);
    $$("#en-mode button", b).forEach((x) => x.onclick = () => setMode(x.dataset.m));
    $("#en-name", b).addEventListener("input", () => { text(); ready(); });
    $("#en-other", b).onclick = () => { variant++; text(); };
    $("#en-idea", b).onclick = () => {
      const pool = TALK_IDEAS[lang]; idea = (idea + 1 + Math.floor(Math.random() * (pool.length - 1))) % pool.length;
      $("#en-idea-text", b).style.display = ""; $("#en-idea-text", b).textContent = pool[idea];
    };
    $("#en-file", b).onchange = ready;
    $("#en-recsel", b).onchange = async (e) => {
      voices = []; pickedVoice = null; drawVoices(); ready();
      if (!e.target.value) return;
      player.src = `/api/recordings/${e.target.value}/audio`;
      try { voices = (await api(`/api/recordings/${e.target.value}/voices`)).items; } catch (err) { toast(err.message); }
      drawVoices();
    };
    $("#en-rec", b).onclick = async () => {
      if (rec && rec.state === "recording") { rec.stop(); return; }
      if (!$("#en-name", b).value.trim()) { toast(mode === "read" ? "Zuerst den Namen eingeben – der Text wird für die Person erstellt." : "Zuerst den Namen eingeben."); $("#en-name", b).focus(); return; }
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: prefs.micId ? { ideal: prefs.micId } : undefined,
        echoCancellation: prefs.echoCancellation, noiseSuppression: prefs.noiseSuppression, autoGainControl: prefs.autoGainControl } }); }
      catch (e) { toast("Mikrofon nicht verfügbar: " + e.message, 5000); return; }
      rec = new MediaRecorder(stream); chunks = []; secs = 0; ready();
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        if (stopMeter) { stopMeter(); stopMeter = null; }
        stream.getTracks().forEach((t) => t.stop());
        $("#en-rec").textContent = "↺ Neu aufnehmen"; $("#en-lvl").style.width = "0%"; ready();
      };
      rec.start(1000);
      $("#en-rec").textContent = "■ Fertig";
      const keepGoing = mode === "read" ? "Weiterlesen" : "Weiterreden lassen";
      stopMeter = speechMeter(stream, ({ speech, wall, level }) => {
        secs = Math.floor(speech);
        $("#en-t").textContent = secs + " s";
        $("#en-lvl").style.width = Math.round(level * 100) + "%";
        $("#en-bar").style.width = Math.min(100, (speech / ENROLL_TARGET) * 100) + "%";
        $("#en-hint").innerHTML = secs < ENROLL_MIN ? `${keepGoing} … noch ${ENROLL_MIN - secs} s Sprache bis zum Minimum.`
          : secs < ENROLL_TARGET ? `<span style="color:#22C55E">✓ Reicht.</span> ${mode === "read" ? "Bis zum Ende lesen" : "Noch etwas länger"} macht die Erkennung noch sicherer.`
          : `<span style="color:#22C55E">✓ Perfekt.</span> Du kannst auf „Fertig“ drücken.`;
        ready();
        if (wall >= (mode === "free" ? 240 : 120)) rec.stop();
      });
    };
  });
  if (rec && rec.state === "recording") rec.stop();
  if (player) player.pause();
  await sleep(250);
  if (r !== "ok") return null;
  const name = $("#en-name").value.trim();
  if (mode === "recording") {
    const v = voices[pickedVoice], rid = $("#en-recsel").value;
    if (!name || !v) { toast("Name und Stimme wählen"); return null; }
    try {
      const prof = await api("/api/profiles/learn", { method: "POST", json: { recording_id: rid, speaker_id: v.speaker_id, voice: v.voice, name } });
      toast(`${name}: Stimme aus der Aufnahme gelernt ✓ (${Math.round(v.seconds)} s)`, 5000);
      return prof;
    } catch (e) { toast(e.message, 7000); return null; }
  }
  const file = $("#en-file").files[0] || (chunks.length ? new File(chunks, "probe.webm", { type: chunks[0].type || "audio/webm" }) : null);
  if (!name || !file) { toast("Name und Sprachprobe nötig"); return null; }
  const fd = new FormData(); fd.append("name", name); fd.append("file", file); fd.append("mode", mode);
  toast("Stimmabdruck wird berechnet …", 8000);
  try {
    const prof = await api("/api/profiles/enroll", { method: "POST", body: fd });
    const q = prof.quality || {};
    const grade = q.consistency >= 0.85 ? "sehr gut" : q.consistency >= 0.75 ? "gut" : "ok – nochmal einsprechen macht sie sicherer";
    toast(`${name}: Stimme gespeichert ✓ · ${Math.round(q.seconds || 0)} s Sprache · Qualität ${grade}`
      + (q.left_out >= 3 ? ` · ${Math.round(q.left_out)} s andere Stimmen weggelassen` : ""), 6000);
    return prof;
  } catch (e) { toast(e.message, 7000); return null; }
}

// ================================================================ TEMPLATES
async function viewTemplates() {
  state.templates = (await api("/api/templates")).items;
  const byCat = {};
  state.templates.forEach((t) => (byCat[t.category] = byCat[t.category] || []).push(t));
  view.innerHTML = `<div class="page">
    <div class="row"><span class="eyebrow">${state.templates.length} Vorlagen</span></div>
    <h1 class="big">Vorlagen<span class="acc">.</span></h1>
    <div class="row" style="margin-bottom:10px"><button class="btn primary" id="new">Eigene Vorlage</button>
      <span class="muted">Jede Vorlage ist ein Prompt. Bau dir dein eigenes Protokoll-Format.</span></div>
    ${Object.entries(byCat).map(([c, ts]) => `<h2>${esc(c)}</h2><div class="grid">${ts.map((t) => `<div class="card tpl" data-id="${t.id}">
      <b>${esc(t.name)}</b>${t.builtin ? "" : ` <span class="badge acc">eigene</span>`}<div class="muted" style="font-size:13.5px;margin-top:4px">${esc(t.description || "")}</div></div>`).join("")}</div>`).join("")}</div>`;
  $$(".tpl").forEach((el) => el.onclick = () => editTemplate(state.templates.find((t) => t.id === el.dataset.id)));
  $("#new").onclick = () => editTemplate(null);
}
async function editTemplate(t) {
  const builtin = t && t.builtin;
  const r = await dialog(`<h2>${t ? esc(t.name) : "Neue Vorlage"}</h2>
    ${builtin ? `<p class="muted" style="margin:0">Eingebaute Vorlage – Speichern legt eine eigene Kopie an.</p>` : ""}
    <input type="text" id="tn" placeholder="Name" value="${esc(t ? (builtin ? t.name + " (eigene)" : t.name) : "")}">
    <input type="text" id="tc" placeholder="Kategorie" value="${esc(t ? (builtin ? "Eigene" : t.category) : "Eigene")}">
    <input type="text" id="td" placeholder="Kurzbeschreibung" value="${esc(t ? t.description : "")}">
    <textarea id="tp" style="min-height:260px;font-family:var(--mono);font-size:13px" placeholder="Was soll die KI liefern? Struktur, Abschnitte, Ton …">${esc(t ? t.prompt : "# <Titel>\n## Kurzfassung\n## …\n## To-dos (- [ ] Aufgabe — **Person** — Deadline)")}</textarea>
    <div class="row">${t && !builtin ? `<button class="btn danger" value="delete">Löschen</button>` : ""}<span class="spacer"></span>
      <button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Speichern</button></div>`);
  if (r === "ok") {
    await api("/api/templates", { method: "POST", json: { id: t && !builtin ? t.id : null, name: $("#tn").value.trim() || "Vorlage", category: $("#tc").value.trim(),
      description: $("#td").value.trim(), prompt: $("#tp").value } });
    toast("Vorlage gespeichert");
  }
  if (r === "delete") await api(`/api/templates/${t.id}`, { method: "DELETE" });
  state.templates = null;
  viewTemplates();
}

// ================================================================ SETTINGS
const ACCENTS = [["#FF5A1F", "Voltage"], ["#2D7FF9", "Electric"], ["#C6F432", "Acid"], ["#E11D74", "Magenta"], ["#8B5CF6", "Violet"],
  ["#FACC15", "Yellow"], ["#EF4444", "Red"], ["#14B8A6", "Teal"], ["#F6F5F2", "Mono"]];
const LANGS = [["", "Automatisch (pro Satz)"], ["de", "Deutsch"], ["en", "Englisch"], ["fr", "Französisch"], ["it", "Italienisch"], ["es", "Spanisch"],
  ["nl", "Niederländisch"], ["pt", "Portugiesisch"], ["pl", "Polnisch"], ["tr", "Türkisch"], ["ru", "Russisch"], ["uk", "Ukrainisch"], ["hr", "Kroatisch"],
  ["sr", "Serbisch"], ["ar", "Arabisch"], ["zh", "Chinesisch"], ["ja", "Japanisch"], ["ko", "Koreanisch"]];

// Lokal (Ollama): install, start, one-click model downloads with progress – no terminal, no website
let ollTimer = null, ollStop = null;
async function ollamaPanel(cfg) {
  clearTimeout(ollTimer); if (ollStop) { ollStop(); ollStop = null; }
  const box = $("#oll"); if (!box) return;
  let st;
  try { st = await api("/api/ollama"); } catch (e) { box.textContent = e.message; return; }
  const pulling = Object.entries(st.pulls).filter(([, v]) => v.state === "downloading");
  const installed = new Set(st.models.map((m) => m.name));
  const settingUp = ["installing", "starting", "pulling"].includes(st.setup.state);
  const fits = `passend zu deinen ${gbFmt(st.ram_gb)} RAM`;
  let html = "";
  if (settingUp) {
    html = `<div id="oll-prog"></div>`;
  } else if (!st.installed) {
    html = IS_LOCAL && st.can_install
      ? `<p style="margin-top:0">Ein Klick: REKORD installiert <b>Ollama</b> (das kostenlose Programm für lokale KI) und lädt <b>${esc(st.default)}</b>, ${fits}.
          Dauert je nach Internet 5–15 Minuten, danach läuft alles offline.</p>
         <div class="row"><button class="btn primary" id="oll-setup">Lokal einrichten</button></div>
         ${st.setup.state === "error" ? `<p style="color:#EF4444">✗ ${esc(st.setup.error)}</p>` : ""}`
      : `<p style="margin-top:0">Die lokale KI wird <b>am Computer</b> eingerichtet: dort REKORD öffnen → Einstellungen → KI → Lokal → <b>Lokal einrichten</b>.</p>`;
  } else if (!st.running) {
    html = `<div class="row"><span class="muted">Ollama ist installiert, läuft aber nicht.</span><button class="btn primary" id="oll-start">Ollama starten</button></div>`;
  } else {
    const has = (n) => installed.has(n) || installed.has(n + ":latest");
    const best = st.recommended.find((r) => r.best) || { name: st.best, size_gb: 0 };
    const bestPull = st.pulls[best.name] || {};
    const pct = (pr) => (pr.total ? Math.round((pr.done / pr.total) * 100) : 0);
    html = `<div class="muted" style="font-size:13px;margin-bottom:10px"><span class="dot ok"></span>Ollama läuft${st.version ? " · v" + esc(st.version) : ""}</div>
      <div class="card" style="margin-bottom:14px;padding:14px">
        <div class="eyebrow" style="margin-bottom:4px">Dein Computer${tip("bestmodel")}</div>
        <div><b>${esc(st.hardware.label)}</b> → am besten: <b>${esc(best.name)}</b> <span class="muted">${gbFmt(best.size_gb)}</span></div>
        <div style="margin-top:8px">${cfg.model === best.name || cfg.model === best.name + ":latest" ? `<span class="badge acc">✓ wird verwendet</span>`
          : bestPull.state === "downloading" ? `<span class="muted">Lädt ${pct(bestPull)} % – danach wird es automatisch verwendet</span>
              <div class="progress" style="width:100%"><i style="width:${pct(bestPull)}%"></i></div>`
          : IS_LOCAL ? `<button class="btn primary sm" id="oll-best">${has(best.name) ? `${esc(best.name)} verwenden` : `${esc(best.name)} laden & verwenden`}</button>` : ""}</div></div>`;
    if (st.models.length) {
      const unused = st.models.filter((m) => m.name !== cfg.model);
      const freeGb = unused.reduce((a, m) => a + (m.size_gb || 0), 0);
      html += `<div class="eyebrow" style="margin-bottom:6px">Auf diesem Computer${IS_LOCAL ? tip("ollamadelete") : ""}</div>
      <div class="oll-models" style="margin-bottom:14px">${st.models.map((m) => {
        const on = m.name === cfg.model;
        return `<div class="model-row"><div><b>${on ? "● " : ""}${esc(m.name)}</b> <span class="muted">${gbFmt(m.size_gb)}</span>
          ${on ? `<span class="badge acc">wird verwendet</span>` : ""}${m.fits === false ? ` <span class="badge" title="Mehr als ~60 % deines Arbeitsspeichers">zu groß für ${gbFmt(st.ram_gb)} RAM</span>` : ""}</div>
          <div class="row" style="gap:6px">${on ? "" : `<button class="btn sm" data-use="${esc(m.name)}">Verwenden</button>`}
          ${IS_LOCAL ? `<button class="btn ghost sm" data-odel="${esc(m.name)}" title="Vom Computer löschen">🗑 Löschen</button>` : ""}</div></div>`;
      }).join("")}
      ${IS_LOCAL && unused.length > 1 ? `<div class="row" style="margin-top:8px"><button class="btn ghost sm" id="oll-clean">Alle nicht verwendeten löschen · ${gbFmt(freeGb)} frei machen</button></div>` : ""}</div>
      ${st.service ? `<p class="muted" style="font-size:13px">Ollama läuft hier als Systemdienst – der Speicherort für dessen Modelle wird im Dienst festgelegt (<span class="kbd">sudo systemctl edit ollama</span> → <span class="kbd">Environment="OLLAMA_MODELS=…"</span>).</p>` : ""}`;
    }
    html += `<div class="eyebrow" style="margin-bottom:6px">Weitere Modelle</div>` + st.recommended.map((r) => {
      const pr = st.pulls[r.name] || {};
      const right = has(r.name) ? `<span class="badge">geladen</span>`
        : pr.state === "downloading" ? `<span class="muted">${pct(pr) ? pct(pr) + " %" : esc(pr.status || "…")}</span>`
        : `<button class="btn sm ${r.best && !st.models.length ? "primary" : ""}" data-pull="${esc(r.name)}">${r.fits ? "Laden & verwenden" : "Trotzdem laden"}</button>`;
      return `<div class="model-row" style="${r.fits ? "" : "opacity:.6"}"><div><b>${esc(r.name)}</b> ${r.best ? `<span class="badge acc">am besten für diesen Computer</span>` : ""}
        <span class="muted">${gbFmt(r.size_gb)} · ab ${r.ram_gb} GB RAM</span>
        <div class="muted" style="font-size:13px">${esc(r.note)}${r.fits ? "" : " · läuft hier nur langsam"}${pr.state === "error" ? ` · <span style="color:#EF4444">${esc(pr.error)}</span>` : ""}</div>
        ${pr.state === "downloading" ? `<div class="progress" style="width:100%"><i style="width:${pct(pr)}%"></i></div>` : ""}</div><div>${right}</div></div>`;
    }).join("");
    const other = Object.entries(st.pulls).filter(([n, v]) => !st.recommended.some((r) => r.name === n) && v.state !== "done");
    html += other.map(([n, pr]) => `<div class="model-row"><div><b>${esc(n)}</b>
        <div class="muted" style="font-size:13px">${pr.state === "error" ? `<span style="color:#EF4444">${esc(pr.error)}</span>` : `lädt ${pct(pr)} %`}</div>
        ${pr.state === "downloading" ? `<div class="progress" style="width:100%"><i style="width:${pct(pr)}%"></i></div>` : ""}</div></div>`).join("");
    if (IS_LOCAL) html += `<div class="eyebrow" style="margin:12px 0 6px">Anderes Modell${tip("othermodel")}</div>
      <div class="row"><input type="text" id="oll-name" placeholder="Name von ollama.com/library, z. B. llama3.1:8b" style="flex:1" autocomplete="off">
        <button class="btn sm" id="oll-other">Laden & verwenden</button></div>`;
  }
  box.innerHTML = html;
  if (settingUp) ollStop = localSetupProgress($("#oll-prog"), async () => {
    const s2 = await api("/api/settings"); cfg.model = s2.llm.ollama.model; refreshStatus(); setTimeout(() => ollamaPanel(cfg), 1500);
  });
  $("#oll-setup") && ($("#oll-setup").onclick = async (e) => {
    e.target.disabled = true;
    try { await api("/api/ollama/setup", { method: "POST", json: {} }); } catch (err) { toast(err.message, 5000); }
    ollamaPanel(cfg);
  });
  $("#oll-start") && ($("#oll-start").onclick = async (e) => { e.target.disabled = true; e.target.textContent = "Startet …";
    const r = await api("/api/ollama/start", { method: "POST" }); if (!r.ok) toast("Ollama startet nicht – Computer einmal neu starten.", 5000); ollamaPanel(cfg); });
  $$("#oll [data-use]").forEach((b) => b.onclick = async () => {
    await api("/api/settings", { method: "PUT", json: { llm: { ollama: { model: b.dataset.use } } } });
    cfg.model = b.dataset.use; toast(`${b.dataset.use} wird verwendet`); refreshStatus(); ollamaPanel(cfg);
  });
  $$("#oll [data-odel]").forEach((b) => b.onclick = async () => {
    const name = b.dataset.odel;
    if (!(await confirmBox(`${name} löschen?`, "Das Modell wird vom Computer entfernt und der Speicher frei. Neu laden geht jederzeit.", "Löschen"))) return;
    b.disabled = true;
    try {
      const r = await api(`/api/ollama/models/${encodeURIComponent(name)}`, { method: "DELETE" });
      cfg.model = r.model; toast(`${name} gelöscht${r.model ? ` · jetzt: ${r.model}` : ""}`); refreshStatus();
    } catch (e) { toast(e.message, 6000); }
    ollamaPanel(cfg);
  });
  $$("#oll [data-pull]").forEach((b) => b.onclick = async () => {
    b.disabled = true; b.textContent = "startet …";
    await api("/api/ollama/pull", { method: "POST", json: { model: b.dataset.pull, use: true } }); ollamaPanel(cfg);
  });
  $("#oll-best") && ($("#oll-best").onclick = async (e) => {
    e.target.disabled = true;
    try {
      const r = await api("/api/ollama/best", { method: "POST" });
      if (!r.pulling) { cfg.model = r.model; toast(`${r.model} wird verwendet`); refreshStatus(); }
      else toast(`${r.model} wird geladen – danach automatisch verwendet`, 4000);
    } catch (err) { toast(err.message, 5000); }
    ollamaPanel(cfg);
  });
  $("#oll-clean") && ($("#oll-clean").onclick = async () => {
    const st2 = await api("/api/ollama");
    const unused = st2.models.filter((m) => m.name !== cfg.model);
    if (!(await confirmBox(`${unused.length} Modelle löschen?`, unused.map((m) => esc(m.name)).join(", ") + ` – nur ${esc(cfg.model || "–")} bleibt.`, "Löschen"))) return;
    for (const m of unused) {
      try { await api(`/api/ollama/models/${encodeURIComponent(m.name)}`, { method: "DELETE" }); } catch (err) { toast(err.message, 6000); }
    }
    toast(`${unused.length} Modelle gelöscht`); ollamaPanel(cfg);
  });
  const otherGo = async () => {
    const name = ($("#oll-name").value || "").trim();
    if (!/^[\w.\-/:]+$/.test(name)) { toast("Name wie auf ollama.com/library, z. B. llama3.1:8b"); return; }
    try { await api("/api/ollama/pull", { method: "POST", json: { model: name, use: true } }); toast(`${name} wird geladen – danach automatisch verwendet`, 4000); }
    catch (err) { toast(err.message, 5000); }
    ollamaPanel(cfg);
  };
  $("#oll-other") && ($("#oll-other").onclick = otherGo);
  $("#oll-name") && $("#oll-name").addEventListener("keydown", (e) => { if (e.key === "Enter") otherGo(); });
  const wasPulling = pulling.length > 0;
  if (!settingUp && (wasPulling || (st.installed && !st.running))) ollTimer = setTimeout(async () => {
    if (!$("#oll")) return;
    const s = await api("/api/settings"); cfg.model = s.llm.ollama.model;  // a finished first download is auto-selected
    ollamaPanel(cfg); refreshStatus();
  }, wasPulling ? 1000 : 4000);
}

// ---------------------------------------------------------------- storage: where data and models live
async function pickLocation(title, current, what) {
  const s = await api("/api/storage");
  const drives = s.drives || [];
  const kindIcon = { internal: "💻", external: "🔌", nvme: "⚡", network: "🌐", removable: "💾" };
  let target = current;
  const r = await dialog(`<h2>${esc(title)}${tip(what === "models" ? "modelsdir" : "storage")}</h2>
    <div class="drive-list">${drives.map((d, k) => `<button type="button" class="drive" data-k="${k}"><span class="drive-ico">${kindIcon[d.kind] || "💽"}</span>
      <span><b>${esc(d.name)}</b><small>${esc(d.kind_label)} · ${gbFmt(d.free_gb)} frei${d.writable ? "" : " · schreibgeschützt"}</small></span></button>`).join("")}</div>
    <label class="muted" for="pl-path">Ordner</label><input type="text" id="pl-path" value="${esc(current)}" spellcheck="false" autocomplete="off">
    ${what === "models" ? `<label class="row"><input type="checkbox" id="pl-oll" checked> Lokale KI-Modelle (Ollama) mitnehmen</label>` : ""}
    <p class="muted" style="margin:0;font-size:13px">${what === "models" ? `Belegt gerade ${gbFmt(s.usage.models_gb + (s.models_custom ? 0 : s.usage.ollama_gb))}.`
      : `Belegt gerade ${gbFmt(s.usage.data_gb)}. Danach startet REKORD kurz neu; der alte Ordner bleibt als Sicherheitskopie.`}</p>
    <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Umziehen</button></div>`,
  (b) => {
    $$(".drive", b).forEach((x) => x.onclick = () => {
      const d = drives[Number(x.dataset.k)], sug = s.suggest[d.path];
      $$(".drive", b).forEach((y) => y.classList.toggle("on", y === x));
      $("#pl-path", b).value = what === "models" ? sug.models : sug.home;
    });
  });
  if (r !== "ok") return null;
  target = $("#pl-path").value.trim();
  return target && target !== current ? { target, ollama: $("#pl-oll") ? $("#pl-oll").checked : true } : null;
}

function watchStorageJob(el, onDone) {
  let t = null;
  const poll = async () => {
    if (!el.isConnected) return;
    let s;
    try { s = await api("/api/storage"); }
    catch (e) {  // the hub restarts in the new place
      el.innerHTML = `<span class="muted">REKORD startet am neuen Ort neu …</span>`;
      t = setTimeout(async () => { try { await api("/api/status"); location.reload(); } catch (e2) { poll(); } }, 1500);
      return;
    }
    const j = s.job, pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
    if (j.state === "error") { el.innerHTML = `<span style="color:#EF4444">✗ ${esc(j.error)}</span>`; return; }
    if (j.state === "done" && !j.restart) { toast("Umgezogen ✓"); onDone && onDone(); return; }
    el.innerHTML = `<div class="muted" style="font-size:13px">${j.restart ? "Fertig – REKORD startet neu …" : `${esc(j.what)} werden verschoben … ${pct} %`}</div>
      <div class="progress" style="width:100%"><i style="width:${j.restart ? 100 : pct}%"></i></div>`;
    t = setTimeout(poll, 800);
  };
  poll();
  return () => clearTimeout(t);
}

async function renderStorage() {
  const h = $("#st-home"), m = $("#st-models"); if (!h || !m) return;
  let s;
  try { s = await api("/api/storage"); } catch (e) { m.textContent = e.message; return; }
  const btn = (id) => IS_LOCAL && !s.env_locked ? `<button class="btn sm" id="${id}">Ändern …</button>` : "";
  h.innerHTML = `<div class="row"><span class="kbd">${esc(s.home)}</span>${btn("st-home-btn")}</div>
    <span class="hint">${s.home_free_gb != null ? gbFmt(s.home_free_gb) + " frei" : ""}${s.usage ? ` · belegt ${gbFmt(s.usage.data_gb)}` : ""}</span><div id="st-home-job"></div>`;
  m.innerHTML = `<div class="row"><span class="kbd">${esc(s.models)}</span>${btn("st-models-btn")}</div>
    <span class="hint">${s.models_free_gb != null ? gbFmt(s.models_free_gb) + " frei" : ""}${s.usage ? ` · Sprachmodelle ${gbFmt(s.usage.models_gb)}` : ""}
      · Lokale KI: ${esc(s.ollama_models)}${s.usage && s.usage.ollama_gb ? ` (${gbFmt(s.usage.ollama_gb)})` : ""}</span><div id="st-models-job"></div>`;
  if (s.job.state === "running") watchStorageJob($(s.job.what === "Daten" ? "#st-home-job" : "#st-models-job"), renderStorage);
  const move = async (what) => {
    const pick = await pickLocation(what === "models" ? "KI-Modelle speichern auf …" : "Speicherort ändern", what === "models" ? s.models : s.home, what);
    if (!pick) return;
    try {
      await api("/api/storage/move", { method: "POST", json: { what, target: pick.target, ollama: pick.ollama } });
      watchStorageJob($(what === "models" ? "#st-models-job" : "#st-home-job"), renderStorage);
    } catch (e) { toast(e.message, 7000); }
  };
  $("#st-home-btn") && ($("#st-home-btn").onclick = () => move("home"));
  $("#st-models-btn") && ($("#st-models-btn").onclick = () => move("models"));
}

// the external drive with the data is not connected: say so instead of showing an empty library
function viewMissing(path) {
  $("#fab").classList.add("hide");
  view.innerHTML = `<div class="page narrow"><h1 class="big">Laufwerk fehlt<span class="acc">.</span></h1>
    <div class="card"><p style="margin-top:0">REKORD speichert auf <span class="kbd">${esc(path)}</span> – dieses Laufwerk ist gerade nicht angeschlossen.</p>
    <p class="muted">Schließ die Festplatte an (oder verbinde das Netzlaufwerk) und tippe auf <b>Nochmal prüfen</b>. Deine Aufnahmen sind dort sicher.</p>
    <div class="row"><button class="btn primary" id="mi-retry">Nochmal prüfen</button><button class="btn" id="mi-forget">Neu auf diesem Computer anfangen</button></div>
    <div id="mi-msg" class="muted" style="margin-top:10px"></div></div></div>`;
  $("#mi-retry").onclick = async () => {
    const r = IS_LOCAL ? await api("/api/storage/missing", { method: "POST", json: { action: "retry" } }) : { found: false };
    if (!r.found) { $("#mi-msg").textContent = "Noch nicht gefunden."; return; }
    $("#mi-msg").textContent = "Gefunden – REKORD startet neu …";
    setTimeout(function wait() { api("/api/status").then((s) => s.storage_missing ? setTimeout(wait, 1000) : location.reload()).catch(() => setTimeout(wait, 1000)); }, 1500);
  };
  $("#mi-forget").onclick = async () => {
    if (!(await confirmBox("Neu anfangen?", "REKORD legt einen neuen, leeren Ordner auf diesem Computer an. Die Daten auf dem Laufwerk bleiben unberührt – du kannst später wieder dorthin wechseln.", "Neu anfangen"))) return;
    await api("/api/storage/missing", { method: "POST", json: { action: "forget" } });
    $("#mi-msg").textContent = "REKORD startet neu …";
    setTimeout(function wait() { api("/api/status").then(() => location.reload()).catch(() => setTimeout(wait, 1000)); }, 2000);
  };
}

let intCache = null;
function integrations(fresh = false) {
  if (fresh || !intCache) intCache = api("/api/integrations").catch((e) => { intCache = null; throw e; });
  return intCache;
}

// ================================================================ updates: the new version replaces the installed one
async function renderUpdate(box, check = false) {
  if (!box) return;
  let u;
  try { u = await api(check ? "/api/update/check" : "/api/update", check ? { method: "POST" } : {}); }
  catch (e) { box.innerHTML = `REKORD ${esc((state.status || {}).version || "")} · ${esc(e.message)}`; return; }
  const again = () => setTimeout(() => box.isConnected && renderUpdate(box), 700);
  const ago = u.checked ? Math.max(1, Math.round((Date.now() / 1000 - u.checked) / 60)) : 0;
  const head = `<div>REKORD <b>${esc(u.current)}</b>${u.available ? ` · neu: <b style="color:var(--accent)">${esc(u.latest)}</b>` : ""}</div>`;
  if (u.state === "downloading") {
    const pct = u.total ? Math.round((u.done / u.total) * 100) : 0;
    box.innerHTML = head + `<div style="margin-top:8px">Lade Version ${esc(u.latest)} … ${pct} %</div><div class="progress" style="width:100%;margin-top:6px"><i style="width:${pct}%"></i></div>`;
    return again();
  }
  if (u.state === "installing") { box.innerHTML = head + `<div style="margin-top:8px">Installiere – ersetzt die alte Version …</div>`; return again(); }
  if (u.state === "restarting") { box.innerHTML = head + `<div style="margin-top:8px">REKORD startet neu …</div>`; return waitForNewVersion(u.current); }
  box.innerHTML = head + (u.error ? `<div style="color:var(--danger,#E5484D);margin-top:6px">${esc(u.error)}</div>` : "")
    + (u.available ? `${u.notes ? `<details style="margin-top:8px"><summary>Was ist neu in ${esc(u.latest)}?</summary><div class="md" style="margin-top:6px">${MD.render(u.notes)}</div></details>` : ""}
        ${u.can_install && IS_LOCAL ? `<div class="row" style="margin-top:10px"><button class="btn primary sm" id="upd-go">Jetzt auf ${esc(u.latest)} aktualisieren</button></div>`
          : `<div style="margin-top:8px">${IS_LOCAL ? MD.render(u.manual || "") : "Am Computer aktualisieren: Einstellungen → Version & Updates."}</div>`}`
      : `<div style="margin-top:6px">${u.latest ? "✓ Aktuell" : u.check_error ? esc(u.check_error) : "Noch nicht geprüft"}${ago && u.latest ? ` · geprüft vor ${ago} min` : ""}</div>`)
    + `<div class="row" style="margin-top:8px"><button class="btn sm" id="upd-check">Nach Updates suchen</button>${u.page ? `<a class="btn sm" href="${esc(u.page)}" target="_blank" rel="noopener">Release-Seite ↗</a>` : ""}</div>`;
  $("#upd-check", box).onclick = (e) => { e.target.disabled = true; e.target.textContent = "Suche …"; renderUpdate(box, true); };
  $("#upd-go", box) && ($("#upd-go", box).onclick = async (e) => {
    if (!(await confirmBox(`Auf ${u.latest} aktualisieren?`, "REKORD lädt die neue Version, ersetzt die alte und startet neu. Aufnahmen, Personen und Einstellungen bleiben.", "Aktualisieren"))) return;
    e.target.disabled = true;
    try { await api("/api/update/install", { method: "POST" }); renderUpdate(box); }
    catch (err) { toast(err.message, 6000); renderUpdate(box); }
  });
}

function waitForNewVersion(old) {
  // the hub is gone for a moment; when it's back with another version, load its new interface
  setTimeout(function wait() {
    api("/api/status").then((s) => s.version !== old ? location.reload() : setTimeout(wait, 1000)).catch(() => setTimeout(wait, 1000));
  }, 1500);
}

async function viewSettings() {
  let s = await api("/api/settings");
  const st = state.status || (await api("/api/status"));
  const save = debounce(async (patch) => { s = await api("/api/settings", { method: "PUT", json: patch }); toast("Gespeichert", 1000); refreshStatus(); }, 500);
  const saveNow = async (patch) => { s = await api("/api/settings", { method: "PUT", json: patch }); refreshStatus(); return s; };
  const sections = [["look", "Darstellung"], ["audio", "Audio & Mikrofon"], ["ai", "KI"], ["asr", "Transkription"], ["spk", "Sprecher-Erkennung"],
    ["models", "Modelle"], ["pair", "iPhone & Geräte"], ["int", "Claude Desktop (MCP)"], ["data", "Speicher & Datenschutz"]];
  const opt = (v, cur, label) => `<option value="${esc(v)}" ${String(v) === String(cur) ? "selected" : ""}>${esc(label)}</option>`;

  view.innerHTML = `<div class="page narrow">
    <h1 class="big">Einstellungen<span class="acc">.</span></h1>
    <div class="set-nav">${sections.map(([k, n]) => `<button class="btn sm" data-go="${k}">${n}</button>`).join("")}</div>

    <section class="set-sec" id="s-look"><h2>Darstellung <span class="badge">dieses Gerät</span></h2><div class="card">
      <div class="field"><div class="lbl">Erscheinungsbild${tip("theme")}</div><div class="seg" id="theme">${[["system", "System", "Wie dein Gerät"], ["light", "Hell", "Immer hell"], ["dark", "Dunkel", "Immer dunkel"]].map(([k, n, t]) =>
        `<button data-v="${k}" title="${t}" class="${prefs.theme === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
      <div class="field"><div class="lbl">Akzentfarbe${tip("accent")}<span class="hint">Knöpfe, Markierungen, Fortschritt.</span></div><div class="swatches" id="acc">
        ${ACCENTS.map(([c, n]) => `<button class="sw ${prefs.accent.toLowerCase() === c.toLowerCase() ? "on" : ""}" style="--c:${c}" title="${n}" data-c="${c}"></button>`).join("")}
        <input type="color" class="sw-custom" id="acc-custom" value="${prefs.accent}" title="Eigene Farbe"></div></div>
      <div class="field"><div class="lbl">Dichte${tip("density")}<span class="hint">Abstände in der App.</span></div><div class="seg" id="dens">${[["comfortable", "Luftig", "Mehr Abstand, gut zum Tippen"], ["compact", "Kompakt", "Weniger Abstand, mehr auf einen Blick"]].map(([k, n, t]) =>
        `<button data-v="${k}" title="${t}" class="${prefs.density === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
    </div></section>

    <section class="set-sec" id="s-audio"><h2>Audio & Mikrofon <span class="badge">dieses Gerät</span></h2><div class="card">
      <div class="field"><label for="mic">Mikrofon${tip("mic")}<span class="hint">USB-Mikro, Headset, Konferenz-Speaker, AirPods …</span></label>
        <div><select id="mic"><option value="">Systemstandard</option></select><div class="row" style="margin-top:8px"><button class="btn sm" id="mic-test">Pegel testen</button>${tip("mictest")}
        <div class="level" style="flex:1"><i id="mic-lvl"></i></div></div></div></div>
      <div class="field"><div class="lbl">Meeting-Art${tip("meeting")}<span class="hint">Vorauswahl – wird vor jeder Aufnahme bei „Wer ist dabei?“ bestätigt.</span></div>
        <div><div class="seg" id="imode">${[["mic", "Vor Ort", "Alle im Raum – das Mikrofon reicht"], ["mic+system", "Online", "Teams, Zoom, Meet … – der Ton des Calls wird mit aufgenommen"], ["lecture", "Vorlesung", "Eine Person trägt vor, Fragen aus dem Hörsaal werden gesammelt"]].map(([k, n, t]) => `<button data-v="${k}" title="${t}" class="${prefs.inputMode === k ? "on" : ""}">${n}</button>`).join("")}</div>
        <div class="hint" id="call-hint" style="margin-top:6px"></div></div></div>
      <div class="field"><div class="lbl">Audio-Verarbeitung${tip("processing")}<span class="hint">Für Raum-Meetings meist alles an. Für Musik/Interviews mit gutem Mikro: aus.</span></div><div>
        ${[["noiseSuppression", "Rauschunterdrückung"], ["echoCancellation", "Echo-Unterdrückung"], ["autoGainControl", "Automatische Lautstärke"]].map(([k, n]) =>
          `<label class="row" style="margin-bottom:6px"><input type="checkbox" data-pref="${k}" ${prefs[k] ? "checked" : ""}> ${n}${tip(k)}</label>`).join("")}</div></div>
      <div class="field"><div class="lbl">Live-Erkennung${tip("liveDetect")}<span class="hint">Aus = nur aufnehmen, Auswertung danach (spart Akku am Handy).</span></div>
        <label class="row"><input type="checkbox" data-pref="liveDetect" ${prefs.liveDetect ? "checked" : ""}> Während der Aufnahme zeigen, wer spricht</label></div>
      <div class="field"><div class="lbl">Bildschirm wach halten${tip("wakeLock")}<span class="hint">Wichtig beim Aufnehmen am Handy.</span></div><label class="row"><input type="checkbox" data-pref="wakeLock" ${prefs.wakeLock ? "checked" : ""}> Während Aufnahme nicht sperren</label></div>
    </div></section>

    <section class="set-sec" id="s-ai"><h2>KI${tip("provider")}</h2><div class="card">
      <div class="provider-grid" id="prov">${[["anthropic", "Claude", "Anthropic API"], ["openai", "ChatGPT", "OpenAI API"], ["ollama", "Lokal", "Ollama – nichts verlässt den PC"],
        ["compatible", "Kompatibel", "LM Studio, llama.cpp, OpenRouter …"], ["none", "Aus", "Nur Transkription"]].map(([k, n, d]) =>
        `<button class="prov ${s.llm.provider === k ? "on" : ""}" data-p="${k}" title="${n}: ${d}"><b>${n}</b><small>${d}</small></button>`).join("")}</div>
      <div id="prov-cfg"></div>
      <div class="field"><label for="sumlang">Sprache der Zusammenfassungen${tip("sumlang")}</label><select id="sumlang">${[["de", "Deutsch"], ["en", "Englisch"], ["auto", "Wie im Gespräch"]].map(([k, n]) => opt(k, s.summary_language, n)).join("")}</select></div>
      <div class="field"><div class="lbl">Automatisch zusammenfassen${tip("autosum")}<span class="hint">Nach jeder Aufnahme, mit dieser Vorlage.</span></div><div>
        <label class="row" style="margin-bottom:8px"><input type="checkbox" id="autosum" ${s.auto_summary ? "checked" : ""}> Aktiv</label>
        <select id="deftpl"></select></div></div>
    </div></section>

    <section class="set-sec" id="s-asr"><h2>Transkription</h2><div class="card">
      <div class="field"><label for="lang">Sprache${tip("lang")}<span class="hint">Fest einstellen = genauer. Auto erkennt pro Satz (gemischte Meetings).</span></label>
        <select id="lang">${LANGS.map(([k, n]) => opt(k, s.language, n)).join("")}</select></div>
      <div class="field"><label for="engine">Engine${tip("engine")}<span class="hint">Was Sprache in Text verwandelt.</span></label><select id="engine">${opt("sherpa", s.asr_engine, "Whisper ONNX (überall, CPU)")}${
        opt("faster-whisper", s.asr_engine, "faster-whisper (GPU/CUDA, Wortzeiten)" + (st.faster_whisper ? "" : " – nicht installiert"))}</select></div>
      <div class="field"><label for="asrm">Modell${tip("asrmodel")}<span class="hint">turbo = beste Qualität pro Sekunde. small = Laptop-Standard.</span></label><select id="asrm"></select></div>
      <div class="field"><label for="thr">CPU-Threads${tip("threads")}<span class="hint">Mehr = schneller, Computer stärker ausgelastet.</span></label><input type="number" id="thr" min="1" max="32" value="${s.threads}" style="max-width:120px"></div>
      <div class="field"><div class="lbl">Vokabular${tip("vocab")}<span class="hint">Namen & Fachbegriffe, die falsch erkannt werden. "Beni" → "Beeni".</span></div><div>
        <div id="vocab"></div><button class="btn sm" id="vadd" style="margin-top:8px">+ Begriff</button></div></div>
    </div></section>

    <section class="set-sec" id="s-spk"><h2>Sprecher-Erkennung</h2><div class="card">
      <div class="field"><label>Personen-Erkennung (Aufnahmen)${tip("pthr")}<span class="hint">Höher = strenger, weniger Verwechslungen. Standard 0.55.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.9" step="0.01" id="pthr" value="${s.profile_threshold}"><b id="pthr-v">${s.profile_threshold}</b></div></div>
      <div class="field"><label>Personen-Erkennung (live)${tip("lthr")}<span class="hint">Live-Ausschnitte sind kurz – etwas lockerer. Standard 0.50.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.9" step="0.01" id="lthr" value="${s.live_profile_threshold}"><b id="lthr-v">${s.live_profile_threshold}</b></div></div>
      <div class="field"><label>Sprecher trennen${tip("cthr")}<span class="hint">Höher = mehr unterschiedliche Sprecher. Wenn eine Person doppelt erscheint: runter.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.95" step="0.01" id="cthr" value="${s.cluster_threshold}"><b id="cthr-v">${s.cluster_threshold}</b></div></div>
      <div class="field"><label for="nspk">Anzahl Sprecher${tip("nspk")}<span class="hint">Für Importe. Live fragt REKORD jedes Mal.</span></label>
        <select id="nspk">${[0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12].map((n) => opt(n, s.num_speakers, n ? n + " Personen" : "Automatisch")).join("")}</select></div>
      <div class="field"><label for="embm">Stimmabdruck-Modell${tip("embm")}<span class="hint">Wechsel macht bestehende Stimmprofile unbrauchbar.</span></label>
        <select id="embm">${["eres2net-base", "campplus", "wespeaker-resnet34"].map((m) => opt(m, s.embedding_model, m)).join("")}</select></div>
    </div></section>

    <section class="set-sec" id="s-models"><h2>Modelle${tip("models")}</h2><div class="card" id="models"></div></section>

    <section class="set-sec" id="s-pair"><h2>iPhone & Geräte${tip("qr")}</h2><div class="card" id="pair"></div></section>

    <section class="set-sec" id="s-int"><h2>Claude Desktop (MCP)</h2><div class="card">
      <p style="margin-top:0">Verbinde deine REKORD-Bibliothek direkt mit <b>Claude Desktop</b> oder <b>Claude Code</b>. Claude kann dann alle Transkripte durchsuchen,
        lesen und Zusammenfassungen zurückspeichern – mit deinem normalen Claude-Abo, ohne API-Key.</p>
      <div class="field"><div class="lbl">Claude Desktop${tip("claudedesktop")}<span class="hint">Die App von claude.ai/download.</span></div><div id="int-cd" class="muted">prüfe …</div></div>
      <div class="field"><div class="lbl">Claude Code${tip("claudecode")}<span class="hint">Claude im Terminal.</span></div><div id="int-cc" class="muted">prüfe …</div></div>
      <details><summary class="muted" style="cursor:pointer">Von Hand eintragen</summary>
        <p class="muted">Claude Desktop → Einstellungen → Entwickler → Konfiguration bearbeiten, und eintragen:</p>
        <pre class="code" id="mcp"></pre><button class="btn sm" id="mcp-copy">Kopieren</button>
        <p class="muted" style="margin-bottom:0">Claude Code: <span class="kbd" id="mcp-cc"></span></p></details></div></section>

    <section class="set-sec" id="s-data"><h2>Speicher & Datenschutz</h2><div class="card">
      <div class="field"><div class="lbl">Speicherort${tip("storage")}<span class="hint">Aufnahmen, Datenbank, Stimmabdrücke. Backup = diesen Ordner kopieren.</span></div><div id="st-home"><span class="kbd">${esc(st.home)}</span></div></div>
      <div class="field"><div class="lbl">KI-Modelle${tip("modelsdir")}<span class="hint">Sprachmodelle und lokale KI – gern auf einem anderen Laufwerk.</span></div><div id="st-models" class="muted">prüfe …</div></div>
      <div class="field"><div class="lbl">Eingangsordner${tip("inbox")}<span class="hint">Dateien, die hier landen, werden automatisch verarbeitet – z. B. per iCloud/Dropbox-Sync vom Handy oder Diktiergerät.</span></div>
        <div><span class="kbd">${esc(st.inbox)}</span><label class="row" style="margin-top:8px"><input type="checkbox" id="inbox" ${s.inbox_enabled ? "checked" : ""}> Überwachen</label></div></div>
      <div class="field"><div class="lbl">Was verlässt das Gerät?${tip("privacy")}</div><div class="muted">Audio, Transkription, Sprecher-Erkennung: <b>nie</b>. Für Zusammenfassungen geht nur der
        <b>Text</b> an die gewählte KI – bei Ollama/LM Studio auch das nicht. Keine Telemetrie, kein Konto. Die Update-Suche fragt GitHub nur nach der neuesten Versionsnummer (abschaltbar unter <i>Version & Updates</i>).</div></div>
      ${IS_LOCAL ? `<div class="field"><div class="lbl">Mit dem Computer starten${tip("autostart")}<span class="hint">REKORD läuft dann ab dem Einschalten im Hintergrund – das iPhone kann sich jederzeit verbinden.</span></div>
        <div id="autost" class="muted">prüfe …</div></div>` : ""}
      <div class="field"><div class="lbl">Hilfe${tip("help")}<span class="hint">Jeder Punkt hat ein ⓘ – drüberfahren oder antippen.</span></div>
        <div class="row"><button class="btn sm" id="tour">Einführung starten</button><a class="btn sm" href="https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md" target="_blank" rel="noopener">Anleitung ↗</a></div></div>
      <div class="field"><div class="lbl">Version & Updates${tip("version")}<span class="hint">Ein Update ersetzt die installierte App und startet sie neu – Aufnahmen und Einstellungen bleiben.</span></div>
        <div><div id="upd" class="muted">REKORD ${esc(st.version)}</div>
        <label class="row" style="margin-top:8px"><input type="checkbox" id="upd-auto" ${s.update_check !== false ? "checked" : ""}> Automatisch nach Updates suchen${tip("updatecheck")}</label></div></div>
      ${["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) ? `<div class="field"><div class="lbl">Beenden${tip("quit")}<span class="hint">Stoppt REKORD auf diesem Computer (läuft sonst im Hintergrund weiter, damit das iPhone verbunden bleibt).</span></div>
        <div><button class="btn danger" id="quit">REKORD beenden</button></div></div>` : ""}
    </div></section></div>`;

  $$("[data-go]").forEach((b) => b.onclick = () => $("#s-" + b.dataset.go).scrollIntoView({ behavior: "smooth" }));
  if (qs().get("s")) setTimeout(() => { const el = $("#s-" + qs().get("s")); el && el.scrollIntoView(); }, 50);

  // look
  $$("#theme button").forEach((b) => b.onclick = () => { setPref("theme", b.dataset.v); $$("#theme button").forEach((x) => x.classList.toggle("on", x === b)); });
  $$("#dens button").forEach((b) => b.onclick = () => { setPref("density", b.dataset.v); $$("#dens button").forEach((x) => x.classList.toggle("on", x === b)); });
  $$("#acc .sw").forEach((b) => b.onclick = () => { setPref("accent", b.dataset.c); $$("#acc .sw").forEach((x) => x.classList.toggle("on", x === b)); $("#acc-custom").value = b.dataset.c; });
  $("#acc-custom").oninput = (e) => { setPref("accent", e.target.value); $$("#acc .sw").forEach((x) => x.classList.remove("on")); };

  // audio
  const fillMics = async () => {
    const mics = await listMics();
    $("#mic").innerHTML = `<option value="">Systemstandard</option>` + mics.map((m) => opt(m.deviceId, prefs.micId, m.label || "Mikrofon " + m.deviceId.slice(0, 5))).join("");
  };
  if (navigator.mediaDevices) { fillMics(); if (navigator.mediaDevices.addEventListener) listen(navigator.mediaDevices, "devicechange", fillMics); }
  $("#mic").onchange = (e) => setPref("micId", e.target.value);
  let testCap = null;
  $("#mic-test").onclick = async () => {
    if (testCap) { testCap.stop(); testCap = null; $("#mic-test").textContent = "Pegel testen"; $("#mic-lvl").style.width = 0; return; }
    testCap = new Capture({ onLevel: (v) => { const l = $("#mic-lvl"); if (l) l.style.width = v * 100 + "%"; } });
    try { await testCap.start("mic"); $("#mic-test").textContent = "Stopp"; fillMics(); } catch (e) { toast(e.message); testCap = null; }
  };
  $$("#imode button").forEach((b) => b.onclick = () => { setPref("inputMode", b.dataset.v); $$("#imode button").forEach((x) => x.classList.toggle("on", x === b)); });
  $("#call-hint").innerHTML = "Online: " + callHint();
  $$("[data-pref]").forEach((cb) => cb.onchange = () => setPref(cb.dataset.pref, cb.checked));

  // AI
  const provCfg = () => {
    const p = s.llm.provider, c = s.llm[p] || {};
    const keyField = (label, hint, url) => `<div class="field"><label for="k">${label}${tip("apikey")}<span class="hint">${hint}</span></label>
      <div><div class="row"><input type="password" id="k" placeholder="${c.has_key ? c.api_key : "Key hier einfügen"}" autocomplete="off" style="flex:1">
      ${url ? `<a class="btn sm" id="key-get" href="${url}" target="_blank" rel="noopener">Key erstellen ↗</a>` : ""}</div></div></div>`;
    const modelField = (hint) => `<div class="field"><label for="m">Modell${tip("model")}<span class="hint">${hint}</span></label><div class="row">
      <input type="text" id="m" list="mlist" value="${esc(c.model || "")}" style="flex:1"><datalist id="mlist"></datalist><button class="btn sm" id="mload">Laden</button></div></div>`;
    let html = "";
    if (p === "anthropic") html = keyField("API-Key", "Auf „Key erstellen“ klicken, Key kopieren, hier einfügen – REKORD testet sofort.", "https://console.anthropic.com/settings/keys") + modelField("claude-opus-5-5 = beste Qualität, claude-haiku-5-5 = günstig & schnell.")
      + `<div class="field"><label for="eff">Denkaufwand${tip("effort")}<span class="hint">Höher = gründlicher, langsamer, teurer.</span></label><select id="eff">${["low", "medium", "high", "xhigh", "max"].map((e) => opt(e, c.effort, e)).join("")}</select></div>
         <div class="field"><div class="lbl">Ausweichmodell${tip("fallback")}<span class="hint">Lehnt das Modell ab, springt automatisch ein anderes Claude-Modell ein.</span></div><label class="row"><input type="checkbox" id="fb" ${c.fallbacks ? "checked" : ""}> Aktiv</label></div>`;
    if (p === "openai") html = keyField("API-Key", "Auf „Key erstellen“ klicken, Key kopieren, hier einfügen. Achtung: ChatGPT-Plus-Abo ≠ API-Guthaben.", "https://platform.openai.com/api-keys") + modelField("Wird nach dem Key automatisch gewählt. „Laden“ zeigt alle deine Modelle.");
    if (p === "ollama") html = `<div class="field"><div class="lbl">Lokales Modell${tip("localmodel")}<span class="hint">Läuft komplett auf diesem Computer, gratis. Ein Klick auf <b>Laden</b> lädt es herunter.</span></div>
        <div id="oll">Prüfe Ollama …</div></div>
      <div class="field"><label for="bu">Ollama-Adresse${tip("ollamaurl")}<span class="hint">Nur ändern, wenn Ollama auf einem anderen Rechner läuft.</span></label>
      <input type="url" id="bu" value="${esc(c.base_url || "http://localhost:11434")}"></div>`
      + `<div class="field"><label for="ctx">Kontextlänge${tip("context")}<span class="hint">Mehr = längere Meetings am Stück, braucht mehr RAM.</span></label><select id="ctx">${[8192, 16384, 32768, 65536, 131072].map((n) => opt(n, c.num_ctx || 32768, n.toLocaleString("de-AT") + " Tokens")).join("")}</select></div>`;
    if (p === "compatible") html = `<div class="field"><label for="bu">Server-Adresse${tip("serverurl")}<span class="hint">LM Studio: http://localhost:1234/v1 · llama.cpp: http://localhost:8080/v1 · OpenRouter: https://openrouter.ai/api/v1</span></label>
      <input type="url" id="bu" value="${esc(c.base_url || "")}"></div>` + keyField("API-Key", "Nur falls der Server einen verlangt.") + modelField("Modelle vom Server laden.")
      + `<div class="field"><label for="ctx">Kontextlänge${tip("context")}<span class="hint">Was dein Server maximal verarbeitet.</span></label><select id="ctx">${[8192, 16384, 32768, 65536, 131072].map((n) => opt(n, c.context_tokens || 32768, n.toLocaleString("de-AT") + " Tokens")).join("")}</select></div>`;
    if (p !== "none") html += `<div class="field"><div class="lbl">Verbindung${tip("connection")}<span class="hint">Prüft, ob die KI antwortet.</span></div><div class="row"><button class="btn" id="ltest">Testen</button><span id="lres" class="muted"></span></div></div>`;
    $("#prov-cfg").innerHTML = html;
    if (p === "ollama") ollamaPanel(c);
    const patch = (obj) => saveNow({ llm: { [p]: obj } });
    $("#k") && $("#k").addEventListener("change", (e) => e.target.value && patch({ api_key: e.target.value.trim() }).then(() => {
      e.target.value = ""; provCfg(); toast("Key gespeichert – teste …"); setTimeout(() => $("#ltest") && $("#ltest").click(), 100);
    }));
    if (qs().get("key") === "1" && $("#k")) setTimeout(() => $("#k") && $("#k").focus(), 300);
    $("#m") && $("#m").addEventListener("change", (e) => patch({ model: e.target.value.trim() }).then(() => toast("Modell gespeichert")));
    $("#bu") && $("#bu").addEventListener("change", (e) => patch({ base_url: e.target.value.trim() }).then(() => p === "compatible" && provCfg()));
    $("#eff") && $("#eff").addEventListener("change", (e) => patch({ effort: e.target.value }));
    $("#fb") && $("#fb").addEventListener("change", (e) => patch({ fallbacks: e.target.checked }));
    $("#ctx") && $("#ctx").addEventListener("change", (e) => patch(p === "ollama" ? { num_ctx: Number(e.target.value) } : { context_tokens: Number(e.target.value) }));
    $("#mload") && ($("#mload").onclick = async () => {
      const r = await api(`/api/llm/models?provider=${p}`);
      if (r.error) toast(r.error, 5000);
      $("#mlist").innerHTML = r.models.map((m) => `<option value="${esc(m)}">`).join("");
      toast(`${r.models.length} Modelle gefunden – ins Feld tippen zum Auswählen`);
      $("#m").focus();
    });
    $("#ltest") && ($("#ltest").onclick = async () => {
      $("#lres").textContent = "teste …";
      const r = await api("/api/llm/test", { method: "POST" });
      $("#lres").innerHTML = r.ok ? `<span style="color:#22C55E">✓ verbunden</span> · „${esc(r.reply)}“ · ${r.ms} ms` : `<span style="color:#EF4444">✗ ${esc(r.error)}</span>`;
      refreshStatus();
    });
  };
  $$("#prov .prov").forEach((b) => b.onclick = async () => {
    await saveNow({ llm: { provider: b.dataset.p } });
    $$("#prov .prov").forEach((x) => x.classList.toggle("on", x === b));
    provCfg();
  });
  provCfg();
  $("#sumlang").onchange = (e) => save({ summary_language: e.target.value });
  $("#autosum").onchange = (e) => save({ auto_summary: e.target.checked });
  if (!state.templates) state.templates = (await api("/api/templates")).items;
  $("#deftpl").innerHTML = state.templates.filter((t) => t.id !== "mindmap").map((t) => opt(t.id, s.default_template, t.name)).join("");
  $("#deftpl").onchange = (e) => save({ default_template: e.target.value });

  // ASR
  const fillAsr = () => {
    const asrModels = (state.status || st).models.filter((m) => m.kind === "asr");
    $("#asrm").innerHTML = s.asr_engine === "faster-whisper"
      ? ["large-v3-turbo", "large-v3", "distil-large-v3", "medium", "small", "base"].map((m) => opt(m, s.faster_whisper_model, m)).join("")
      : asrModels.map((m) => opt(m.id, s.asr_model, `${m.name} · ${m.size_mb} MB${m.installed ? " ✓" : " (wird geladen)"}`)).join("");
  };
  fillAsr();
  $("#lang").onchange = (e) => save({ language: e.target.value });
  $("#engine").onchange = async (e) => { await saveNow({ asr_engine: e.target.value }); fillAsr(); toast("Gespeichert"); };
  $("#asrm").onchange = async (e) => {
    if (s.asr_engine === "faster-whisper") return save({ faster_whisper_model: e.target.value });
    await saveNow({ asr_model: e.target.value });
    const m = st.models.find((x) => x.id === e.target.value);
    if (m && !m.installed) { await api(`/api/models/${m.id}/download`, { method: "POST" }); toast(`${m.name} wird geladen …`); renderModels(); }
  };
  $("#thr").onchange = (e) => save({ threads: Number(e.target.value) });
  const renderVocab = () => {
    $("#vocab").innerHTML = (s.vocabulary || []).map((v, i) => `<div class="row" style="margin-bottom:6px"><input type="text" value="${esc(v.from)}" data-i="${i}" data-k="from" placeholder="erkannt als" style="flex:1">
      → <input type="text" value="${esc(v.to)}" data-i="${i}" data-k="to" placeholder="richtig" style="flex:1"><button class="btn ghost sm icon" data-del="${i}">✕</button></div>`).join("") || `<div class="muted">Noch nichts.</div>`;
    $$("#vocab input").forEach((inp) => inp.onchange = () => { s.vocabulary[inp.dataset.i][inp.dataset.k] = inp.value; save({ vocabulary: s.vocabulary }); });
    $$("#vocab [data-del]").forEach((b) => b.onclick = () => { s.vocabulary.splice(Number(b.dataset.del), 1); save({ vocabulary: s.vocabulary }); renderVocab(); });
  };
  renderVocab();
  $("#vadd").onclick = () => { s.vocabulary = [...(s.vocabulary || []), { from: "", to: "" }]; renderVocab(); };

  // speakers
  [["pthr", "profile_threshold"], ["lthr", "live_profile_threshold"], ["cthr", "cluster_threshold"]].forEach(([id, k]) => {
    $("#" + id).oninput = (e) => { $(`#${id}-v`).textContent = e.target.value; save({ [k]: Number(e.target.value) }); };
  });
  $("#nspk").onchange = (e) => save({ num_speakers: Number(e.target.value) });
  $("#embm").onchange = async (e) => {
    if (!(await confirmBox("Modell wechseln?", "Gespeicherte Stimmprofile passen dann nicht mehr und müssen neu angelernt werden.", "Wechseln"))) { e.target.value = s.embedding_model; return; }
    await saveNow({ embedding_model: e.target.value });
    await api(`/api/models/${e.target.value}/download`, { method: "POST" });
    toast("Gespeichert");
  };

  // models
  const renderModels = async () => {
    const ms = await api("/api/models");
    const kinds = { asr: "Spracherkennung", segmentation: "Sprecherwechsel", embedding: "Stimmabdruck", vad: "Sprach-Erkennung" };
    $("#models").innerHTML = ms.map((m) => {
      const p = m.progress || {};
      const dl = p.state === "downloading" || p.state === "extracting";
      return `<div class="model-row"><div><b>${esc(m.name)}</b> <span class="badge">${kinds[m.kind]}</span> <span class="muted">${m.size_mb} MB</span>
        <div class="muted" style="font-size:13px">${esc(m.description)}${p.state === "error" ? ` · <span style="color:#EF4444">${esc(p.error)}</span>` : ""}</div>
        ${dl ? `<div class="progress" style="width:100%"><i style="width:${p.state === "extracting" ? 100 : Math.round((p.done / (p.total || 1)) * 100)}%"></i></div>` : ""}</div>
        <div>${m.installed ? `<span class="badge">installiert</span> <button class="btn ghost sm" data-del="${m.id}">Entfernen</button>`
          : dl ? `<span class="muted">${p.state === "extracting" ? "entpacke …" : Math.round((p.done / (p.total || 1)) * 100) + " %"}</span>`
          : `<button class="btn sm" data-dl="${m.id}">Laden</button>`}</div></div>`;
    }).join("");
    $$("[data-dl]").forEach((b) => b.onclick = async () => { await api(`/api/models/${b.dataset.dl}/download`, { method: "POST" }); renderModels(); });
    $$("#models [data-del]").forEach((b) => b.onclick = async () => { if (await confirmBox("Modell entfernen?", b.dataset.del)) { await api(`/api/models/${b.dataset.del}`, { method: "DELETE" }); renderModels(); } });
    if (ms.some((m) => ["downloading", "extracting"].includes((m.progress || {}).state))) setTimeout(() => $("#models") && renderModels(), 1500);
  };
  renderModels();

  // pairing
  try {
    const p = await api("/api/pair");
    $("#pair").innerHTML = `
      ${p.lan ? "" : `<p style="margin-top:0"><b>REKORD ist gerade nur auf diesem Computer erreichbar.</b> Starte REKORD über die App (Mac/Windows/Linux),
        dann ist es automatisch im WLAN sichtbar. Im Terminal: <span class="kbd">rekord serve --host 0.0.0.0</span></p>`}
      <div class="row" style="align-items:flex-start;gap:28px">
        <div><div class="qr">${p.qr_app}</div><p style="max-width:260px"><b>REKORD-App am iPhone</b><br><span class="muted">In der App „Koppeln“ → QR-Code scannen
          – oder den 6-stelligen Code unten eintippen. Danach nimmst du am iPhone auf und siehst live, wer spricht.</span></p></div>
      </div>
      <div id="fw"></div>
      <div class="field"><div class="lbl">Adresse${tip("address")}<span class="hint">Handy und Computer im selben WLAN.</span></div><div>${p.urls.map((u) => `<span class="kbd">${esc(u)}</span>`).join(" ") || "–"}</div></div>
      <div class="field"><div class="lbl">Kopplungs-Code${tip("paircode")}<span class="hint">In der REKORD-App am iPhone eintippen. Gilt 10 Minuten.</span></div>
        <div><div class="row" style="align-items:center"><b id="pcode" style="font-size:34px;letter-spacing:.12em;font-variant-numeric:tabular-nums">${esc(p.code.code.slice(0, 3) + " " + p.code.code.slice(3))}</b>
          <span class="muted" id="pcode-left"></span>${IS_LOCAL ? `<button class="btn sm" id="pcode-new">Neuer Code</button>` : ""}</div></div></div>
      <div class="field"><div class="lbl">Gekoppelte Geräte${tip("devices")}<span class="hint">Jedes Gerät mit Code hat einen eigenen Schlüssel.</span></div>
        <div>${p.devices.length ? p.devices.map((d) => `<div class="row" style="margin-bottom:6px"><span>📱 <b>${esc(d.name)}</b> <span class="muted">· seit ${fmtDate(d.created)}</span></span>
            ${IS_LOCAL ? `<button class="btn ghost sm" data-unpair="${esc(d.id)}">Trennen</button>` : ""}</div>`).join("") : `<span class="muted">Noch keins – oder per QR-Code gekoppelt.</span>`}
          ${IS_LOCAL ? `<div class="row" style="margin-top:6px"><button class="btn danger sm" id="rot">Alle Geräte trennen</button></div>` : ""}</div></div>`;
    let codeExp = p.code.expires;
    const tick = () => {
      const left = Math.max(0, Math.round(codeExp - Date.now() / 1000)), el = $("#pcode-left");
      if (!el) return clearInterval(codeTimer);
      if (left <= 0) { api("/api/pair").then((q) => { codeExp = q.code.expires; $("#pcode").textContent = q.code.code.slice(0, 3) + " " + q.code.code.slice(3); }).catch(() => {}); }
      el.textContent = `noch ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
    };
    const codeTimer = setInterval(tick, 1000); tick();
    disposers.push(() => clearInterval(codeTimer));
    $("#pcode-new") && ($("#pcode-new").onclick = async () => {
      const c = await api("/api/pair/code", { method: "POST" }); codeExp = c.expires; $("#pcode").textContent = c.code.slice(0, 3) + " " + c.code.slice(3); tick();
    });
    $$("[data-unpair]").forEach((b) => b.onclick = async () => {
      if (!(await confirmBox("Gerät trennen?", "Es muss danach neu gekoppelt werden.", "Trennen"))) return;
      await api(`/api/pair/devices/${b.dataset.unpair}`, { method: "DELETE" }); viewSettings();
    });
    if (IS_LOCAL) integrations().then((it) => {
      const fw = it.firewall, box = $("#fw");
      if (!box || !fw.tool || fw.open === true) return;
      box.innerHTML = `<div class="field"><div class="lbl">Firewall${tip("firewall")}<span class="hint">Die ${esc(fw.tool)}-Firewall dieses Computers blockiert das iPhone.</span></div>
        <div class="row"><button class="btn primary" id="fw-open">Für iPhone freigeben</button><span class="muted" id="fw-res"></span></div></div>`;
      $("#fw-open").onclick = async (e) => {
        e.target.disabled = true; $("#fw-res").textContent = "Passwort-Fenster beachten …";
        try { const r = await api("/api/integrations/firewall", { method: "POST" }); $("#fw-res").innerHTML = `<span style="color:#22C55E">✓ ${esc(r.message)}</span>`; }
        catch (err) { $("#fw-res").innerHTML = `<span style="color:#EF4444">✗ ${esc(err.message)}</span>`; e.target.disabled = false; }
      };
    });
    $("#rot") && ($("#rot").onclick = async () => { if (await confirmBox("Alle Geräte trennen?", "Alle gekoppelten Handys – auch die per QR-Code – müssen neu koppeln. Gut, wenn ein Handy verloren ging.", "Alle trennen")) { await api("/api/settings/rotate-token", { method: "POST" }); viewSettings(); } });
  } catch (e) { $("#pair").textContent = e.message; }

  // MCP
  const [cmd, ...args] = st.mcp_command || [st.python || "python", "-m", "rekord", "mcp"];
  const cfg = { mcpServers: { rekord: { command: cmd, args, env: { REKORD_HOME: st.home } } } };
  $("#mcp").textContent = JSON.stringify(cfg, null, 2);
  $("#mcp-cc").textContent = `claude mcp add rekord -e REKORD_HOME="${st.home}" -- "${cmd}" ${args.join(" ")}`;
  $("#mcp-copy").onclick = () => { navigator.clipboard.writeText($("#mcp").textContent); toast("Kopiert"); };
  const renderInt = (it) => {
    const cd = it.claude_desktop, cc = it.claude_code, ok = (t) => `<span style="color:#22C55E">✓ ${t}</span>`;
    if (!IS_LOCAL) { $("#int-cd").textContent = $("#int-cc").textContent = "Nur am Computer selbst einrichtbar."; return; }
    $("#int-cd").innerHTML = `<div class="row">${cd.connected ? ok("Verbunden") : `<button class="btn ${cd.installed ? "primary" : ""}" id="cd-connect">Mit Claude Desktop verbinden</button>`}
      ${cd.connected && cd.running ? `<button class="btn sm" id="cd-restart">Claude neu starten</button>` : ""}
      ${cd.installed ? "" : `<a class="btn sm" href="${cd.download_url}" target="_blank" rel="noopener">Claude Desktop laden ↗</a>`}</div>
      ${cd.connected ? `<span class="hint">Claude einmal neu starten, dann im Chat fragen: „Was haben wir im letzten Meeting entschieden?“</span>` : ""}`;
    $("#int-cc").innerHTML = cc.connected ? ok("Verbunden") : cc.installed ? `<button class="btn" id="cc-connect">Mit Claude Code verbinden</button>`
      : `<span class="muted">Nicht installiert – brauchst du nur, wenn du Claude im Terminal nutzt.</span>`;
    const act = (id, path, done) => $(id) && ($(id).onclick = async (e) => {
      e.target.disabled = true;
      try { const r = await api(path, { method: "POST" }); done(r); renderInt(await integrations(true)); }
      catch (err) { toast(err.message, 6000); e.target.disabled = false; }
    });
    act("#cd-connect", "/api/integrations/claude-desktop", (r) => toast(r.running ? "Eingetragen – Claude jetzt neu starten." : "Eingetragen – beim nächsten Start von Claude ist REKORD da.", 5000));
    act("#cd-restart", "/api/integrations/claude-desktop/restart", () => toast("Claude startet neu."));
    act("#cc-connect", "/api/integrations/claude-code", () => toast("Claude Code ist verbunden."));
  };
  const renderAutostart = (it) => {
    const box = $("#autost"); if (!box) return;
    const a = it.autostart;
    box.innerHTML = a.supported ? `<label class="row"><input type="checkbox" id="autost-cb" ${a.enabled ? "checked" : ""}> Aktiv</label>` : esc(a.reason);
    $("#autost-cb") && ($("#autost-cb").onchange = async (e) => {
      try { const r = await api("/api/integrations/autostart", { method: "POST", json: { enabled: e.target.checked } }); e.target.checked = r.enabled; toast(r.enabled ? "Startet ab jetzt mit dem Computer" : "Startet nicht mehr automatisch"); }
      catch (err) { toast(err.message, 5000); e.target.checked = !e.target.checked; }
    });
  };
  integrations().then((it) => { renderInt(it); renderAutostart(it); }).catch((e) => { $("#int-cd").textContent = e.message; });

  $("#inbox").onchange = (e) => save({ inbox_enabled: e.target.checked });
  $("#upd-auto").onchange = (e) => save({ update_check: e.target.checked });
  $("#tour").onclick = () => welcome(true);
  renderStorage();
  renderUpdate($("#upd"));
  $("#quit") && ($("#quit").onclick = async () => {
    if (!(await confirmBox("REKORD beenden?", "Laufende Verarbeitungen werden beim nächsten Start fortgesetzt.", "Beenden"))) return;
    try { await api("/api/shutdown", { method: "POST" }); view.innerHTML = `<div class="page empty"><h2>REKORD ist beendet.</h2><p>Du kannst dieses Fenster schließen.</p></div>`; }
    catch (e) { toast(e.message, 5000); }
  });
  cleanup = () => { if (testCap) testCap.stop(); clearTimeout(ollTimer); if (ollStop) { ollStop(); ollStop = null; } };
}

// ================================================================ mind map renderer (pure SVG, horizontal tree)
function mindmapSvg(tree) {
  const cs = getComputedStyle(document.documentElement);
  const fg = cs.getPropertyValue("--fg").trim(), fg2 = cs.getPropertyValue("--fg2").trim(), line = cs.getPropertyValue("--line2").trim();
  const palette = ["#FF5A1F", "#2D7FF9", "#16A34A", "#E11D74", "#A855F7", "#EAB308", "#0EA5E9", "#F97316"];
  const LH = 30, COLW = 250, PAD = 24;
  let y = 0;
  const measure = (n, depth) => {
    n.depth = depth;
    if (!n.children.length) { n.y = y; y += LH; return; }
    n.children.forEach((c) => measure(c, depth + 1));
    n.y = (n.children[0].y + n.children[n.children.length - 1].y) / 2;
  };
  measure(tree, 0);
  const H = Math.max(y, LH) + PAD * 2;
  let maxDepth = 0;
  const walk = (n, f) => { f(n); n.children.forEach((c) => walk(c, f)); };
  walk(tree, (n) => (maxDepth = Math.max(maxDepth, n.depth)));
  const W = (maxDepth + 1) * COLW + PAD * 2;
  let out = "";
  const x = (d) => PAD + d * COLW;
  const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
  tree.children.forEach((c, i) => walk(c, (n) => (n.color = palette[i % palette.length])));
  walk(tree, (n) => {
    n.children.forEach((c) => {
      const x1 = n.depth === 0 ? x(0) + 204 : x(n.depth) + 14 + Math.min(n.text.length, 30) * (n.depth === 1 ? 8.2 : 7.2), y1 = n.y + PAD,
        x2 = x(c.depth), y2 = c.y + PAD, mx = (x1 + x2) / 2;
      out += `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2 - 6},${y2}" fill="none" stroke="${c.color || line}" stroke-width="${c.depth === 1 ? 2.5 : 1.5}" opacity=".75"/>`;
    });
  });
  walk(tree, (n) => {
    const tx = x(n.depth), ty = n.y + PAD;
    if (n.depth === 0) {
      out += `<rect x="${tx - 10}" y="${ty - 20}" width="214" height="40" rx="20" fill="${fg}"/><text x="${tx + 97}" y="${ty + 5}" text-anchor="middle" font-size="15" font-weight="800" fill="${cs.getPropertyValue("--bg").trim()}">${esc(trunc(n.text, 24))}</text>`;
    } else {
      out += `<circle cx="${tx - 2}" cy="${ty}" r="${n.depth === 1 ? 5 : 3.5}" fill="${n.color}"/>
        <text x="${tx + 8}" y="${ty + 4.5}" font-size="${n.depth === 1 ? 14 : 13}" font-weight="${n.depth === 1 ? 800 : 500}" fill="${n.depth === 1 ? fg : fg2}">${esc(trunc(n.text, 30))}</text>`;
    }
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="Inter, -apple-system, Segoe UI, sans-serif">${out}</svg>`;
}

// ================================================================ boot
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
refreshStatus().then(route).then(() => welcome());
