#!/usr/bin/env python3
"""First-run model setup for the packaged Shoot Sorter app.

Downloads what the app needs but does not ship, into SHOOT_SORTER_HOME
(~/Library/Application Support/Shoot Sorter on macOS, %APPDATA%\\Shoot Sorter
on Windows):

  1. Ollama (standalone, localhost only) unless one is already in the folder
  2. The qwen2.5vl:3b caption model, through the local Ollama server
     (skipped when the running server already has it)
  3. Aesthetic predictor weights (rank pass)
  4. Face models (people pass): ArcFace embedding, plus the SCRFD detector
     used on Windows in place of Apple Vision
  5. SigLIP image model (tagging), into models/hf
  6. CLIP ViT-L-14 (aesthetic score for index/rank), into models/hf

Progress is written to logs/setup-status.json, which the menu-bar app shows.
Each step is skipped when its files are already present, so it is safe to
re-run after a failed or interrupted download.

Usage: first_run.py [--skip STEP ...]   (steps: ollama, vlm, aesthetic, faces, siglip, clip_l14)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

IS_WINDOWS = os.name == "nt"


def _default_home() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "Shoot Sorter"
    return Path.home() / "Library" / "Application Support" / "Shoot Sorter"


HOME = Path(os.environ.get("SHOOT_SORTER_HOME") or _default_home())
if str(HOME) not in sys.path:
    sys.path.insert(0, str(HOME))
STATUS = HOME / "logs" / "setup-status.json"
OLLAMA_VER = "0.40.15"
OLLAMA_ASSET = "ollama-windows-amd64.zip" if IS_WINDOWS else "ollama-darwin.tgz"
OLLAMA_URL = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VER}/{OLLAMA_ASSET}"
OLLAMA_BIN = "ollama.exe" if IS_WINDOWS else "ollama"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
VLM = "qwen2.5vl:3b"
AES_URL = ("https://github.com/christophschuhmann/improved-aesthetic-predictor/raw/main/"
           "sac+logos+ava1-l14-linearMSE.pth")
FACES_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip"
# Bump with the launcher's kSetupVersion when steps are added, so existing installs re-run setup.
SETUP_VERSION = 3 if IS_WINDOWS else 2
STEPS = ["ollama", "vlm", "aesthetic", "faces", "siglip", "clip_l14"]
LABELS = {
    "ollama": "Downloading Ollama",
    "vlm": f"Downloading caption model ({VLM})",
    "aesthetic": "Downloading aesthetic weights",
    "faces": "Downloading face model",
    "siglip": "Downloading SigLIP image model",
    "clip_l14": "Downloading CLIP ViT-L-14 (aesthetic score)",
}

_state = {"state": "running", "step": "", "label": "", "index": 0, "total": len(STEPS),
          "progress": 0.0, "message": "", "skipped": [], "done": [], "errors": {},
          "started": time.time(), "updated": time.time()}


def status(**kw) -> None:
    _state.update(kw)
    _state["updated"] = time.time()
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(_state, indent=1))
    os.replace(tmp, STATUS)


def _mb(n: float) -> str:
    return f"{n / 1e6:,.0f} MB"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "ShootSorter-setup"})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as fh:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, 0.0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            got += len(chunk)
            if time.time() - last > 0.5:
                last = time.time()
                status(progress=(got / total) if total else 0.0,
                       message=f"{_mb(got)} of {_mb(total)}" if total else _mb(got))
    os.replace(part, dest)


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen(f"http://{OLLAMA_HOST}/api/version", timeout=2):
            return True
    except OSError:
        return False


def step_ollama() -> str | None:
    binp = HOME / "ollama" / OLLAMA_BIN
    if binp.exists():
        return "already installed"
    if IS_WINDOWS and _ollama_up():
        return "using the Ollama server already running on " + OLLAMA_HOST
    if IS_WINDOWS:
        # The Windows zip carries ollama.exe and lib/ollama (CUDA runners), about 1.6 GB.
        dest = HOME / "ollama"
        with tempfile.TemporaryDirectory(dir=str(HOME)) as td:
            z = Path(td) / OLLAMA_ASSET
            download(OLLAMA_URL, z)
            status(message="Unpacking")
            with zipfile.ZipFile(z) as zf:
                zf.extractall(Path(td) / "x")
            found = [p for p in (Path(td) / "x").rglob(OLLAMA_BIN) if p.is_file()]
            if not found:
                raise RuntimeError("ollama.exe not found in the download")
            shutil.copytree(found[0].parent, dest, dirs_exist_ok=True)
        return None
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "ollama.tgz"
        download(OLLAMA_URL, tgz)
        status(message="Unpacking")
        with tarfile.open(tgz) as tf:
            tf.extractall(td, filter="data")
        found = [p for p in Path(td).rglob("ollama") if p.is_file()]
        if not found:
            raise RuntimeError("ollama binary not found in the download")
        shutil.copytree(found[0].parent, HOME / "ollama", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("ollama.tgz"))
    (HOME / "ollama").chmod(0o755)
    binp.chmod(0o755)
    return None


def step_vlm() -> str | None:
    if not _ollama_up() and IS_WINDOWS:
        import compat  # in SHOOT_SORTER_HOME
        compat.start_ollama(HOME, wait=60)
    if not _ollama_up():
        script = HOME / "start-ollama.sh"
        if script.exists() and (HOME / "ollama" / "ollama").exists():
            subprocess.run([str(script)], env={**os.environ, "SHOOT_SORTER_HOME": str(HOME)},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        for _ in range(30):
            if _ollama_up():
                break
            time.sleep(1)
    if not _ollama_up():
        raise RuntimeError("Ollama is not running on " + OLLAMA_HOST)
    with urllib.request.urlopen(f"http://{OLLAMA_HOST}/api/tags", timeout=10) as r:
        names = {m.get("name") for m in json.load(r).get("models", [])}
    if VLM in names:
        return "already on the local Ollama server"
    body = json.dumps({"model": VLM, "stream": True}).encode()
    req = urllib.request.Request(f"http://{OLLAMA_HOST}/api/pull", data=body,
                                 headers={"Content-Type": "application/json"})
    last = 0.0
    with urllib.request.urlopen(req, timeout=3600) as r:
        for line in r:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("error"):
                raise RuntimeError(ev["error"])
            tot, done = ev.get("total") or 0, ev.get("completed") or 0
            if time.time() - last > 0.5 or ev.get("status") == "success":
                last = time.time()
                msg = ev.get("status", "")
                if tot:
                    msg = f"{_mb(done)} of {_mb(tot)}"
                status(progress=(done / tot) if tot else _state["progress"], message=msg)
    return None


def step_aesthetic() -> str | None:
    dst = HOME / "models" / "aesthetic" / "sac+logos+ava1-l14-linearMSE.pth"
    if dst.exists():
        return "already downloaded"
    download(AES_URL, dst)
    return None


FACE_FILES = ["w600k_mbf.onnx", "det_500m.onnx"]  # embedding; detector (non-mac)


def step_faces() -> str | None:
    fdir = HOME / "models" / "faces"
    if all((fdir / n).exists() for n in FACE_FILES):
        return "already downloaded"
    with tempfile.TemporaryDirectory() as td:
        z = Path(td) / "buffalo_s.zip"
        download(FACES_URL, z)
        with zipfile.ZipFile(z) as zf:
            fdir.mkdir(parents=True, exist_ok=True)
            for want in FACE_FILES:
                names = [n for n in zf.namelist() if n.endswith(want)]
                if not names:
                    raise RuntimeError(f"{want} not found in buffalo_s.zip")
                with zf.open(names[0]) as src, open(fdir / want, "wb") as out:
                    shutil.copyfileobj(src, out)
    return None


def _dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def _openclip_fetch(model: str, tag: str) -> str | None:
    """Download an open_clip model into models/hf, with progress from the folder size."""
    hf = HOME / "models" / "hf"
    os.environ["HF_HOME"] = str(hf)
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    marker = hf / f".ready-{model}-{tag}"
    if marker.exists():
        return "already downloaded"
    import open_clip  # bundled

    expected = 0
    try:
        hub = (open_clip.get_pretrained_cfg(model, tag) or {}).get("hf_hub", "").strip("/")
        if hub:
            from huggingface_hub import HfApi
            info = HfApi().model_info(hub, files_metadata=True)
            sizes = [s.size or 0 for s in info.siblings if s.rfilename.startswith("open_clip")]
            expected = max(sizes) if sizes else 0
    except Exception:
        expected = 0

    before = _dir_bytes(hf)
    err: list[BaseException] = []

    def work():
        try:
            open_clip.create_model_and_transforms(model, pretrained=tag)
            open_clip.get_tokenizer(model)
        except BaseException as e:  # reported below
            err.append(e)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    while t.is_alive():
        got = max(0, _dir_bytes(hf) - before)
        status(progress=min(0.99, got / expected) if expected else 0.0,
               message=f"{_mb(got)} of {_mb(expected)}" if expected else _mb(got))
        t.join(1.0)
    if err:
        raise err[0]
    marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S\n"))
    return None


def step_siglip() -> str | None:
    cfg = {}
    try:
        cfg = json.loads((HOME / "config.json").read_text())
    except (OSError, ValueError):
        pass
    return _openclip_fetch(cfg.get("siglip_model", "ViT-B-16-SigLIP-256"),
                           cfg.get("siglip_pretrained", "webli"))


def step_clip_l14() -> str | None:
    # Used with the aesthetic weights by the index/rank passes (features.py).
    return _openclip_fetch("ViT-L-14", "openai")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip", nargs="*", default=[], choices=STEPS)
    a = ap.parse_args()
    funcs = {"ollama": step_ollama, "vlm": step_vlm, "aesthetic": step_aesthetic,
             "faces": step_faces, "siglip": step_siglip,
             "clip_l14": step_clip_l14}
    status(state="running")
    for i, name in enumerate(STEPS, 1):
        status(step=name, label=LABELS[name], index=i, progress=0.0, message="")
        if name in a.skip:
            _state["skipped"].append(name)
            continue
        try:
            note = funcs[name]()
            if note:
                _state["skipped"].append(name)
                status(message=note)
            else:
                _state["done"].append(name)
            print(f"{name}: {note or 'done'}", flush=True)
        except Exception as e:  # keep going; the menu shows what failed
            _state["errors"][name] = str(e)
            print(f"{name}: FAILED {e}", file=sys.stderr, flush=True)
            status()
    ok = not _state["errors"]
    status(state="done" if ok else "error", step="", label="", progress=1.0,
           message="Models ready" if ok else "Some downloads failed: " + ", ".join(_state["errors"]))
    if ok:
        (HOME / "logs" / "setup-done").write_text(f"v{SETUP_VERSION}\n" + time.strftime("%Y-%m-%d %H:%M:%S\n"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
