import AVFoundation
import SwiftUI

struct LibraryView: View {
    @EnvironmentObject var hub: HubClient
    @State private var items: [RecordingItem] = []
    @State private var query = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            List {
                if let error { Text(error).foregroundStyle(.orange).font(.footnote) }
                ForEach(items) { r in
                    NavigationLink(value: r.id) { row(r) }
                }
            }
            .listStyle(.plain)
            .navigationTitle("Aufnahmen")
            .navigationDestination(for: String.self) { DetailView(id: $0) }
            .searchable(text: $query, prompt: "Suchen – auch im Gesagten")
            .onSubmit(of: .search) { Task { await load() } }
            .onChange(of: query) { _, q in if q.isEmpty { Task { await load() } } }
            .refreshable { await load() }
            .task { await load() }
            .overlay { if items.isEmpty && error == nil { ContentUnavailableView("Noch keine Aufnahmen", systemImage: "waveform", description: Text("Im Live-Tab aufnehmen.")) } }
        }
    }

    private func row(_ r: RecordingItem) -> some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(spacing: 0) {
                Text(r.date.formatted(.dateTime.day())).font(.system(size: 24, weight: .black))
                Text(r.date.formatted(.dateTime.month(.abbreviated))).font(.caption2.weight(.bold)).foregroundStyle(.secondary).textCase(.uppercase)
            }
            .frame(width: 44)
            VStack(alignment: .leading, spacing: 5) {
                Text(r.title).font(.headline.weight(.heavy))
                HStack(spacing: 6) {
                    Text("\(r.date.formatted(date: .omitted, time: .shortened)) · \(fmt(r.duration ?? 0))")
                    if r.status != "done" { Text(r.status == "error" ? "Fehler" : (r.stage ?? "…")).foregroundStyle(.tint).fontWeight(.semibold) }
                }
                .font(.caption).foregroundStyle(.secondary)
                if let s = r.speakers, !s.isEmpty {
                    HStack(spacing: 6) {
                        ForEach(s.prefix(4), id: \.self) { sp in
                            HStack(spacing: 4) { Circle().fill(Color(hex: sp.color)).frame(width: 6, height: 6); Text(sp.name) }
                                .font(.caption2.weight(.semibold)).padding(.horizontal, 7).padding(.vertical, 3)
                                .background(Capsule().fill(Color(.tertiarySystemBackground)))
                        }
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func load() async {
        do { items = try await hub.recordings(query: query); error = nil } catch { self.error = error.localizedDescription }
    }
}

struct DetailView: View {
    let id: String
    @EnvironmentObject var hub: HubClient
    @State private var rec: RecordingDetail?
    @State private var tab = 0
    @State private var player: AVPlayer?
    @State private var playing = false
    @State private var templates: [Template] = []
    @State private var streaming: String?
    @State private var question = ""
    @State private var answer: String?
    @State private var error: String?

    var body: some View {
        ScrollView {
            if let rec {
                VStack(alignment: .leading, spacing: 16) {
                    Text(rec.title).font(.system(size: 32, weight: .black))
                    Text("\(Date(timeIntervalSince1970: rec.created_at).formatted()) · \(fmt(rec.duration ?? 0))").font(.footnote).foregroundStyle(.secondary)
                    if rec.status != "done" {
                        VStack(alignment: .leading) {
                            Text(rec.stage ?? "In Warteschlange").font(.subheadline.bold())
                            ProgressView(value: rec.progress ?? 0)
                        }
                        .padding().background(RoundedRectangle(cornerRadius: 14).fill(Color(.secondarySystemBackground)))
                    }
                    playerBar
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack { ForEach(rec.speakers) { s in speakerChip(s) } }
                    }
                    Picker("", selection: $tab) {
                        Text("Zusammenfassung").tag(0); Text("Transkript").tag(1); Text("Fragen").tag(2)
                    }
                    .pickerStyle(.segmented)
                    if tab == 0 { summaries(rec) } else if tab == 1 { transcript(rec) } else { ask }
                    if let error { Text(error).foregroundStyle(.red).font(.footnote) }
                }
                .padding(16)
            } else {
                ProgressView().padding(60)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task { await load(); templates = (try? await hub.templates()) ?? [] }
        .refreshable { await load() }
        .onDisappear { player?.pause() }
    }

    private var playerBar: some View {
        HStack(spacing: 16) {
            Button { seek(-15) } label: { Image(systemName: "gobackward.15") }
            Button {
                if player == nil, let u = try? hub.audioURL(id) { player = AVPlayer(url: u) }
                playing ? player?.pause() : player?.play()
                playing.toggle()
            } label: { Image(systemName: playing ? "pause.circle.fill" : "play.circle.fill").font(.system(size: 44)) }
            Button { seek(15) } label: { Image(systemName: "goforward.15") }
            Spacer()
        }
        .font(.title3)
    }

    private func seek(_ d: Double) {
        guard let p = player else { return }
        p.seek(to: CMTime(seconds: max(0, p.currentTime().seconds + d), preferredTimescale: 600))
    }

    private func seekTo(_ t: Double) {
        if player == nil, let u = try? hub.audioURL(id) { player = AVPlayer(url: u) }
        player?.seek(to: CMTime(seconds: t, preferredTimescale: 600))
        player?.play(); playing = true
    }

    private func speakerChip(_ s: Speaker) -> some View {
        HStack(spacing: 8) {
            Text(initials(s.name)).font(.caption.weight(.heavy)).foregroundStyle(.white).frame(width: 26, height: 26).background(Circle().fill(Color(hex: s.color)))
            VStack(alignment: .leading, spacing: 0) {
                Text(s.name).font(.subheadline.bold())
                Text(s.profile_id != nil ? "erkannt" : "unbekannt").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 6).padding(.leading, 6).padding(.trailing, 12)
        .background(Capsule().stroke(Color(.separator)))
        .contextMenu {
            Button("Umbenennen & Stimme merken") { rename(s) }
        }
        .onTapGesture { rename(s) }
    }

    private func rename(_ s: Speaker) {
        // UIKit alert with text field (works in context menus and taps alike)
        let a = UIAlertController(title: "Wer ist das?", message: "Stimme wird gespeichert und künftig automatisch erkannt.", preferredStyle: .alert)
        a.addTextField { $0.text = s.name.hasPrefix("Sprecher ") ? "" : s.name; $0.placeholder = "Name" }
        a.addAction(UIAlertAction(title: "Abbrechen", style: .cancel))
        a.addAction(UIAlertAction(title: "Merken", style: .default) { _ in
            let name = a.textFields?.first?.text?.trimmingCharacters(in: .whitespaces) ?? ""
            guard !name.isEmpty else { return }
            Task {
                do { try await hub.send("/api/speakers/\(s.id)", method: "PATCH", json: ["name": name, "remember": true]); await load() }
                catch { self.error = error.localizedDescription }
            }
        })
        UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first?.rootViewController?.topMost.present(a, animated: true)
    }

    @ViewBuilder private func summaries(_ rec: RecordingDetail) -> some View {
        Menu {
            ForEach(templates.filter { $0.id != "mindmap" }) { t in
                Button(t.name) { generate(t.id) }
            }
        } label: { Label("Zusammenfassen mit Vorlage …", systemImage: "sparkles") }
            .buttonStyle(.borderedProminent)
            .disabled(streaming != nil || rec.segments.isEmpty)
        if let streaming { MarkdownView(text: streaming, onSeek: seekTo).padding().background(card) }
        ForEach(rec.summaries.filter { $0.template_id != "mindmap" }) { s in
            VStack(alignment: .leading, spacing: 8) {
                HStack { Text(s.title.uppercased()).font(.caption.weight(.bold)).tracking(1.4).foregroundStyle(.secondary); Spacer()
                    ShareLink(item: s.content) { Image(systemName: "square.and.arrow.up") } }
                MarkdownView(text: s.content, onSeek: seekTo)
            }
            .padding().background(card)
        }
    }

    private var card: some View { RoundedRectangle(cornerRadius: 16).fill(Color(.secondarySystemBackground)) }

    private func transcript(_ rec: RecordingDetail) -> some View {
        LazyVStack(alignment: .leading, spacing: 12) {
            ForEach(rec.segments) { seg in
                let sp = rec.speakers.first { $0.id == seg.speaker_id }
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(sp?.name ?? "?").font(.footnote.weight(.heavy)).foregroundStyle(Color(hex: sp?.color ?? "#888"))
                        Text(fmt(seg.start)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        if (rec.highlights ?? []).contains(where: { $0 >= seg.start - 2 && $0 <= seg.end + 2 }) { Image(systemName: "star.fill").font(.caption2).foregroundStyle(.tint) }
                    }
                    Text(seg.text).textSelection(.enabled)
                }
                .contentShape(Rectangle())
                .onTapGesture { seekTo(seg.start) }
            }
        }
    }

    private var ask: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                TextField("Frag etwas zu dieser Aufnahme …", text: $question, axis: .vertical).textFieldStyle(.roundedBorder)
                Button { askNow() } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }.disabled(question.isEmpty)
            }
            if let answer { MarkdownView(text: answer, onSeek: seekTo).padding().background(card) }
        }
    }

    private func askNow() {
        let q = question; question = ""; answer = ""
        Task {
            do { try await hub.stream("/api/recordings/\(id)/ask", json: ["question": q]) { t in Task { @MainActor in answer = t } } }
            catch { self.error = error.localizedDescription }
        }
    }

    private func generate(_ tid: String) {
        streaming = ""
        Task {
            do { try await hub.stream("/api/recordings/\(id)/summaries", json: ["template_id": tid]) { t in Task { @MainActor in streaming = t } } }
            catch { self.error = error.localizedDescription }
            streaming = nil
            await load()
        }
    }

    private func load() async {
        do { rec = try await hub.recording(id); error = nil } catch { self.error = error.localizedDescription }
    }
}

