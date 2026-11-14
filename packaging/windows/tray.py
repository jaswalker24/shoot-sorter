"""Shoot Sorter tray launcher for Windows.

The Windows counterpart of packaging/launcher/ShootSorterApp.swift. It starts
the bundled control panel (gui/server.py) on a free localhost port, opens it
in the browser, and offers the same menu as the macOS menu-bar app: status,
model download progress, Open Panel, Start/Stop Panel, Download Models,
Start at Login, Show Data Folder, Show Logs and Quit.

Settings and data live in %APPDATA%\\Shoot Sorter; the install folder
(%LOCALAPPDATA%\\Programs\\Shoot Sorter by default) is treated as read-only.

Run with the bundled pythonw.exe:
  pythonw.exe runtime\\tray.py [--background] [--no-setup]
  python.exe  runtime\\tray.py --stop     (quit a running copy; used by the installer)
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Shoot Sorter"
PREFERRED_PORT = 8786
RESERVED_PORTS = {8765, 8766, 8777, 11434}
# Must match SETUP_VERSION in runtime/first_run.py (Windows value).
SETUP_VERSION = 3
MUTEX_NAME = "Local\\ShootSorterTray"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200

RES = Path(__file__).resolve().parent.parent          # install folder
RUNTIME = RES / "runtime"
PYDIR = RES / "python"
PYTHON = PYDIR / "python.exe"
PYTHONW = PYDIR / "pythonw.exe"
EXIFTOOL = RES / "app" / "tools" / "exiftool" / "exiftool.exe"
ICON_FILE = RES / "ShootSorter.ico"


def app_home() -> Path:
    env = os.environ.get("SHOOT_SORTER_APP_HOME")
    if env:
        return Path(os.path.expandvars(os.path.expanduser(env)))
    return Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / APP_NAME


HOME = app_home()
LOGS = HOME / "logs"
SETTINGS = HOME / "app-settings.json"
STOP_FLAG = LOGS / "tray.stop"
STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_LNK = STARTUP_DIR / f"{APP_NAME}.lnk"

log = logging.getLogger("tray")


def version() -> str:
    try:
        bi = json.loads((RES / "build-info.json").read_text(encoding="utf-8"))
        return str(bi.get("version") or "")
    except (OSError, ValueError):
        return ""


# ------------------------------------------------------------------ helpers

def port_is_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def ephemeral_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def read_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def saved_port() -> int | None:
    p = read_json(SETTINGS).get("port")
    return int(p) if isinstance(p, int) else None


def save_port(port: int) -> None:
    d = read_json(SETTINGS)
    d["port"] = port
    SETTINGS.write_text(json.dumps(d, indent=2, sort_keys=True), encoding="utf-8")


def panel_url(port: int) -> str:
    try:
        tok = (HOME / "gui" / "auth.token").read_text(encoding="utf-8").strip()
    except OSError:
        tok = ""
    return f"http://127.0.0.1:{port}/" + (f"?token={tok}" if tok else "")


def child_env(port: int | None = None) -> dict:
    e = dict(os.environ)
    for k in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP"):
        e.pop(k, None)
    e.update({
        "SHOOT_SORTER_HOME": str(HOME),
        "SHOOT_SORTER_EXIFTOOL": str(EXIFTOOL),
        "HF_HOME": str(HOME / "models" / "hf"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "OLLAMA_MODELS": str(HOME / "models"),
        "PATH": os.pathsep.join([str(PYDIR), str(PYDIR / "Scripts"), str(EXIFTOOL.parent),
                                 str(HOME / "ollama"), os.environ.get("PATH", "")]),
    })
    if port:
        e["SHOOT_SORTER_GUI_PORT"] = str(port)
    return e


def spawn(args: list[str], logfile: Path, port: int | None = None) -> subprocess.Popen:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    fh = open(logfile, "ab")
    return subprocess.Popen(args, cwd=str(HOME), env=child_env(port), stdin=subprocess.DEVNULL,
                            stdout=fh, stderr=subprocess.STDOUT,
                            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)


def stop_tree(proc: subprocess.Popen | None, timeout: float = 6) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        import psutil
        parent = psutil.Process(proc.pid)
        procs = parent.children(recursive=True) + [parent]
        for p in procs:
            try:
                p.terminate()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(procs, timeout=timeout)
        for p in alive:
            try:
                p.kill()
            except psutil.Error:
                pass
    except Exception:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=CREATE_NO_WINDOW)


def stop_own_ollama() -> None:
    """Stop the Ollama server from the data folder (not a separately installed Ollama)."""
    try:
        import psutil
    except ImportError:
        return
    own = str((HOME / "ollama").resolve()).lower()
    for p in psutil.process_iter(["exe"]):
        try:
            exe = (p.info.get("exe") or "").lower()
            if exe.startswith(own):
                p.terminate()
        except Exception:
            continue


def startup_enabled() -> bool:
    return STARTUP_LNK.exists()


def set_startup(on: bool) -> None:
    if not on:
        STARTUP_LNK.unlink(missing_ok=True)
        return
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    q = lambda s: str(s).replace("'", "''")  # noqa: E731
    ps = (
        "$s = New-Object -ComObject WScript.Shell;"
        f"$l = $s.CreateShortcut('{q(STARTUP_LNK)}');"
        f"$l.TargetPath = '{q(PYTHONW)}';"
        f"$l.Arguments = '\"{q(RUNTIME / 'tray.py')}\" --background';"
        f"$l.WorkingDirectory = '{q(RES)}';"
        f"$l.IconLocation = '{q(ICON_FILE)}';"
        f"$l.Description = '{APP_NAME}';"
        "$l.Save()"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                   capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=30)


def open_folder(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    os.startfile(str(p))  # noqa: S606


def message_box(text: str, title: str = APP_NAME) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)
    except Exception:
        pass


# ------------------------------------------------------------------ app

class Tray:
    def __init__(self, background: bool, auto_setup: bool):
        self.server: subprocess.Popen | None = None
        self.setup: subprocess.Popen | None = None
        self.port = 0
        self.ready = False
        self.open_when_ready = not background
        self.auto_setup = auto_setup
        self.icon = None
        self.lock = threading.RLock()
        self.quitting = False

    # -- runtime
    def prepare_home(self) -> bool:
        try:
            sys.path.insert(0, str(RUNTIME))
            import prepare_home  # noqa: E402
            out = prepare_home.prepare(RES, HOME)
            log.info("prepared %s", out)
            return True
        except Exception as e:
            log.exception("prepare_home failed")
            message_box(f"Shoot Sorter could not prepare its data folder.\n\n{e}\n\nSee {LOGS / 'app.log'}")
            return False

    def choose_port(self) -> int:
        cands = []
        sp = saved_port()
        if sp:
            cands.append(sp)
        cands += list(range(PREFERRED_PORT, PREFERRED_PORT + 13))
        for p in cands:
            if p not in RESERVED_PORTS and port_is_free(p):
                return p
        for _ in range(10):
            p = ephemeral_port()
            if p and p not in RESERVED_PORTS:
                return p
        return 0

    def start_server(self) -> None:
        with self.lock:
            if self.server and self.server.poll() is None:
                return
            self.port = self.choose_port()
            if not self.port:
                message_box("No free local port for the control panel.")
                return
            save_port(self.port)
            self.ready = False
            self.server = spawn([str(PYTHON), str(HOME / "gui" / "server.py")],
                                LOGS / "gui" / "server.out.log", self.port)
            log.info("server pid %s on port %s", self.server.pid, self.port)
        self.refresh()

    def stop_server(self) -> None:
        with self.lock:
            stop_tree(self.server)
            self.server = None
            self.ready = False
        self.refresh()

    def running(self) -> bool:
        return bool(self.server and self.server.poll() is None)

    def setup_running(self) -> bool:
        return bool(self.setup and self.setup.poll() is None)

    def probe(self) -> None:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/login_status", timeout=1):
                pass
        except urllib.error.HTTPError:
            pass  # any HTTP answer means the server is up
        except OSError:
            return
        self.ready = True
        if self.open_when_ready:
            self.open_when_ready = False
            webbrowser.open(panel_url(self.port))
        if self.auto_setup:
            self.auto_setup = False
            self.maybe_run_setup()

    def maybe_run_setup(self) -> None:
        try:
            stamp = (LOGS / "setup-done").read_text(encoding="utf-8")
        except OSError:
            stamp = ""
        if not stamp.startswith(f"v{SETUP_VERSION}\n"):
            self.run_setup()

    def run_setup(self) -> None:
        with self.lock:
            if self.setup_running():
                return
            self.setup = spawn([str(PYTHON), str(RUNTIME / "first_run.py")], LOGS / "setup.log")
            log.info("setup pid %s", self.setup.pid)
        self.refresh()

    # -- menu text
    def state_text(self, _=None) -> str:
        if self.running() and self.ready:
            return f"Panel running on 127.0.0.1:{self.port}"
        if self.running():
            return "Starting panel…"
        return "Panel stopped"

    def setup_status(self) -> tuple[str, str]:
        """(menu line, tooltip suffix); empty when nothing to show."""
        j = read_json(LOGS / "setup-status.json")
        if not j:
            return "", ""
        if self.setup_running():
            pct = int(float(j.get("progress") or 0) * 100)
            label = j.get("label") or "Downloading models"
            msg = j.get("message") or ""
            line = f"{label} {pct}% ({j.get('index', 0)}/{j.get('total', 0)})" + (f" – {msg}" if msg else "")
            return line, f" – {pct}%"
        if j.get("state") == "error":
            return "Model download incomplete – use Download Models…", " – models incomplete"
        return "", ""

    def refresh(self) -> None:
        if not self.icon:
            return
        line, tip = self.setup_status()
        title = f"{APP_NAME} – {self.state_text()}{tip}"
        try:
            self.icon.title = title[:127]
            self.icon.update_menu()
        except Exception:
            pass

    # -- actions
    def open_panel(self, *_):
        if not self.running():
            self.open_when_ready = True
            self.start_server()
            return
        if not self.ready:
            self.open_when_ready = True
            return
        webbrowser.open(panel_url(self.port))

    def toggle_server(self, *_):
        if self.running():
            self.stop_server()
        else:
            self.start_server()

    def toggle_login(self, *_):
        set_startup(not startup_enabled())
        self.refresh()

    def quit(self, *_):
        if self.quitting:
            return
        self.quitting = True
        log.info("quitting")
        stop_tree(self.setup, timeout=3)
        self.stop_server()
        stop_own_ollama()
        if self.icon:
            self.icon.stop()

    # -- loop
    def tick(self) -> None:
        while not self.quitting:
            try:
                if STOP_FLAG.exists():
                    STOP_FLAG.unlink(missing_ok=True)
                    self.quit()
                    return
                if self.server and self.server.poll() is not None:
                    log.info("server exited rc=%s", self.server.returncode)
                    self.server = None
                    self.ready = False
                if self.running() and not self.ready:
                    self.probe()
                self.refresh()
            except Exception:
                log.exception("tick")
            time.sleep(1.0)

    def build_icon(self):
        import pystray
        from PIL import Image
        img = None
        for p in (ICON_FILE, HOME / "gui" / "static" / "logo.png"):
            try:
                img = Image.open(p)
                img.load()
                break
            except Exception:
                continue
        if img is None:
            img = Image.new("RGBA", (64, 64), (40, 40, 40, 255))
        M = pystray.MenuItem
        menu = pystray.Menu(
            M(lambda _: self.state_text(), None, enabled=False),
            M(lambda _: self.setup_status()[0] or "-", None, enabled=False,
              visible=lambda _: bool(self.setup_status()[0])),
            pystray.Menu.SEPARATOR,
            M("Open Panel", self.open_panel, default=True),
            M(lambda _: "Stop Panel" if self.running() else "Start Panel", self.toggle_server),
            pystray.Menu.SEPARATOR,
            M("Download Models…", lambda *_: self.run_setup(), enabled=lambda _: not self.setup_running()),
            M("Start at Login", self.toggle_login, checked=lambda _: startup_enabled()),
            M("Show Data Folder", lambda *_: open_folder(HOME)),
            M("Show Logs", lambda *_: open_folder(LOGS)),
            pystray.Menu.SEPARATOR,
            M(f"{APP_NAME} {version()}", None, enabled=False),
            M(f"Quit {APP_NAME}", self.quit),
        )
        self.icon = pystray.Icon("ShootSorter", img, APP_NAME, menu)

    def run(self) -> int:
        HOME.mkdir(parents=True, exist_ok=True)
        if not self.prepare_home():
            return 1
        STOP_FLAG.unlink(missing_ok=True)
        self.build_icon()
        self.start_server()
        threading.Thread(target=self.tick, daemon=True).start()
        self.icon.run()
        return 0


def stop_running(timeout: float = 20) -> int:
    """Ask a running tray to quit, then make sure nothing from this install is left running."""
    LOGS.mkdir(parents=True, exist_ok=True)
    h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, MUTEX_NAME)  # SYNCHRONIZE
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        STOP_FLAG.write_text("stop", encoding="utf-8")
        t0 = time.time()
        while time.time() - t0 < timeout and STOP_FLAG.exists():
            time.sleep(0.5)
        STOP_FLAG.unlink(missing_ok=True)
        time.sleep(1)
    try:
        import psutil
    except ImportError:
        return 0
    me = os.getpid()
    roots = [str(PYDIR.resolve()).lower(), str((HOME / "ollama").resolve()).lower(),
             str(EXIFTOOL.parent.resolve()).lower()]
    victims = []
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            exe = (p.info.get("exe") or "").lower()
            if p.info["pid"] != me and any(exe.startswith(r) for r in roots):
                victims.append(p)
        except Exception:
            continue
    for p in victims:
        try:
            p.terminate()
        except Exception:
            pass
    psutil.wait_procs(victims, timeout=5)
    print(f"stopped; {len(victims)} leftover process(es) terminated")
    return 0


def main() -> int:
    args = sys.argv[1:]
    LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(LOGS / "app.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if "--stop" in args:
        return stop_running()
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS: open the running copy's panel
        p = saved_port()
        if p:
            webbrowser.open(panel_url(p))
        return 0
    try:
        return Tray(background="--background" in args, auto_setup="--no-setup" not in args).run()
    except Exception as e:
        log.exception("tray failed")
        message_box(f"Shoot Sorter failed to start.\n\n{e}\n\nSee {LOGS / 'app.log'}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
