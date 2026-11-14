#!/usr/bin/env python3
"""Platform helpers so the same code runs on macOS and Windows.

macOS keeps its original behaviour (Apple Vision, MPS, launchd, Finder).
Everywhere else these helpers provide portable replacements:

  * torch_device()      CUDA, then Apple MPS, then CPU (override with
                        SHOOT_SORTER_DEVICE or config.json "device")
  * onnx_providers()    the onnxruntime providers that are actually installed
  * python_exe()        the interpreter to run helper scripts with
  * exiftool()          bundled ExifTool (exiftool.exe on Windows)
  * tag_cmd()           the `tag` wrapper (tag.py on Windows)
  * start_ollama()      start the local Ollama server if it is not running
  * proc_running(), kill_children()   pgrep/pkill replacements
  * reveal(), notify()  show a file in Explorer/Finder, desktop notification
  * ocr()               Apple Vision on macOS, RapidOCR (ONNX) elsewhere
  * saliency_box()      spectral-residual saliency (Vision objectness on macOS)
  * detect_faces_onnx() SCRFD face detector with 5 landmarks (InsightFace)
  * replace_with_retry() os.replace that waits out Windows sharing locks
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# Windows process creation flags (no-ops elsewhere).
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def _home() -> Path:
    if os.environ.get("SHOOT_SORTER_HOME"):
        return Path(os.environ["SHOOT_SORTER_HOME"])
    return Path.home() / "shoot-sorter"


def _cfg(home: Path | None = None) -> dict:
    try:
        d = json.loads(((home or _home()) / "config.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def default_data_home(app_name: str = "Shoot Sorter") -> Path:
    """Per-user data folder for the packaged app."""
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / app_name
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / app_name
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")) / app_name


# ------------------------------------------------------------------ torch / onnx

def torch_device(torch=None) -> str:
    """CUDA if available, then Apple MPS, then CPU. SHOOT_SORTER_DEVICE / config "device" override."""
    if torch is None:
        import torch  # noqa: F811
    want = (os.environ.get("SHOOT_SORTER_DEVICE") or str(_cfg().get("device") or "auto")).strip().lower()
    if want in ("cpu",):
        return "cpu"
    if want.startswith("cuda") and torch.cuda.is_available():
        return want
    if want == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def onnx_providers() -> list[str]:
    try:
        import onnxruntime as ort
        have = set(ort.get_available_providers())
    except Exception:
        have = {"CPUExecutionProvider"}
    order = ["CUDAExecutionProvider", "CoreMLExecutionProvider", "DmlExecutionProvider", "CPUExecutionProvider"]
    out = [p for p in order if p in have]
    return out or ["CPUExecutionProvider"]


# ------------------------------------------------------------------ executables

def python_exe(home: Path | None = None) -> str:
    home = home or _home()
    for c in (home / "venv" / "bin" / "python", home / "venv" / "Scripts" / "python.exe"):
        if c.exists():
            return str(c)
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        exe = exe.parent / "python.exe"
    return str(exe)


def exiftool(home: Path | None = None) -> str:
    home = home or _home()
    env = os.environ.get("SHOOT_SORTER_EXIFTOOL")
    if env and Path(env).exists():
        return env
    names = ["exiftool.exe", "exiftool"] if IS_WINDOWS else ["exiftool"]
    for n in names:
        if (home / "bin" / n).exists():
            return str(home / "bin" / n)
    for pat in ("tools/exiftool/exiftool.exe", "tools/Image-ExifTool-*/exiftool"):
        hits = sorted(home.glob(pat))
        if hits:
            return str(hits[-1])
    return shutil.which("exiftool") or str(home / "bin" / names[0])


def tag_cmd(home: Path | None = None) -> list[str]:
    """Command prefix for the `tag` wrapper."""
    home = home or _home()
    if IS_WINDOWS or not (home / "tag").exists():
        return [python_exe(home), str(home / "tag.py")]
    return [str(home / "tag")]


def popen_flags(low_priority: bool = False, hidden: bool = True) -> dict:
    """Keyword arguments for subprocess on Windows (no console window, optional low priority)."""
    if not IS_WINDOWS:
        return {}
    fl = 0
    if hidden:
        fl |= CREATE_NO_WINDOW
    if low_priority:
        fl |= BELOW_NORMAL_PRIORITY_CLASS
    return {"creationflags": fl} if fl else {}


# ------------------------------------------------------------------ ollama

def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")


def ollama_up(host: str | None = None, timeout: float = 2.0) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{host or _ollama_host()}/api/version", timeout=timeout):
            return True
    except OSError:
        return False


def ollama_binary(home: Path | None = None) -> str | None:
    home = home or _home()
    for c in (home / "ollama" / "ollama.exe", home / "ollama" / "ollama"):
        if c.is_file():
            return str(c)
    return shutil.which("ollama")


def start_ollama(home: Path | None = None, wait: float = 30.0) -> bool:
    """Start Ollama (localhost only, models under <home>/models) unless it is already running."""
    home = home or _home()
    if ollama_up():
        return True
    if IS_MAC and (home / "start-ollama.sh").exists():
        subprocess.run([str(home / "start-ollama.sh")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=60, env={**os.environ, "SHOOT_SORTER_HOME": str(home)})
    else:
        binp = ollama_binary(home)
        if not binp:
            return False
        env = {**os.environ}
        env.setdefault("OLLAMA_MODELS", str(home / "models"))
        env.setdefault("OLLAMA_HOST", _ollama_host())
        env.setdefault("OLLAMA_KEEP_ALIVE", "5m")
        env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")
        (home / "logs").mkdir(parents=True, exist_ok=True)
        log = open(home / "logs" / "ollama.log", "ab")
        kw = {"start_new_session": True} if not IS_WINDOWS else {
            "creationflags": CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP}
        p = subprocess.Popen([binp, "serve"], env=env, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, cwd=str(home), **kw)
        (home / "logs" / "ollama.pid").write_text(str(p.pid))
    t0 = time.time()
    while time.time() - t0 < wait:
        if ollama_up():
            return True
        time.sleep(0.5)
    return ollama_up()


# ------------------------------------------------------------------ processes

def proc_running(pattern: str, ignore_case: bool = False) -> bool:
    """True if a process command line contains pattern (pgrep -f replacement)."""
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is None:
        if IS_WINDOWS:
            return False
        args = ["pgrep", "-if" if ignore_case else "-f", pattern]
        try:
            return subprocess.run(args, capture_output=True).returncode == 0
        except OSError:
            return False
    me = os.getpid()
    pat = pattern.lower() if ignore_case else pattern
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.info["pid"] == me:
                continue
            cl = " ".join(p.info.get("cmdline") or []) or (p.info.get("name") or "")
            if (pat in cl.lower()) if ignore_case else (pat in cl):
                return True
        except Exception:
            continue
    return False


def kill_children(pid: int) -> None:
    """Terminate all descendants of pid (pkill -P replacement, recursive)."""
    try:
        import psutil
    except ImportError:
        if not IS_WINDOWS:
            subprocess.run(["pkill", "-P", str(pid)], capture_output=True)
        else:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, **popen_flags())
        return
    try:
        kids = psutil.Process(pid).children(recursive=True)
    except Exception:
        return
    for k in kids:
        try:
            k.terminate()
        except Exception:
            pass
    _, alive = psutil.wait_procs(kids, timeout=5)
    for k in alive:
        try:
            k.kill()
        except Exception:
            pass


def reveal(path: str | Path) -> subprocess.CompletedProcess:
    """Show a file or folder in Finder / Explorer."""
    p = str(path)
    if IS_MAC:
        return subprocess.run(["open", "-R", p], capture_output=True, text=True, timeout=15)
    if IS_WINDOWS:
        arg = f'/select,"{p}"' if Path(p).is_file() else f'"{p}"'
        subprocess.Popen(f"explorer.exe {arg}")
        return subprocess.CompletedProcess(["explorer.exe", arg], 0, "", "")
    return subprocess.run(["xdg-open", str(Path(p).parent if Path(p).is_file() else p)],
                          capture_output=True, text=True, timeout=15)


def notify(title: str, msg: str) -> None:
    if IS_MAC:
        subprocess.run(["osascript", "-e",
                        f'display notification {json.dumps(msg[:200])} with title {json.dumps(title)}'])
    else:
        print(f"[{title}] {msg}", flush=True)


def replace_with_retry(src, dst, tries: int = 20, delay: float = 0.25) -> None:
    """os.replace, retrying while another program (e.g. Lightroom, antivirus) holds dst open on Windows."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if not IS_WINDOWS or i == tries - 1:
                raise
            time.sleep(delay)


