#!/usr/bin/env python3
"""Runtime paths and names for Shoot Sorter."""
import json
import os
from pathlib import Path

APP_NAME = "Shoot Sorter"
DEFAULT_HOME_DIR = "shoot-sorter"
DEFAULT_PORT = 8766
DEFAULT_HOST = "127.0.0.1"
LAUNCHD_LABEL = "com.shootsorter.gui"
PANEL_BUNDLE_ID = "com.shootsorter.panel"
DOCK_APP_NAME = "Shoot Sorter"


def apply_privacy_defaults() -> None:
    """Turn off Hugging Face usage stats. Does not block model downloads."""
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")


apply_privacy_defaults()


def home() -> Path:
    return Path(os.environ.get("SHOOT_SORTER_HOME") or (Path.home() / DEFAULT_HOME_DIR))


def _config_value(key: str, default=None):
    cfg = home() / "config.json"
    if not cfg.exists():
        return default
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(data, dict):
        return default
    return data.get(key, default)


def gui_host() -> str:
    """Panel bind address: env, then config.json gui_host, then 127.0.0.1."""
    env = os.environ.get("SHOOT_SORTER_GUI_HOST")
    if env:
        return env
    val = _config_value("gui_host")
    if val:
        return str(val)
    return DEFAULT_HOST


def gui_port() -> int:
    env = os.environ.get("SHOOT_SORTER_GUI_PORT")
    if env:
        return int(env)
    val = _config_value("gui_port")
    if val is not None and val != "":
        return int(val)
    return DEFAULT_PORT
