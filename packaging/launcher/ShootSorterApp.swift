// Shoot Sorter menu-bar launcher.
//
// Starts the bundled control panel (gui/server.py) on a free localhost port,
// opens it in the browser, and offers Start/Stop, model setup, a login item
// toggle and Quit. Settings and data live in
// ~/Library/Application Support/Shoot Sorter; the app bundle is read-only.
//
// Build: swiftc -O -target arm64-apple-macos14.0 -framework AppKit ShootSorterApp.swift -o ShootSorter

import AppKit
import Darwin

let kBundleID = "com.shootsorter.app"
let kLoginLabel = "com.shootsorter.app.login"
let kPreferredPort = 8786
// Must match SETUP_VERSION in runtime/first_run.py.
let kSetupVersion = 2
// Ports other local tools commonly use (including the script edition's 8766). Never chosen.
let kReservedPorts: Set<Int> = [8765, 8766, 8777, 11434]

func appHome() -> URL {
    if let env = ProcessInfo.processInfo.environment["SHOOT_SORTER_APP_HOME"], !env.isEmpty {
        return URL(fileURLWithPath: (env as NSString).expandingTildeInPath)
    }
    let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
    return base.appendingPathComponent("Shoot Sorter", isDirectory: true)
}

// MARK: - process helpers

/// Spawns a process in its own process group so it and its children can be stopped together.
func spawn(_ args: [String], env: [String: String], cwd: String, log: URL) -> pid_t {
    try? FileManager.default.createDirectory(at: log.deletingLastPathComponent(), withIntermediateDirectories: true)
    var fa: posix_spawn_file_actions_t?
    var attr: posix_spawnattr_t?
    posix_spawn_file_actions_init(&fa)
    posix_spawnattr_init(&attr)
    defer {
        posix_spawn_file_actions_destroy(&fa)
        posix_spawnattr_destroy(&attr)
    }
    posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0)
    posix_spawn_file_actions_addopen(&fa, 1, log.path, O_WRONLY | O_CREAT | O_APPEND, 0o644)
    posix_spawn_file_actions_adddup2(&fa, 1, 2)
    posix_spawn_file_actions_addchdir_np(&fa, cwd)
    posix_spawnattr_setflags(&attr, Int16(POSIX_SPAWN_SETPGROUP))
    posix_spawnattr_setpgroup(&attr, 0)

    let cArgs: [UnsafeMutablePointer<CChar>?] = args.map { strdup($0) } + [nil]
    let cEnv: [UnsafeMutablePointer<CChar>?] = env.map { strdup("\($0.key)=\($0.value)") } + [nil]
    defer {
        cArgs.forEach { free($0) }
        cEnv.forEach { free($0) }
    }
    var pid: pid_t = 0
    let rc = posix_spawn(&pid, args[0], &fa, &attr, cArgs, cEnv)
    return rc == 0 ? pid : 0
}

/// Returns true when the process has exited (and reaps it).
func reaped(_ pid: pid_t) -> Bool {
    if pid <= 0 { return true }
    var st: Int32 = 0
    let r = waitpid(pid, &st, WNOHANG)
    return r == pid || (r == -1 && errno == ECHILD)
}

func stopGroup(_ pid: pid_t, timeout: TimeInterval = 6) {
    guard pid > 0 else { return }
    kill(-pid, SIGTERM)
    let end = Date().addingTimeInterval(timeout)
    while Date() < end {
        if reaped(pid) {
            kill(-pid, SIGTERM)   // children that outlived the server
            return
        }
        usleep(100_000)
    }
    kill(-pid, SIGKILL)
    _ = reaped(pid)
}

func portIsFree(_ port: Int) -> Bool {
    let fd = socket(AF_INET, SOCK_STREAM, 0)
    if fd < 0 { return false }
    defer { close(fd) }
    var addr = sockaddr_in()
    addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = in_port_t(UInt16(port).bigEndian)
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    let ok = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
        }
    }
    return ok
}

