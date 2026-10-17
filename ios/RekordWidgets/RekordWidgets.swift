import ActivityKit
import AppIntents
import SwiftUI
import WidgetKit

@main
struct RekordWidgetsBundle: WidgetBundle {
    var body: some Widget {
        RekordLiveActivity()
        RekordStatusWidget()
        RekordRecordButtonWidget()
        RekordRecordControl()
    }
}

// MARK: - Live Activity: lock screen banner + Dynamic Island, shows who is speaking right now

struct RekordLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: RekordActivityAttributes.self) { ctx in
            LockScreenLiveView(ctx: ctx)
                .activityBackgroundTint(Color.black.opacity(0.85))
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { ctx in
            let color = Color(hex: ctx.state.speakerColor)
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 8) {
                        Text(initials(ctx.state.speaker)).font(.system(size: 15, weight: .black)).foregroundStyle(.white)
                            .frame(width: 36, height: 36).background(Circle().fill(color))
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(timerInterval: ctx.attributes.startedAt...Date.distantFuture, countsDown: false)
                        .font(.system(.title3, design: .rounded).weight(.bold)).monospacedDigit().frame(maxWidth: 80)
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(ctx.state.speaker).font(.headline.weight(.black)).foregroundStyle(color).lineLimit(1)
                        Text(ctx.state.known ? "spricht · erkannt" : "spricht").font(.caption2).foregroundStyle(.secondary)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(alignment: .leading, spacing: 8) {
                        if !ctx.state.lastLine.isEmpty { Text(ctx.state.lastLine).font(.caption).lineLimit(2).foregroundStyle(.secondary) }
                        HStack {
                            Button(intent: HighlightIntent()) { Label("Markieren", systemImage: "star.fill") }.tint(.orange)
                            Button(intent: PauseRecordingIntent()) { Image(systemName: ctx.state.paused ? "play.fill" : "pause.fill") }
                            Spacer()
                            Button(intent: StopRecordingIntent()) { Label("Stopp", systemImage: "stop.fill") }.tint(.red)
                        }
                        .font(.caption.bold())
                    }
                }
            } compactLeading: {
                HStack(spacing: 4) {
                    Circle().fill(.red).frame(width: 7, height: 7)
                    Text(initials(ctx.state.speaker)).font(.caption2.weight(.black)).foregroundStyle(color)
                }
            } compactTrailing: {
                Text(timerInterval: ctx.attributes.startedAt...Date.distantFuture, countsDown: false)
                    .monospacedDigit().font(.caption2.weight(.semibold)).frame(maxWidth: 44)
            } minimal: {
                Text(initials(ctx.state.speaker)).font(.caption2.weight(.black)).foregroundStyle(color)
            }
            .keylineTint(color)
        }
    }
}

struct LockScreenLiveView: View {
    let ctx: ActivityViewContext<RekordActivityAttributes>
    var body: some View {
        let color = Color(hex: ctx.state.speakerColor)
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Circle().fill(ctx.state.paused ? .gray : .red).frame(width: 8, height: 8)
                Text(ctx.state.paused ? "PAUSE" : "REKORD · LIVE").font(.caption2.weight(.heavy)).tracking(1.2).foregroundStyle(.white.opacity(0.7))
                Spacer()
                if ctx.state.highlights > 0 { Label("\(ctx.state.highlights)", systemImage: "star.fill").font(.caption2.bold()).foregroundStyle(.orange) }
                Text(timerInterval: ctx.attributes.startedAt...Date.distantFuture, countsDown: false)
                    .font(.system(.body, design: .rounded).weight(.bold)).monospacedDigit().foregroundStyle(.white).frame(width: 70, alignment: .trailing)
            }
            HStack(spacing: 12) {
                Text(initials(ctx.state.speaker)).font(.system(size: 18, weight: .black)).foregroundStyle(.white)
                    .frame(width: 44, height: 44).background(Circle().fill(color))
                VStack(alignment: .leading, spacing: 2) {
                    Text(ctx.state.speaker).font(.system(size: 24, weight: .black)).foregroundStyle(.white).lineLimit(1)
                    Text(ctx.state.lastLine.isEmpty ? "\(ctx.state.peopleCount) Personen im Raum" : ctx.state.lastLine)
                        .font(.caption).foregroundStyle(.white.opacity(0.7)).lineLimit(1)
                }
                Spacer()
                Button(intent: HighlightIntent()) { Image(systemName: "star.fill") }.tint(.orange)
                Button(intent: StopRecordingIntent()) { Image(systemName: "stop.fill") }.tint(.red)
            }
        }
        .padding(16)
    }
}

// MARK: - Status widget (lock screen rectangular/inline + home screen small/medium)

struct StatusEntry: TimelineEntry {
    let date: Date
    let recording: Bool
    let startedAt: Date?
    let speaker: String?
    let speakerColor: String?
    let lastTitle: String?
    let lastDate: Date?
    let lastSpeakers: [String]
}