extension UIViewController {
    var topMost: UIViewController { presentedViewController?.topMost ?? self }
}

/// Lightweight Markdown renderer: headings, bullets, checkboxes, quotes, tables (as rows), inline bold/italic/links, [mm:ss] seek.
struct MarkdownView: View {
    let text: String
    var onSeek: (Double) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(text.components(separatedBy: "\n").enumerated()), id: \.offset) { _, raw in
                line(raw)
            }
        }
        .environment(\.openURL, OpenURLAction { url in
            if url.scheme == "seek", let t = Double(url.host ?? "") { onSeek(t); return .handled }
            return .systemAction
        })
    }

    @ViewBuilder private func line(_ raw: String) -> some View {
        let l = raw.trimmingCharacters(in: .whitespaces)
        if l.hasPrefix("# ") { Text(inline(String(l.dropFirst(2)))).font(.title2.weight(.black)).padding(.top, 4) }
        else if l.hasPrefix("## ") { Text(inline(String(l.dropFirst(3)))).font(.headline.weight(.heavy)).padding(.top, 8) }
        else if l.hasPrefix("### ") || l.hasPrefix("#### ") { Text(inline(l.drop { $0 == "#" }.trimmingCharacters(in: .whitespaces))).font(.subheadline.bold()) }
        else if l.hasPrefix("- [ ] ") || l.hasPrefix("- [x] ") || l.hasPrefix("- [X] ") {
            Label { Text(inline(String(l.dropFirst(6)))) } icon: { Image(systemName: l.hasPrefix("- [ ]") ? "square" : "checkmark.square.fill") }
        }
        else if l.hasPrefix("- ") || l.hasPrefix("* ") {
            HStack(alignment: .firstTextBaseline, spacing: 8) { Text("•").bold(); Text(inline(String(l.dropFirst(2)))) }
                .padding(.leading, CGFloat(raw.prefix { $0 == " " }.count) * 6)
        }
        else if l.hasPrefix("> ") { Text(inline(String(l.dropFirst(2)))).italic().padding(.leading, 10).overlay(alignment: .leading) { Rectangle().fill(.tint).frame(width: 3) } }
        else if l.hasPrefix("|") {
            if !l.contains("---") { Text(inline(l.trimmingCharacters(in: CharacterSet(charactersIn: "|")).replacingOccurrences(of: "|", with: "  ·  "))).font(.callout) }
        }
        else if !l.isEmpty { Text(inline(l)) }
    }

    private func inline(_ s: String) -> AttributedString {
        // [mm:ss] → seek://seconds links
        var md = s
        let re = try! NSRegularExpression(pattern: #"\[((?:\d+:)?\d{1,2}:\d{2})\]"#)
        for m in re.matches(in: s, range: NSRange(s.startIndex..., in: s)).reversed() {
            guard let r = Range(m.range(at: 1), in: s), let full = Range(m.range, in: md) else { continue }
            let ts = String(s[r])
            let secs = ts.split(separator: ":").reduce(0) { $0 * 60 + (Int($1) ?? 0) }
            md.replaceSubrange(full, with: "[\(ts)](seek://\(secs))")
        }
        md = md.replacingOccurrences(of: #"\[\[[a-f0-9]+@([\d:]+)\]\]"#, with: "($1)", options: .regularExpression)
        return (try? AttributedString(markdown: md, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(s)
    }
}
