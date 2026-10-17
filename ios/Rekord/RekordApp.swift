import SwiftUI

@main
struct RekordApp: App {
    @StateObject private var settings = AppSettings.shared
    @StateObject private var recorder = LiveRecorder.shared
    @StateObject private var hub = HubClient.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(settings)
                .environmentObject(recorder)
                .environmentObject(hub)
                .tint(settings.accent)
                .preferredColorScheme(settings.colorScheme)
                .onOpenURL { url in
                    // rekord://record  (lock screen widget) · rekord://pair?d=<json> (QR from the hub)
                    if url.host == "record" {
                        settings.selectedTab = .live
                        if !recorder.isRecording { Task { await recorder.start(title: nil) } }
                    }
                }
                .task { await hub.refreshStatus(); await recorder.flushPendingUploads() }
        }
    }
}

enum Tab: Hashable { case live, library, people, settings }

struct RootView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var hub: HubClient

    var body: some View {
        if !settings.isPaired {
            PairingView()
        } else {
            TabView(selection: $settings.selectedTab) {
                LiveView().tabItem { Label("Live", systemImage: "record.circle") }.tag(Tab.live)
                LibraryView().tabItem { Label("Aufnahmen", systemImage: "list.bullet") }.tag(Tab.library)
                PeopleView().tabItem { Label("Personen", systemImage: "person.2") }.tag(Tab.people)
                SettingsView().tabItem { Label("Einstellungen", systemImage: "gearshape") }.tag(Tab.settings)
            }
        }
    }
}