struct StatusProvider: TimelineProvider {
    func placeholder(in context: Context) -> StatusEntry {
        StatusEntry(date: .now, recording: false, startedAt: nil, speaker: nil, speakerColor: nil, lastTitle: "Budget Sommerfestival",
                    lastDate: .now, lastSpeakers: ["Emil", "Lisa"])
    }
    func getSnapshot(in context: Context, completion: @escaping (StatusEntry) -> Void) { completion(entry()) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<StatusEntry>) -> Void) {
        completion(Timeline(entries: [entry()], policy: .after(.now.addingTimeInterval(15 * 60))))
    }
    private func entry() -> StatusEntry {
        let d = Shared.defaults
        return StatusEntry(date: .now, recording: d.bool(forKey: Shared.Key.isRecording), startedAt: d.object(forKey: Shared.Key.startedAt) as? Date,
                           speaker: d.string(forKey: Shared.Key.currentSpeaker), speakerColor: d.string(forKey: Shared.Key.currentColor),
                           lastTitle: d.string(forKey: Shared.Key.lastTitle), lastDate: d.object(forKey: Shared.Key.lastDate) as? Date,
                           lastSpeakers: d.stringArray(forKey: Shared.Key.lastSpeakers) ?? [])
    }
}

struct RekordStatusWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "RekordStatus", provider: StatusProvider()) { e in
            StatusWidgetView(e: e).containerBackground(for: .widget) { Color.black }
        }
        .configurationDisplayName("REKORD Status")
        .description("Läuft eine Aufnahme? Wer spricht? Letztes Meeting.")
        .supportedFamilies([.accessoryRectangular, .accessoryInline, .systemSmall, .systemMedium])
    }
}

struct StatusWidgetView: View {
    let e: StatusEntry
    @Environment(\.widgetFamily) var family

    var body: some View {
        switch family {
        case .accessoryInline:
            if e.recording, let s = e.startedAt { Text("● REKORD \(s, style: .timer)") } else { Text("REKORD · \(e.lastTitle ?? "bereit")") }
        case .accessoryRectangular:
            VStack(alignment: .leading, spacing: 1) {
                if e.recording, let s = e.startedAt {
                    HStack { Image(systemName: "record.circle.fill"); Text(s, style: .timer).monospacedDigit() }.font(.headline)
                    Text(e.speaker ?? "Hört zu …").font(.body.weight(.bold)).lineLimit(1)
                } else {
                    Text("REKORD").font(.headline.weight(.black))
                    Text(e.lastTitle ?? "Tippen zum Aufnehmen").font(.caption).lineLimit(2)
                }
            }
            .widgetURL(URL(string: "rekord://record"))
        default:
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("REKORD").font(.system(size: 15, weight: .black)).foregroundStyle(.white)
                    Circle().fill(Shared.accent).frame(width: 6, height: 6).offset(y: -5)
                    Spacer()
                    if e.recording { Circle().fill(.red).frame(width: 9, height: 9) }
                }
                Spacer()
                if e.recording, let s = e.startedAt {
                    Text(s, style: .timer).font(.system(size: 26, weight: .black, design: .rounded)).foregroundStyle(.white).monospacedDigit()
                    Text(e.speaker ?? "Hört zu …").font(.headline.weight(.heavy)).foregroundStyle(Color(hex: e.speakerColor ?? "#FFFFFF"))
                } else {
                    Text(e.lastTitle ?? "Noch nichts aufgenommen").font(.headline.weight(.heavy)).foregroundStyle(.white).lineLimit(2)
                    if !e.lastSpeakers.isEmpty { Text(e.lastSpeakers.joined(separator: " · ")).font(.caption).foregroundStyle(.white.opacity(0.6)).lineLimit(1) }
                    if family == .systemMedium {
                        Button(intent: StartRecordingIntent()) { Label("Aufnehmen", systemImage: "record.circle") }.tint(.red)
                    }
                }
            }
            .widgetURL(URL(string: "rekord://record"))
        }
    }
}

// MARK: - Lock screen circular record button

struct RekordRecordButtonWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "RekordRecordButton", provider: StatusProvider()) { e in
            ZStack {
                AccessoryWidgetBackground()
                Image(systemName: e.recording ? "waveform" : "record.circle").font(.system(size: 26, weight: .semibold))
            }
            .widgetURL(URL(string: "rekord://record"))
            .containerBackground(for: .widget) { Color.clear }
        }
        .configurationDisplayName("Aufnahme-Knopf")
        .description("Ein Tipp auf dem Sperrbildschirm startet die Aufnahme.")
        .supportedFamilies([.accessoryCircular])
    }
}

// MARK: - Control (Control Center, Lock Screen controls, Action Button) – iOS 18

struct RekordRecordControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "app.rekord.record") {
            ControlWidgetButton(action: StartRecordingIntent()) {
                Label(Shared.defaults.bool(forKey: Shared.Key.isRecording) ? "REKORD läuft" : "REKORD Aufnahme",
                      systemImage: Shared.defaults.bool(forKey: Shared.Key.isRecording) ? "waveform" : "record.circle")
            }
        }
        .displayName("REKORD Aufnahme")
        .description("Startet eine Live-Aufnahme mit Sprecher-Erkennung.")
    }
}