def _install_windows_replace_retry() -> None:
    """Windows: os.replace fails with "Access is denied" while another process has the
    target open (the panel reading a job file, the tray reading setup status, Lightroom
    or antivirus touching a sidecar). The code writes JSON/XMP via tmp + replace in many
    places, so retry those briefly process-wide instead of failing the job."""
    if not IS_WINDOWS or getattr(os.replace, "_shoot_sorter_retry", False):
        return
    _orig = os.replace

    def replace(src, dst, *a, **kw):
        for i in range(40):
            try:
                return _orig(src, dst, *a, **kw)
            except PermissionError:
                if i == 39:
                    raise
                time.sleep(0.05 if i < 10 else 0.1)

    replace._shoot_sorter_retry = True
    os.replace = replace


_install_windows_replace_retry()


# ------------------------------------------------------------------ OCR (non-mac)

_RAPID = {}


def _rapid():
    if "e" not in _RAPID:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            from rapidocr import RapidOCR  # newer package name
        _RAPID["e"] = RapidOCR()
    return _RAPID["e"]


def ocr(path, min_conf: float = 0.0) -> list[dict]:
    """Text lines with confidence and a normalised top-left box: {text, conf, x, y, w, h}.

    Non-mac only (macOS callers keep Apple Vision). Uses RapidOCR (PP-OCR models on
    onnxruntime); the bundled models read Latin text, digits and CJK ideographs.
    """
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGB")
    W, H = im.size
    res, _ = _rapid()(np.asarray(im)[:, :, ::-1].copy())
    out = []
    for item in res or []:
        box, text, conf = item[0], item[1], float(item[2])
        if conf < min_conf or not str(text).strip():
            continue
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        x0, x1, y0, y1 = max(0.0, min(xs)), min(W, max(xs)), max(0.0, min(ys)), min(H, max(ys))
        out.append({"text": str(text), "conf": conf, "x": x0 / W, "y": y0 / H,
                    "w": (x1 - x0) / W, "h": (y1 - y0) / H})
    # reading order: top to bottom, then left to right
    out.sort(key=lambda d: (round(d["y"], 2), d["x"]))
    return out