func ephemeralPort() -> Int {
    let fd = socket(AF_INET, SOCK_STREAM, 0)
    if fd < 0 { return 0 }
    defer { close(fd) }
    var addr = sockaddr_in()
    addr.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = 0
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    var len = socklen_t(MemoryLayout<sockaddr_in>.size)
    let ok = withUnsafeMutablePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            bind(fd, $0, len) == 0 && getsockname(fd, $0, &len) == 0
        }
    }
    return ok ? Int(UInt16(bigEndian: addr.sin_port)) : 0
}

// MARK: - app

final class AppDelegate: NSObject, NSApplicationDelegate {
    let res = Bundle.main.resourceURL!
    let home = appHome()
    var python: String { res.appendingPathComponent("python/bin/python3").path }
    var settingsURL: URL { home.appendingPathComponent("app-settings.json") }
    var loginPlist: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(kLoginLabel).plist")
    }

    var statusItem: NSStatusItem!
    let stateItem = NSMenuItem(title: "Starting…", action: nil, keyEquivalent: "")
    let setupItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    var startStopItem: NSMenuItem!
    var loginItem: NSMenuItem!
    var setupMenuItem: NSMenuItem!

    var serverPID: pid_t = 0
    var setupPID: pid_t = 0
    var port = 0
    var ready = false
    var openWhenReady = !CommandLine.arguments.contains("--background")
    var autoSetup = !CommandLine.arguments.contains("--no-setup")
    var timer: Timer?
    var readySince: Date?

    func applicationDidFinishLaunching(_ note: Notification) {
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: kBundleID)
            .filter { $0.processIdentifier != getpid() }
        if !others.isEmpty {
            // Already running: just open its panel.
            if let p = savedPort() { NSWorkspace.shared.open(panelURL(port: p)) }
            NSApp.terminate(nil)
            return
        }
        buildMenu()
        prepareHome()
        startServer()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in self?.tick() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openPanel()
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        timer?.invalidate()
        stopGroup(setupPID, timeout: 3)
        stopGroup(serverPID)
        return .terminateNow
    }

    // MARK: menu

    func buildMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let b = statusItem.button {
            b.image = NSImage(systemSymbolName: "camera.aperture", accessibilityDescription: "Shoot Sorter")
            b.imagePosition = .imageLeading
        }
        let m = NSMenu()
        stateItem.isEnabled = false
        m.addItem(stateItem)
        setupItem.isEnabled = false
        setupItem.isHidden = true
        m.addItem(setupItem)
        m.addItem(.separator())
        m.addItem(item("Open Panel", #selector(openPanel), "o"))
        startStopItem = item("Stop Panel", #selector(toggleServer), "")
        m.addItem(startStopItem)
        m.addItem(.separator())
        setupMenuItem = item("Download Models…", #selector(runSetupFromMenu), "")
        m.addItem(setupMenuItem)
        loginItem = item("Start at Login", #selector(toggleLogin), "")
        m.addItem(loginItem)
        m.addItem(item("Show Data Folder", #selector(showData), ""))
        m.addItem(item("Show Logs", #selector(showLogs), ""))
        m.addItem(.separator())
        let ver = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        let v = NSMenuItem(title: "Shoot Sorter \(ver)", action: nil, keyEquivalent: "")
        v.isEnabled = false
        m.addItem(v)
        m.addItem(item("Quit Shoot Sorter", #selector(quit), "q"))
        statusItem.menu = m
        refreshMenu()
    }

    func item(_ title: String, _ sel: Selector, _ key: String) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: sel, keyEquivalent: key)
        i.target = self
        return i
    }

    func refreshMenu() {
        let running = serverPID > 0
        if running && ready {
            stateItem.title = "Panel running on 127.0.0.1:\(port)"
        } else if running {
            stateItem.title = "Starting panel…"
        } else {
            stateItem.title = "Panel stopped"
        }
        startStopItem.title = running ? "Stop Panel" : "Start Panel"
        loginItem.state = FileManager.default.fileExists(atPath: loginPlist.path) ? .on : .off
        setupMenuItem.isEnabled = setupPID == 0
        updateSetupStatus()
    }

    func updateSetupStatus() {
        let url = home.appendingPathComponent("logs/setup-status.json")
        guard let d = try? Data(contentsOf: url),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else {
            setupItem.isHidden = true
            statusItem.button?.title = ""
            return
        }
        let state = j["state"] as? String ?? ""
        if setupPID > 0 {
            let label = j["label"] as? String ?? "Downloading models"
            let pct = Int(((j["progress"] as? Double) ?? 0) * 100)
            let idx = j["index"] as? Int ?? 0, total = j["total"] as? Int ?? 0
            let msg = j["message"] as? String ?? ""
            setupItem.title = "\(label) \(pct)% (\(idx)/\(total))" + (msg.isEmpty ? "" : " – \(msg)")
            setupItem.isHidden = false
            statusItem.button?.title = " \(pct)%"
        } else if state == "error" {
            setupItem.title = "Model download incomplete – use Download Models…"
            setupItem.isHidden = false
            statusItem.button?.title = " !"
        } else {
            setupItem.isHidden = true
            statusItem.button?.title = ""
        }
    }

    // MARK: runtime

    func childEnv() -> [String: String] {
        var e = ProcessInfo.processInfo.environment
        for k in ["PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"] { e.removeValue(forKey: k) }
        e["SHOOT_SORTER_HOME"] = home.path
        e["SHOOT_SORTER_GUI_PORT"] = String(port)
        e["HF_HOME"] = home.appendingPathComponent("models/hf").path
        e["HF_HUB_DISABLE_TELEMETRY"] = "1"
        e["DO_NOT_TRACK"] = "1"
        e["PYTHONNOUSERSITE"] = "1"
        e["PYTHONDONTWRITEBYTECODE"] = "1"
        e["PYTHONUNBUFFERED"] = "1"
        e["PATH"] = home.appendingPathComponent("venv/bin").path + ":/usr/bin:/bin:/usr/sbin:/sbin"
        return e
    }

    func prepareHome() {
        try? FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        let log = home.appendingPathComponent("logs/app.log")
        let pid = spawn([python, res.appendingPathComponent("runtime/prepare_home.py").path, res.path, home.path],
                        env: childEnv(), cwd: home.path, log: log)
        var st: Int32 = 0
        if pid > 0 { waitpid(pid, &st, 0) }
        if pid == 0 || st != 0 {
            alert("Shoot Sorter could not prepare its data folder.", "See \(log.path)")
        }
    }

    func savedPort() -> Int? {
        guard let d = try? Data(contentsOf: settingsURL),
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return nil }
        return j["port"] as? Int
    }

    func savePort(_ p: Int) {
        var j: [String: Any] = [:]
        if let d = try? Data(contentsOf: settingsURL),
           let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] { j = o }
        j["port"] = p
        if let d = try? JSONSerialization.data(withJSONObject: j, options: [.prettyPrinted, .sortedKeys]) {
            try? d.write(to: settingsURL)
        }
    }

    func choosePort() -> Int {
        var candidates: [Int] = []
        if let p = savedPort() { candidates.append(p) }
        candidates += Array(kPreferredPort...(kPreferredPort + 12))
        for p in candidates where !kReservedPorts.contains(p) && portIsFree(p) { return p }
        for _ in 0..<10 {
            let p = ephemeralPort()
            if p > 0 && !kReservedPorts.contains(p) { return p }
        }
        return 0
    }

    func startServer() {
        guard serverPID == 0 else { return }
        port = choosePort()
        guard port > 0 else {
            alert("No free local port for the control panel.", "")
            return
        }
        savePort(port)
        ready = false
        readySince = nil
        let server = home.appendingPathComponent("gui/server.py").path
        serverPID = spawn([python, server], env: childEnv(), cwd: home.path,
                          log: home.appendingPathComponent("logs/gui/server.out.log"))
        if serverPID == 0 {
            alert("The control panel failed to start.", "See \(home.path)/logs/gui/server.out.log")
        }
        refreshMenu()
    }

    @objc func toggleServer() {
        if serverPID > 0 {
            stopGroup(serverPID)
            serverPID = 0
            ready = false
        } else {
            openWhenReady = true
            startServer()
        }
        refreshMenu()
    }

    func tick() {
        if serverPID > 0 && reaped(serverPID) {
            serverPID = 0
            ready = false
        }
        if setupPID > 0 && reaped(setupPID) {
            setupPID = 0
        }
        if serverPID > 0 && !ready { probe() }
        refreshMenu()
    }

    func probe() {
        let p = port
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(p)/api/login_status")!)
        req.timeoutInterval = 1
        URLSession.shared.dataTask(with: req) { [weak self] _, resp, _ in
            guard let self, (resp as? HTTPURLResponse) != nil else { return }
            DispatchQueue.main.async {
                guard !self.ready, self.port == p else { return }
                self.ready = true
                self.refreshMenu()
                if self.openWhenReady { self.openPanel() }
                self.openWhenReady = false
                if self.autoSetup { self.maybeRunSetup() }
            }
        }.resume()
    }

    func panelURL(port: Int) -> URL {
        let tokFile = home.appendingPathComponent("gui/auth.token")
        let tok = (try? String(contentsOf: tokFile, encoding: .utf8))?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        var c = URLComponents(string: "http://127.0.0.1:\(port)/")!
        if !tok.isEmpty { c.queryItems = [URLQueryItem(name: "token", value: tok)] }
        return c.url!
    }

    @objc func openPanel() {
        if serverPID == 0 {
            openWhenReady = true
            startServer()
            return
        }
        if !ready { openWhenReady = true; return }
        NSWorkspace.shared.open(panelURL(port: port))
    }

    // MARK: models

    func maybeRunSetup() {
        let done = home.appendingPathComponent("logs/setup-done")
        let stamp = (try? String(contentsOf: done, encoding: .utf8)) ?? ""
        if !stamp.hasPrefix("v\(kSetupVersion)\n") { runSetup() }
    }

    func runSetup() {
        guard setupPID == 0 else { return }
        setupPID = spawn([python, res.appendingPathComponent("runtime/first_run.py").path],
                         env: childEnv(), cwd: home.path, log: home.appendingPathComponent("logs/setup.log"))
        refreshMenu()
    }

    @objc func runSetupFromMenu() { runSetup() }

    // MARK: login item (a per-user LaunchAgent, off by default)

    @objc func toggleLogin() {
        let fm = FileManager.default
        if fm.fileExists(atPath: loginPlist.path) {
            try? fm.removeItem(at: loginPlist)
        } else {
            let plist: [String: Any] = [
                "Label": kLoginLabel,
                "ProgramArguments": ["/usr/bin/open", "-g", "-a", Bundle.main.bundlePath, "--args", "--background"],
                "RunAtLoad": true,
                "LimitLoadToSessionType": "Aqua",
            ]
            try? fm.createDirectory(at: loginPlist.deletingLastPathComponent(), withIntermediateDirectories: true)
            if let d = try? PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0) {
                try? d.write(to: loginPlist)
            }
        }
        refreshMenu()
    }

    @objc func showData() { NSWorkspace.shared.open(home) }
    @objc func showLogs() { NSWorkspace.shared.open(home.appendingPathComponent("logs")) }
    @objc func quit() { NSApp.terminate(nil) }

    func alert(_ msg: String, _ info: String) {
        let a = NSAlert()
        a.messageText = msg
        a.informativeText = info
        NSApp.activate(ignoringOtherApps: true)
        a.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
// Quit cleanly (stopping the panel and any job) when asked to by the installer or uninstaller.
signal(SIGTERM, SIG_IGN)
let termSource = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
termSource.setEventHandler { NSApp.terminate(nil) }
termSource.resume()
app.setActivationPolicy(.accessory)
app.run()
