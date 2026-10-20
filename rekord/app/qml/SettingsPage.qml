import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

// Einstellungen: look, microphone, AI, transcription, speaker recognition, models, iPhone, Claude, storage, updates.
Page {
    id: page
    objectName: "settingsPage"
    required property var app
    property var s: null          // the settings (/api/settings)
    property var st: null         // /api/status (models, home, inbox, mcp …)
    property var models: []
    property var templates: []
    property var pair: null
    property var integ: null
    property var storage: null
    property bool micTest: false
    readonly property var sections: [["look", "Darstellung"], ["audio", "Audio & Mikrofon"], ["ai", "KI"], ["asr", "Transkription"],
                                     ["spk", "Sprecher-Erkennung"], ["models", "Modelle"], ["pair", "iPhone & Geräte"],
                                     ["int", "Claude Desktop (MCP)"], ["data", "Speicher & Datenschutz"]]
    readonly property var langs: [["", "Automatisch (pro Satz)"], ["de", "Deutsch"], ["en", "Englisch"], ["fr", "Französisch"], ["it", "Italienisch"],
                                  ["es", "Spanisch"], ["nl", "Niederländisch"], ["pt", "Portugiesisch"], ["pl", "Polnisch"], ["tr", "Türkisch"],
                                  ["ru", "Russisch"], ["uk", "Ukrainisch"], ["hr", "Kroatisch"], ["sr", "Serbisch"], ["ar", "Arabisch"],
                                  ["zh", "Chinesisch"], ["ja", "Japanisch"], ["ko", "Koreanisch"]]
    readonly property var accents: [["#FF5A1F", "Voltage"], ["#2D7FF9", "Electric"], ["#C6F432", "Acid"], ["#E11D74", "Magenta"], ["#8B5CF6", "Violet"],
                                    ["#FACC15", "Yellow"], ["#EF4444", "Red"], ["#14B8A6", "Teal"], ["#F6F5F2", "Mono"]]
    readonly property string prov: s ? s.llm.provider : ""
    readonly property var pc: s && s.llm[prov] ? s.llm[prov] : ({})

    function load() {
        app.call("GET", "/api/settings", null, (r) => page.s = r)
        app.call("GET", "/api/status", null, (r) => page.st = r)
        loadModels()
        app.call("GET", "/api/templates", null, (r) => page.templates = r.items)
        loadPair()
        app.call("GET", "/api/integrations", null, (r) => page.integ = r, () => {})
        loadStorage()
    }
    function loadModels() { app.call("GET", "/api/models", null, (r) => page.models = r) }
    function loadPair() { app.call("GET", "/api/pair", null, (r) => page.pair = r, () => {}) }
    function loadStorage() { app.call("GET", "/api/storage", null, (r) => page.storage = r, () => {}) }
    function save(patch, quiet) {
        app.call("PUT", "/api/settings", patch, (r) => { page.s = r; rekord.refresh(); if (!quiet) page.app.toast("Gespeichert") })
    }
    function provPatch(obj) { const p = {}; p[prov] = obj; save({ llm: p }) }
    function opts(list) { return list.map(x => ({ value: x[0], label: x[1] })) }
    function gb(n) { return (n || 0).toLocaleString(Qt.locale("de_AT"), "f", 1) + " GB" }
    function jump(key) {
        const item = { look: secLook, audio: secAudio, ai: secAi, asr: secAsr, spk: secSpk, models: secModels, pair: secPair, int: secInt, data: secData }[key]
        if (item) flick.contentY = Math.max(0, Math.min(item.y - 8, flick.contentHeight - flick.height))
    }
    onShownChanged: {
        if (shown) { load(); if (app.settingsSection) Qt.callLater(() => jump(app.settingsSection)) }
        else if (micTest) { voice.discard(); micTest = false }
    }
    Timer { running: page.shown && page.models.some(m => m.progress && ["downloading", "extracting"].indexOf(m.progress.state) >= 0); interval: 1500; repeat: true; onTriggered: page.loadModels() }
    Timer {  // the pairing code renews itself every 10 minutes
        id: codeTick
        running: page.shown && page.pair !== null
        interval: 1000; repeat: true
        property int left: 0
        onTriggered: { left = Math.max(0, Math.round(page.pair.code.expires - Date.now() / 1000)); if (left <= 0) page.loadPair() }
    }

    DrivePicker { id: picker; app: page.app }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 36
        anchors.bottomMargin: 0
        spacing: 14
        Title { text: "Einstellungen" }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: page.sections
                delegate: Btn { required property var modelData; small: true; text: modelData[1]; onClicked: page.jump(modelData[0]) }
            }
        }

        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentHeight: col.implicitHeight + 40
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            Behavior on contentY { NumberAnimation { duration: Theme.mid; easing.type: Easing.OutCubic } }

            ColumnLayout {
                id: col
                width: Math.min(flick.width - 16, 980)
                spacing: 28
                visible: page.s !== null

                // ================================================================ Darstellung
                Section {
                    id: secLook
                    title: "Darstellung"
                    badge: "dieses Gerät"
                    Field {
                        label: "Erscheinungsbild"; tip: "theme"
                        Segmented {
                            Layout.maximumWidth: 420
                            Layout.fillWidth: true
                            model: [{ value: "system", label: "System" }, { value: "light", label: "Hell" }, { value: "dark", label: "Dunkel" }]
                            value: rekord.theme
                            onPicked: (v) => rekord.setTheme(v)
                        }
                    }
                    Field {
                        label: "Akzentfarbe"; tip: "accent"; hint: "Knöpfe, Markierungen, Fortschritt."
                        Flow {
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: page.accents
                                delegate: Rectangle {
                                    required property var modelData
                                    width: 32; height: 32; radius: 16
                                    color: modelData[0]
                                    border.width: rekord.accent.toUpperCase() === modelData[0] ? 3 : 1
                                    border.color: rekord.accent.toUpperCase() === modelData[0] ? Theme.fg : Theme.line
                                    ToolTip.visible: accHover.hovered
                                    ToolTip.text: modelData[1]
                                    HoverHandler { id: accHover; cursorShape: Qt.PointingHandCursor }
                                    TapHandler { onTapped: rekord.setAccent(modelData[0]) }
                                }
                            }
                            Input { width: 110; placeholderText: "#RRGGBB"; text: rekord.accent; onEditingFinished: rekord.setAccent(text.trim()) }
                        }
                    }
                }

                // ================================================================ Audio
                Section {
                    id: secAudio
                    title: "Audio & Mikrofon"
                    badge: "dieses Gerät"
                    Field {
                        label: "Mikrofon"; tip: "mic"; hint: "USB-Mikro, Headset, Konferenz-Speaker, AirPods …"
                        Select {
                            Layout.fillWidth: true
                            Layout.maximumWidth: 460
                            options: [{ value: "", label: "Standard-Mikrofon des Systems" }].concat(live.mics.map(m => ({ value: m.id, label: m.name })))
                            value: live.mic
                            onPicked: (v) => { live.setMic(v); if (page.micTest) { voice.discard(); voice.start(600) } }
                            Component.onCompleted: live.refreshMics()
                        }
                        RowLayout {
                            Btn {
                                small: true
                                text: page.micTest ? "Stopp" : "Pegel testen"
                                onClicked: { if (page.micTest) { voice.discard(); page.micTest = false } else { voice.start(600); page.micTest = true } }
                            }
                            Tip { key: "mictest" }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.maximumWidth: 300
                                height: 10; radius: 5
                                color: Theme.card2
                                Rectangle { height: parent.height; radius: 5; width: parent.width * (page.micTest ? voice.level : 0); color: Theme.accent; Behavior on width { NumberAnimation { duration: 80 } } }
                            }
                        }
                    }
                    Field {
                        label: "Mitschrift während der Aufnahme"; tip: "liveDetect"; hint: "Aus = nur zeigen, wer spricht – die Texte kommen danach. Spart Rechenleistung."
                        Check { text: "Live mitschreiben"; checked: page.s ? page.s.live_transcribe !== false : true; onToggled: page.save({ live_transcribe: checked }) }
                    }
                    Field {
                        label: "Computer wach halten"; tip: "wakeLock"; hint: "Während einer Aufnahme geht der Computer nicht in den Ruhezustand."
                        Check { text: "Während der Aufnahme nicht einschlafen"; checked: rekord.pref("keep_awake") !== false; onToggled: rekord.setPref("keep_awake", checked) }
                    }
                }

                // ================================================================ KI
                Section {
                    id: secAi
                    title: "KI"
                    tip: "provider"
                    Flow {
                        id: provs
                        Layout.fillWidth: true
                        spacing: 10
                        Repeater {
                            model: [["anthropic", "Claude", "Anthropic API"], ["openai", "ChatGPT", "OpenAI API"], ["ollama", "Lokal", "Ollama – nichts verlässt den PC"],
                                    ["compatible", "Kompatibel", "LM Studio, llama.cpp, OpenRouter …"], ["none", "Aus", "Nur Transkription"]]
                            delegate: AbstractButton {
                                id: pb
                                required property var modelData
                                width: Math.max(150, Math.floor((provs.width - 40) / 5)); height: 72
                                hoverEnabled: true
                                readonly property bool on: page.prov === modelData[0]
                                onClicked: page.save({ llm: { provider: modelData[0] } })
                                background: Rectangle {
                                    radius: 12
                                    color: pb.on ? Theme.fg : pb.hovered ? Theme.card2 : Theme.bg
                                    border.width: 1
                                    border.color: pb.on ? Theme.fg : Theme.line
                                }
                                contentItem: ColumnLayout {
                                    spacing: 2
                                    Text { Layout.leftMargin: 14; Layout.topMargin: 12; text: pb.modelData[1]; font.family: Theme.text; font.pixelSize: 15; font.weight: Font.Black; color: pb.on ? Theme.bg : Theme.fg }
                                    Text { Layout.leftMargin: 14; Layout.rightMargin: 10; Layout.fillWidth: true; text: pb.modelData[2]; elide: Text.ElideRight; font.family: Theme.text; font.pixelSize: 12; color: pb.on ? Theme.bg : Theme.fg3 }
                                    Item { Layout.fillHeight: true }
                                }
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                    }
                    Field {
                        visible: page.prov === "anthropic" || page.prov === "openai" || page.prov === "compatible"
                        label: "API-Key"; tip: "apikey"
                        hint: page.prov === "anthropic" ? "Auf „Key erstellen“ klicken, Key kopieren, hier einfügen – REKORD testet sofort."
                            : page.prov === "openai" ? "Achtung: ChatGPT-Plus-Abo ≠ API-Guthaben." : "Nur falls der Server einen verlangt."
                        RowLayout {
                            Layout.fillWidth: true
                            Input {
                                id: keyF
                                Layout.fillWidth: true
                                echoMode: TextInput.Password
                                placeholderText: page.pc.has_key ? page.pc.api_key : "Key hier einfügen"
                                onEditingFinished: if (text.trim()) {
                                    const k = text.trim(); text = ""
                                    page.provPatch({ api_key: k })
                                    page.app.toast("Key gespeichert – teste …")
                                    testTimer.start()
                                }
                            }
                            Btn {
                                visible: page.prov !== "compatible"
                                small: true; text: "Key erstellen"; iconName: "open"
                                onClicked: api.openUrl(page.prov === "anthropic" ? "https://console.anthropic.com/settings/keys" : "https://platform.openai.com/api-keys")
                            }
                        }
                    }
                    Field {
                        visible: page.prov === "compatible"
                        label: "Server-Adresse"; tip: "serverurl"; hint: "LM Studio: http://localhost:1234/v1 · llama.cpp: http://localhost:8080/v1 · OpenRouter: https://openrouter.ai/api/v1"
                        Input { Layout.fillWidth: true; text: page.pc.base_url || ""; onEditingFinished: if (text.trim() !== (page.pc.base_url || "")) page.provPatch({ base_url: text.trim() }) }
                    }
                    Field {
                        visible: page.prov === "anthropic" || page.prov === "openai" || page.prov === "compatible"
                        label: "Modell"; tip: "model"
                        hint: page.prov === "anthropic" ? "claude-opus-5-5 = beste Qualität, claude-haiku-5-5 = günstig & schnell." : "„Laden“ zeigt alle Modelle."
                        RowLayout {
                            Layout.fillWidth: true
                            NameField {
                                id: modelF
                                Layout.fillWidth: true
                                placeholder: "Modell"
                                text: page.pc.model || ""
                                names: []
                                onAccepted: if (text.trim() !== (page.pc.model || "")) page.provPatch({ model: text.trim() })
                            }
                            Btn {
                                small: true; text: "Laden"
                                onClicked: page.app.call("GET", "/api/llm/models?provider=" + page.prov, null, (r) => {
                                    if (r.error) page.app.toast(r.error)
                                    modelF.names = r.models
                                    page.app.toast(r.models.length + " Modelle gefunden – ▾ zum Auswählen")
                                })
                            }
                            Btn { small: true; text: "Übernehmen"; onClicked: page.provPatch({ model: modelF.text.trim() }) }
                        }
                    }
                    Field {
                        visible: page.prov === "anthropic"
                        label: "Denkaufwand"; tip: "effort"; hint: "Höher = gründlicher, langsamer, teurer."
                        Select {
                            Layout.maximumWidth: 240
                            options: ["low", "medium", "high", "xhigh", "max"].map(e => ({ value: e, label: e }))
                            value: page.pc.effort || "medium"
                            onPicked: (v) => page.provPatch({ effort: v })
                        }
                    }
                    Field {
                        visible: page.prov === "anthropic"
                        label: "Ausweichmodell"; tip: "fallback"; hint: "Lehnt das Modell ab, springt automatisch ein anderes Claude-Modell ein."
                        Check { text: "Aktiv"; checked: !!page.pc.fallbacks; onToggled: page.provPatch({ fallbacks: checked }) }
                    }
                    Field {
                        visible: page.prov === "ollama"
                        label: "Lokales Modell"; tip: "localmodel"; hint: "Läuft komplett auf diesem Computer, gratis."
                        OllamaPanel {
                            id: ollama
                            Layout.fillWidth: true
                            app: page.app
                            visible: page.prov === "ollama" && page.shown
                            model: page.s ? page.s.llm.ollama.model || "" : ""
                            onModelChosen: (m) => { page.app.call("GET", "/api/settings", null, (r) => page.s = r) }
                            onVisibleChanged: if (visible) load()
                        }
                    }
                    Field {
                        visible: page.prov === "ollama"
                        label: "Ollama-Adresse"; tip: "ollamaurl"; hint: "Nur ändern, wenn Ollama auf einem anderen Rechner läuft."
                        Input { Layout.fillWidth: true; text: page.pc.base_url || "http://localhost:11434"; onEditingFinished: if (text.trim() !== (page.pc.base_url || "")) page.provPatch({ base_url: text.trim() }) }
                    }
                    Field {
                        visible: page.prov === "ollama" || page.prov === "compatible"
                        label: "Kontextlänge"; tip: "context"; hint: page.prov === "ollama" ? "Mehr = längere Meetings am Stück, braucht mehr RAM." : "Was dein Server maximal verarbeitet."
                        Select {
                            Layout.maximumWidth: 240
                            options: [8192, 16384, 32768, 65536, 131072].map(n => ({ value: n, label: n.toLocaleString(Qt.locale("de_AT"), "f", 0) + " Tokens" }))
                            value: page.prov === "ollama" ? (page.pc.num_ctx || 32768) : (page.pc.context_tokens || 32768)
                            onPicked: (v) => page.provPatch(page.prov === "ollama" ? { num_ctx: v } : { context_tokens: v })
                        }
                    }
                    Field {
                        visible: page.prov !== "none" && page.prov !== ""
                        label: "Verbindung"; tip: "connection"; hint: "Prüft, ob die KI antwortet."
                        RowLayout {
                            Layout.fillWidth: true
                            Btn { id: testBtn; text: "Testen"; onClicked: page.testAi() }
                            Text { id: testRes; Layout.fillWidth: true; wrapMode: Text.WordWrap; textFormat: Text.StyledText; font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2 }
                        }
                    }
                    Field {
                        label: "Sprache der Zusammenfassungen"; tip: "sumlang"
                        Select {
                            Layout.maximumWidth: 260
                            options: page.opts([["de", "Deutsch"], ["en", "Englisch"], ["auto", "Wie im Gespräch"]])
                            value: page.s ? page.s.summary_language : "de"
                            onPicked: (v) => page.save({ summary_language: v })
                        }
                    }
                    Field {
                        label: "Automatisch zusammenfassen"; tip: "autosum"; hint: "Nach jeder Aufnahme, mit dieser Vorlage."
                        Check { text: "Aktiv"; checked: page.s ? page.s.auto_summary : false; onToggled: page.save({ auto_summary: checked }) }
                        Select {
                            Layout.maximumWidth: 360
                            Layout.fillWidth: true
                            options: page.templates.filter(t => t.id !== "mindmap").map(t => ({ value: t.id, label: t.name }))
                            value: page.s ? page.s.default_template : "auto"
                            onPicked: (v) => page.save({ default_template: v })
                        }
                    }
                }

                // ================================================================ Transkription
                Section {
                    id: secAsr
                    title: "Transkription"
                    Field {
                        label: "Sprache"; tip: "lang"; hint: "Fest einstellen = genauer. Auto erkennt pro Satz (gemischte Meetings)."
                        Select { Layout.maximumWidth: 300; options: page.opts(page.langs); value: page.s ? page.s.language : ""; onPicked: (v) => page.save({ language: v }) }
                    }
                    Field {
                        label: "Engine"; tip: "engine"; hint: "Was Sprache in Text verwandelt."
                        Select {
                            Layout.maximumWidth: 420
                            Layout.fillWidth: true
                            options: [{ value: "sherpa", label: "Whisper ONNX (überall, CPU)" },
                                      { value: "faster-whisper", label: "faster-whisper (GPU/CUDA, Wortzeiten)" + (page.st && page.st.faster_whisper ? "" : " – nicht installiert") }]
                            value: page.s ? page.s.asr_engine : "sherpa"
                            onPicked: (v) => page.save({ asr_engine: v })
                        }
                    }
                    Field {
                        label: "Modell"; tip: "asrmodel"; hint: "turbo = beste Qualität pro Sekunde. small = Laptop-Standard."
                        Select {
                            Layout.maximumWidth: 420
                            Layout.fillWidth: true
                            options: page.s && page.s.asr_engine === "faster-whisper"
                                     ? ["large-v3-turbo", "large-v3", "distil-large-v3", "medium", "small", "base"].map(m => ({ value: m, label: m }))
                                     : page.models.filter(m => m.kind === "asr").map(m => ({ value: m.id, label: m.name + " · " + m.size_mb + " MB" + (m.installed ? " ✓" : " (wird geladen)") }))
                            value: page.s ? (page.s.asr_engine === "faster-whisper" ? page.s.faster_whisper_model : page.s.asr_model) : ""
                            onPicked: (v) => {
                                if (page.s.asr_engine === "faster-whisper") { page.save({ faster_whisper_model: v }); return }
                                page.save({ asr_model: v })
                                const m = page.models.find(x => x.id === v)
                                if (m && !m.installed) page.app.call("POST", "/api/models/" + v + "/download", null, () => { page.app.toast(m.name + " wird geladen …"); page.loadModels() })
                            }
                        }
                    }
                    Field {
                        label: "CPU-Threads"; tip: "threads"; hint: "Mehr = schneller, Computer stärker ausgelastet."
                        SpinBox {
                            from: 1; to: 32
                            value: page.s ? page.s.threads : 4
                            editable: true
                            onValueModified: page.save({ threads: value })
                        }
                    }
                    Field {
                        label: "Vokabular"; tip: "vocab"; hint: "Namen & Fachbegriffe, die falsch erkannt werden. „Beni“ → „Beeni“."
                        Repeater {
                            id: vocab
                            model: page.s ? page.s.vocabulary : []
                            delegate: RowLayout {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                Input { Layout.fillWidth: true; text: modelData.from; placeholderText: "erkannt als"; onEditingFinished: page.setVocab(index, "from", text) }
                                Text { text: "→"; color: Theme.fg3; font.pixelSize: 16 }
                                Input { Layout.fillWidth: true; text: modelData.to; placeholderText: "richtig"; onEditingFinished: page.setVocab(index, "to", text) }
                                Btn { kind: "ghost"; small: true; iconName: "close"; onClicked: { const v = page.s.vocabulary.slice(); v.splice(index, 1); page.save({ vocabulary: v }) } }
                            }
                        }
                        Muted { visible: !page.s || page.s.vocabulary.length === 0; text: "Noch nichts." }
                        Btn { small: true; iconName: "plus"; text: "Begriff"; onClicked: { const r = Object.assign({}, page.s); r.vocabulary = page.s.vocabulary.concat([{ from: "", to: "" }]); page.s = r } }
                    }
                }

                // ================================================================ Sprecher-Erkennung
                Section {
                    id: secSpk
                    title: "Sprecher-Erkennung"
                    Repeater {
                        model: [["profile_threshold", "Personen-Erkennung (Aufnahmen)", "pthr", "Höher = strenger, weniger Verwechslungen. Standard 0.55.", 0.3, 0.9],
                                ["live_profile_threshold", "Personen-Erkennung (live)", "lthr", "Live-Ausschnitte sind kurz – etwas lockerer. Standard 0.50.", 0.3, 0.9],
                                ["cluster_threshold", "Sprecher trennen", "cthr", "Höher = mehr unterschiedliche Sprecher. Wenn eine Person doppelt erscheint: runter.", 0.3, 0.95]]
                        delegate: Field {
                            required property var modelData
                            label: modelData[1]; tip: modelData[2]; hint: modelData[3]
                            RowLayout {
                                Layout.fillWidth: true
                                Slider {
                                    id: sl
                                    Layout.fillWidth: true
                                    Layout.maximumWidth: 360
                                    from: modelData[4]; to: modelData[5]; stepSize: 0.01
                                    value: page.s ? page.s[modelData[0]] : 0.5
                                    onMoved: thrSave.restart()
                                    Timer { id: thrSave; interval: 400; onTriggered: { const p = {}; p[modelData[0]] = Math.round(sl.value * 100) / 100; page.save(p, true) } }
                                }
                                Text { text: sl.value.toFixed(2); font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg; font.features: ({ "tnum": 1 }) }
                            }
                        }
                    }
                    Field {
                        label: "Anzahl Sprecher"; tip: "nspk"; hint: "Für Importe. Live fragt REKORD jedes Mal."
                        Select {
                            Layout.maximumWidth: 240
                            options: [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12].map(n => ({ value: n, label: n ? n + " Personen" : "Automatisch" }))
                            value: page.s ? page.s.num_speakers : 0
                            onPicked: (v) => page.save({ num_speakers: v })
                        }
                    }
                    Field {
                        label: "Stimmabdruck-Modell"; tip: "embm"; hint: "Wechsel macht bestehende Stimmprofile unbrauchbar."
                        Select {
                            id: embm
                            Layout.maximumWidth: 300
                            options: ["eres2net-base", "campplus", "wespeaker-resnet34"].map(m => ({ value: m, label: m }))
                            value: page.s ? page.s.embedding_model : ""
                            onPicked: (v) => {
                                const old = page.s.embedding_model
                                embm.value = old
                                page.app.confirm("Modell wechseln?", "Gespeicherte Stimmprofile passen dann nicht mehr und müssen neu angelernt werden.", "Wechseln", () => {
                                    page.save({ embedding_model: v })
                                    page.app.call("POST", "/api/models/" + v + "/download", null, () => page.loadModels())
                                })
                            }
                        }
                    }
                }

                // ================================================================ Modelle
                Section {
                    id: secModels
                    title: "Modelle"
                    tip: "models"
                    Repeater {
                        model: page.models
                        delegate: ColumnLayout {
                            id: mr
                            required property var modelData
                            readonly property var p: modelData.progress || ({})
                            readonly property bool dl: p.state === "downloading" || p.state === "extracting"
                            Layout.fillWidth: true
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                Text { text: mr.modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                                Text { text: ({ asr: "Spracherkennung", segmentation: "Sprecherwechsel", embedding: "Stimmabdruck", vad: "Sprach-Erkennung" })[mr.modelData.kind] || ""; font.pixelSize: 12; color: Theme.fg3 }
                                Muted { text: mr.modelData.size_mb + " MB"; font.pixelSize: 12 }
                                Item { Layout.fillWidth: true }
                                Text { visible: mr.modelData.installed; text: "installiert"; font.pixelSize: 12; color: Theme.ok; font.weight: Font.Bold }
                                Btn {
                                    visible: mr.modelData.installed; kind: "ghost"; small: true; text: "Entfernen"
                                    onClicked: page.app.confirm("Modell entfernen?", mr.modelData.name, "Entfernen", () => page.app.call("DELETE", "/api/models/" + mr.modelData.id, null, () => page.loadModels()))
                                }
                                Text { visible: mr.dl; text: mr.p.state === "extracting" ? "entpacke …" : Math.round(mr.p.done / (mr.p.total || 1) * 100) + " %"; font.pixelSize: 12; color: Theme.fg2 }
                                Btn { visible: !mr.modelData.installed && !mr.dl; small: true; text: "Laden"; iconName: "download"; onClicked: page.app.call("POST", "/api/models/" + mr.modelData.id + "/download", null, () => page.loadModels()) }
                            }
                            Muted { Layout.fillWidth: true; font.pixelSize: 12; text: mr.modelData.description + (mr.p.state === "error" ? " · " + mr.p.error : "") }
                            Bar { visible: mr.dl; Layout.fillWidth: true; value: mr.p.state === "extracting" ? 1 : mr.p.done / (mr.p.total || 1) }
                        }
                    }
                }

                // ================================================================ iPhone
                Section {
                    id: secPair
                    title: "iPhone & Geräte"
                    tip: "qr"
                    Muted {
                        visible: page.pair !== null && !page.pair.lan
                        Layout.fillWidth: true
                        text: "REKORD ist gerade nur auf diesem Computer erreichbar. Starte REKORD über die App (Mac/Windows/Linux), dann ist es automatisch im WLAN sichtbar. Im Terminal: rekord serve --host 0.0.0.0"
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 24
                        QrView { rows: page.pair ? page.pair.qr_rows : []; Layout.preferredWidth: 220; Layout.preferredHeight: 220 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text { text: "REKORD-App am iPhone"; font.family: Theme.text; font.pixelSize: 16; font.weight: Font.Black; color: Theme.fg }
                            Muted { Layout.fillWidth: true; text: "In der App „Koppeln“ → QR-Code scannen – oder den 6-stelligen Code eintippen. Danach nimmst du am iPhone auf und siehst live, wer spricht." }
                            RowLayout {
                                spacing: 12
                                Text {
                                    text: page.pair ? page.pair.code.code.slice(0, 3) + " " + page.pair.code.code.slice(3) : ""
                                    font.family: Theme.display; font.pixelSize: 40; font.weight: Font.Black; font.letterSpacing: 4; font.features: ({ "tnum": 1 })
                                    color: Theme.fg
                                }
                                Tip { key: "paircode" }
                            }
                            RowLayout {
                                Muted { text: "noch " + Math.floor(codeTick.left / 60) + ":" + (codeTick.left % 60 < 10 ? "0" : "") + codeTick.left % 60; font.pixelSize: 13 }
                                Btn { small: true; text: "Neuer Code"; iconName: "refresh"; onClicked: page.app.call("POST", "/api/pair/code", null, () => page.loadPair()) }
                            }
                        }
                    }
                    Field {
                        visible: page.integ !== null && !!page.integ.firewall.tool && page.integ.firewall.open !== true
                        label: "Firewall"; tip: "firewall"; hint: page.integ ? "Die " + page.integ.firewall.tool + "-Firewall dieses Computers blockiert das iPhone." : ""
                        RowLayout {
                            Btn {
                                kind: "primary"; text: "Für iPhone freigeben"
                                onClicked: { enabled = false; fwRes.text = "Passwort-Fenster beachten …"; page.app.call("POST", "/api/integrations/firewall", null, (r) => { fwRes.text = "✓ " + r.message; fwRes.color = Theme.ok }, (e) => { fwRes.text = "✗ " + e; fwRes.color = Theme.err; enabled = true }) }
                            }
                            Text { id: fwRes; font.pixelSize: 13; color: Theme.fg2; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        }
                    }
                    Field {
                        label: "Adresse"; tip: "address"; hint: "Handy und Computer im selben WLAN."
                        Text { text: page.pair && page.pair.urls.length ? page.pair.urls.join("   ") : "–"; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }
                    Field {
                        label: "Gekoppelte Geräte"; tip: "devices"; hint: "Jedes Gerät mit Code hat einen eigenen Schlüssel."
                        Repeater {
                            model: page.pair ? page.pair.devices : []
                            delegate: RowLayout {
                                required property var modelData
                                Icon { name: "phone"; width: 18; height: 18; color: Theme.fg2 }
                                Text { text: modelData.name; font.family: Theme.text; font.pixelSize: 14; font.weight: Font.Bold; color: Theme.fg }
                                Muted { text: "· seit " + new Date(modelData.created * 1000).toLocaleString(Qt.locale("de_AT"), "dd.MM.yyyy"); font.pixelSize: 13 }
                                Btn {
                                    kind: "ghost"; small: true; text: "Trennen"
                                    onClicked: page.app.confirm("Gerät trennen?", "Es muss danach neu gekoppelt werden.", "Trennen", () => page.app.call("DELETE", "/api/pair/devices/" + modelData.id, null, () => page.loadPair()))
                                }
                            }
                        }
                        Muted { visible: !page.pair || page.pair.devices.length === 0; text: "Noch keins – oder per QR-Code gekoppelt." }
                        Btn {
                            kind: "danger"; small: true; text: "Alle Geräte trennen"
                            onClicked: page.app.confirm("Alle Geräte trennen?", "Alle gekoppelten Handys – auch die per QR-Code – müssen neu koppeln. Gut, wenn ein Handy verloren ging.", "Alle trennen",
                                                        () => page.app.call("POST", "/api/settings/rotate-token", null, () => { page.app.toast("Alle Geräte getrennt"); page.loadPair() }))
                        }
                    }
                }

                // ================================================================ Claude Desktop
                Section {
                    id: secInt
                    title: "Claude Desktop (MCP)"
                    Muted {
                        Layout.fillWidth: true
                        text: "Verbinde deine REKORD-Bibliothek direkt mit Claude Desktop oder Claude Code. Claude kann dann alle Transkripte durchsuchen, lesen und Zusammenfassungen zurückspeichern – mit deinem normalen Claude-Abo, ohne API-Key."
                    }
                    Field {
                        label: "Claude Desktop"; tip: "claudedesktop"; hint: "Die App von claude.ai/download."
                        readonly property var cd: page.integ ? page.integ.claude_desktop : null
                        id: cdField
                        Muted { visible: !cdField.cd; text: "prüfe …" }
                        RowLayout {
                            visible: !!cdField.cd
                            Text { visible: cdField.cd && cdField.cd.connected; text: "✓ Verbunden"; color: Theme.ok; font.pixelSize: 14; font.weight: Font.Bold }
                            Btn {
                                visible: cdField.cd && !cdField.cd.connected
                                kind: cdField.cd && cdField.cd.installed ? "primary" : "default"
                                text: "Mit Claude Desktop verbinden"
                                onClicked: page.app.call("POST", "/api/integrations/claude-desktop", null, (r) => {
                                    page.app.toast(r.running ? "Eingetragen – Claude jetzt neu starten." : "Eingetragen – beim nächsten Start von Claude ist REKORD da.")
                                    page.app.call("GET", "/api/integrations", null, (i) => page.integ = i)
                                })
                            }
                            Btn {
                                visible: cdField.cd && cdField.cd.connected && cdField.cd.running
                                small: true; text: "Claude neu starten"
                                onClicked: page.app.call("POST", "/api/integrations/claude-desktop/restart", null, () => page.app.toast("Claude startet neu."))
                            }
                            Btn { visible: cdField.cd && !cdField.cd.installed; small: true; text: "Claude Desktop laden"; iconName: "open"; onClicked: api.openUrl(cdField.cd.download_url) }
                        }
                        Muted { visible: cdField.cd && cdField.cd.connected; font.pixelSize: 12; Layout.fillWidth: true; text: "Claude einmal neu starten, dann im Chat fragen: „Was haben wir im letzten Meeting entschieden?“" }
                    }
                    Field {
                        label: "Claude Code"; tip: "claudecode"; hint: "Claude im Terminal."
                        readonly property var cc: page.integ ? page.integ.claude_code : null
                        id: ccField
                        Text { visible: ccField.cc && ccField.cc.connected; text: "✓ Verbunden"; color: Theme.ok; font.pixelSize: 14; font.weight: Font.Bold }
                        Btn {
                            visible: ccField.cc && !ccField.cc.connected && ccField.cc.installed
                            text: "Mit Claude Code verbinden"
                            onClicked: page.app.call("POST", "/api/integrations/claude-code", null, () => { page.app.toast("Claude Code ist verbunden."); page.app.call("GET", "/api/integrations", null, (i) => page.integ = i) })
                        }
                        Muted { visible: ccField.cc && !ccField.cc.installed; text: "Nicht installiert – brauchst du nur, wenn du Claude im Terminal nutzt." }
                    }
                    Field {
                        label: "Von Hand eintragen"
                        hint: "Claude Desktop → Einstellungen → Entwickler → Konfiguration bearbeiten."
                        readonly property var cmd: page.st && page.st.mcp_command ? page.st.mcp_command : ["python", "-m", "rekord", "mcp"]
                        readonly property string json: JSON.stringify({ mcpServers: { rekord: { command: cmd[0], args: cmd.slice(1), env: { REKORD_HOME: page.st ? page.st.home : "" } } } }, null, 2)
                        id: manual
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: mcpT.implicitHeight + 24
                            radius: 10
                            color: Theme.card2
                            TextEdit { id: mcpT; anchors.fill: parent; anchors.margins: 12; text: manual.json; readOnly: true; selectByMouse: true; wrapMode: TextEdit.WrapAnywhere; font.family: Qt.platform.os === "windows" ? "Consolas" : "Menlo"; font.pixelSize: 12; color: Theme.fg }
                        }
                        RowLayout {
                            Btn { small: true; text: "Kopieren"; iconName: "copy"; onClicked: { api.copyText(manual.json); page.app.toast("Kopiert") } }
                            Btn {
                                small: true; text: "Claude-Code-Befehl kopieren"
                                onClicked: { api.copyText("claude mcp add rekord -e REKORD_HOME=\"" + (page.st ? page.st.home : "") + "\" -- \"" + manual.cmd[0] + "\" " + manual.cmd.slice(1).join(" ")); page.app.toast("Kopiert") }
                            }
                        }
                    }
                }

                // ================================================================ Speicher & Datenschutz
                Section {
                    id: secData
                    title: "Speicher & Datenschutz"
                    Field {
                        label: "Speicherort"; tip: "storage"; hint: "Aufnahmen, Datenbank, Stimmabdrücke. Backup = diesen Ordner kopieren."
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: page.storage ? page.storage.home : ""; elide: Text.ElideMiddle; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg }
                            Btn { small: true; text: "Öffnen"; onClicked: api.reveal(page.storage.home) }
                            Btn {
                                visible: page.storage && !page.storage.env_locked
                                small: true; text: "Ändern …"
                                onClicked: picker.ask("home", "Speicherort ändern", (t) => page.app.call("POST", "/api/storage/move", { what: "home", target: t }, () => homeJob.active = true))
                            }
                        }
                        Muted { font.pixelSize: 12; text: page.storage ? (page.storage.home_free_gb !== null ? page.gb(page.storage.home_free_gb) + " frei" : "") : "" }
                        StorageJob { id: homeJob; Layout.fillWidth: true; app: page.app; onFinished: page.loadStorage() }
                    }
                    Field {
                        label: "KI-Modelle"; tip: "modelsdir"; hint: "Sprachmodelle und lokale KI – gern auf einem anderen Laufwerk."
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: page.storage ? page.storage.models : ""; elide: Text.ElideMiddle; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg }
                            Btn {
                                visible: page.storage && !page.storage.env_locked
                                small: true; text: "Ändern …"
                                onClicked: picker.ask("models", "KI-Modelle speichern auf …", (t, withOll) => page.app.call("POST", "/api/storage/move", { what: "models", target: t, ollama: withOll }, () => modelsJob.active = true))
                            }
                        }
                        Muted { font.pixelSize: 12; Layout.fillWidth: true; text: page.storage ? (page.storage.models_free_gb !== null ? page.gb(page.storage.models_free_gb) + " frei · " : "") + "Lokale KI: " + page.storage.ollama_models : "" }
                        StorageJob { id: modelsJob; Layout.fillWidth: true; app: page.app; onFinished: page.loadStorage() }
                    }
                    Field {
                        label: "Eingangsordner"; tip: "inbox"; hint: "Dateien, die hier landen, werden automatisch verarbeitet – z. B. per iCloud/Dropbox-Sync vom Handy oder Diktiergerät."
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: page.st ? page.st.inbox : ""; elide: Text.ElideMiddle; font.family: Theme.text; font.pixelSize: 14; color: Theme.fg }
                            Btn { small: true; text: "Öffnen"; onClicked: api.reveal(page.st.inbox) }
                        }
                        Check { text: "Überwachen"; checked: page.s ? page.s.inbox_enabled : true; onToggled: page.save({ inbox_enabled: checked }) }
                    }
                    Field {
                        label: "Was verlässt das Gerät?"; tip: "privacy"
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            textFormat: Text.StyledText
                            font.family: Theme.text; font.pixelSize: 13; color: Theme.fg2
                            text: "Audio, Transkription, Sprecher-Erkennung: <b>nie</b>. Für Zusammenfassungen geht nur der <b>Text</b> an die gewählte KI – bei Ollama/LM Studio auch das nicht. Keine Telemetrie, kein Konto. Die Update-Suche fragt GitHub nur nach der neuesten Versionsnummer."
                        }
                    }
                    Field {
                        label: "Mit dem Computer starten"; tip: "autostart"; hint: "REKORD läuft dann ab dem Einschalten im Hintergrund – das iPhone kann sich jederzeit verbinden."
                        readonly property var a: page.integ ? page.integ.autostart : null
                        id: autoField
                        Check {
                            visible: autoField.a && autoField.a.supported
                            text: "Aktiv"
                            checked: autoField.a ? autoField.a.enabled : false
                            onToggled: page.app.call("POST", "/api/integrations/autostart", { enabled: checked }, (r) => {
                                checked = r.enabled
                                page.app.toast(r.enabled ? "Startet ab jetzt mit dem Computer" : "Startet nicht mehr automatisch")
                            }, (e) => { page.app.toast(e); checked = !checked })
                        }
                        Muted { visible: autoField.a && !autoField.a.supported; text: autoField.a ? autoField.a.reason : "" }
                    }
                    Field {
                        label: "Hilfe"; tip: "help"; hint: "Jeder Punkt hat ein ⓘ – drüberfahren oder antippen."
                        RowLayout {
                            Btn { small: true; text: "Einführung starten"; onClicked: page.app.welcome(true) }
                            Btn { small: true; text: "Anleitung"; iconName: "open"; onClicked: api.openUrl("https://github.com/KimJongUnNK/rekord/blob/main/docs/ANLEITUNG.md") }
                        }
                    }
                    Field {
                        label: "Version & Updates"; tip: "version"; hint: "Ein Update ersetzt die installierte App und startet sie neu – Aufnahmen und Einstellungen bleiben."
                        UpdatePanel { Layout.fillWidth: true; app: page.app }
                        RowLayout { Check { text: "Automatisch nach Updates suchen"; checked: page.s ? page.s.update_check !== false : true; onToggled: page.save({ update_check: checked }) } Tip { key: "updatecheck" } }
                    }
                    Field {
                        label: "Beenden"; tip: "quit"; hint: "Stoppt REKORD auf diesem Computer (auch im Hintergrund)."
                        Btn {
                            kind: "danger"; iconName: "power"; text: "REKORD beenden"
                            onClicked: page.app.confirm("REKORD beenden?", "Laufende Verarbeitungen werden beim nächsten Start fortgesetzt.", "Beenden", () => page.app.quitApp())
                        }
                    }
                }
            }
        }
    }

    function setVocab(i, key, value) {
        const v = s.vocabulary.map(x => Object.assign({}, x))
        if (v[i][key] === value) return
        v[i][key] = value
        save({ vocabulary: v.filter(x => x.from || x.to) })
    }
    function testAi() {
        testRes.text = "teste …"
        testRes.color = Theme.fg2
        app.call("POST", "/api/llm/test", null, (r) => {
            testRes.text = r.ok ? "<font color='" + Theme.ok + "'>✓ verbunden</font> · „" + r.reply + "“ · " + r.ms + " ms" : "<font color='" + Theme.err + "'>✗ " + r.error + "</font>"
            rekord.refresh()
        })
    }
    Timer { id: testTimer; interval: 300; onTriggered: page.testAi() }
}
