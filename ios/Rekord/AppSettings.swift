import AVFoundation
import SwiftUI

/// Per-device preferences (the hub keeps the AI/transcription settings).
@MainActor
final class AppSettings: ObservableObject {
    static let shared = AppSettings()

    @AppStorage("hubURL") var hubURL: String = "" { willSet { objectWillChange.send() } }
    @AppStorage("hubToken") var hubToken: String = "" { willSet { objectWillChange.send() } }
    @AppStorage("theme") var theme: String = "system" { willSet { objectWillChange.send() } }        // system | light | dark
    @AppStorage("accentHex") var accentHex: String = "#FF5A1F" {
        willSet { objectWillChange.send() }
        didSet { Shared.defaults.set(accentHex, forKey: Shared.Key.accentHex) }
    }
    @AppStorage("preferredInputUID") var preferredInputUID: String = "" { willSet { objectWillChange.send() } }
    @AppStorage("voiceProcessing") var voiceProcessing: Bool = true { willSet { objectWillChange.send() } }  // echo + noise suppression + AGC
    @AppStorage("liveDetect") var liveDetect: Bool = true { willSet { objectWillChange.send() } }
    @AppStorage("keepAwake") var keepAwake: Bool = true { willSet { objectWillChange.send() } }
    @AppStorage("hapticOnSpeaker") var hapticOnSpeaker: Bool = true { willSet { objectWillChange.send() } }
    @AppStorage("participantsCSV") var participantsCSV: String = "" { willSet { objectWillChange.send() } }
    @AppStorage("guests") var guests: Int = 0 { willSet { objectWillChange.send() } }
    @AppStorage("whoTotal") var whoTotal: Int = 0 { willSet { objectWillChange.send() } }  // "Wer ist dabei?": people talking
    @Published var selectedTab: Tab = .live

    static let accents: [(String, String)] = [("#FF5A1F", "Voltage"), ("#2D7FF9", "Electric"), ("#C6F432", "Acid"), ("#E11D74", "Magenta"),
                                              ("#8B5CF6", "Violet"), ("#FACC15", "Yellow"), ("#EF4444", "Red"), ("#14B8A6", "Teal")]

    var isPaired: Bool { !hubURL.isEmpty }
    var accent: Color { Color(hex: accentHex) }
    var colorScheme: ColorScheme? { theme == "light" ? .light : theme == "dark" ? .dark : nil }

    var participants: [Int] {
        get { participantsCSV.split(separator: ",").compactMap { Int($0) } }
        set { participantsCSV = newValue.map(String.init).joined(separator: ",") }
    }

    var availableInputs: [AVAudioSessionPortDescription] {
        let s = AVAudioSession.sharedInstance()
        try? s.setCategory(.playAndRecord, mode: .default, options: [.allowBluetooth, .defaultToSpeaker])
        return s.availableInputs ?? []
    }
}
