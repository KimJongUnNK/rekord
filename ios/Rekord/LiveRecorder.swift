import ActivityKit
import AVFoundation
import Combine
import SwiftUI
import UIKit
import WidgetKit

/// Runs on the real-time audio thread: resample → local file → websocket. No main-actor hops per buffer.
final class AudioPipe: @unchecked Sendable {
    private let lock = NSLock()
    private let converter: AVAudioConverter
    private let target: AVAudioFormat
    private let inputRate: Double
    private var file: FileHandle?
    private var _ws: URLSessionWebSocketTask?
    private var _paused = false
    private var _streaming = true
    var onLevel: ((Float) -> Void)?

    init(converter: AVAudioConverter, target: AVAudioFormat, inputRate: Double, file: FileHandle) {
        self.converter = converter; self.target = target; self.inputRate = inputRate; self.file = file
    }
    var ws: URLSessionWebSocketTask? { get { lock.withLock { _ws } } set { lock.withLock { _ws = newValue } } }
    var paused: Bool { get { lock.withLock { _paused } } set { lock.withLock { _paused = newValue } } }
    var streaming: Bool { get { lock.withLock { _streaming } } set { lock.withLock { _streaming = newValue } } }

    func process(_ buffer: AVAudioPCMBuffer) {
        if let ch = buffer.floatChannelData?[0] {
            let n = Int(buffer.frameLength)
            var sum: Float = 0
            for i in 0..<n { sum += ch[i] * ch[i] }
            onLevel?(n > 0 ? sqrt(sum / Float(n)) : 0)
        }
        if paused { return }
        let cap = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / inputRate) + 32
        guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: cap) else { return }
        var fed = false
        var err: NSError?
        converter.convert(to: out, error: &err) { _, status in
            if fed { status.pointee = .noDataNow; return nil }
            fed = true
            status.pointee = .haveData
            return buffer
        }
        guard err == nil, out.frameLength > 0, let p = out.int16ChannelData?[0] else { return }
        let data = Data(bytes: p, count: Int(out.frameLength) * 2)
        lock.withLock { try? file?.write(contentsOf: data) }
        if streaming, let ws { ws.send(.data(data)) { _ in } }
    }

    func close() { lock.withLock { try? file?.close(); file = nil } }
}

/// Captures the mic (any input: built-in, AirPods, USB/Lightning mic), converts to 16 kHz PCM, streams it to the hub
/// and turns the hub's events into UI + Live Activity. Keeps a local WAV copy, so nothing is lost if Wi-Fi drops.
@MainActor
final class LiveRecorder: ObservableObject {
    static let shared = LiveRecorder()

    struct Now: Equatable { var key: Int?; var name: String; var color: String; var known: Bool; var score: Double; var silence: Bool }
    struct RosterItem: Identifiable, Equatable { var id: String { key.map(String.init) ?? "p-\(name)" }; var key: Int?; var name: String; var color: String; var known: Bool; var talk: Double; var waiting: Bool }
    struct Line: Identifiable, Equatable { let id = UUID(); var key: Int?; var name: String; var color: String; let start: Double; let text: String }

    @Published private(set) var isRecording = false
    @Published private(set) var paused = false
    @Published private(set) var stopping = false
    @Published private(set) var offline = false
    @Published private(set) var startedAt: Date?
    @Published private(set) var now: Now?
    @Published private(set) var roster: [RosterItem] = []
    @Published private(set) var lines: [Line] = []
    @Published fileprivate(set) var level: Float = 0
    @Published private(set) var highlights: [Double] = []
    @Published var lastSavedId: String?
    @Published var error: String?