# ------------------------------------------------------------------ saliency (non-mac)

def saliency_box(path):
    """Spectral-residual saliency -> (x0, y0, x1, y1) normalised, top-left origin, or None."""
    import cv2
    import numpy as np
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    H, W = img.shape
    sw = 128
    sh = max(8, int(round(sw * H / W)))
    g = cv2.resize(img, (sw, sh)).astype(np.float32)
    F = np.fft.fft2(g)
    log_amp = np.log(np.abs(F) + 1e-8)
    phase = np.angle(F)
    resid = log_amp - cv2.blur(log_amp, (3, 3))
    sal = np.abs(np.fft.ifft2(np.exp(resid + 1j * phase))) ** 2
    sal = cv2.GaussianBlur(sal.astype(np.float32), (0, 0), 2.5)
    sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-8)
    mask = (sal > max(0.25, 3 * float(sal.mean()))).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return None
    # largest component weighted by saliency mass
    best, best_s = None, 0.0
    for i in range(1, n):
        s = float(sal[lab == i].sum())
        if s > best_s:
            best, best_s = i, s
    x, y, w, h = stats[best, :4]
    if w * h < 4:
        return None
    return (float(x / sw), float(y / sh), float((x + w) / sw), float((y + h) / sh))


# ------------------------------------------------------------------ faces (non-mac)

