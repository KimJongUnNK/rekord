import SwiftUI

struct LiveView: View {
    @EnvironmentObject var rec: LiveRecorder
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var hub: HubClient
    @State private var title = ""
    @State private var people: [Profile] = []
    @State private var naming: LiveRecorder.RosterItem?
    @State private var newName = ""
    @State private var showIntro = false
    @State private var openRecording: String?
    @State private var askWho = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header
                    stage
                    if !rec.isRecording { setup }
                    if !rec.roster.isEmpty { roster }
                    if !rec.lines.isEmpty { feed }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 40)
            }
            .navigationDestination(item: $openRecording) { id in DetailView(id: id) }
            .task { people = (try? await hub.profiles()) ?? [] }
            .onChange(of: rec.lastSavedId) { _, id in if let id, !rec.isRecording { openRecording = id } }
            .alert("Wer ist das?", isPresented: Binding(get: { naming != nil }, set: { if !$0 { naming = nil } })) {
                TextField("Name", text: $newName)
                Button("Abbrechen", role: .cancel) {}
                Button("Merken") { if let k = naming?.key, !newName.isEmpty { rec.nameSpeaker(key: k, name: newName) }; newName = "" }
            } message: { Text("Die Stimme wird gespeichert und ab jetzt automatisch erkannt.") }
            .sheet(isPresented: $askWho) {
                WhoSheet(people: $people) { go in
                    askWho = false
                    if go { Task { await rec.start(title: title) } }
                }
                .environmentObject(settings).environmentObject(hub)
            }
            .sheet(isPresented: $showIntro) {
                EnrollSheet(intro: true) { prof in
                    if let prof { settings.participants = Array(Set(settings.participants + [prof.id])) }
                    Task { people = (try? await hub.profiles()) ?? [] }
                }
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("LIVE · SPRECHER-ERKENNUNG").font(.caption.weight(.bold)).tracking(1.6).foregroundStyle(.secondary)
            if rec.isRecording {
                TimelineView(.periodic(from: .now, by: 1)) { _ in
                    Text(fmt(rec.elapsed)).font(.system(size: 44, weight: .black, design: .rounded)).monospacedDigit()
                }
            } else {
                TextField("Meeting \(Date().formatted(.dateTime.day().month()))", text: $title)
                    .font(.system(size: 34, weight: .black)).textInputAutocapitalization(.sentences)
            }
            if let e = rec.error { Text(e).font(.footnote).foregroundStyle(.orange) }
        }
        .padding(.top, 8)
    }

    private var stage: some View {
        let n = rec.now
        let color = Color(hex: n?.color ?? "#8A877F")
        return VStack(spacing: 18) {
            HStack {
                Circle().fill(rec.isRecording && !rec.paused ? .red : .secondary).frame(width: 9, height: 9)
                Text(rec.isRecording ? (rec.paused ? "PAUSE" : rec.offline ? "AUFNAHME (OFFLINE)" : "LIVE") : "BEREIT")
                    .font(.caption.weight(.heavy)).tracking(1.6)
                Spacer()
                if rec.highlights.count > 0 { Label("\(rec.highlights.count)", systemImage: "star.fill").font(.caption.bold()).foregroundStyle(settings.accent) }
            }
            ZStack {
                Circle().stroke(color.opacity(0.3 + Double(rec.level) * 0.7), lineWidth: 3)
                    .frame(width: 150 + CGFloat(rec.level) * 50, height: 150 + CGFloat(rec.level) * 50)
                    .animation(.easeOut(duration: 0.12), value: rec.level)
                Circle().fill(color.opacity(0.16)).frame(width: 140, height: 140)
                Text(n.map { $0.silence ? "·" : initials($0.name) } ?? "·").font(.system(size: 50, weight: .black)).foregroundStyle(color)
            }
            .frame(height: 210)
            VStack(spacing: 6) {
                Text(n.map { $0.silence ? "Stille" : $0.name } ?? (rec.isRecording ? "…" : "Wer spricht?"))
                    .font(.system(size: 40, weight: .black)).minimumScaleFactor(0.5).lineLimit(1)
                    .foregroundStyle(n?.known == true && n?.silence == false ? .primary : .secondary)
                Text(subtitle(n)).font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
            }
            .contentTransition(.opacity)
            .animation(.easeInOut(duration: 0.25), value: n?.name)
            HStack(spacing: 22) {
                ctl("star.fill", disabled: !rec.isRecording) { rec.highlight() }
                Button {
                    // before every recording: how many people talk, who of them REKORD knows
                    if rec.isRecording { Task { await rec.stop() } } else { askWho = true }
                } label: {
                    ZStack {
                        Circle().stroke(.primary, lineWidth: 4).frame(width: 80, height: 80)
                        RoundedRectangle(cornerRadius: rec.isRecording ? 8 : 28).fill(.red)
                            .frame(width: rec.isRecording ? 30 : 56, height: rec.isRecording ? 30 : 56)
                    }
                }
                .disabled(rec.stopping)
                .sensoryFeedback(.impact, trigger: rec.isRecording)
                .accessibilityLabel(rec.isRecording ? "Aufnahme stoppen" : "Aufnahme starten")
                ctl(rec.paused ? "play.fill" : "pause.fill", disabled: !rec.isRecording) { rec.togglePause() }
            }
            if rec.stopping { ProgressView("Speichert …").font(.footnote) }
        }
        .padding(20)
        .background(RoundedRectangle(cornerRadius: 24).fill(Color(.secondarySystemBackground)))
    }

    private func subtitle(_ n: LiveRecorder.Now?) -> String {
        guard let n else { return rec.isRecording ? "Hört zu …" : "Start drücken – REKORD zeigt live, wer redet." }
        if n.silence { return "" }
        if n.known { return "erkannt · \(Int(n.score * 100)) %" }
        return n.key == nil ? "Noch nicht zugeordnet" : "Unten bei „Im Raum“ antippen, um sie zu benennen"
    }

    private func ctl(_ icon: String, disabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon).font(.title3).frame(width: 56, height: 56).background(Circle().fill(Color(.tertiarySystemBackground)))
        }
        .disabled(disabled).opacity(disabled ? 0.35 : 1)
    }

    // MARK: who is in the meeting (asked again before every recording)
    private var setup: some View {
        let known = people.filter { settings.participants.contains($0.id) }
        let total = max(settings.whoTotal, known.count)
        return VStack(alignment: .leading, spacing: 12) {
            Text("WER IST DABEI?").font(.caption.weight(.bold)).tracking(1.6).foregroundStyle(.secondary)
            if total > 0 {
                Text("\(total) \(total == 1 ? "Person" : "Personen")" + (known.isEmpty ? "" : ": " + known.map(\.name).joined(separator: ", "))
                     + (total - known.count > 0 ? " + \(total - known.count) neu" : "")).fontWeight(.semibold)
                Text("Wird beim Start nochmal bestätigt.").font(.footnote).foregroundStyle(.secondary)
            } else {
                Text("Fragt REKORD beim Start: wie viele ihr seid und wer schon bekannt ist – so erkennt es jede Stimme richtig.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            HStack {
                Button("Festlegen") { askWho = true }.buttonStyle(.bordered)
                Button { showIntro = true } label: { Label("Vorstellungsrunde", systemImage: "waveform.badge.plus") }.buttonStyle(.bordered)
            }
        }
        .padding(18)
        .background(RoundedRectangle(cornerRadius: 20).fill(Color(.secondarySystemBackground)))
    }

    private var roster: some View {
        let total = max(1, rec.roster.reduce(0) { $0 + $1.talk })
        return VStack(alignment: .leading, spacing: 8) {
            Text("IM RAUM").font(.caption.weight(.bold)).tracking(1.6).foregroundStyle(.secondary)
            ForEach(rec.roster) { p in
                Button { if !p.known, p.key != nil { naming = p; newName = "" } } label: {
                    HStack(spacing: 12) {
                        Text(initials(p.name)).font(.footnote.weight(.heavy)).foregroundStyle(.white)
                            .frame(width: 34, height: 34).background(Circle().fill(Color(hex: p.color)))
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name).fontWeight(.bold)
                            Text(p.waiting ? "dabei · noch still" : p.known ? "erkannt · \(fmt(p.talk))"
                                 : (p.voices ?? 1) > 1 ? "\(p.voices ?? 1) Stimmen · antippen benennt die zuletzt gehörte" : "antippen zum Benennen · \(fmt(p.talk))")
                                .font(.caption).foregroundStyle(.secondary)
                            ProgressView(value: p.talk / total).tint(Color(hex: p.color))
                        }
                        Spacer()
                    }
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 14).stroke(rec.now?.key == p.key && p.key != nil ? Color(hex: p.color) : Color(.separator),
                                                                          lineWidth: rec.now?.key == p.key && p.key != nil ? 2 : 1))
                    .opacity(p.waiting ? 0.5 : 1)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var feed: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("MITSCHRIFT").font(.caption.weight(.bold)).tracking(1.6).foregroundStyle(.secondary)
            ForEach(rec.lines.suffix(60).reversed()) { l in
                HStack(alignment: .top, spacing: 10) {
                    RoundedRectangle(cornerRadius: 2).fill(Color(hex: l.color)).frame(width: 4)
                    VStack(alignment: .leading, spacing: 2) {
                        HStack { Text(l.name).font(.footnote.bold()); Text(fmt(l.start)).font(.caption.monospacedDigit()).foregroundStyle(.secondary) }
                        Text(l.text.isEmpty ? "…" : l.text)
                    }
                }
            }
        }
    }
}

