import AVFoundation
import SwiftUI

struct PeopleView: View {
    @EnvironmentObject var hub: HubClient
    @State private var people: [Profile] = []
    @State private var enroll = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("REKORD erkennt Menschen an ihrer Stimme – live und in jeder Aufnahme. Neue Person: hier einsprechen, im Live-Modus auf die unbekannte Stimme tippen oder im Transkript umbenennen.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                ForEach(people) { p in
                    HStack(spacing: 14) {
                        Text(initials(p.name)).font(.headline.weight(.heavy)).foregroundStyle(.white)
                            .frame(width: 44, height: 44).background(Circle().fill(Color(hex: p.color)))
                        VStack(alignment: .leading) {
                            Text(p.name).font(.headline.weight(.heavy))
                            Text("\(p.recordings) Aufnahmen · \(p.samples) Stimmproben").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .swipeActions {
                        Button(role: .destructive) {
                            Task { try? await hub.send("/api/profiles/\(p.id)", method: "DELETE"); await load() }
                        } label: { Label("Vergessen", systemImage: "trash") }
                    }
                }
            }
            .navigationTitle("Personen")
            .toolbar { Button { enroll = true } label: { Label("Einsprechen", systemImage: "plus") } }
            .sheet(isPresented: $enroll) { EnrollSheet(intro: false) { _ in Task { await load() } } }
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private func load() async { people = (try? await hub.profiles()) ?? [] }
}

/// One voice of a recording ("Aus Aufnahme lernen").
struct RecordingVoice: Codable, Identifiable, Hashable {
    let speaker_id: Int
    let voice: Int?
    let name: String
    let known: Bool
    let color: String
    let seconds: Double
    let lines: Int
    let first: Double
    let text: String
    let samples: [[Double]]
    var id: String { "\(speaker_id)-\(voice ?? -1)" }
}
private struct VoiceList: Codable { let items: [RecordingVoice] }

enum EnrollMode: String, CaseIterable, Identifiable {
    case read, free, recording
    var id: String { rawValue }
    var label: String {
        switch self {
        case .read: return "Text vorlesen"
        case .free: return "Einfach reden"
        case .recording: return "Aus Aufnahme"
        }
    }
}

private let talkIdeas = [
    "Erzähl, was du heute schon gemacht hast.", "Was ist dein Lieblingsessen – und wie kocht man es?",
    "Beschreib den Weg von dir zuhause zur Arbeit oder Uni.", "Was war dein letzter Urlaub – wo, mit wem, was war das Beste?",
    "Woran arbeitest du gerade, und was ist dabei schwierig?", "Erklär einem Kind, was du beruflich machst oder studierst.",
    "Welches Buch, welche Serie oder welcher Film hat dich zuletzt beeindruckt?", "Was würdest du mit einem freien Tag machen?",
]

/// Teach REKORD a voice: read a text, just let the person talk (anything – e.g. the lecturer in a lecture), or take
/// the voice from a finished recording. Only seconds with real speech count.
struct EnrollSheet: View {
    let intro: Bool
    let done: (Profile?) -> Void
    @Environment(\.dismiss) private var dismiss
    private var hub: HubClient { HubClient.shared }
    @AppStorage("enrollMode") private var modeRaw = EnrollMode.read.rawValue
    @State private var name = ""
    @State private var recorder: AVAudioRecorder?
    @State private var seconds = 0
    @State private var speech = 0.0
    @State private var wall = 0.0
    @State private var floorDB: Float = -50
    @State private var lastVoice = -1.0
    @State private var level: Double = 0
    @State private var timer: Timer?
    @State private var fileURL: URL?
    @State private var busy = false
    @State private var error: String?
    @State private var variant = 0
    @State private var idea: String?
    @State private var recordings: [RecordingItem] = []
    @State private var recordingID = ""
    @State private var voices: [RecordingVoice] = []
    @State private var picked: RecordingVoice?
    @State private var player: AVPlayer?
    private let target = 45, minimum = 25

