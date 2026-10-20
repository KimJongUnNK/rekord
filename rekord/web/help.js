/* REKORD help: the ⓘ next to every setting and term. Hover (mouse) or tap (touch) shows what it does.
   Texts live here, in one place; app.js only writes ${tip("key")}. */
"use strict";

const TIPS = {
  // ---------------------------------------------------------------- Darstellung
  theme: "<b>System</b> folgt deinem Gerät – wechselt es abends auf dunkel, macht REKORD mit. <b>Hell</b> und <b>Dunkel</b> bleiben immer so. Gilt nur für dieses Gerät.",
  accent: "Die Farbe für Knöpfe, Markierungen, Fortschrittsbalken und den Aufnahme-Ring. Eigene Farbe über das Farbfeld rechts. Die Schrift auf Knöpfen passt sich automatisch an, damit sie lesbar bleibt.",
  density: "Wie viel Platz zwischen den Elementen ist. <b>Luftig</b>: mehr Abstand, ruhiger, gut zum Tippen. <b>Kompakt</b>: weniger Abstand, mehr auf einen Blick – gut für kleine Laptop-Bildschirme.",
  // ---------------------------------------------------------------- Audio
  mic: "Welches Mikrofon dieses Gerät für Aufnahmen nutzt. <b>Systemstandard</b> ist das, was im Betriebssystem eingestellt ist. Die Namen der Mikrofone erscheinen erst, wenn du den Mikrofon-Zugriff einmal erlaubt hast.",
  mictest: "Zeigt live, wie laut das Mikrofon dich hört. Beim normalen Sprechen sollte der Balken etwa bis zur Mitte gehen. Bleibt er leer: anderes Mikrofon wählen oder den Zugriff erlauben.",
  meeting: "<b>Vor Ort</b>: alle sitzen im Raum, das Mikrofon reicht. <b>Online</b>: Teams, Zoom, Meet … – REKORD nimmt zusätzlich den Ton des Calls direkt am Computer auf, also die Stimmen der anderen. Das geht auch, wenn der Call in der Teams- oder Zoom-App läuft. Nur Ton, kein Bild. Am Mac fragt macOS beim ersten Mal nach „Bildschirm- & Systemaudioaufnahme“ – das ist für den Ton nötig. Mit Kopfhörern ist der Ton am saubersten. <b>Vorlesung</b>: eine Person trägt vor (z. B. an der Uni), Fragen aus dem Hörsaal werden als „Publikum“ gesammelt – ohne Mitzählen.",
  lecture: "REKORD erkennt die vortragende Person an der Stimme – ist sie schon bekannt, steht ihr Name da, sonst „Vortragende Person“ (danach mit „Wer ist das?“ benennen). Alle anderen Stimmen landen gesammelt unter „Publikum“. Das Protokoll wird automatisch ein Lernzettel: Kernaussagen, Definitionen, Prüfungsrelevantes, Fragen aus dem Hörsaal.",
  processing: "Filter, die das Gerät auf das Mikrofon anwendet, bevor REKORD es hört. Für Besprechungen im Raum meist alles an lassen.",
  noiseSuppression: "Filtert gleichmäßige Geräusche wie Lüfter, Klimaanlage oder Straßenlärm heraus. Bei Musik oder sehr leisen Stimmen eher aus.",
  echoCancellation: "Entfernt den Ton deiner eigenen Lautsprecher aus dem Mikrofon – wichtig, wenn ein Call laut über Boxen läuft. Mit Kopfhörern unnötig.",
  autoGainControl: "Regelt die Lautstärke automatisch: leise Stimmen werden lauter, laute leiser. Bei einem guten, fest eingestellten Mikro eher aus.",
  liveDetect: "<b>An</b>: Während der Aufnahme siehst du, wer gerade spricht, und die Mitschrift läuft mit. <b>Aus</b>: REKORD nimmt nur auf und wertet danach aus – spart Akku und Rechenleistung, z. B. am Handy.",
  wakeLock: "Verhindert, dass sich der Bildschirm während einer Aufnahme ausschaltet. Wichtig am Handy im Browser: Bei gesperrtem Bildschirm stoppt der Browser das Mikrofon.",
  // ---------------------------------------------------------------- KI
  provider: "Welche KI Protokolle, To-dos, Mind Maps und Antworten schreibt. Aufnahme, Transkript und Sprecher-Erkennung laufen immer lokal – egal, was du hier wählst.<br><b>Claude / ChatGPT</b>: beste Texte, kostet wenige Cent pro Meeting, nur der Text geht an den Anbieter.<br><b>Lokal</b>: gratis, nichts verlässt den Computer, braucht 8–16 GB Arbeitsspeicher.<br><b>Kompatibel</b>: eigener Server wie LM Studio.<br><b>Aus</b>: nur Transkript.",
  apikey: "Eine Art Passwort für die KI des Anbieters. Bleibt auf diesem Computer und wird nur an den Anbieter geschickt. Abgerechnet wird über dein Konto dort – meist wenige Cent pro Meeting. Ein ChatGPT-Plus- oder Claude-Pro-Abo enthält das nicht.",
  model: "Welches KI-Modell schreibt. Größere Modelle schreiben bessere Protokolle, sind aber langsamer und teurer. Claude: <b>claude-opus-5-5</b> beste Qualität, <b>claude-haiku-5-5</b> schnell und günstig.",
  effort: "Wie lange Claude nachdenkt, bevor es schreibt. <b>low</b>: schnell und günstig. <b>medium</b>: Standard. <b>high</b> bis <b>max</b>: gründlicher bei langen, komplizierten Meetings – dauert länger und kostet mehr.",
  fallback: "Lehnt das gewählte Claude-Modell eine Anfrage ab, beantwortet sie automatisch ein anderes Claude-Modell, statt mit einem Fehler abzubrechen.",
  localmodel: "Die KI, die komplett auf deinem Computer läuft (mit dem kostenlosen Programm Ollama). <b>Lokal einrichten</b> erledigt alles: installieren, starten, passendes Modell laden. Größere Modelle schreiben besser, brauchen aber mehr Arbeitsspeicher.",
  ollamaurl: "Wo Ollama erreichbar ist. Standard: http://localhost:11434, also dieser Computer. Nur ändern, wenn Ollama auf einem anderen Rechner im Netz läuft.",
  context: "Wie viel Text die KI auf einmal lesen kann. Mehr = längere Meetings in einem Stück, braucht aber mehr Arbeitsspeicher. 32.768 Tokens reichen für etwa 1,5 Stunden Gespräch; längere werden automatisch in Teilen verarbeitet.",
  serverurl: "Adresse eines Servers, der wie die OpenAI-Schnittstelle funktioniert – z. B. LM Studio (http://localhost:1234/v1), llama.cpp, Jan, vLLM oder OpenRouter.",
  connection: "Schickt eine Mini-Anfrage an die gewählte KI und zeigt, ob sie antwortet und wie schnell.",
  sumlang: "In welcher Sprache Protokolle und Zusammenfassungen geschrieben werden. <b>Wie im Gespräch</b>: die Sprache, die im Meeting überwiegend gesprochen wurde.",
  autosum: "Nach jeder Aufnahme schreibt REKORD automatisch ein Protokoll mit der gewählten Vorlage. Andere Vorlagen kannst du in jeder Aufnahme zusätzlich erzeugen.",
  // ---------------------------------------------------------------- Transkription
  lang: "Die gesprochene Sprache. Fest eingestellt (z. B. Deutsch) ist am genauesten. <b>Automatisch</b> erkennt die Sprache pro Satz – gut für gemischte Meetings, bei sehr kurzen Sätzen aber manchmal falsch.",
  engine: "Das Programm, das Sprache in Text verwandelt. <b>Whisper ONNX</b> läuft auf jedem Computer. <b>faster-whisper</b> nutzt eine NVIDIA-Grafikkarte und ist dann deutlich schneller – muss extra installiert werden.",
  asrmodel: "Größe der Spracherkennung. <b>tiny/base</b>: sehr schnell, mehr Fehler. <b>small</b>: guter Standard für Laptops. <b>medium/large</b>: genauer, deutlich langsamer. <b>turbo</b>: fast so gut wie large, viel schneller. Ein neues Modell wird beim Auswählen automatisch geladen.",
  threads: "Wie viele Prozessorkerne REKORD gleichzeitig nutzt. Mehr = schneller fertig, aber der Computer ist währenddessen stärker ausgelastet. Voreingestellt passend zu deinem Computer.",
  vocab: "Wörter, die die Spracherkennung immer wieder falsch schreibt – Namen, Firmen, Fachbegriffe. Links, wie es erkannt wird, rechts, wie es richtig heißt. Wird in jeder Aufnahme automatisch ersetzt.",
  // ---------------------------------------------------------------- Sprecher
  pthr: "Wie sicher REKORD sein muss, bevor es eine Stimme einer bekannten Person zuordnet. <b>Höher</b>: weniger Verwechslungen, dafür öfter „Nicht erkannte Stimme“ statt Name. <b>Niedriger</b>: erkennt öfter, verwechselt aber leichter. Standard 0.55.",
  lthr: "Wie oben, aber für die Live-Anzeige. Live hat REKORD nur kurze Ausschnitte, darum etwas lockerer. Standard 0.50.",
  cthr: "Ab wann zwei Stimmen als verschiedene Personen gelten. <b>Höher</b>: trennt feiner (gut bei ähnlichen Stimmen). <b>Niedriger</b>: fasst eher zusammen (gut, wenn eine Person doppelt auftaucht). Standard 0.60.",
  nspk: "Wie viele Leute in Aufnahmen sprechen, wenn du es vorher nicht angibst. <b>Automatisch</b>: REKORD schätzt selbst. Bei Live-Aufnahmen fragt REKORD jedes Mal „Wer ist dabei?“ – das hat Vorrang.",
  embm: "Das Modell, das aus einer Stimme einen Stimmabdruck berechnet. Ein Wechsel macht alle gespeicherten Stimmabdrücke unbrauchbar – alle Personen müssen neu eingesprochen werden. Nur ändern, wenn du weißt, warum.",
  // ---------------------------------------------------------------- Modelle
  models: "Die Programme, mit denen REKORD hört – alle laufen auf diesem Computer. <b>Spracherkennung</b> schreibt den Text, <b>Sprecherwechsel</b> merkt, wann jemand anderes redet, <b>Stimmabdruck</b> erkennt Personen wieder, <b>Sprach-Erkennung</b> trennt Sprechen von Stille. Fehlende lädt REKORD beim Start selbst.",
  // ---------------------------------------------------------------- iPhone & Geräte
  qr: "Für die REKORD-App am iPhone (Aufnahme auch bei gesperrtem Bildschirm, Sperrbildschirm-Widget). Eine Web-Version fürs Handy gibt es nicht – im WLAN spricht nur die App mit REKORD.",
  address: "Unter dieser Adresse ist REKORD im WLAN erreichbar. Handy und Computer müssen im selben WLAN sein – Gäste-WLANs trennen Geräte voneinander.",
  paircode: "6 Ziffern zum Eintippen am Handy – statt QR-Code. Der Code gilt 10 Minuten und nur zum Koppeln: Das Handy bekommt dabei einen eigenen, langen Schlüssel. Nach 5 falschen Versuchen ist 1 Minute Pause. <b>Neuer Code</b> macht sofort einen neuen.",
  devices: "Alle Handys und Geräte, die mit dem Code gekoppelt wurden. <b>Trennen</b> sperrt ein einzelnes Gerät aus (z. B. ein altes Handy). <b>Alle Geräte trennen</b> sperrt alle aus – auch die per QR-Code gekoppelten.",
  firewall: "Die Firewall dieses Linux-Computers blockiert Verbindungen vom iPhone. Der Knopf gibt genau den REKORD-Port frei (8765) und fragt dafür nach deinem Passwort.",
  // ---------------------------------------------------------------- Claude
  claudedesktop: "Verbindet die Claude-App mit deiner REKORD-Bibliothek (über MCP, einen offenen Standard). Claude kann dann deine Transkripte durchsuchen und lesen und Zusammenfassungen zurückspeichern – mit deinem normalen Claude-Abo, ohne API-Key. Danach Claude einmal neu starten.",
  claudecode: "Dasselbe für Claude Code, die Terminal-Version von Claude. Nur nötig, wenn du Claude Code nutzt.",
  // ---------------------------------------------------------------- Speicher
  storage: "Wo REKORD Aufnahmen, Datenbank und Stimmabdrücke ablegt. Das kann der eingebaute Speicher sein, eine externe Festplatte (USB/Thunderbolt), eine zweite SSD (z. B. NVMe) oder ein Netzlaufwerk (NAS). Beim Ändern zieht REKORD alles um und startet kurz neu. Ist ein externes Laufwerk beim Start nicht angeschlossen, sagt REKORD Bescheid, statt einen leeren Ordner anzulegen.",
  modelsdir: "Wo die Modelle liegen: die Sprachmodelle (~0,7 GB) und die lokale KI (3–10 GB pro Modell). Kann ein anderes Laufwerk sein als die Aufnahmen – z. B. die großen Modelle auf eine externe SSD, die Aufnahmen auf den Computer. Beim Ändern werden vorhandene Modelle mitgenommen.",
  bestmodel: "REKORD erkennt den Arbeitsspeicher (RAM) und ob ein Grafikchip da ist (Apple-Chip oder NVIDIA) und sucht das stärkste Modell aus, das darauf noch flott läuft. Mehr RAM = besseres Modell. <b>Laden & verwenden</b> lädt es und schaltet danach automatisch um.",
  othermodel: "Jedes Modell aus der Ollama-Bibliothek (ollama.com/library) – Namen eintippen, z. B. <b>llama3.1:8b</b> oder <b>mistral</b>. Faustregel: Das Modell sollte höchstens etwa 60 % deines RAMs groß sein, sonst wird es sehr langsam.",
  ask: "Eine Frage an alle Aufnahmen auf einmal – z. B. „Was hat Anna zum Budget gesagt?“ oder „Welche To-dos sind offen?“. REKORD sucht die passenden Stellen und lässt die KI antworten; jede Antwort nennt, wer es wann gesagt hat – ein Klick auf die Zeit öffnet die Aufnahme genau dort. Braucht eine KI (Einstellungen → KI). Der Verlauf bleibt auf diesem Computer.",
  templates: "Eine Vorlage ist die Anleitung für die KI: welche Abschnitte das Protokoll hat, wie ausführlich, in welchem Ton. Eingebaute Vorlagen lassen sich nicht überschreiben – Bearbeiten legt eine eigene Kopie an. Eigene Vorlagen erscheinen überall, wo du zusammenfasst (auch in der iPhone-App).",
  tplorder: "Die Reihenfolge deiner Vorlagen: Was oben steht, steht auch beim Zusammenfassen ganz oben in der Auswahl (am Computer und in der iPhone-App). Am ⠿-Griff ziehen oder mit ↑ ↓ ⤒ verschieben – wird sofort gespeichert. <b>Reihenfolge zurücksetzen</b> stellt die ursprüngliche wieder her.",
  ollamadelete: "Löscht das Modell vom Computer und gibt den Speicher frei. War es das aktive Modell, nimmt REKORD automatisch ein anderes vorhandenes. Neu laden geht jederzeit mit „Laden“.",
  datadir: "Hier liegt alles: Audio, Datenbank, Stimmabdrücke, Modelle. Backup = diesen Ordner kopieren. Neuer Computer = Ordner rüberkopieren.",
  inbox: "Ein Ordner, den REKORD beobachtet: Jede Audio- oder Videodatei, die hier landet, wird automatisch verarbeitet. Praktisch mit iCloud-, Dropbox- oder OneDrive-Sync vom Handy oder für Diktiergeräte.",
  privacy: "Audio, Transkript und Stimmabdrücke bleiben immer auf diesem Computer. Nur wenn du Claude oder ChatGPT nutzt, geht der Text eines Gesprächs zum Zusammenfassen an den Anbieter.",
  autostart: "REKORD startet beim Einschalten des Computers unsichtbar im Hintergrund. So kann sich das iPhone jederzeit verbinden, ohne dass du REKORD erst öffnen musst. Das Fenster öffnest du wie gewohnt über das App-Symbol.",
  help: "Startet die Einführung vom ersten Start noch einmal: Speicherort, Aussehen, Sprache, Mikrofon, KI, deine Stimme, iPhone.",
  version: "Die installierte Version. <b>Jetzt aktualisieren</b> lädt die neue Version, <b>ersetzt</b> die alte (keine zweite App daneben) und startet REKORD neu. Aufnahmen, Personen und Einstellungen bleiben. Läuft gerade eine Aufnahme, geht das erst danach. Startest du eine neuere REKORD-Version, während die alte noch offen ist, beendet sich die alte von selbst.",
  updatecheck: "REKORD fragt beim Start und dann alle 6 Stunden bei GitHub nach, ob es eine neue Version gibt, und zeigt sie links an. Installiert wird nur, wenn du auf <b>Aktualisieren</b> klickst. Dabei wird nichts über dich gesendet.",
  quit: "Beendet REKORD komplett, auch den Teil im Hintergrund. Danach kann sich das iPhone nicht mehr verbinden, bis du REKORD wieder öffnest.",
  // ---------------------------------------------------------------- Live & Aufnahmen
  who: "Vor jeder Aufnahme: Wie viele Leute sprechen, und wer davon ist schon bekannt? Dann weiß REKORD genau, wie viele Stimmen es trennen muss, und vergleicht nur mit den Leuten im Raum – das verhindert fast alle Verwechslungen.",
  total: "Alle, die in diesem Meeting reden – dich mitgezählt.",
  known: "Leute, deren Stimme REKORD schon kennt. Antippen, wer dabei ist. Alle anderen zählen als neu.",
  newpeople: "Stimmen, die REKORD noch nicht kennt. Sie landen gesammelt unter „Nicht erkannte Stimme“ – transkribiert wird trotzdem alles. Am besten jetzt kurz einsprechen lassen (jede Person bekommt ihren eigenen Text), sonst nach der Aufnahme bei „Wer ist das?“ benennen – ab dann werden sie automatisch erkannt.",
  intro: "Jede neue Person spricht ca. 45 Sekunden – Text vorlesen oder einfach reden. Danach erkennt REKORD sie mit Namen, in diesem und in allen künftigen Meetings.",
  enrollmode: "<b>Text vorlesen</b>: Die Person liest ihren eigenen Text – am genauesten. <b>Einfach reden lassen</b>: Die Person redet über irgendwas, oder du lässt jemanden reden, der sowieso spricht (z. B. den Prof in der Vorlesung) – kurze Zwischenrufe anderer lässt REKORD weg. <b>Aus Aufnahme lernen</b>: Die Stimme aus einer fertigen Aufnahme nehmen. Gezählt werden nur Sekunden, in denen wirklich gesprochen wird.",
  room: "Alle Stimmen dieser Aufnahme mit ihrem Redeanteil. Eine unbekannte Stimme antippen und Namen eingeben – ab sofort wird sie erkannt.",
  remember: "Speichert den Stimmabdruck dieser Person. In künftigen Aufnahmen erkennt REKORD sie automatisch mit Namen. Jede Bestätigung macht die Erkennung besser.",
  naming: "Hier stehen Stimmen, die REKORD noch nicht kennt. Anhören, Namen eingeben, <b>Merken</b> – ab der nächsten Aufnahme werden sie automatisch erkannt. Hat sich jemand vorgestellt („Hier ist Emil“), schlägt REKORD den Namen vor.",
  people: "Ein Stimmabdruck ist eine Zahlenreihe, die beschreibt, wie jemand klingt. Er bleibt auf diesem Computer. Je öfter du einen Namen bestätigst, desto zuverlässiger erkennt REKORD die Person.",
};

