#!/usr/bin/env python3
"""Lay out the runtime folder for the packaged Shoot Sorter app.

The Python code expects one folder (SHOOT_SORTER_HOME) that holds both the
code and its data. In the app, the code is read-only inside the bundle and
the data lives in ~/Library/Application Support/Shoot Sorter. This script
fills that folder with symlinks to the bundled code and creates the data
folders, so the code runs unchanged.

Safe to run on every launch:
  * links that point into an app bundle are refreshed (handles updates and
    a moved app);
  * real files (config.json, auth token, jobs, history, models, outputs)
    are never overwritten;
  * profiles, keywords and the example schedule are copied, not linked,
    because the panel edits them. Shipped copies are refreshed only when
    the app version changes, as install.sh does.

On Windows the install folder plays the part of the bundle Resources
folder and the data folder is %APPDATA%\\Shoot Sorter. Symlinks there need
Developer Mode or admin rights, so shipped code is copied instead, and
refreshed whenever the installed version changes. ExifTool and Python stay
in the install folder (found through SHOOT_SORTER_EXIFTOOL and the running
interpreter).

Usage: prepare_home.py <bundle Resources dir | install dir> <home dir>
"""
from __future__ import annotations

import json
import os
import plistlib
import secrets
import shutil
import sys
from pathlib import Path

# Folders that mix shipped code with files the app writes at run time.
MIXED = {"gui", "bin", "tools", "scripts"}
# Folders the user edits through the panel: copy, never link.
COPIED = {"profiles", "keywords", "schedules"}
IS_WINDOWS = os.name == "nt"
# Shipped in the install folder, never copied into the data folder (Windows).
WIN_SKIP = {"exiftool"}
DATA_DIRS = [
    "models/hf", "models/aesthetic", "models/faces", "cache", "out",
    "logs/gui", "logs/scripts", "index", "people", "ollama",
    "gui/jobs", "gui/history",
]


def _is_bundle_link(p: Path) -> bool:
    if not p.is_symlink():
        return False
    target = os.readlink(p)
    return ".app/Contents/Resources/" in target


def _copy_owned(src: Path, dst: Path, refresh: bool) -> None:
    """Windows: shipped code is copied; refreshed when the app version changes."""
    if src.name == "__pycache__" or src.name in WIN_SKIP:
        return
    if src.is_dir():
        if dst.exists() and not dst.is_dir():
            return
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy_owned(child, dst / child.name, refresh)
    elif refresh or not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


_REFRESH = {"on": False}


def _link(src: Path, dst: Path) -> None:
    if IS_WINDOWS:
        _copy_owned(src, dst, _REFRESH["on"])
        return
    if dst.is_symlink():
        if os.readlink(dst) == str(src):
            return
        dst.unlink()
    elif dst.exists():
        # A real file or folder the user (or an older install) put here wins.
        return
    dst.symlink_to(src)


def _clean_stale(home: Path) -> None:
    if IS_WINDOWS:
        return
    for top in [home, *[home / d for d in MIXED], home / "venv" / "bin"]:
        if not top.is_dir() or top.is_symlink():
            continue
        for child in top.iterdir():
            if _is_bundle_link(child) and not child.exists():
                child.unlink()


def _copy_tree(src: Path, dst: Path, refresh: bool) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*"):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(src)
        out = dst / rel
        if f.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif refresh or not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)


def prepare(res: Path, home: Path) -> dict:
    app = res / "app"
    py = res / "python" / "bin" / "python3"
    home.mkdir(parents=True, exist_ok=True)
    for d in DATA_DIRS + ([] if IS_WINDOWS else ["venv/bin"]):
        (home / d).mkdir(parents=True, exist_ok=True)
    _clean_stale(home)

    stamp = home / ".app-version"
    try:
        if IS_WINDOWS:
            bi = json.loads((res / "build-info.json").read_text(encoding="utf-8"))
            info = "{} ({}, {})".format(bi.get("version"), bi.get("build"), bi.get("git"))
        else:
            with open(res.parent / "Info.plist", "rb") as fh:
                pl = plistlib.load(fh)
            info = "{} ({}, {})".format(pl.get("CFBundleShortVersionString"), pl.get("CFBundleVersion"),
                                        pl.get("ShootSorterGitRevision"))
    except (OSError, ValueError):
        info = "unknown"
    refresh = not stamp.exists() or stamp.read_text().strip() != info or info == "unknown"
    _REFRESH["on"] = refresh

    for entry in sorted(app.iterdir()):
        name = entry.name
        if name == "__pycache__":
            continue
        dst = home / name
        if name in COPIED and entry.is_dir():
            if dst.is_symlink():
                dst.unlink()
            _copy_tree(entry, dst, refresh)
        elif name in MIXED and entry.is_dir():
            if dst.is_symlink():
                dst.unlink()
            dst.mkdir(exist_ok=True)
            for child in sorted(entry.iterdir()):
                if child.name == "__pycache__":
                    continue
                _link(child, dst / child.name)
        else:
            _link(entry, dst)

    if not IS_WINDOWS:
        # Python: venv/bin/python points at the bundled interpreter.
        for n in ("python", "python3"):
            _link(py, home / "venv" / "bin" / n)

        # ExifTool shipped inside the app.
        exif = sorted(app.glob("tools/Image-ExifTool-*/exiftool"))
        if exif:
            _link(exif[-1], home / "bin" / "exiftool")

    cfg = home / "config.json"
    if not cfg.exists() and (app / "config.example.json").exists():
        shutil.copy2(app / "config.example.json", cfg)

    tok = home / "gui" / "auth.token"
    if not tok.exists():
        tok.write_text(secrets.token_urlsafe(24), encoding="utf-8")
    os.chmod(tok, 0o600)

    stamp.write_text(info + "\n")
    return {"home": str(home), "refreshed": refresh}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    out = prepare(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).expanduser())
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
