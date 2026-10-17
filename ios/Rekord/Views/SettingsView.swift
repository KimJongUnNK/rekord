import AVFoundation
import Network
import SwiftUI
import VisionKit

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var hub: HubClient
    @State private var inputs: [AVAudioSessionPortDescription] = []
    @State private var ai: [String: Any] = [:]
    @State private var provider = "anthropic"
    @State private var model = ""
    @State private var apiKey = ""
    @State private var baseURL = ""
    @State private var testResult: String?
    @State private var customColor = Color.orange

    private let providers: [(String, String)] = [("anthropic", "Claude"), ("openai", "ChatGPT"), ("ollama", "Lokal (Ollama)"),
                                                 ("compatible", "OpenAI-kompatibel"), ("none", "Aus")]

    var body: some View {
        NavigationStack {
            Form {
                Section("Darstellung") {
                    Picker("Erscheinungsbild", selection: $settings.theme) {
                        Text("System").tag("system"); Text("Hell").tag("light"); Text("Dunkel").tag("dark")
                    }
                    .pickerStyle(.segmented)
                    VStack(alignment: .leading) {
                        Text("Akzentfarbe")
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 12) {
                                ForEach(AppSettings.accents, id: \.0) { hex, name in
                                    Circle().fill(Color(hex: hex)).frame(width: 34, height: 34)
                                        .overlay(Circle().stroke(Color.primary, lineWidth: settings.accentHex.lowercased() == hex.lowercased() ? 3 : 0).padding(-4))
                                        .onTapGesture { settings.accentHex = hex }
                                        .accessibilityLabel(name)
                                }
                                ColorPicker("", selection: $customColor, supportsOpacity: false).labelsHidden()
                                    .onChange(of: customColor) { _, c in settings.accentHex = c.hexString }
                            }
                            .padding(6)
                        }
                    }
                }

                Section {
                    Picker("Mikrofon", selection: $settings.preferredInputUID) {
                        Text("Automatisch").tag("")
                        ForEach(inputs, id: \.uid) { Text($0.portName).tag($0.uid) }
                    }
                    Toggle("Echo- & Rauschunterdrückung", isOn: $settings.voiceProcessing)
                    Toggle("Live zeigen, wer spricht", isOn: $settings.liveDetect)
                    Toggle("Bildschirm wach halten", isOn: $settings.keepAwake)
                    Toggle("Vibration bei Sprecherwechsel", isOn: $settings.hapticOnSpeaker)
                } header: { Text("Audio") } footer: {
                    Text("Unterdrückung aus = Rohsignal, besser mit gutem externem Mikro. Live aus = nur aufnehmen, Auswertung danach (spart Akku).")
                }

                Section {
                    Picker("Anbieter", selection: $provider) { ForEach(providers, id: \.0) { Text($0.1).tag($0.0) } }
                        .onChange(of: provider) { _, p in Task { await push(["provider": p]); await loadAI() } }
                    if provider == "anthropic" || provider == "openai" || provider == "compatible" {
                        SecureField(keyPlaceholder, text: $apiKey).onSubmit { Task { await push([provider: ["api_key": apiKey]]); apiKey = ""; await loadAI() } }
                    }
                    if provider == "ollama" || provider == "compatible" {
                        TextField("Server-Adresse", text: $baseURL).textInputAutocapitalization(.never).keyboardType(.URL)
                            .onSubmit { Task { await push([provider: ["base_url": baseURL]]) } }
                    }
                    if provider != "none" {
                        TextField("Modell", text: $model).textInputAutocapitalization(.never)
                            .onSubmit { Task { await push([provider: ["model": model]]) } }
                        Button("Verbindung testen") { Task { await test() } }
                        if let testResult { Text(testResult).font(.footnote) }
                    }
                } header: { Text("KI (läuft über deinen Hub)") } footer: {
                    Text("Claude/ChatGPT brauchen einen API-Key (Abo ≠ API). „Lokal“ nutzt Ollama auf deinem Computer – dann verlässt nichts dein Netzwerk.")
                }

                Section("Hub") {
                    LabeledContent("Adresse", value: settings.hubURL)
                    LabeledContent("Status", value: hub.reachable ? "verbunden · v\(hub.status?.version ?? "")" : "nicht erreichbar")
                    if let s = hub.status { LabeledContent("KI", value: (s.provider_name ?? s.provider) + (s.model.map { " · \($0)" } ?? "")) }
                    Button("Neu koppeln", role: .destructive) { settings.hubURL = ""; settings.hubToken = "" }
                }

                Section("Sperrbildschirm & Steuerung") {
                    Text("• Sperrbildschirm bearbeiten → Widgets → REKORD (Start-Knopf & Status)\n• Kontrollzentrum / Sperrbildschirm-Steuerelemente → „REKORD Aufnahme“\n• Action Button → Kurzbefehl „REKORD Aufnahme starten“\n• Während der Aufnahme: Live Activity mit aktuellem Sprecher, ★-Markieren & Stopp")
                        .font(.footnote)
                }
            }
            .navigationTitle("Einstellungen")
            .task { inputs = settings.availableInputs; customColor = Color(hex: settings.accentHex); await hub.refreshStatus(); await loadAI() }
        }
    }

    private var keyPlaceholder: String {
        let llm = ai["llm"] as? [String: Any]
        let cfg = llm?[provider] as? [String: Any]
        return (cfg?["has_key"] as? Bool ?? false) ? "API-Key gespeichert (\(cfg?["api_key"] as? String ?? ""))" : "API-Key"
    }

    private func loadAI() async {
        guard let d = try? await hub.send("/api/settings", method: "GET"),
              let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return }
        ai = obj
        let llm = obj["llm"] as? [String: Any] ?? [:]
        provider = llm["provider"] as? String ?? "none"
        let cfg = llm[provider] as? [String: Any] ?? [:]
        model = cfg["model"] as? String ?? ""
        baseURL = cfg["base_url"] as? String ?? ""
    }

    private func push(_ llm: [String: Any]) async {
        _ = try? await hub.send("/api/settings", method: "PUT", json: ["llm": llm])
        await hub.refreshStatus()
    }

    private func test() async {
        testResult = "teste …"
        guard let d = try? await hub.send("/api/llm/test"), let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else {
            testResult = "Hub nicht erreichbar"; return
        }
        testResult = (o["ok"] as? Bool ?? false) ? "✓ verbunden (\(o["ms"] ?? "") ms)" : "✗ \(o["error"] ?? "")"
    }
}

