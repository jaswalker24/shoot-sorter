#!/usr/bin/env python3
"""Cross-platform `tag` wrapper (the bash `tag` script does the same on macOS).

usage:
  tag.py <folder> --profile motorsport|gig|street [--sample N] [--apply]      (tagger)
  tag.py index|search|ocr|sharpness|bursts|rank|captions|journal|ask|faces|name-person|schedule|scene|camera ...   (features)

Starts the local Ollama server if needed, then runs features.py or tagger.py
at low priority with the same interpreter.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("SHOOT_SORTER_HOME") or Path(__file__).resolve().parent)
if str(HOME) not in sys.path:
    sys.path.insert(0, str(HOME))
import compat  # noqa: E402

FEATURES = {"index", "search", "ocr", "sharpness", "bursts", "rank", "captions", "journal", "ask",
            "faces", "name-person", "schedule", "scene", "camera"}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    compat.start_ollama(HOME)
    script = "features.py" if argv[0] in FEATURES else "tagger.py"
    cmd = [compat.python_exe(HOME), str(HOME / script), *argv]
    env = {**os.environ, "SHOOT_SORTER_HOME": str(HOME)}
    kw = compat.popen_flags(low_priority=True, hidden=False)
    if not compat.IS_WINDOWS:
        kw["preexec_fn"] = lambda: os.nice(10)
    try:
        return subprocess.call(cmd, env=env, **kw)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
