/* REKORD web app — runs as PWA on Mac, Windows, Linux, iPhone, Android. No build step, no CDN, works offline on the LAN. */
"use strict";

// ================================================================ helpers
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = $("#view");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const debounce = (fn, ms = 400) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const initials = (n) => (n || "?").replace(/^Sprecher\s*/, "S").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

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
    u.searchParams.delete("token");
    history.replaceState(null, "", u.pathname + u.hash);
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

async function refreshStatus() {
  try {
    state.status = await api("/api/status");
    const s = state.status;
    const busy = s.jobs_pending > 0 || s.live.length > 0;
    const dl = s.models.find((m) => m.progress && m.progress.state === "downloading");
    $("#engine-status").innerHTML = `
      <div><span class="dot ${!s.ready ? "busy" : busy ? "busy" : "ok"}"></span><b>${!s.ready ? "Modelle werden geladen" : busy ? "Arbeitet …" : "Bereit · lokal"}</b></div>
      ${dl ? `<div>${esc(dl.name)} ${Math.round((dl.progress.done / dl.progress.total) * 100)} %</div>` : ""}
      ${s.ai_ready ? `<div>KI: ${esc(s.provider_name)}${s.model ? ` · ${esc(s.model)}` : ""}</div>`
        : `<div><a href="#/settings?s=ai" style="color:var(--accent)">KI verbinden →</a></div>`}`;
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
  for (const [re, fn] of routes) {
    const m = h.match(re);
    if (m) { view.scrollTop = 0; await fn(m); return; }
  }
  viewLibrary();
}
window.addEventListener("hashchange", route);
const qs = () => new URLSearchParams((location.hash.split("?")[1]) || "");

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
    let sum = 0;
    for (let i = 0; i < ch.length; i++) sum += ch[i] * ch[i];
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
    this.port.postMessage({ rms: Math.sqrt(sum / ch.length) });
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
    this.node.port.onmessage = (e) => { if (e.data instanceof ArrayBuffer) this.onPcm && this.onPcm(e.data); else this.onLevel && this.onLevel(e.data.rms); };
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
    const mute = this.ctx.createGain(); mute.gain.value = 0;
    this.node.connect(mute).connect(this.ctx.destination);
    this.mediaStream = mic;
  }
  stop() {
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
  const secure = window.isSecureContext;
  view.innerHTML = `<div class="page">
    <div class="row"><span class="eyebrow">Live · Sprecher-Erkennung in Echtzeit</span><span class="spacer"></span>
      <div class="seg" id="mode"><button data-m="mic">Mikrofon</button><button data-m="mic+system">Mikro + Call-Ton</button></div></div>
    <h1 class="big" style="margin-bottom:16px"><input id="title" class="det-title" style="background:none;border:0;width:100%;padding:0;font:inherit;letter-spacing:inherit"
      placeholder="Meeting ${new Date().toLocaleDateString("de-AT")}"></h1>
    ${secure ? "" : `<div class="card" style="border-color:var(--accent);margin-bottom:14px"><b>Hier im Browser kann nicht aufgenommen werden.</b>
      <span class="muted">Handy-Browser geben das Mikrofon nur über HTTPS frei. Nimm mit der REKORD-App auf dem iPhone auf oder direkt am Computer.</span></div>`}
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
        <div class="eyebrow" style="margin-bottom:10px">Im Raum</div>
        <div class="roster" id="roster"><div class="muted">Stimmen erscheinen hier. Tipp auf eine unbekannte Stimme, um ihr einen Namen zu geben – REKORD erkennt sie ab dann immer.</div></div>
        <div class="eyebrow" style="margin:22px 0 10px">Mitschrift</div>
        <div class="feed" id="feed"></div>
      </aside>
    </div></div>`;

  $$("#mode button").forEach((b) => {
    b.classList.toggle("on", b.dataset.m === prefs.inputMode);
    b.onclick = () => { setPref("inputMode", b.dataset.m); $$("#mode button").forEach((x) => x.classList.toggle("on", x === b)); };
  });
  if (!navigator.mediaDevices?.getDisplayMedia || /iPhone|iPad|Android/.test(navigator.userAgent)) $('#mode [data-m="mic+system"]').remove();

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
        : n.key == null ? "Neue Stimme – noch nicht zugeordnet" : "Unbekannt · antippen rechts, um zu benennen";
    },
    roster() {
      const s = liveSession; if (!s || !$("#roster")) return;
      if (!s.speakers.length) return;
      const total = s.speakers.reduce((a, b) => a + (b.talk || 0), 0) || 1;
      $("#roster").innerHTML = s.speakers.map((p) => p.waiting ? `<div class="who" style="--c:${p.color};opacity:.55;cursor:default">
        <span class="avatar">${esc(initials(p.name))}</span><span><div class="who-name">${esc(p.name)}</div><div class="who-sub">dabei · noch nicht gesprochen</div></span><span></span></div>`
        : `<button class="who ${s.now && !s.now.silence && s.now.key === p.key ? "talking" : ""}" data-key="${p.key}" data-known="${p.known ? 1 : 0}" style="--c:${p.color}">
        <span class="avatar">${esc(initials(p.name))}</span><span><div class="who-name">${esc(p.name)}</div>
        <div class="who-sub">${p.known ? "erkannt" : "tippen zum Benennen"} · ${fmtTime(p.talk || 0)}</div><div class="bar"><i style="width:${Math.round(((p.talk || 0) / total) * 100)}%"></i></div></span>
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

  $("#rec").onclick = () => (liveSession ? stopLive() : startLive($("#title").value.trim()));
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
  if (qs().get("autostart") === "1" && !liveSession) startLive("");
}
let liveUI = null;

// "Wer ist dabei?" — pick participants before the meeting. Fewer candidates = far fewer mix-ups.
async function renderSetup() {
  const box = $("#setup"); if (!box) return;
  let people = [];
  try { people = (await api("/api/profiles")).items; } catch (e) {}
  prefs.participants = prefs.participants.filter((id) => people.some((p) => p.id === id));
  const sel = new Set(prefs.participants);
  box.innerHTML = `<div class="card" style="margin-bottom:22px">
    <div class="eyebrow" style="margin-bottom:10px">Wer ist dabei?</div>
    <div class="row" id="ppl" style="gap:8px">${people.map((p) => `<button class="chip" data-id="${p.id}" style="--c:${p.color};cursor:pointer;${sel.has(p.id)
      ? "background:var(--fg);color:var(--bg);border-color:var(--fg)" : ""}"><i></i>${esc(p.name)}</button>`).join("") || `<span class="muted">Noch keine bekannten Stimmen.</span>`}</div>
    <div class="row" style="margin-top:12px"><span class="muted">+ Gäste (unbekannt)</span><span class="spacer"></span>
      <button class="btn sm icon" id="gm">−</button><b id="gn" style="min-width:20px;text-align:center">${prefs.guests}</b><button class="btn sm icon" id="gp">+</button></div>
    <button class="btn sm" id="intro" style="margin-top:12px;width:100%">🎙 Vorstellungsrunde – Person einsprechen</button>
    <div class="muted" style="font-size:12.5px;margin-top:10px">${sel.size ? (prefs.guests ? `Vergleicht nur mit ${sel.size} gewählten Personen, ${prefs.guests} Gäste werden als „Sprecher N“ geführt.`
      : `Geschlossene Runde: jede Stimme wird einer der ${sel.size} Personen zugeordnet.`) : "Nichts gewählt = alle bekannten Personen + Unbekannte."}</div></div>`;
  $$("#ppl [data-id]").forEach((b) => b.onclick = () => {
    const id = Number(b.dataset.id);
    setPref("participants", sel.has(id) ? prefs.participants.filter((x) => x !== id) : [...prefs.participants, id]);
    renderSetup();
  });
  $("#gm").onclick = () => { setPref("guests", Math.max(0, prefs.guests - 1)); renderSetup(); };
  $("#gp").onclick = () => { setPref("guests", prefs.guests + 1); renderSetup(); };
  $("#intro").onclick = async () => {
    const prof = await enrollDialog({ intro: true });
    if (prof) { setPref("participants", [...new Set([...prefs.participants, prof.id])]); renderSetup(); }
  };
}

async function startLive(title) {
  const s = liveSession = { title: title || `Meeting ${new Date().toLocaleString("de-AT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`,
    speakers: [], lines: [], now: null, paused: false, offline: false, highlights: [], t0: Date.now(), pausedMs: 0, pausedAt: 0,
    participants: [...prefs.participants], guests: prefs.guests,
    elapsed() { return ((this.pausedAt || Date.now()) - this.t0 - this.pausedMs) / 1000; } };
  liveUI && liveUI.render();
  const useWs = prefs.liveDetect;
  try {
    s.capture = new Capture({
      onPcm: (buf) => { if (s.paused) return; if (s.ws && s.ws.readyState === 1) s.ws.send(buf); else if (s.offline) s.chunks.push(buf); },
      onLevel: (rms) => { const v = Math.min(1, rms * 9); const l = $("#lvl"); if (l) l.style.width = v * 100 + "%"; const r = $("#ring"); if (r) r.style.setProperty("--lvl", v.toFixed(2)); },
    });
    await s.capture.start(prefs.inputMode);
  } catch (e) {
    liveSession = null; liveUI && liveUI.render();
    toast("Mikrofon nicht verfügbar: " + e.message, 5000);
    return;
  }
  if (prefs.wakeLock && navigator.wakeLock) { try { s.wake = await navigator.wakeLock.request("screen"); } catch (e) {} }
  const goOffline = () => { s.offline = true; s.chunks = s.chunks || []; liveUI && liveUI.render(); };
  if (!useWs) { goOffline(); return; }
  s.ws = new WebSocket(wsUrl("/ws/live"));
  s.ws.binaryType = "arraybuffer";
  s.ws.onopen = () => s.ws.send(JSON.stringify({ type: "start", sample_rate: 16000, title: s.title, participants: s.participants, guests: s.guests }));
  s.ws.onerror = () => { if (!s.started) { toast("Hub nicht erreichbar – nehme offline auf."); goOffline(); } };
  s.ws.onclose = () => { if (!s.stopping && s.started) { toast("Verbindung verloren – Aufnahme wird lokal fortgesetzt."); goOffline(); } };
  s.ws.onmessage = (m) => {
    const ev = JSON.parse(m.data);
    if (ev.type === "started") { s.started = true; s.id = ev.id; }
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
  if (s.offline && s.chunks && s.chunks.length) {
    // upload what we captured as WAV
    const wav = pcmToWav(s.chunks);
    const fd = new FormData();
    fd.append("files", new File([wav], "aufnahme.wav", { type: "audio/wav" }));
    fd.append("title", s.title);
    fd.append("source", "record");
    fd.append("highlights", JSON.stringify(s.highlights));
    if (s.participants.length) fd.append("participants", JSON.stringify({ ids: s.participants, guests: s.guests }));
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
    <div class="tabs" id="tabs">
      <button data-tab="summary">Zusammenfassung</button><button data-tab="transcript">Transkript</button>
      <button data-tab="mindmap">Mind Map</button><button data-tab="ask">Fragen</button><button data-tab="notes">Notizen</button><button data-tab="export">Export</button>
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
      s.profile_id ? `erkannt${s.match_score && s.match_score < 1 ? " " + Math.round(s.match_score * 100) + " %" : ""}` : "unbekannt"}</small></span></button>`).join("");
    $$("#spk .spk-card").forEach((b) => b.onclick = () => editSpeaker(Number(b.dataset.sid)));
    drawTimeline();
  };
  async function editSpeaker(sid) {
    const s = rec.speakers.find((x) => x.id === sid);
    const others = rec.speakers.filter((x) => x.id !== sid);
    const r = await dialog(`<h2>Sprecher</h2>
      <label class="muted">Name</label><input type="text" id="sp-name" value="${esc(s.name)}">
      <label class="row"><input type="checkbox" id="sp-rem" ${s.profile_id || /^Sprecher \d+$/.test(s.name) ? "checked" : ""}> Stimme merken – in Zukunft automatisch erkennen</label>
      ${others.length ? `<label class="muted">Oder zusammenführen mit (falls doppelt erkannt)</label>
        <select id="sp-merge"><option value="">—</option>${others.map((o) => `<option value="${o.id}">${esc(o.name)}</option>`).join("")}</select>` : ""}
      <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok">Speichern</button></div>`,
    (b) => $("#sp-name", b).select());
    if (r !== "ok") return;
    const merge = $("#sp-merge") && $("#sp-merge").value;
    if (merge) {
      await api(`/api/recordings/${id}/speakers/merge`, { method: "POST", json: { source: sid, target: Number(merge) } });
      toast("Zusammengeführt");
    } else {
      const name = $("#sp-name").value.trim();
      const remember = $("#sp-rem").checked;
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
          <div class="spk"><button data-sid="${s.speaker_id}">${esc(p.name)}</button><span class="ts" data-seek="${s.start}">${fmtTime(s.start)}${isHl ? " ★" : ""}</span></div>
          <div class="tx" contenteditable="plaintext-only" spellcheck="false" data-id="${s.id}">${esc(s.text)}</div></div>`;
      }).join("")}</div>`;
    $$("#segs .spk button").forEach((b) => b.onclick = () => editSpeaker(Number(b.dataset.sid)));
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
    <div class="row"><span class="eyebrow">Stimmabdrücke · bleiben auf diesem Gerät</span></div>
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

async function enrollDialog(opts = {}) {
  const TEXT = opts.intro
    ? "Stell dich kurz vor: Name, was du machst, und worum es dir in diesem Meeting geht. Ganz normal reden, ca. 10–15 Sekunden."
    : "Hallo, ich nehme jetzt eine kurze Sprachprobe auf. REKORD lernt meine Stimme, damit es mich in Meetings automatisch erkennt. Ich lese diesen Text ganz normal vor, so wie ich auch im Alltag spreche. Eins, zwei, drei, vier, fünf.";
  let rec, chunks = [], timer, secs = 0, stream;
  const r = await dialog(`<h2>${opts.intro ? "Vorstellungsrunde" : "Person einsprechen"}</h2><input type="text" id="en-name" placeholder="Name" value="${esc(opts.name || "")}">
    <p class="muted" style="margin:0">${opts.intro ? "Handy/Mikro zur Person, dann:" : "Lies diesen Text in normaler Lautstärke vor (ca. 15 Sekunden):"}</p>
    <blockquote style="margin:0;padding:12px 16px;border-left:3px solid var(--accent);background:var(--card2);border-radius:8px">${TEXT}</blockquote>
    <div class="row"><button type="button" class="btn primary" id="en-rec">● Aufnahme starten</button><span class="timer" id="en-t">0 s</span></div>
    <label class="muted">…oder Datei mit nur dieser Person wählen</label><input type="file" id="en-file" accept="audio/*">
    <div class="row"><span class="spacer"></span><button class="btn" value="cancel">Abbrechen</button><button class="btn primary" value="ok" id="en-ok">Speichern</button></div>`,
  (b) => {
    $("#en-rec", b).onclick = async () => {
      if (rec && rec.state === "recording") { rec.stop(); return; }
      stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: prefs.micId ? { ideal: prefs.micId } : undefined } });
      rec = new MediaRecorder(stream); chunks = []; secs = 0;
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => { clearInterval(timer); stream.getTracks().forEach((t) => t.stop()); $("#en-rec").textContent = "↺ Neu aufnehmen"; };
      rec.start();
      $("#en-rec").textContent = "■ Stopp";
      timer = setInterval(() => { secs++; $("#en-t").textContent = secs + " s"; if (secs >= 30) rec.stop(); }, 1000);
    };
  });
  if (rec && rec.state === "recording") rec.stop();
  await sleep(150);
  if (r !== "ok") return null;
  const name = $("#en-name").value.trim();
  const file = $("#en-file").files[0] || (chunks.length ? new File(chunks, "probe.webm", { type: chunks[0].type || "audio/webm" }) : null);
  if (!name || !file) { toast("Name und Sprachprobe nötig"); return null; }
  const fd = new FormData(); fd.append("name", name); fd.append("file", file);
  try { const prof = await api("/api/profiles/enroll", { method: "POST", body: fd }); toast(`${name}: Stimme gespeichert ✓`); return prof; }
  catch (e) { toast(e.message, 5000); return null; }
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
      <div class="field"><div class="lbl">Erscheinungsbild</div><div class="seg" id="theme">${[["system", "System"], ["light", "Hell"], ["dark", "Dunkel"]].map(([k, n]) =>
        `<button data-v="${k}" class="${prefs.theme === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
      <div class="field"><div class="lbl">Akzentfarbe<span class="hint">Knöpfe, Markierungen, Fortschritt.</span></div><div class="swatches" id="acc">
        ${ACCENTS.map(([c, n]) => `<button class="sw ${prefs.accent.toLowerCase() === c.toLowerCase() ? "on" : ""}" style="--c:${c}" title="${n}" data-c="${c}"></button>`).join("")}
        <input type="color" class="sw-custom" id="acc-custom" value="${prefs.accent}" title="Eigene Farbe"></div></div>
      <div class="field"><div class="lbl">Dichte</div><div class="seg" id="dens">${[["comfortable", "Luftig"], ["compact", "Kompakt"]].map(([k, n]) =>
        `<button data-v="${k}" class="${prefs.density === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
    </div></section>

    <section class="set-sec" id="s-audio"><h2>Audio & Mikrofon <span class="badge">dieses Gerät</span></h2><div class="card">
      <div class="field"><label for="mic">Mikrofon<span class="hint">USB-Mikro, Headset, Konferenz-Speaker, AirPods …</span></label>
        <div><select id="mic"><option value="">Systemstandard</option></select><div class="row" style="margin-top:8px"><button class="btn sm" id="mic-test">Pegel testen</button>
        <div class="level" style="flex:1"><i id="mic-lvl"></i></div></div></div></div>
      <div class="field"><div class="lbl">Standard-Quelle<span class="hint">"Call-Ton" nimmt in Chrome/Edge am Computer zusätzlich Zoom/Teams/Meet auf.</span></div>
        <div class="seg" id="imode">${[["mic", "Mikrofon"], ["mic+system", "Mikro + Call-Ton"]].map(([k, n]) => `<button data-v="${k}" class="${prefs.inputMode === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
      <div class="field"><div class="lbl">Audio-Verarbeitung<span class="hint">Für Raum-Meetings meist alles an. Für Musik/Interviews mit gutem Mikro: aus.</span></div><div>
        ${[["noiseSuppression", "Rauschunterdrückung"], ["echoCancellation", "Echo-Unterdrückung"], ["autoGainControl", "Automatische Lautstärke"]].map(([k, n]) =>
          `<label class="row" style="margin-bottom:6px"><input type="checkbox" data-pref="${k}" ${prefs[k] ? "checked" : ""}> ${n}</label>`).join("")}</div></div>
      <div class="field"><div class="lbl">Live-Erkennung<span class="hint">Aus = nur aufnehmen, Auswertung danach (spart Akku am Handy).</span></div>
        <label class="row"><input type="checkbox" data-pref="liveDetect" ${prefs.liveDetect ? "checked" : ""}> Während der Aufnahme zeigen, wer spricht</label></div>
      <div class="field"><div class="lbl">Bildschirm wach halten</div><label class="row"><input type="checkbox" data-pref="wakeLock" ${prefs.wakeLock ? "checked" : ""}> Während Aufnahme nicht sperren</label></div>
    </div></section>

    <section class="set-sec" id="s-ai"><h2>KI</h2><div class="card">
      <div class="provider-grid" id="prov">${[["anthropic", "Claude", "Anthropic API"], ["openai", "ChatGPT", "OpenAI API"], ["ollama", "Lokal", "Ollama – nichts verlässt den PC"],
        ["compatible", "Kompatibel", "LM Studio, llama.cpp, OpenRouter …"], ["none", "Aus", "Nur Transkription"]].map(([k, n, d]) =>
        `<button class="prov ${s.llm.provider === k ? "on" : ""}" data-p="${k}"><b>${n}</b><small>${d}</small></button>`).join("")}</div>
      <div id="prov-cfg"></div>
      <div class="field"><label for="sumlang">Sprache der Zusammenfassungen</label><select id="sumlang">${[["de", "Deutsch"], ["en", "Englisch"], ["auto", "Wie im Gespräch"]].map(([k, n]) => opt(k, s.summary_language, n)).join("")}</select></div>
      <div class="field"><div class="lbl">Automatisch zusammenfassen<span class="hint">Nach jeder Aufnahme, mit dieser Vorlage.</span></div><div>
        <label class="row" style="margin-bottom:8px"><input type="checkbox" id="autosum" ${s.auto_summary ? "checked" : ""}> Aktiv</label>
        <select id="deftpl"></select></div></div>
    </div></section>

    <section class="set-sec" id="s-asr"><h2>Transkription</h2><div class="card">
      <div class="field"><label for="lang">Sprache<span class="hint">Fest einstellen = genauer. Auto erkennt pro Satz (gemischte Meetings).</span></label>
        <select id="lang">${LANGS.map(([k, n]) => opt(k, s.language, n)).join("")}</select></div>
      <div class="field"><label for="engine">Engine</label><select id="engine">${opt("sherpa", s.asr_engine, "Whisper ONNX (überall, CPU)")}${
        opt("faster-whisper", s.asr_engine, "faster-whisper (GPU/CUDA, Wortzeiten)" + (st.faster_whisper ? "" : " – nicht installiert"))}</select></div>
      <div class="field"><label for="asrm">Modell<span class="hint">turbo = beste Qualität pro Sekunde. small = Laptop-Standard.</span></label><select id="asrm"></select></div>
      <div class="field"><label for="thr">CPU-Threads</label><input type="number" id="thr" min="1" max="32" value="${s.threads}" style="max-width:120px"></div>
      <div class="field"><div class="lbl">Vokabular<span class="hint">Namen & Fachbegriffe, die falsch erkannt werden. "Beni" → "Beeni".</span></div><div>
        <div id="vocab"></div><button class="btn sm" id="vadd" style="margin-top:8px">+ Begriff</button></div></div>
    </div></section>

    <section class="set-sec" id="s-spk"><h2>Sprecher-Erkennung</h2><div class="card">
      <div class="field"><label>Personen-Erkennung (Aufnahmen)<span class="hint">Höher = strenger, weniger Verwechslungen. Standard 0.55.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.9" step="0.01" id="pthr" value="${s.profile_threshold}"><b id="pthr-v">${s.profile_threshold}</b></div></div>
      <div class="field"><label>Personen-Erkennung (live)<span class="hint">Live-Ausschnitte sind kurz – etwas lockerer. Standard 0.50.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.9" step="0.01" id="lthr" value="${s.live_profile_threshold}"><b id="lthr-v">${s.live_profile_threshold}</b></div></div>
      <div class="field"><label>Sprecher trennen<span class="hint">Höher = mehr unterschiedliche Sprecher. Wenn eine Person doppelt erscheint: runter.</span></label>
        <div class="row"><input type="range" min="0.3" max="0.95" step="0.01" id="cthr" value="${s.cluster_threshold}"><b id="cthr-v">${s.cluster_threshold}</b></div></div>
      <div class="field"><label for="nspk">Anzahl Sprecher<span class="hint">Wenn bekannt, fix einstellen = präziser.</span></label>
        <select id="nspk">${[0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12].map((n) => opt(n, s.num_speakers, n ? n + " Personen" : "Automatisch")).join("")}</select></div>
      <div class="field"><label for="embm">Stimmabdruck-Modell<span class="hint">Wechsel macht bestehende Stimmprofile unbrauchbar.</span></label>
        <select id="embm">${["eres2net-base", "campplus", "wespeaker-resnet34"].map((m) => opt(m, s.embedding_model, m)).join("")}</select></div>
    </div></section>

    <section class="set-sec" id="s-models"><h2>Modelle</h2><div class="card" id="models"></div></section>

    <section class="set-sec" id="s-pair"><h2>iPhone & Geräte</h2><div class="card" id="pair"></div></section>

    <section class="set-sec" id="s-int"><h2>Claude Desktop (MCP)</h2><div class="card">
      <p style="margin-top:0">Verbinde deine REKORD-Bibliothek direkt mit <b>Claude Desktop</b> oder <b>Claude Code</b>. Claude kann dann alle Transkripte durchsuchen,
        lesen und Zusammenfassungen zurückspeichern – mit deinem normalen Claude-Abo, ohne API-Key.</p>
      <p class="muted">Claude Desktop → Einstellungen → Entwickler → Konfiguration bearbeiten, und eintragen:</p>
      <pre class="code" id="mcp"></pre><button class="btn sm" id="mcp-copy">Kopieren</button>
      <p class="muted" style="margin-bottom:0">Claude Code: <span class="kbd" id="mcp-cc"></span></p></div></section>

    <section class="set-sec" id="s-data"><h2>Speicher & Datenschutz</h2><div class="card">
      <div class="field"><div class="lbl">Datenordner</div><div><span class="kbd">${esc(st.home)}</span><span class="hint">Audio, Datenbank, Modelle. Backup = diesen Ordner kopieren.</span></div></div>
      <div class="field"><div class="lbl">Eingangsordner<span class="hint">Dateien, die hier landen, werden automatisch verarbeitet – z. B. per iCloud/Dropbox-Sync vom Handy oder Diktiergerät.</span></div>
        <div><span class="kbd">${esc(st.inbox)}</span><label class="row" style="margin-top:8px"><input type="checkbox" id="inbox" ${s.inbox_enabled ? "checked" : ""}> Überwachen</label></div></div>
      <div class="field"><div class="lbl">Was verlässt das Gerät?</div><div class="muted">Audio, Transkription, Sprecher-Erkennung: <b>nie</b>. Für Zusammenfassungen geht nur der
        <b>Text</b> an die gewählte KI – bei Ollama/LM Studio auch das nicht. Keine Telemetrie, kein Konto.</div></div>
      <div class="field"><div class="lbl">Version</div><div class="muted">REKORD ${esc(st.version)}</div></div>
      ${["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) ? `<div class="field"><div class="lbl">Beenden<span class="hint">Stoppt REKORD auf diesem Computer (läuft sonst im Hintergrund weiter, damit das iPhone verbunden bleibt).</span></div>
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
    testCap = new Capture({ onLevel: (r) => { const l = $("#mic-lvl"); if (l) l.style.width = Math.min(100, r * 900) + "%"; } });
    try { await testCap.start("mic"); $("#mic-test").textContent = "Stopp"; fillMics(); } catch (e) { toast(e.message); testCap = null; }
  };
  $$("#imode button").forEach((b) => b.onclick = () => { setPref("inputMode", b.dataset.v); $$("#imode button").forEach((x) => x.classList.toggle("on", x === b)); });
  $$("[data-pref]").forEach((cb) => cb.onchange = () => setPref(cb.dataset.pref, cb.checked));

  // AI
  const provCfg = () => {
    const p = s.llm.provider, c = s.llm[p] || {};
    const keyField = (label, hint) => `<div class="field"><label for="k">${label}<span class="hint">${hint}</span></label>
      <input type="password" id="k" placeholder="${c.has_key ? c.api_key : "nicht gesetzt"}" autocomplete="off"></div>`;
    const modelField = (hint) => `<div class="field"><label for="m">Modell<span class="hint">${hint}</span></label><div class="row">
      <input type="text" id="m" list="mlist" value="${esc(c.model || "")}" style="flex:1"><datalist id="mlist"></datalist><button class="btn sm" id="mload">Laden</button></div></div>`;
    let html = "";
    if (p === "anthropic") html = keyField("API-Key", "console.anthropic.com → API Keys. Leer = ANTHROPIC_API_KEY aus der Umgebung.") + modelField("claude-opus-5-5 = beste Qualität, claude-haiku-5-5 = günstig & schnell.")
      + `<div class="field"><label for="eff">Denkaufwand<span class="hint">Höher = gründlicher, langsamer, teurer.</span></label><select id="eff">${["low", "medium", "high", "xhigh", "max"].map((e) => opt(e, c.effort, e)).join("")}</select></div>
         <div class="field"><div class="lbl">Ausweichmodell<span class="hint">Lehnt das Modell ab, springt automatisch ein anderes Claude-Modell ein.</span></div><label class="row"><input type="checkbox" id="fb" ${c.fallbacks ? "checked" : ""}> Aktiv</label></div>`;
    if (p === "openai") html = keyField("API-Key", "platform.openai.com → API Keys. Achtung: ChatGPT-Plus-Abo ≠ API-Guthaben.") + modelField("Auf „Laden“ klicken, um deine verfügbaren Modelle zu sehen.");
    if (p === "ollama") html = `<div class="field"><label for="bu">Ollama-Adresse<span class="hint">ollama.com installieren, dann z. B. <span class="kbd">ollama pull qwen3:8b</span></span></label>
      <input type="url" id="bu" value="${esc(c.base_url || "http://localhost:11434")}"></div>` + modelField("Installierte Modelle laden.")
      + `<div class="field"><label for="ctx">Kontextlänge<span class="hint">Mehr = längere Meetings am Stück, braucht mehr RAM.</span></label><select id="ctx">${[8192, 16384, 32768, 65536, 131072].map((n) => opt(n, c.num_ctx || 32768, n.toLocaleString("de-AT") + " Tokens")).join("")}</select></div>`;
    if (p === "compatible") html = `<div class="field"><label for="bu">Server-Adresse<span class="hint">LM Studio: http://localhost:1234/v1 · llama.cpp: http://localhost:8080/v1 · OpenRouter: https://openrouter.ai/api/v1</span></label>
      <input type="url" id="bu" value="${esc(c.base_url || "")}"></div>` + keyField("API-Key", "Nur falls der Server einen verlangt.") + modelField("Modelle vom Server laden.")
      + `<div class="field"><label for="ctx">Kontextlänge</label><select id="ctx">${[8192, 16384, 32768, 65536, 131072].map((n) => opt(n, c.context_tokens || 32768, n.toLocaleString("de-AT") + " Tokens")).join("")}</select></div>`;
    if (p !== "none") html += `<div class="field"><div class="lbl">Verbindung</div><div class="row"><button class="btn" id="ltest">Testen</button><span id="lres" class="muted"></span></div></div>`;
    $("#prov-cfg").innerHTML = html;
    const patch = (obj) => saveNow({ llm: { [p]: obj } });
    $("#k") && $("#k").addEventListener("change", (e) => e.target.value && patch({ api_key: e.target.value.trim() }).then(() => { e.target.value = ""; provCfg(); toast("Key gespeichert"); }));
    $("#m") && $("#m").addEventListener("change", (e) => patch({ model: e.target.value.trim() }).then(() => toast("Modell gespeichert")));
    $("#bu") && $("#bu").addEventListener("change", (e) => patch({ base_url: e.target.value.trim() }));
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
        <div><div class="qr">${p.qr_app}</div><p style="max-width:220px"><b>REKORD iOS-App</b><br><span class="muted">Aufnehmen am iPhone, live sehen wer spricht, Sperrbildschirm-Widget. In der App „QR-Code scannen“.</span></p></div>
        <div><div class="qr">${p.qr_web}</div><p style="max-width:220px"><b>Im Browser (jedes Handy)</b><br><span class="muted">Kamera auf den Code → Link öffnen → Teilen → „Zum Home-Bildschirm“.
          Ansehen, anhören, Fragen stellen. Aufnehmen am Handy geht mit der REKORD-App.</span></p></div>
      </div>
      <div class="field"><div class="lbl">Adresse</div><div>${p.urls.map((u) => `<span class="kbd">${esc(u)}</span>`).join(" ") || "–"}</div></div>
      <div class="field"><div class="lbl">Kopplungs-Code<span class="hint">Neu erzeugen trennt alle gekoppelten Geräte.</span></div>
        <div class="row"><span class="kbd" id="tok" style="filter:blur(4px);cursor:pointer" title="anzeigen">${esc(p.token)}</span><button class="btn sm" id="rot">Neu erzeugen</button></div></div>`;
    $("#tok").onclick = (e) => (e.target.style.filter = "none");
    $("#rot").onclick = async () => { if (await confirmBox("Code neu erzeugen?", "Alle gekoppelten Geräte müssen neu koppeln.", "Neu erzeugen")) { await api("/api/settings/rotate-token", { method: "POST" }); viewSettings(); } };
  } catch (e) { $("#pair").textContent = e.message; }

  // MCP
  const [cmd, ...args] = st.mcp_command || [st.python || "python", "-m", "rekord", "mcp"];
  const cfg = { mcpServers: { rekord: { command: cmd, args, env: { REKORD_HOME: st.home } } } };
  $("#mcp").textContent = JSON.stringify(cfg, null, 2);
  $("#mcp-cc").textContent = `claude mcp add rekord -e REKORD_HOME="${st.home}" -- "${cmd}" ${args.join(" ")}`;
  $("#mcp-copy").onclick = () => { navigator.clipboard.writeText($("#mcp").textContent); toast("Kopiert"); };

  $("#inbox").onchange = (e) => save({ inbox_enabled: e.target.checked });
  $("#quit") && ($("#quit").onclick = async () => {
    if (!(await confirmBox("REKORD beenden?", "Laufende Verarbeitungen werden beim nächsten Start fortgesetzt.", "Beenden"))) return;
    try { await api("/api/shutdown", { method: "POST" }); view.innerHTML = `<div class="page empty"><h2>REKORD ist beendet.</h2><p>Du kannst dieses Fenster schließen.</p></div>`; }
    catch (e) { toast(e.message, 5000); }
  });
  cleanup = () => { if (testCap) testCap.stop(); };
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
refreshStatus().then(route);
