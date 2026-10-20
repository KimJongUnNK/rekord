/* REKORD first start: a short guided setup instead of dropping people into the app.
   Steps: Willkommen → Speicherort (before any big download) → Aussehen → Mikrofon → KI → Deine Stimme → iPhone → Fertig.
   Everything can be skipped and changed later in the settings; "Einführung starten" there shows it again. */
"use strict";

const WELCOME_KEY = "rekord.welcome";

function welcomeDone() {
  try { return localStorage.getItem(WELCOME_KEY) === "done"; } catch (e) { return false; }
}
async function markWelcomeDone() {
  try { localStorage.setItem(WELCOME_KEY, "done"); localStorage.removeItem(WELCOME_KEY + ".step"); } catch (e) {}
  if (IS_LOCAL) { try { await api("/api/settings", { method: "PUT", json: { welcome_done: true } }); } catch (e) {} }
}

async function welcome(force = false) {
  if ($("#welcome")) return;
  const st = state.status || (await api("/api/status").catch(() => null));
  if (!st || st.storage_missing) return;
  const firstRun = IS_LOCAL ? !st.welcome_done : !welcomeDone();
  if (!force && !firstRun) return;
  const needStorage = IS_LOCAL && !st.storage_chosen;
  const steps = ["hi", ...(IS_LOCAL ? ["storage"] : []), "look", "lang", "mic", "ai", "voice", ...(IS_LOCAL ? ["phone"] : []), "done"];
  let i = 0;
  try { i = Math.min(steps.length - 1, Number(localStorage.getItem(WELCOME_KEY + ".step") || 0)); } catch (e) {}
  if (needStorage) i = Math.min(i, steps.indexOf("storage"));
  const result = {};
  let cap = null, stopProg = null, timer = null;

  const ov = document.createElement("div");
  ov.id = "welcome";
  ov.className = "welcome";
  ov.setAttribute("role", "dialog");
  ov.setAttribute("aria-modal", "true");
  ov.setAttribute("aria-label", "Einrichtung");
  document.body.appendChild(ov);
  document.body.classList.add("welcome-open");

  const close = async (done = true) => {
    cleanupStep();
    if (done) await markWelcomeDone();
    ov.remove();
    document.body.classList.remove("welcome-open");
    refreshStatus();
    if (location.hash.startsWith("#/settings")) route();
  };
  const cleanupStep = () => {
    if (cap) { cap.stop(); cap = null; }
    if (stopProg) { stopProg(); stopProg = null; }
    clearTimeout(timer);
  };
  const go = (n) => {
    cleanupStep();
    i = Math.max(0, Math.min(steps.length - 1, n));
    try { localStorage.setItem(WELCOME_KEY + ".step", String(i)); } catch (e) {}
    render();
  };

  const frame = (body, { next = "Weiter", nextId = "wl-next", canSkip = true, back = true } = {}) => `
    <div class="wl-card">
      <div class="wl-top"><span class="brand-word">REKORD</span><span class="wl-dots">${steps.map((_, k) => `<i class="${k === i ? "on" : k < i ? "done" : ""}"></i>`).join("")}</span>
        ${canSkip ? `<button class="btn ghost sm" id="wl-skip">Überspringen</button>` : ""}</div>
      <div class="wl-body">${body}</div>
      <div class="wl-foot">${back && i > 0 ? `<button class="btn" id="wl-back">Zurück</button>` : "<span></span>"}<span class="spacer"></span>
        ${next ? `<button class="btn primary" id="${nextId}">${next}</button>` : ""}</div></div>`;

  const bindFrame = () => {
    $("#wl-back", ov) && ($("#wl-back", ov).onclick = () => go(i - 1));
    $("#wl-skip", ov) && ($("#wl-skip", ov).onclick = async () => {
      if (steps[i] === "storage" && needStorage) { await chooseStorage(null); return; }  // keep the default, but go on
      close(true);
    });
    $("#wl-next", ov) && ($("#wl-next", ov).onclick = () => go(i + 1));
  };

  // ------------------------------------------------------------------ storage (before any big download)
  async function chooseStorage(home, models) {
    try {
      const r = await api("/api/storage/choose", { method: "POST", json: home ? { home, models } : {} });
      if (r.state === "running") return watchMove();
      go(i + 1);
    } catch (e) { toast(e.message, 7000); }
  }
  async function watchMove() {
    const box = $("#wl-move", ov) || $(".wl-body", ov);
    const poll = async () => {
      let s;
      try { s = await api("/api/storage"); } catch (e) {  // restarting: wait for the new process, then continue there
        box.innerHTML = `<div class="muted">REKORD startet am neuen Ort neu …</div>`;
        timer = setTimeout(async () => {
          try { await api("/api/status"); try { localStorage.setItem(WELCOME_KEY + ".step", String(i + 1)); } catch (e2) {} location.reload(); }
          catch (e2) { poll(); }
        }, 1500);
        return;
      }
      const j = s.job;
      if (j.state === "error") { box.innerHTML = `<div style="color:#EF4444">✗ ${esc(j.error)}</div>`; return; }
      const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
      box.innerHTML = `<div class="muted">${j.restart ? "Fertig – REKORD startet am neuen Ort neu …" : "Wird eingerichtet … " + pct + " %"}</div>
        <div class="progress" style="width:100%"><i style="width:${j.restart ? 100 : pct}%"></i></div>`;
      if (j.state === "done" && !j.restart) { go(i + 1); return; }
      timer = setTimeout(poll, 800);
    };
    poll();
  }

  async function renderStorage() {
    let s;
    try { s = await api("/api/storage"); } catch (e) { go(i + 1); return; }
    const drives = s.drives || [];
    let pick = drives.find((d) => s.home.startsWith(d.path) && d.path !== "/") || drives[0];
    let sameModels = true;
    const kindIcon = { internal: "💻", external: "🔌", nvme: "⚡", network: "🌐", removable: "💾" };
    ov.innerHTML = frame(`
      <div class="eyebrow">Schritt ${i + 1} · Speicherort</div>
      <h1 class="wl-h">Wo soll REKORD speichern?${tip("storage")}</h1>
      <p class="wl-lead">Aufnahmen, Stimmabdrücke und die KI-Modelle. Wähle ein Laufwerk – auch eine externe Festplatte, eine zweite SSD (NVMe) oder ein Netzlaufwerk geht.
        ${needStorage ? "Erst danach lädt REKORD die Sprachmodelle (~0,7 GB)." : ""}</p>
      <div class="drive-list" id="wl-drives">${drives.map((d, k) => `<button type="button" class="drive" data-k="${k}">
        <span class="drive-ico">${kindIcon[d.kind] || "💽"}</span><span><b>${esc(d.name)}</b><small>${esc(d.kind_label)} · ${gbFmt(d.free_gb)} frei${d.writable ? "" : " · schreibgeschützt"}</small></span></button>`).join("")}</div>
      <label class="muted" for="wl-home">Ordner für REKORD</label><input type="text" id="wl-home" autocomplete="off" spellcheck="false">
      <label class="row"><input type="checkbox" id="wl-same" checked> KI-Modelle im selben Ordner${tip("modelsdir")}</label>
      <div id="wl-models-box" class="hidden"><label class="muted" for="wl-models">Ordner für KI-Modelle</label><input type="text" id="wl-models" autocomplete="off" spellcheck="false"></div>
      <div class="muted" style="font-size:13px">Platzbedarf: Sprachmodelle ~0,7 GB · lokale KI 3–6 GB (optional) · Aufnahmen ~30 MB pro Stunde.</div>
      <div id="wl-move"></div>`, { next: needStorage ? "Hier speichern" : "Weiter", nextId: "wl-store" });
    bindFrame();
    const show = () => {
      $$("#wl-drives .drive", ov).forEach((b) => b.classList.toggle("on", drives[Number(b.dataset.k)] === pick));
      const sug = (s.suggest || {})[pick.path] || { home: s.home, models: s.models };
      $("#wl-home", ov).value = pick.path && s.home.startsWith(pick.path) && pick.path !== "/" && !needStorage ? s.home : sug.home;
      if (sameModels) $("#wl-models", ov).value = sug.models;
    };
    $$("#wl-drives .drive", ov).forEach((b) => b.onclick = () => { pick = drives[Number(b.dataset.k)]; show(); });
    $("#wl-same", ov).onchange = (e) => { sameModels = e.target.checked; $("#wl-models-box", ov).classList.toggle("hidden", sameModels); show(); };
    if (pick) show(); else $("#wl-home", ov).value = s.home;
    $("#wl-store", ov).onclick = async (e) => {
      const home = $("#wl-home", ov).value.trim(), models = sameModels ? "" : $("#wl-models", ov).value.trim();
      if (!needStorage && home === s.home && !models) { go(i + 1); return; }
      e.target.disabled = true;
      if (!needStorage && home !== s.home) {  // later tour: moving existing data → settings do it with a restart
        try { await api("/api/storage/move", { method: "POST", json: { what: "home", target: home } }); watchMove(); }
        catch (err) { toast(err.message, 7000); e.target.disabled = false; }
        return;
      }
      await chooseStorage(home, models);
      e.target.disabled = false;
    };
  }

  // ------------------------------------------------------------------ the other steps
  async function render() {
    const step = steps[i];
    if (step === "storage") return renderStorage();
    if (step === "hi") {
      ov.innerHTML = frame(`
        <h1 class="wl-big">Hallo<span class="acc">.</span></h1>
        <p class="wl-lead">REKORD nimmt Meetings auf, erkennt live, <b>wer gerade spricht</b>, und schreibt dir danach Protokoll, To-dos und Mind Map.</p>
        <ul class="wl-points">
          <li><b>Erkennt Menschen an der Stimme</b> – einmal einsprechen, ab dann in jedem Meeting.</li>
          <li><b>Alles auf deinem Computer</b> – Audio und Stimmen verlassen ihn nie.</li>
          <li><b>Deine KI</b> – Claude, ChatGPT oder komplett offline.</li></ul>
        <p class="muted">Die Einrichtung dauert 2–3 Minuten. Jeder Schritt lässt sich überspringen und später ändern. Überall, wo du ein <span class="info" style="pointer-events:none">i</span> siehst, steht die Erklärung.</p>`,
      { next: "Los geht's" });
      bindFrame();
      return;
    }
    if (step === "look") {
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · Aussehen</div><h1 class="wl-h">So soll's aussehen.</h1>
        <div class="wl-field"><b>Erscheinungsbild</b>${tip("theme")}<div class="seg" id="wl-theme">${[["system", "System"], ["light", "Hell"], ["dark", "Dunkel"]].map(([k, n]) =>
          `<button data-v="${k}" class="${prefs.theme === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
        <div class="wl-field"><b>Akzentfarbe</b>${tip("accent")}<div class="swatches" id="wl-acc">${ACCENTS.map(([c, n]) =>
          `<button class="sw ${prefs.accent.toLowerCase() === c.toLowerCase() ? "on" : ""}" style="--c:${c}" title="${n}" data-c="${c}"></button>`).join("")}</div></div>
        <div class="wl-field"><b>Dichte</b>${tip("density")}<div class="seg" id="wl-dens">${[["comfortable", "Luftig"], ["compact", "Kompakt"]].map(([k, n]) =>
          `<button data-v="${k}" class="${prefs.density === k ? "on" : ""}">${n}</button>`).join("")}</div></div>
        <p class="muted" style="font-size:13px">Gilt nur für dieses Gerät. Du siehst die Änderung sofort.</p>`);
      bindFrame();
      $$("#wl-theme button", ov).forEach((b) => b.onclick = () => { setPref("theme", b.dataset.v); $$("#wl-theme button", ov).forEach((x) => x.classList.toggle("on", x === b)); });
      $$("#wl-dens button", ov).forEach((b) => b.onclick = () => { setPref("density", b.dataset.v); $$("#wl-dens button", ov).forEach((x) => x.classList.toggle("on", x === b)); });
      $$("#wl-acc .sw", ov).forEach((b) => b.onclick = () => { setPref("accent", b.dataset.c); $$("#wl-acc .sw", ov).forEach((x) => x.classList.toggle("on", x === b)); });
      return;
    }
    if (step === "lang") {
      const cfg = await api("/api/settings").catch(() => ({ language: "", summary_language: "de" }));
      const opt = (v, cur, n) => `<option value="${esc(v)}" ${String(v) === String(cur) ? "selected" : ""}>${esc(n)}</option>`;
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · Sprache</div><h1 class="wl-h">Welche Sprache sprecht ihr?</h1>
        <div class="wl-field"><b>Sprache in den Meetings</b>${tip("lang")}<select id="wl-lang">${LANGS.map(([k, n]) => opt(k, cfg.language, n)).join("")}</select>
          <span class="muted" style="font-size:13px">Fest eingestellt ist am genauesten. <b>Automatisch</b> erkennt die Sprache pro Satz – für gemischte Runden.</span></div>
        <div class="wl-field"><b>Protokolle schreiben auf</b>${tip("sumlang")}<select id="wl-sumlang">${[["de", "Deutsch"], ["en", "Englisch"], ["auto", "Wie im Gespräch"]].map(([k, n]) => opt(k, cfg.summary_language, n)).join("")}</select></div>
        <p class="muted" style="font-size:13px">Gilt für alle Aufnahmen und lässt sich unter Einstellungen → Transkription bzw. KI ändern. Die App selbst ist auf Deutsch.</p>`);
      bindFrame();
      $("#wl-lang", ov).onchange = (e) => api("/api/settings", { method: "PUT", json: { language: e.target.value } }).then(() => toast("Gespeichert", 1000));
      $("#wl-sumlang", ov).onchange = (e) => api("/api/settings", { method: "PUT", json: { summary_language: e.target.value } }).then(() => toast("Gespeichert", 1000));
      return;
    }
    if (step === "mic") {
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · Mikrofon</div><h1 class="wl-h">Hört REKORD dich?</h1>
        <p class="wl-lead">Wähle dein Mikrofon und sag etwas – der Balken sollte bis etwa zur Mitte ausschlagen.</p>
        <div class="wl-field"><b>Mikrofon</b>${tip("mic")}<select id="wl-mic"><option value="">Systemstandard</option></select></div>
        <div class="level" style="height:14px"><i id="wl-lvl"></i></div>
        <div class="muted" id="wl-micmsg" style="font-size:13px">Fragt REKORD nach dem Mikrofon: <b>Erlauben</b>.</div>`);
      bindFrame();
      const startCap = async () => {
        if (cap) cap.stop();
        cap = new Capture({ onLevel: (v) => { const l = $("#wl-lvl", ov); if (l) l.style.width = v * 100 + "%"; if (v > 0.25) result.mic = true; } });
        try {
          await cap.start("mic");
          const mics = await listMics();
          const sel = $("#wl-mic", ov);
          if (sel) sel.innerHTML = `<option value="">Systemstandard</option>` + mics.map((m) => `<option value="${esc(m.deviceId)}" ${m.deviceId === prefs.micId ? "selected" : ""}>${esc(m.label || "Mikrofon")}</option>`).join("");
          $("#wl-micmsg", ov).innerHTML = "Sag etwas – zum Beispiel deinen Namen.";
        } catch (e) { $("#wl-micmsg", ov).innerHTML = `<span style="color:#EF4444">Kein Zugriff aufs Mikrofon: ${esc(e.message)}</span>`; cap = null; }
      };
      $("#wl-mic", ov).onchange = (e) => { setPref("micId", e.target.value); startCap(); };
      startCap();
      return;
    }
    if (step === "ai") {
      const s = await api("/api/status").catch(() => state.status);
      const oll = await api("/api/ollama").catch(() => null);
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · KI</div><h1 class="wl-h">Wer schreibt deine Protokolle?${tip("provider")}</h1>
        ${s.ai_ready ? `<p class="wl-lead"><span style="color:#22C55E">✓ Schon eingerichtet:</span> ${esc(s.provider_name)}${s.model ? " · " + esc(s.model) : ""}. Du kannst das jederzeit ändern.</p>` : ""}
        <div class="provider-grid" id="wl-ai">
          <button class="prov" data-k="local"><b>Lokal · gratis</b><small>Ein Klick: REKORD lädt Ollama und ${oll ? esc(oll.default) : "ein passendes Modell"}. Nichts verlässt den Computer.</small></button>
          <button class="prov" data-k="anthropic"><b>Claude</b><small>Beste Qualität. API-Key einfügen.</small></button>
          <button class="prov" data-k="openai"><b>ChatGPT</b><small>API-Key einfügen.</small></button>
          <button class="prov" data-k="none"><b>Erstmal ohne</b><small>Nur Transkript und Sprecher.</small></button></div>
        <div id="wl-aicfg"></div>`);
      bindFrame();
      const cfg = $("#wl-aicfg", ov);
      $$("#wl-ai .prov", ov).forEach((b) => b.onclick = async () => {
        $$("#wl-ai .prov", ov).forEach((x) => x.classList.toggle("on", x === b));
        const k = b.dataset.k;
        if (stopProg) { stopProg(); stopProg = null; }
        if (k === "local") {
          if (!IS_LOCAL && !(oll && oll.installed)) { cfg.innerHTML = `<p class="muted">Die lokale KI wird am Computer eingerichtet.</p>`; return; }
          try { await api("/api/ollama/setup", { method: "POST", json: {} }); } catch (e) { cfg.innerHTML = `<p style="color:#EF4444">${esc(e.message)}</p>`; return; }
          cfg.innerHTML = `<div id="wl-prog"></div><p class="muted" style="font-size:13px">Du kannst schon weitermachen – das läuft im Hintergrund weiter.</p>`;
          stopProg = localSetupProgress($("#wl-prog", ov), () => refreshStatus());
          return;
        }
        await api("/api/settings", { method: "PUT", json: { llm: { provider: k } } });
        if (k === "none") { cfg.innerHTML = `<p class="muted">Ohne KI. Unter Einstellungen → KI jederzeit nachholen.</p>`; return; }
        const url = k === "anthropic" ? "https://console.anthropic.com/settings/keys" : "https://platform.openai.com/api-keys";
        cfg.innerHTML = `<div class="wl-field"><b>API-Key</b>${tip("apikey")}<div class="row"><input type="password" id="wl-key" placeholder="Key hier einfügen" autocomplete="off" style="flex:1">
          <a class="btn sm" href="${url}" target="_blank" rel="noopener">Key erstellen ↗</a></div></div><div id="wl-keyres" class="muted"></div>`;
        $("#wl-key", ov).focus();
        $("#wl-key", ov).addEventListener("change", async (e) => {
          const key = e.target.value.trim(); if (!key) return;
          $("#wl-keyres", ov).textContent = "teste …";
          await api("/api/settings", { method: "PUT", json: { llm: { [k]: { api_key: key } } } });
          const r = await api("/api/llm/test", { method: "POST" });
          $("#wl-keyres", ov).innerHTML = r.ok ? `<span style="color:#22C55E">✓ verbunden</span>` : `<span style="color:#EF4444">✗ ${esc(r.error)}</span>`;
          refreshStatus();
        });
      });
      return;
    }
    if (step === "voice") {
      let people = [];
      try { people = (await api("/api/profiles")).items; } catch (e) {}
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · Deine Stimme</div><h1 class="wl-h">Damit REKORD dich erkennt.</h1>
        <p class="wl-lead">Ca. 45 Sekunden sprechen – entweder einen Text vorlesen (jede Person bekommt ihren eigenen) oder einfach über irgendwas reden. Danach steht in jedem Meeting dein Name statt „${UNKNOWN}“.</p>
        ${people.length ? `<p>Schon bekannt: ${people.map((p) => `<span class="chip" style="--c:${p.color}"><i></i>${esc(p.name)}</span>`).join(" ")}</p>` : ""}
        <div class="row"><input type="text" id="wl-name" placeholder="Dein Name" autocomplete="off" style="max-width:280px">
          <button class="btn primary" id="wl-enroll">🎙 Jetzt einsprechen</button></div>
        <p class="muted" style="font-size:13px">Andere Leute sprichst du später unter <b>Personen</b> ein – oder direkt vor einem Meeting bei „Wer ist dabei?“.</p>`);
      bindFrame();
      $("#wl-enroll", ov).onclick = async () => {
        const prof = await enrollDialog({ name: $("#wl-name", ov).value.trim() });
        if (prof) { result.voice = prof.name; setPref("participants", [...new Set([...prefs.participants, prof.id])]); render(); }
      };
      return;
    }
    if (step === "phone") {
      let p = null;
      try { p = await api("/api/pair"); } catch (e) {}
      ov.innerHTML = frame(`
        <div class="eyebrow">Schritt ${i + 1} · iPhone</div><h1 class="wl-h">Auch am iPhone aufnehmen?</h1>
        <p class="wl-lead">Mit der REKORD-App am iPhone: dort auf <b>Koppeln</b> tippen, den Code scannen oder die 6 Ziffern eintippen. Alles, was du am iPhone aufnimmst, landet hier.</p>
        ${p && p.urls.length ? `<div class="row" style="align-items:center;gap:24px"><div class="qr">${p.qr_app}</div>
          <div><b style="font-size:34px;letter-spacing:.12em">${esc(p.code.code.slice(0, 3) + " " + p.code.code.slice(3))}</b>
          <p class="muted" style="max-width:260px">iPhone und Computer im selben WLAN. Der Code gilt 10 Minuten – später jederzeit unter Einstellungen → iPhone & Geräte.</p></div></div>`
          : `<p class="muted">Gerade kein WLAN gefunden. Später unter Einstellungen → iPhone & Geräte.</p>`}`,
      { next: "Weiter" });
      bindFrame();
      return;
    }
    if (step === "done") {
      const s = await api("/api/status").catch(() => state.status || {});
      const row = (ok, text) => `<li class="${ok ? "ok" : ""}">${ok ? "✓" : "–"} ${text}</li>`;
      ov.innerHTML = frame(`
        <h1 class="wl-big">Fertig<span class="acc">.</span></h1>
        <ul class="wl-check">
          ${row(true, "Aussehen")}
          ${row(result.mic, result.mic ? "Mikrofon hört dich" : "Mikrofon – nicht getestet")}
          ${row(s.ai_ready, s.ai_ready ? `KI: ${esc(s.provider_name)}` : "KI – später unter Einstellungen → KI")}
          ${row(result.voice, result.voice ? `Deine Stimme: ${esc(result.voice)}` : "Deine Stimme – später unter Personen")}</ul>
        <p class="wl-lead">Vor jeder Aufnahme fragt REKORD kurz: <b>Wer ist dabei?</b> – wie viele ihr seid und wer schon bekannt ist. So erkennt es jede Stimme richtig.</p>`,
      { next: "", back: true, canSkip: false });
      $(".wl-foot", ov).insertAdjacentHTML("beforeend", `<button class="btn" id="wl-app">Zur App</button><button class="btn primary" id="wl-rec">● Erste Aufnahme</button>`);
      bindFrame();
      $("#wl-app", ov).onclick = () => close(true);
      $("#wl-rec", ov).onclick = async () => { await close(true); location.hash = "#/live"; };
    }
  }
  render();
}
