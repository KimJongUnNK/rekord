import Foundation
import Network

// MARK: - DTOs (mirror the hub's JSON)

struct SpeakerChip: Codable, Hashable { let name: String; let color: String }

struct RecordingItem: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let created_at: Double
    let duration: Double?
    let status: String
    let stage: String?
    let progress: Double?
    let language: String?
    let speakers: [SpeakerChip]?
    var date: Date { Date(timeIntervalSince1970: created_at) }
}

struct Speaker: Codable, Identifiable, Hashable {
    let id: Int
    let label: Int
    let name: String
    let color: String
    let profile_id: Int?
    let match_score: Double?
}

struct Segment: Codable, Identifiable, Hashable {
    let id: Int
    let start: Double
    let end: Double
    let speaker_id: Int?
    var text: String
}

struct Summary: Codable, Identifiable, Hashable {
    let id: Int
    let template_id: String
    let title: String
    let content: String
    let model: String?
    let created_at: Double
}

struct RecordingDetail: Codable {
    let id: String
    let title: String
    let created_at: Double
    let duration: Double?
    let status: String
    let stage: String?
    let progress: Double?
    let highlights: [Double]?
    let speakers: [Speaker]
    let segments: [Segment]
    let summaries: [Summary]
}

struct Profile: Codable, Identifiable, Hashable {
    let id: Int
    let name: String
    let color: String
    let samples: Int
    let recordings: Int
}

struct HubStatus: Codable {
    let version: String
    let ready: Bool
    let provider: String
    let provider_name: String?
    let model: String?
    let jobs_pending: Int
}

struct Template: Codable, Identifiable, Hashable { let id: String; let name: String; let category: String }

struct PairPayload: Codable { let rekord: Int; let urls: [String]; let token: String }

// MARK: - Client

@MainActor
final class HubClient: ObservableObject {
    static let shared = HubClient()
    @Published var status: HubStatus?
    @Published var reachable = false
    @Published var discovered: [NWBrowser.Result] = []

    private var settings: AppSettings { AppSettings.shared }
    private var browser: NWBrowser?

    enum HubError: LocalizedError {
        case notPaired, http(Int, String)
        var errorDescription: String? {
            switch self {
            case .notPaired: return "Kein Hub gekoppelt."
            case .http(let c, let m): return "Hub-Fehler \(c): \(m)"
            }
        }
    }

    func url(_ path: String, query: [URLQueryItem] = []) throws -> URL {
        guard var c = URLComponents(string: settings.hubURL) else { throw HubError.notPaired }
        let parts = path.split(separator: "?", maxSplits: 1)
        c.path = String(parts[0])
        var q = query
        if parts.count > 1 { q += URLComponents(string: "?" + parts[1])?.queryItems ?? [] }
        q.append(URLQueryItem(name: "token", value: settings.hubToken))
        c.queryItems = q
        guard let u = c.url else { throw HubError.notPaired }
        return u
    }

    func wsURL(_ path: String) throws -> URL {
        var c = URLComponents(url: try url(path), resolvingAgainstBaseURL: false)!
        c.scheme = c.scheme == "https" ? "wss" : "ws"
        return c.url!
    }