    private var title = ""
    private var engine: AVAudioEngine?
    private var pipe: AudioPipe?
    private let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true)!
    private var ws: URLSessionWebSocketTask? { didSet { pipe?.ws = ws } }
    private var pcmURL: URL?
    private var pausedTotal: TimeInterval = 0
    private var pausedAt: Date?
    private var activity: Activity<RekordActivityAttributes>?
    private var lastActivityUpdate = Date.distantPast
    private var savedContinuation: CheckedContinuation<Void, Never>?
    private let haptic = UIImpactFeedbackGenerator(style: .medium)

    var elapsed: TimeInterval {
        guard let s = startedAt else { return 0 }
        return (pausedAt ?? Date()).timeIntervalSince(s) - pausedTotal
    }

    // MARK: start

    func start(title: String?) async {
        guard !isRecording else { return }
        let settings = AppSettings.shared
        error = nil
        guard await AVAudioApplication.requestRecordPermission() else {
            error = "Mikrofon-Zugriff verweigert (Einstellungen → REKORD → Mikrofon)."
            return
        }
        do {
            try configureSession(settings)
            try startEngine()
        } catch {
            self.error = "Audio konnte nicht starten: \(error.localizedDescription)"
            teardownAudio()
            return
        }
        self.title = title?.isEmpty == false ? title! : "Meeting " + Date().formatted(.dateTime.day().month().hour().minute())
        isRecording = true
        paused = false
        stopping = false
        offline = !settings.liveDetect
        pipe?.streaming = settings.liveDetect
        startedAt = Date()
        pausedTotal = 0
        pausedAt = nil
        now = nil
        lines = []
        roster = []
        highlights = []
        lastSavedId = nil
        UIApplication.shared.isIdleTimerDisabled = settings.keepAwake
        startActivity()
        publishShared()
        if settings.liveDetect { connect() }
    }

    private func configureSession(_ settings: AppSettings) throws {
        let s = AVAudioSession.sharedInstance()
        // voiceChat = Apple's echo cancel + noise suppression + AGC; measurement = raw signal (good external mics)
        try s.setCategory(.playAndRecord, mode: settings.voiceProcessing ? .voiceChat : .measurement,
                          options: [.allowBluetooth, .defaultToSpeaker, .mixWithOthers])
        if !settings.preferredInputUID.isEmpty, let port = s.availableInputs?.first(where: { $0.uid == settings.preferredInputUID }) {
            try s.setPreferredInput(port)
        }
        try s.setPreferredSampleRate(48000)
        try s.setActive(true)
    }

    private func startEngine() throws {
        let engine = AVAudioEngine()
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, let conv = AVAudioConverter(from: format, to: target) else {
            throw NSError(domain: "rekord", code: 1, userInfo: [NSLocalizedDescriptionKey: "Kein Eingangssignal"])
        }
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("Pending", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent("rec-\(Int(Date().timeIntervalSince1970)).pcm")
        FileManager.default.createFile(atPath: url.path, contents: nil)
        pcmURL = url
        let pipe = AudioPipe(converter: conv, target: target, inputRate: format.sampleRate, file: try FileHandle(forWritingTo: url))
        pipe.onLevel = { rms in Task { @MainActor in LiveRecorder.shared.level = min(1, rms * 9) } }
        self.pipe = pipe
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { buffer, _ in pipe.process(buffer) }
        engine.prepare()
        try engine.start()
        self.engine = engine
    }

    // MARK: websocket

    private func connect() {
        guard let url = try? HubClient.shared.wsURL("/ws/live") else { offline = true; return }
        let task = URLSession.shared.webSocketTask(with: url)
        task.maximumMessageSize = 4 * 1024 * 1024
        ws = task
        task.resume()
        let settings = AppSettings.shared
        let start: [String: Any] = ["type": "start", "sample_rate": 16000, "title": title, "source": "ios",
                                    "participants": settings.participants, "guests": settings.guests]
        sendJSON(start)
        receive()
    }

    private func sendJSON(_ obj: [String: Any]) {
        guard let ws, let d = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: d, encoding: .utf8) else { return }
        ws.send(.string(s)) { _ in }
    }

    private func receive() {
        ws?.receive { [weak self] result in
            Task { @MainActor in
                guard let self else { return }
                switch result {
                case .success(.string(let s)):
                    if let d = s.data(using: .utf8), let ev = try? JSONSerialization.jsonObject(with: d) as? [String: Any] { self.handle(ev) }
                    self.receive()
                case .success:
                    self.receive()
                case .failure:
                    if self.isRecording && !self.stopping {
                        self.offline = true          // keep recording locally, upload later
                        self.pipe?.streaming = false
                        self.error = "Hub-Verbindung verloren – nehme lokal weiter auf."
                    }
                    self.savedContinuation?.resume()
                    self.savedContinuation = nil
                }
            }
        }
    }

    private func handle(_ ev: [String: Any]) {
        let type = ev["type"] as? String ?? ""
        switch type {
        case "speaking":
            let n = Now(key: ev["key"] as? Int, name: ev["name"] as? String ?? "?", color: ev["color"] as? String ?? "#888888",
                        known: ev["known"] as? Bool ?? false, score: ev["score"] as? Double ?? 0, silence: false)
            if AppSettings.shared.hapticOnSpeaker, n.name != now?.name, now != nil { haptic.impactOccurred() }
            now = n
            updateActivity()
        case "silence":
            if now != nil { now?.silence = true }
        case "segment":
            let l = Line(key: ev["key"] as? Int, name: ev["name"] as? String ?? "?", color: ev["color"] as? String ?? "#888888",
                         start: ev["start"] as? Double ?? 0, text: ev["text"] as? String ?? "")
            lines.append(l)
            if let i = roster.firstIndex(where: { $0.key == l.key && l.key != nil }) {
                roster[i].talk += (ev["end"] as? Double ?? 0) - l.start
            }
            updateActivity(force: true)
        case "speakers":
            let old = Dictionary(uniqueKeysWithValues: roster.compactMap { r in r.key.map { ($0, r.talk) } })
            roster = (ev["items"] as? [[String: Any]] ?? []).map {
                let key = $0["key"] as? Int
                return RosterItem(key: key, name: $0["name"] as? String ?? "?", color: $0["color"] as? String ?? "#888888",
                                  known: $0["known"] as? Bool ?? false,
                                  talk: max($0["talk"] as? Double ?? 0, key.flatMap { old[$0] } ?? 0), waiting: $0["waiting"] as? Bool ?? false)
            }
            for i in lines.indices { if let r = roster.first(where: { $0.key == lines[i].key && $0.key != nil }) { lines[i].name = r.name; lines[i].color = r.color } }
        case "stopped":
            lastSavedId = ev["id"] as? String
            savedContinuation?.resume()
            savedContinuation = nil
        case "error":
            error = ev["error"] as? String
            offline = true
            pipe?.streaming = false
        default: break
        }
    }

    // MARK: controls

    func highlight() {
        guard isRecording else { return }
        highlights.append(elapsed)
        sendJSON(["type": "highlight"])
        haptic.impactOccurred(intensity: 1)
        updateActivity(force: true)
    }

    func togglePause() {
        guard isRecording else { return }
        paused.toggle()
        pipe?.paused = paused
        if paused { pausedAt = Date() } else if let p = pausedAt { pausedTotal += Date().timeIntervalSince(p); pausedAt = nil }
        sendJSON(["type": paused ? "pause" : "resume"])
        updateActivity(force: true)
    }

    func nameSpeaker(key: Int, name: String) {
        sendJSON(["type": "name_speaker", "key": key, "name": name])
    }

    func stop() async {
        guard isRecording, !stopping else { return }
        stopping = true
        teardownAudio()
        pipe?.close()
        pipe = nil
        if !offline, let ws, ws.state == .running {
            sendJSON(["type": "stop"])
            await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
                savedContinuation = c
                Task { try? await Task.sleep(for: .seconds(45)); self.savedContinuation?.resume(); self.savedContinuation = nil }
            }
        }
        ws?.cancel(with: .normalClosure, reason: nil)
        ws = nil
        if lastSavedId == nil, let pcmURL {
            await uploadOffline(pcmURL)              // offline / connection lost: send the local copy
        } else if let pcmURL {
            try? FileManager.default.removeItem(at: pcmURL)
        }
        await endActivity()
        isRecording = false
        stopping = false
        UIApplication.shared.isIdleTimerDisabled = false
        Shared.defaults.set(title, forKey: Shared.Key.lastTitle)
        Shared.defaults.set(Date(), forKey: Shared.Key.lastDate)
        Shared.defaults.set(roster.filter { !$0.waiting }.map(\.name), forKey: Shared.Key.lastSpeakers)
        publishShared()
    }

    private func teardownAudio() {
        engine?.inputNode.removeTap(onBus: 0)
        engine?.stop()
        engine = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    // MARK: offline upload queue

    private func uploadOffline(_ pcm: URL) async {
        guard let wav = try? Self.wrapWAV(pcm) else { return }
        try? FileManager.default.removeItem(at: pcm)
        var pending = Shared.defaults.stringArray(forKey: Shared.Key.pendingUploads) ?? []
        pending.append("\(wav.lastPathComponent)|\(title)|\(highlights.map { String(format: "%.1f", $0) }.joined(separator: ","))")
        Shared.defaults.set(pending, forKey: Shared.Key.pendingUploads)
        await flushPendingUploads()
    }

    func flushPendingUploads() async {
        var pending = Shared.defaults.stringArray(forKey: Shared.Key.pendingUploads) ?? []
        guard !pending.isEmpty else { return }
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("Pending")
        var remaining: [String] = []
        for entry in pending {
            let parts = entry.split(separator: "|", omittingEmptySubsequences: false).map(String.init)
            let file = dir.appendingPathComponent(parts[0])
            guard FileManager.default.fileExists(atPath: file.path) else { continue }
            let hl = "[" + (parts.count > 2 ? parts[2] : "") + "]"
            do {
                let data = try await HubClient.shared.upload(path: "/api/recordings", fileURL: file, fileField: "files",
                                                             fields: ["title": parts.count > 1 ? parts[1] : "iPhone", "source": "ios", "highlights": hl])
                try? FileManager.default.removeItem(at: file)
                if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let items = obj["items"] as? [[String: Any]], let id = items.first?["id"] as? String { lastSavedId = id }
            } catch {
                remaining.append(entry)
            }
        }
        pending = remaining
        Shared.defaults.set(pending, forKey: Shared.Key.pendingUploads)
        if !remaining.isEmpty { self.error = "\(remaining.count) Aufnahme(n) warten auf den Hub – werden automatisch hochgeladen." }
    }

    nonisolated static func wrapWAV(_ pcm: URL) throws -> URL {
        let data = try Data(contentsOf: pcm)
        var h = Data()
        func u32(_ v: UInt32) { var x = v.littleEndian; h.append(Data(bytes: &x, count: 4)) }
        func u16(_ v: UInt16) { var x = v.littleEndian; h.append(Data(bytes: &x, count: 2)) }
        h.append("RIFF".data(using: .ascii)!); u32(UInt32(36 + data.count)); h.append("WAVEfmt ".data(using: .ascii)!)
        u32(16); u16(1); u16(1); u32(16000); u32(32000); u16(2); u16(16)
        h.append("data".data(using: .ascii)!); u32(UInt32(data.count))
        let wav = pcm.deletingPathExtension().appendingPathExtension("wav")
        try (h + data).write(to: wav)
        return wav
    }

    // MARK: Live Activity + widgets

    private func state() -> RekordActivityAttributes.ContentState {
        .init(speaker: now.map { $0.silence ? "…" : $0.name } ?? "Hört zu …", speakerColor: now?.color ?? "#888888",
              known: now?.known ?? false, lastLine: lines.last.map { "\($0.name): \($0.text)" } ?? "",
              paused: paused, highlights: highlights.count, peopleCount: roster.filter { !$0.waiting }.count)
    }

    private func startActivity() {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }
        let attrs = RekordActivityAttributes(title: title, startedAt: startedAt ?? Date())
        activity = try? Activity.request(attributes: attrs, content: .init(state: state(), staleDate: nil), pushType: nil)
    }

    private func updateActivity(force: Bool = false) {
        Shared.defaults.set(now?.name, forKey: Shared.Key.currentSpeaker)
        Shared.defaults.set(now?.color, forKey: Shared.Key.currentColor)
        guard let activity, force || Date().timeIntervalSince(lastActivityUpdate) > 1.0 else { return }
        lastActivityUpdate = Date()
        let s = state()
        Task { await activity.update(.init(state: s, staleDate: nil)) }
    }

    private func endActivity() async {
        guard let activity else { return }
        var s = state()
        s.speaker = "Gespeichert"
        s.lastLine = "Feinschliff läuft auf deinem Hub"
        await activity.end(.init(state: s, staleDate: nil), dismissalPolicy: .after(.now + 8))
        self.activity = nil
    }

    private func publishShared() {
        let d = Shared.defaults
        d.set(isRecording, forKey: Shared.Key.isRecording)
        d.set(startedAt, forKey: Shared.Key.startedAt)
        d.set(now?.name, forKey: Shared.Key.currentSpeaker)
        d.set(now?.color, forKey: Shared.Key.currentColor)
        WidgetCenter.shared.reloadAllTimelines()
        ControlCenter.shared.reloadAllControls()
    }
}
