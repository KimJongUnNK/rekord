import ActivityKit
import AppIntents
import Foundation
import SwiftUI
import WidgetKit

// MARK: - App Group store (app ⇄ widgets)

enum Shared {
    static let appGroup = "group.app.rekord.shared"
    static var defaults: UserDefaults { UserDefaults(suiteName: appGroup) ?? .standard }

    enum Key {
        static let isRecording = "isRecording"
        static let startedAt = "startedAt"
        static let currentSpeaker = "currentSpeaker"
        static let currentColor = "currentColor"
        static let lastTitle = "lastTitle"
        static let lastDate = "lastDate"
        static let lastSpeakers = "lastSpeakers"
        static let accentHex = "accentHex"
        static let pendingUploads = "pendingUploads"
    }

    static var accent: Color { Color(hex: defaults.string(forKey: Key.accentHex) ?? "#FF5A1F") }
}

// MARK: - Live Activity (lock screen + Dynamic Island)

struct RekordActivityAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var speaker: String          // who is talking right now
        var speakerColor: String     // hex
        var known: Bool
        var lastLine: String
        var paused: Bool
        var highlights: Int
        var peopleCount: Int
    }
    var title: String
    var startedAt: Date
}

// MARK: - Color helpers

extension Color {
    init(hex: String) {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "#", with: "")
        if s.count == 3 { s = s.map { "\($0)\($0)" }.joined() }
        var v: UInt64 = 0
        Scanner(string: s).scanHexInt64(&v)
        self.init(.sRGB, red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255,
                  blue: Double(v & 0xFF) / 255, opacity: 1)
    }
}

func initials(_ name: String) -> String {
    let n: String = name.hasPrefix("Sprecher ") ? "S" + String(name.dropFirst(9)) : name
    return String(n.split(separator: " ").compactMap(\.first).prefix(2)).uppercased()
}

// MARK: - App Intents (lock screen control, widgets, Siri, Shortcuts, Action Button)

/// Starts a live recording from the Lock Screen / Control Center / Action Button.
/// AudioRecordingIntent lets the system launch the recorder in the background; it must start a Live Activity.
struct StartRecordingIntent: AudioRecordingIntent {
    static var title: LocalizedStringResource = "REKORD Aufnahme starten"
    static var description = IntentDescription("Startet eine Live-Aufnahme mit Sprecher-Erkennung.")

    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await LiveRecorder.shared.start(title: nil)
        #endif
        return .result()
    }
}

struct StopRecordingIntent: LiveActivityIntent {
    static var title: LocalizedStringResource = "REKORD Aufnahme stoppen"
    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await LiveRecorder.shared.stop()
        #endif
        return .result()
    }
}

struct HighlightIntent: LiveActivityIntent {
    static var title: LocalizedStringResource = "Moment markieren"
    static var description = IntentDescription("Markiert den aktuellen Moment als wichtig (★).")
    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await LiveRecorder.shared.highlight()
        #endif
        return .result()
    }
}

struct PauseRecordingIntent: LiveActivityIntent {
    static var title: LocalizedStringResource = "REKORD pausieren/fortsetzen"
    func perform() async throws -> some IntentResult {
        #if !WIDGET_EXTENSION
        await LiveRecorder.shared.togglePause()
        #endif
        return .result()
    }
}

#if !WIDGET_EXTENSION
struct RekordShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: StartRecordingIntent(), phrases: ["Starte \(.applicationName)", "Meeting aufnehmen mit \(.applicationName)"],
                    shortTitle: "Aufnehmen", systemImageName: "record.circle")
        AppShortcut(intent: HighlightIntent(), phrases: ["Markiere das in \(.applicationName)"],
                    shortTitle: "Markieren", systemImageName: "star")
        AppShortcut(intent: StopRecordingIntent(), phrases: ["Stoppe \(.applicationName)"],
                    shortTitle: "Stopp", systemImageName: "stop.circle")
    }
}
#endif