func fmt(_ t: Double) -> String {
    let s = Int(max(0, t))
    return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, s % 3600 / 60, s % 60) : String(format: "%02d:%02d", s / 60, s % 60)
}

/// Simple wrapping layout for chips.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let w = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, maxX: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > w, x > 0 { x = 0; y += rowH + spacing; rowH = 0 }
            x += s.width + spacing; rowH = max(rowH, s.height); maxX = max(maxX, x)
        }
        return CGSize(width: min(maxX, w), height: y + rowH)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > bounds.maxX, x > bounds.minX { x = bounds.minX; y += rowH + spacing; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; rowH = max(rowH, s.height)
        }
    }
}

/// "Wer ist dabei?" – required before every recording: the headcount (you included) and who of them REKORD knows.
/// With it REKORD separates exactly that many voices; unknown ones are collected as "Nicht erkannte Stimme".
struct WhoSheet: View {
    @Binding var people: [Profile]
    let done: (Bool) -> Void
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var hub: HubClient
    @State private var total = 0
    @State private var chosen: Set<Int> = []
    @State private var enrolling = false
    @State private var toEnroll = 0

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Art", selection: $settings.lecture) {
                        Text("Gespräch").tag(false)
                        Text("Vorlesung").tag(true)
                    }
                    .pickerStyle(.segmented)
                } footer: {
                    if settings.lecture {
                        Text("Eine Person trägt vor, Fragen aus dem Hörsaal sammelt REKORD unter „Publikum“. Mitzählen musst du nicht – Handy Richtung Vortrag legen.")
                    }
                }
                if !settings.lecture { Section {
                    Stepper(value: $total, in: max(1, chosen.count)...30) {
                        HStack { Text("Wie viele sprechen?"); Spacer(); Text(total > 0 ? "\(total)" : "–").font(.title2.weight(.black)).monospacedDigit() }
                    }
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack { ForEach([1, 2, 3, 4, 5, 6, 8], id: \.self) { n in
                            Button("\(n)") { total = max(n, chosen.count) }
                                .buttonStyle(.bordered).tint(total == n ? .accentColor : .secondary)
                        } }
                    }
                } footer: { Text("Dich mitgezählt. Damit weiß REKORD, wie viele Stimmen es trennen muss.") } }
                if !people.isEmpty {
                    Section(settings.lecture ? "Vortragende Person schon bekannt?" : "Wer davon ist bekannt?") {
                        ForEach(people) { p in
                            Button {
                                if chosen.contains(p.id) { chosen.remove(p.id) } else { chosen.insert(p.id); total = max(total, chosen.count) }
                            } label: {
                                HStack {
                                    Circle().fill(Color(hex: p.color)).frame(width: 10, height: 10)
                                    Text(p.name).foregroundStyle(.primary)
                                    Spacer()
                                    if chosen.contains(p.id) { Image(systemName: "checkmark").foregroundStyle(Color.accentColor) }
                                }
                            }
                        }
                    }
                }
                if total > 0 && !settings.lecture {
                    let fresh = total - chosen.count
                    Section {
                        Text(fresh == 0 ? "Geschlossene Runde: jede Stimme wird einer dieser Personen zugeordnet."
                             : "\(fresh) neu – landen unter „Nicht erkannte Stimme“. Besser: jetzt kurz einsprechen lassen, dann erkennt REKORD sie mit Namen.")
                            .font(.footnote)
                        if fresh > 0 {
                            Button { toEnroll = fresh; enrolling = true } label: {
                                Label(fresh == 1 ? "Neue Person jetzt einsprechen" : "\(fresh) neue Personen jetzt einsprechen", systemImage: "waveform.badge.plus")
                            }
                        }
                    }
                }
            }
            .navigationTitle("Wer ist dabei?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { done(false) } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Aufnahme starten") {
                        settings.participants = Array(chosen)
                        settings.guests = max(0, total - chosen.count)
                        settings.whoTotal = total
                        done(true)
                    }.disabled(total == 0 && !settings.lecture).fontWeight(.bold)
                }
            }
            .sheet(isPresented: $enrolling) {
                EnrollSheet(intro: true) { prof in
                    if let prof {
                        chosen.insert(prof.id)
                        if !people.contains(where: { $0.id == prof.id }) { people.append(prof) }
                        toEnroll -= 1
                    } else { toEnroll = 0 }
                    if toEnroll > 0 { DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { enrolling = true } }
                }
            }
            .onAppear {
                chosen = Set(settings.participants.filter { id in people.contains { $0.id == id } })
                total = settings.whoTotal > 0 ? max(settings.whoTotal, chosen.count) : 0
            }
        }
    }
}