const tip = (k) => (TIPS[k] ? `<button type="button" class="info" data-tip="${k}" aria-label="Was ist das?">i</button>` : "");

// one floating bubble for all ⓘ: hover on computers, tap on phones, focus + Enter on keyboards
(function tooltips() {
  const el = document.createElement("div");
  el.id = "tip";
  el.setAttribute("role", "tooltip");
  document.body.appendChild(el);
  let cur = null;
  const hover = matchMedia("(hover: hover) and (pointer: fine)");
  const place = () => {
    if (!cur) return;
    const r = cur.getBoundingClientRect(), w = Math.min(340, innerWidth - 32);
    el.style.width = w + "px";
    const left = Math.min(Math.max(16, r.left + r.width / 2 - w / 2), innerWidth - w - 16);
    el.style.left = left + "px";
    const below = r.bottom + 8, h = el.offsetHeight;
    const top = below + h > innerHeight - 8 && r.top - h - 8 > 8 ? r.top - h - 8 : below;
    el.style.top = top + "px";
    el.style.setProperty("--arrow", Math.round(r.left + r.width / 2 - left) + "px");
    el.classList.toggle("up", top < r.top);
  };
  const show = (b) => {
    if (!TIPS[b.dataset.tip]) return;
    cur = b;
    const host = b.closest("dialog") || document.body;  // modal dialogs sit in the top layer – the bubble must too
    if (el.parentNode !== host) host.appendChild(el);
    el.innerHTML = TIPS[b.dataset.tip];
    el.classList.add("show");
    b.setAttribute("aria-describedby", "tip");
    place();
  };
  const hide = () => { if (cur) cur.removeAttribute("aria-describedby"); cur = null; el.classList.remove("show"); };
  document.addEventListener("mouseover", (e) => {
    if (!hover.matches) return;
    const b = e.target.closest && e.target.closest(".info");
    if (b) { if (b !== cur) show(b); } else if (cur && !e.target.closest("#tip")) hide();
  });
  // capture: the ⓘ sits inside labels – a click must not toggle the checkbox next to it
  document.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest(".info");
    if (b) { e.preventDefault(); e.stopPropagation(); if (cur === b && !hover.matches) hide(); else show(b); }
    else if (cur && !e.target.closest("#tip")) hide();
  }, true);
  document.addEventListener("focusin", (e) => { if (e.target.classList && e.target.classList.contains("info")) show(e.target); });
  document.addEventListener("focusout", (e) => { if (e.target === cur) hide(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  addEventListener("scroll", hide, true);
  addEventListener("resize", hide);
  addEventListener("hashchange", hide);
})();
