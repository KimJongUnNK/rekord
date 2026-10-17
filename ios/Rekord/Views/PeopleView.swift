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

/// Record ~15 s of one person and turn it into a voice profile on the hub.
struct EnrollSheet: View {
    let intro: Bool
    let done: (Profile?) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var recorder: AVAudioRecorder?
    @State private var seconds = 0
    @State private var timer: Timer?
    @State private var fileURL: URL?
    @State private var busy = false
    @State private var error: String?

    private let text = "Hallo, ich nehme jetzt eine kurze Sprachprobe auf. REKORD lernt meine Stimme, damit es mich in Meetings automatisch erkennt. Ich spreche ganz normal, so wie im Alltag. Eins, zwei, drei, vier, fünf."

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: $name).font(.title3.bold())
                Section(intro ? "Vorstellung (10–15 s)" : "Vorlesen (ca. 15 s)") {
                    Text(intro ? "Handy zur Person. Name, was du machst, worum es dir heute geht – ganz normal reden." : text)
                        .font(.callout)
                    HStack {
                        Button {
                            recorder?.isRecording == true ? stopRec() : startRec()
                        } label: {
                            Label(recorder?.isRecording == true ? "Stopp" : (fileURL == nil ? "Aufnahme starten" : "Neu aufnehmen"),
                                  systemImage: recorder?.isRecording == true ? "stop.circle.fill" : "record.circle")
                        }
                        Spacer()
                        Text("\(seconds) s").monospacedDigit().foregroundStyle(seconds >= 8 ? .green : .secondary)
                    }
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle(intro ? "Vorstellungsrunde" : "Person einsprechen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { stopRec(); done(nil); dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(busy ? "…" : "Speichern") { save() }.disabled(name.isEmpty || fileURL == nil || busy || recorder?.isRecording == true)
                }
            }
        }
    }

    private func startRec() {
        Task {
            guard await AVAudioApplication.requestRecordPermission() else { error = "Kein Mikrofon-Zugriff"; return }
            let s = AVAudioSession.sharedInstance()
            try? s.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try? s.setActive(true)
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("enroll-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 16000, AVNumberOfChannelsKey: 1]
            recorder = try? AVAudioRecorder(url: url, settings: settings)
            recorder?.record()
            fileURL = url
            seconds = 0
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
                Task { @MainActor in seconds += 1; if seconds >= 30 { stopRec() } }
            }
        }
    }

    private func stopRec() {
        recorder?.stop()
        timer?.invalidate()
        timer = nil
        recorder = nil
    }

    private func save() {
        guard let fileURL else { return }
        busy = true
        Task {
            do {
                let data = try await HubClient.shared.upload(path: "/api/profiles/enroll", fileURL: fileURL, fileField: "file", fields: ["name": name])
                let prof = try JSONDecoder().decode(Profile.self, from: data)
                done(prof)
                dismiss()
            } catch {
                self.error = error.localizedDescription
            }
            busy = false
        }
    }
}