    private func request(_ path: String, method: String = "GET", json: Any? = nil) async throws -> Data {
        var r = URLRequest(url: try url(path))
        r.httpMethod = method
        r.timeoutInterval = 30
        r.setValue(settings.hubToken, forHTTPHeaderField: "X-Rekord-Token")
        if let json {
            r.httpBody = try JSONSerialization.data(withJSONObject: json)
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, resp) = try await URLSession.shared.data(for: r)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw HubError.http(code, msg ?? String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    func get<T: Decodable>(_ path: String, as: T.Type = T.self) async throws -> T {
        try JSONDecoder().decode(T.self, from: try await request(path))
    }

    @discardableResult
    func send(_ path: String, method: String = "POST", json: Any? = nil) async throws -> Data {
        try await request(path, method: method, json: json)
    }

    func refreshStatus() async {
        guard settings.isPaired else { return }
        do { status = try await get("/api/status"); reachable = true } catch { reachable = false }
    }

    // MARK: recordings
    struct RecList: Codable { let items: [RecordingItem] }
    func recordings(query: String = "") async throws -> [RecordingItem] {
        let q = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        return try await get("/api/recordings?q=\(q)", as: RecList.self).items
    }
    func recording(_ id: String) async throws -> RecordingDetail { try await get("/api/recordings/\(id)") }
    func audioURL(_ id: String) throws -> URL { try url("/api/recordings/\(id)/audio") }

    struct ProfList: Codable { let items: [Profile] }
    func profiles() async throws -> [Profile] { try await get("/api/profiles", as: ProfList.self).items }

    struct TplList: Codable { let items: [Template] }
    func templates() async throws -> [Template] { try await get("/api/templates", as: TplList.self).items }

    /// Streams an LLM answer (summary / ask). Calls `onText` with the full text so far.
    func stream(_ path: String, json: [String: Any], onText: @escaping (String) -> Void) async throws {
        var r = URLRequest(url: try url(path))
        r.httpMethod = "POST"
        r.httpBody = try JSONSerialization.data(withJSONObject: json)
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.timeoutInterval = 600
        let (bytes, _) = try await URLSession.shared.bytes(for: r)
        var buf = Data()
        for try await b in bytes {
            buf.append(b)
            if b == 0x0A || buf.count % 64 == 0, let s = String(data: buf, encoding: .utf8) {
                if let e = s.range(of: "\u{0}ERROR:") { throw HubError.http(500, String(s[e.upperBound...])) }
                onText(s)
            }
        }
        if let s = String(data: buf, encoding: .utf8) {
            if let e = s.range(of: "\u{0}ERROR:") { throw HubError.http(500, String(s[e.upperBound...])) }
            onText(s)
        }
    }

    /// Multipart upload (offline recordings, voice samples).
    func upload(path: String, fileURL: URL, fileField: String, fields: [String: String]) async throws -> Data {
        let boundary = "rekord-\(UUID().uuidString)"
        var body = Data()
        for (k, v) in fields {
            body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(k)\"\r\n\r\n\(v)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(fileField)\"; filename=\"\(fileURL.lastPathComponent)\"\r\nContent-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
        body.append(try Data(contentsOf: fileURL))
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        var r = URLRequest(url: try url(path))
        r.httpMethod = "POST"
        r.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        r.timeoutInterval = 600
        let (data, resp) = try await URLSession.shared.upload(for: r, from: body)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else { throw HubError.http(code, String(data: data, encoding: .utf8) ?? "") }
        return data
    }

    // MARK: pairing

    /// Tries every URL from the QR code and keeps the first one that answers.
    func pair(with payload: PairPayload) async -> Bool {
        for u in payload.urls {
            guard let url = URL(string: u + "/api/status?token=\(payload.token)") else { continue }
            var r = URLRequest(url: url)
            r.timeoutInterval = 4
            if let (_, resp) = try? await URLSession.shared.data(for: r), (resp as? HTTPURLResponse)?.statusCode == 200 {
                settings.hubURL = u
                settings.hubToken = payload.token
                await refreshStatus()
                return true
            }
        }
        return false
    }

    /// Manual pairing: the hub's address plus the 6-digit code shown on the computer (a long key still works).
    /// The code is traded for this iPhone's own key.
    func pair(url: String, token: String) async -> Bool {
        let clean = url.trimmingCharacters(in: .whitespaces).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let withScheme = clean.hasPrefix("http") ? clean : "http://\(clean)"
        let digits = token.filter(\.isNumber)
        guard digits.count == 6, digits.count == token.filter({ !$0.isWhitespace && $0 != "-" }).count else {
            return await pair(with: PairPayload(rekord: 1, urls: [withScheme], token: token.trimmingCharacters(in: .whitespaces)))
        }
        guard let claimURL = URL(string: withScheme + "/api/pair/claim") else { return false }
        var r = URLRequest(url: claimURL)
        r.httpMethod = "POST"
        r.timeoutInterval = 6
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.httpBody = try? JSONSerialization.data(withJSONObject: ["code": digits, "name": "iPhone-App"])
        guard let (data, resp) = try? await URLSession.shared.data(for: r), (resp as? HTTPURLResponse)?.statusCode == 200,
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let key = obj["token"] as? String
        else { return false }
        return await pair(with: PairPayload(rekord: 1, urls: [withScheme], token: key))
    }

    // MARK: Bonjour discovery (_rekord._tcp)

    func startDiscovery() {
        let b = NWBrowser(for: .bonjour(type: "_rekord._tcp", domain: nil), using: .tcp)
        b.browseResultsChangedHandler = { [weak self] results, _ in
            Task { @MainActor in self?.discovered = Array(results) }
        }
        b.start(queue: .main)
        browser = b
    }

    func stopDiscovery() { browser?.cancel(); browser = nil }

    /// Resolves a Bonjour result to "http://ip:port".
    func resolve(_ result: NWBrowser.Result) async -> String? {
        await withCheckedContinuation { cont in
            let conn = NWConnection(to: result.endpoint, using: .tcp)
            var done = false
            conn.stateUpdateHandler = { state in
                guard !done else { return }
                if case .ready = state, case .hostPort(let host, let port)? = conn.currentPath?.remoteEndpoint {
                    done = true
                    var h = "\(host)"
                    if let pct = h.firstIndex(of: "%") { h = String(h[..<pct]) }  // strip interface scope
                    if h.contains(":") { h = "[\(h)]" }
                    conn.cancel()
                    cont.resume(returning: "http://\(h):\(port)")
                } else if case .failed = state {
                    done = true
                    conn.cancel()
                    cont.resume(returning: nil)
                }
            }
            conn.start(queue: .global())
        }
    }
}
