#!/usr/bin/env python3
"""Runtime paths and names for Shoot Sorter."""
import os
from pathlib import Path

APP_NAME = "Shoot Sorter"
DEFAULT_HOME_DIR = "shoot-sorter"
DEFAULT_PORT = 8766
LAUNCHD_LABEL = "com.shootsorter.gui"
PANEL_BUNDLE_ID = "com.shootsorter.panel"
DOCK_APP_NAME = "Shoot Sorter"


def home() -> Path:
    return Path(os.environ.get("SHOOT_SORTER_HOME") or (Path.home() / DEFAULT_HOME_DIR))


def gui_port() -> int:
    return int(os.environ.get("SHOOT_SORTER_GUI_PORT", str(DEFAULT_PORT)))