extension Color {
    var hexString: String {
        let c = UIColor(self).resolvedColor(with: .current)
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        c.getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02X%02X%02X", Int(r * 255), Int(g * 255), Int(b * 255))
    }
}

// MARK: - Pairing

struct PairingView: View {
    @EnvironmentObject var hub: HubClient
    @State private var scanning = false
    @State private var manualURL = ""
    @State private var manualToken = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("REKORD").font(.system(size: 54, weight: .black)) + Text(".").font(.system(size: 54, weight: .black)).foregroundColor(.accentColor)
                    Text("Lokaler KI-Rekorder. Dein Computer rechnet, dein iPhone nimmt auf und zeigt live, wer spricht.")
                        .font(.title3.weight(.medium)).foregroundStyle(.secondary)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("1. REKORD am Mac/PC öffnen (gleiches WLAN)").font(.subheadline)
                        Text("2. Einstellungen → iPhone & Geräte → QR-Code").font(.subheadline)
                        Text("3. Hier scannen").font(.subheadline)
                    }
                    Button { scanning = true } label: {
                        Label("QR-Code scannen", systemImage: "qrcode.viewfinder").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 8)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!DataScannerViewController.isSupported)

                    if !hub.discovered.isEmpty {
                        Text("IM WLAN GEFUNDEN").font(.caption.weight(.bold)).tracking(1.4).foregroundStyle(.secondary)
                        ForEach(Array(hub.discovered.enumerated()), id: \.offset) { _, r in
                            Button {
                                Task { if let u = await hub.resolve(r) { manualURL = u } }
                            } label: { Label(name(r), systemImage: "desktopcomputer") }
                        }
                    }

                    Text("MANUELL").font(.caption.weight(.bold)).tracking(1.4).foregroundStyle(.secondary)
                    TextField("http://192.168.1.20:8765", text: $manualURL).textFieldStyle(.roundedBorder).keyboardType(.URL).textInputAutocapitalization(.never)
                    TextField("Kopplungs-Code", text: $manualToken).textFieldStyle(.roundedBorder).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button(busy ? "Verbinde …" : "Koppeln") {
                        busy = true
                        Task { if !(await hub.pair(url: manualURL, token: manualToken)) { error = "Hub nicht erreichbar oder Code falsch." }; busy = false }
                    }
                    .buttonStyle(.bordered).disabled(manualURL.isEmpty || manualToken.isEmpty || busy)
                    if let error { Text(error).foregroundStyle(.red).font(.footnote) }
                }
                .padding(20)
            }
            .sheet(isPresented: $scanning) {
                QRScanner { code in
                    scanning = false
                    guard let d = code.data(using: .utf8), let p = try? JSONDecoder().decode(PairPayload.self, from: d) else {
                        error = "Kein REKORD-Code."; return
                    }
                    busy = true
                    Task { if !(await hub.pair(with: p)) { error = "Computer nicht erreichbar – gleiches WLAN? Läuft REKORD am Computer? (Windows: Firewall „Private Netzwerke“ erlauben)" }; busy = false }
                }
                .ignoresSafeArea()
            }
            .onAppear { hub.startDiscovery() }
            .onDisappear { hub.stopDiscovery() }
        }
    }

    private func name(_ r: NWBrowser.Result) -> String {
        if case .service(let n, _, _, _) = r.endpoint { return n }
        return "REKORD Hub"
    }
}

struct QRScanner: UIViewControllerRepresentable {
    let onCode: (String) -> Void

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let vc = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])], qualityLevel: .balanced,
                                           isHighlightingEnabled: true)
        vc.delegate = context.coordinator
        try? vc.startScanning()
        return vc
    }

    func updateUIViewController(_ vc: DataScannerViewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        let onCode: (String) -> Void
        private var fired = false
        init(onCode: @escaping (String) -> Void) { self.onCode = onCode }
        func dataScanner(_ s: DataScannerViewController, didAdd items: [RecognizedItem], allItems: [RecognizedItem]) {
            for case .barcode(let b) in items {
                if let v = b.payloadStringValue, !fired { fired = true; s.stopScanning(); onCode(v) }
            }
        }
    }
}