_SCRFD = {}


def _nms(dets, thresh=0.4):
    import numpy as np
    x1, y1, x2, y2, sc = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = sc.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]]); yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]]); yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1); h = np.maximum(0.0, yy2 - yy1 + 1)
        ovr = (w * h) / (areas[i] + areas[order[1:]] - w * h)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


def detect_faces_onnx(path, W, H, model_path, thresh: float = 0.5):
    """SCRFD (InsightFace det_500m / det_10g) -> [(box[x,y,w,h], five_points[5,2], True), ...] in W x H pixels."""
    import cv2
    import numpy as np
    import onnxruntime as ort
    key = str(model_path)
    if key not in _SCRFD:
        _SCRFD[key] = ort.InferenceSession(key, providers=onnx_providers())
    sess = _SCRFD[key]
    img = cv2.imread(str(path))
    if img is None:
        return []
    ih, iw = img.shape[:2]
    size = 640
    if ih / iw > 1:
        nh, nw = size, int(size * iw / ih)
    else:
        nw, nh = size, int(size * ih / iw)
    scale = nh / ih
    det = np.zeros((size, size, 3), np.uint8)
    det[:nh, :nw] = cv2.resize(img, (nw, nh))
    blob = cv2.dnn.blobFromImage(det, 1.0 / 128, (size, size), (127.5, 127.5, 127.5), swapRB=True)
    inp = sess.get_inputs()[0].name
    outs = sess.run(None, {inp: blob})
    fmc = 3 if len(outs) in (6, 9) else 5
    strides = [8, 16, 32] if fmc == 3 else [8, 16, 32, 64, 128]
    has_kps = len(outs) == fmc * 3
    boxes, scores, kpss = [], [], []
    for idx, st in enumerate(strides):
        sc = outs[idx]; bb = outs[idx + fmc]; kp = outs[idx + 2 * fmc] if has_kps else None
        if sc.ndim == 3:
            sc, bb = sc[0], bb[0]
            kp = kp[0] if kp is not None else None
        sc = sc.reshape(-1); bb = bb.reshape(-1, 4) * st
        fh, fw = size // st, size // st
        na = sc.shape[0] // (fh * fw)
        centers = np.stack(np.mgrid[:fh, :fw][::-1], axis=-1).astype(np.float32)
        centers = (centers * st).reshape(-1, 2)
        if na > 1:
            centers = np.stack([centers] * na, axis=1).reshape(-1, 2)
        pos = np.where(sc >= thresh)[0]
        if not len(pos):
            continue
        c = centers[pos]; d = bb[pos]
        boxes.append(np.stack([c[:, 0] - d[:, 0], c[:, 1] - d[:, 1], c[:, 0] + d[:, 2], c[:, 1] + d[:, 3]], -1))
        scores.append(sc[pos])
        if kp is not None:
            k = kp.reshape(-1, 10)[pos] * st
            pts = np.stack([np.stack([c[:, 0] + k[:, 2 * j], c[:, 1] + k[:, 2 * j + 1]], -1) for j in range(5)], 1)
            kpss.append(pts)
    if not boxes:
        return []
    boxes = np.vstack(boxes) / scale
    scores = np.concatenate(scores)
    kps = (np.vstack(kpss) / scale) if kpss else None
    keep = _nms(np.hstack([boxes, scores[:, None]]), 0.4)
    sx, sy = W / iw, H / ih
    out = []
    for i in keep:
        x0, y0, x1, y1 = boxes[i]
        box = [float(x0 * sx), float(y0 * sy), float((x1 - x0) * sx), float((y1 - y0) * sy)]
        if kps is not None:
            five = (kps[i] * np.array([sx, sy], np.float32)).astype(np.float32)
            out.append((box, five, True))
        else:
            out.append((box, None, False))
    return out