    private var mode: EnrollMode { EnrollMode(rawValue: modeRaw) ?? .read }

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: $name).font(.title3.bold())
                Section {
                    Picker("Wie lernen?", selection: $modeRaw) {
                        ForEach(EnrollMode.allCases) { Text($0.label).tag($0.rawValue) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: modeRaw) { _, _ in stopRec(); if mode == .recording { Task { await loadRecordings() } } }
                } header: { Text("Wie soll REKORD die Stimme lernen?") }

                switch mode {
                case .read:
                    Section(intro ? "Handy zur Person – sie liest ihren eigenen Text (ca. 45 s)" : "Vorlesen (ca. 45 s)") {
                        Text(ReadingText.make(name: name, variant: variant)).font(.body)
                        Button("Anderer Text") { variant += 1 }.font(.footnote)
                        recordControls
                    }
                case .free:
                    Section("Einfach reden lassen") {
                        Text("Die Person redet über irgendwas – kein Text. Passt auch, wenn jemand sowieso redet, z. B. der Prof am Anfang der Vorlesung: Handy in seine Richtung, Aufnahme starten. Kurze Zwischenrufe anderer lässt REKORD weg.")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("💬 Gesprächsidee") { idea = talkIdeas.filter { $0 != idea }.randomElement() }.font(.footnote)
                        if let idea { Text(idea).font(.body) }
                        recordControls
                    }
                case .recording:
                    Section("Stimme aus einer fertigen Aufnahme") {
                        Picker("Aufnahme", selection: $recordingID) {
                            Text(recordings.isEmpty ? "Noch keine fertige Aufnahme" : "Aufnahme wählen …").tag("")
                            ForEach(recordings) { Text($0.title).tag($0.id) }
                        }
                        .onChange(of: recordingID) { _, id in Task { await loadVoices(id) } }
                        ForEach(voices) { v in
                            HStack {
                                Button { play(v) } label: { Image(systemName: "play.circle.fill") }.buttonStyle(.borderless)
                                VStack(alignment: .leading) {
                                    Text(v.known || v.name != "Nicht erkannte Stimme" ? v.name : "Stimme ab \(Int(v.first) / 60):\(String(format: "%02d", Int(v.first) % 60))")
                                        .bold() + Text(" · \(Int(v.seconds)) s").foregroundColor(.secondary)
                                    Text("„\(v.text)“").font(.footnote).foregroundStyle(.secondary).lineLimit(2)
                                }
                                Spacer()
                                if picked == v { Image(systemName: "checkmark.circle.fill").foregroundStyle(.tint) }
                            }
                            .contentShape(Rectangle())
                            .onTapGesture { picked = v; if name.isEmpty && v.known { name = v.name } }
                        }
                    }
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle(intro ? "Vorstellungsrunde" : "Person einsprechen")
            .navigationBarTitleDisplayMode(.inline)
            .task { if mode == .recording { await loadRecordings() } }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { stopRec(); player?.pause(); done(nil); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(busy ? "…" : (mode == .recording ? "Lernen" : "Speichern")) { save() }
                        .disabled(name.isEmpty || busy || (mode == .recording ? picked == nil
                                  : (fileURL == nil || recorder?.isRecording == true || seconds < minimum)))
                }
            }
        }
    }

    @ViewBuilder private var recordControls: some View {
        HStack {
            Button {
                recorder?.isRecording == true ? stopRec() : startRec()
            } label: {
                Label(recorder?.isRecording == true ? "Fertig" : (fileURL == nil ? "Aufnahme starten" : "Neu aufnehmen"),
                      systemImage: recorder?.isRecording == true ? "stop.circle.fill" : "record.circle")
            }
            Spacer()
            ProgressView(value: level).frame(width: 60)
            Text("\(seconds) s").monospacedDigit().foregroundStyle(seconds >= minimum ? .green : .secondary)
        }
        ProgressView(value: min(1, Double(seconds) / Double(target))).tint(seconds >= minimum ? .green : .accentColor)
        Text(seconds < minimum ? "Gezählt wird nur echte Sprache. Mindestens \(minimum) Sekunden – je länger, desto sicherer."
             : seconds < target ? "Reicht. Noch etwas länger macht die Erkennung sicherer." : "Perfekt – du kannst auf „Fertig“ tippen.")
            .font(.footnote).foregroundStyle(.secondary)
    }

    private func startRec() {
        Task {
            guard !name.trimmingCharacters(in: .whitespaces).isEmpty else { error = "Zuerst den Namen eingeben."; return }
            guard await AVAudioApplication.requestRecordPermission() else { error = "Kein Mikrofon-Zugriff"; return }
            let s = AVAudioSession.sharedInstance()
            try? s.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try? s.setActive(true)
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("enroll-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 16000, AVNumberOfChannelsKey: 1]
            recorder = try? AVAudioRecorder(url: url, settings: settings)
            recorder?.isMeteringEnabled = true
            recorder?.record()
            fileURL = url
            seconds = 0; speech = 0; wall = 0; floorDB = -50; lastVoice = -1; error = nil
            let limit = mode == .free ? 240.0 : 120.0
            timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
                Task { @MainActor in
                    guard let r = recorder, r.isRecording else { return }
                    r.updateMeters()
                    let db = r.averagePower(forChannel: 0)
                    floorDB = db < floorDB ? db : floorDB + 0.02  // background noise, follows slowly upwards
                    if db > max(-52, floorDB + 8) { lastVoice = wall }
                    if lastVoice >= 0 && wall - lastVoice <= 0.4 { speech += 0.1 }  // short gaps between words still count
                    wall += 0.1
                    level = Double(max(0, min(1, (db + 60) / 60)))
                    seconds = Int(speech)
                    if wall >= limit { stopRec() }
                }
            }
        }
    }

    private func stopRec() {
        recorder?.stop()
        timer?.invalidate()
        timer = nil
        recorder = nil
        level = 0
    }

    private func loadRecordings() async {
        recordings = ((try? await hub.recordings()) ?? []).filter { $0.status == "done" }
    }

    private func loadVoices(_ id: String) async {
        voices = []; picked = nil
        guard !id.isEmpty else { return }
        voices = (try? await hub.get("/api/recordings/\(id)/voices", as: VoiceList.self).items) ?? []
        if let u = try? hub.audioURL(id) { player = AVPlayer(url: u) }
    }

    private func play(_ v: RecordingVoice) {
        guard let s = v.samples.first, s.count == 2, let player else { return }
        player.seek(to: CMTime(seconds: s[0], preferredTimescale: 600))
        player.play()
        let length = min(8, s[1] - s[0])
        Task { try? await Task.sleep(for: .seconds(length)); player.pause() }
    }

    private func save() {
        busy = true
        Task {
            do {
                let data: Data
                if mode == .recording, let v = picked {
                    var body: [String: Any] = ["recording_id": recordingID, "speaker_id": v.speaker_id, "name": name]
                    if let voice = v.voice { body["voice"] = voice }
                    data = try await hub.send("/api/profiles/learn", json: body)
                } else {
                    guard let fileURL else { busy = false; return }
                    data = try await hub.upload(path: "/api/profiles/enroll", fileURL: fileURL, fileField: "file",
                                                fields: ["name": name, "mode": mode == .free ? "free" : "read"])
                }
                let prof = try JSONDecoder().decode(Profile.self, from: data)
                player?.pause()
                done(prof)
                dismiss()
            } catch {
                self.error = error.localizedDescription
            }
            busy = false
        }
    }
}
