#!/usr/bin/env python3
"""Panel bind address and Hugging Face telemetry defaults."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app_home


class PrivacyDefaults(unittest.TestCase):
    def test_telemetry_defaults_are_set(self):
        app_home.apply_privacy_defaults()
        self.assertEqual(os.environ.get("HF_HUB_DISABLE_TELEMETRY"), "1")
        self.assertEqual(os.environ.get("DO_NOT_TRACK"), "1")

    def test_setdefault_does_not_override(self):
        with mock.patch.dict(os.environ, {"HF_HUB_DISABLE_TELEMETRY": "0", "DO_NOT_TRACK": "0"}):
            app_home.apply_privacy_defaults()
            self.assertEqual(os.environ["HF_HUB_DISABLE_TELEMETRY"], "0")
            self.assertEqual(os.environ["DO_NOT_TRACK"], "0")


class GuiBindDefaults(unittest.TestCase):
    def test_default_host_is_localhost(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"SHOOT_SORTER_HOME": td}):
                os.environ.pop("SHOOT_SORTER_GUI_HOST", None)
                self.assertEqual(app_home.gui_host(), "127.0.0.1")

    def test_config_overrides_default(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "config.json").write_text(json.dumps({"gui_host": "0.0.0.0"}))
            with mock.patch.dict(os.environ, {"SHOOT_SORTER_HOME": td}):
                os.environ.pop("SHOOT_SORTER_GUI_HOST", None)
                self.assertEqual(app_home.gui_host(), "0.0.0.0")

    def test_env_overrides_config(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "config.json").write_text(json.dumps({"gui_host": "127.0.0.1"}))
            with mock.patch.dict(os.environ, {
                "SHOOT_SORTER_HOME": td,
                "SHOOT_SORTER_GUI_HOST": "0.0.0.0",
            }):
                self.assertEqual(app_home.gui_host(), "0.0.0.0")

    def test_default_port(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"SHOOT_SORTER_HOME": td}):
                os.environ.pop("SHOOT_SORTER_GUI_PORT", None)
                self.assertEqual(app_home.gui_port(), 8766)

    def test_config_port_and_env_override(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "config.json").write_text(json.dumps({"gui_port": 9000}))
            with mock.patch.dict(os.environ, {"SHOOT_SORTER_HOME": td}):
                os.environ.pop("SHOOT_SORTER_GUI_PORT", None)
                self.assertEqual(app_home.gui_port(), 9000)
            with mock.patch.dict(os.environ, {
                "SHOOT_SORTER_HOME": td,
                "SHOOT_SORTER_GUI_PORT": "9010",
            }):
                self.assertEqual(app_home.gui_port(), 9010)


class SourceDefaults(unittest.TestCase):
    def test_server_and_plist_no_longer_bind_all_interfaces(self):
        root = Path(__file__).resolve().parent
        server = (root / "gui" / "server.py").read_text()
        self.assertNotIn('"0.0.0.0"', server)
        self.assertIn("gui_host()", server)
        self.assertIn("apply_privacy_defaults()", server)
        plist = (root / "gui" / "com.shootsorter.gui.plist").read_text()
        self.assertNotIn("0.0.0.0", plist)
        self.assertIn("HF_HUB_DISABLE_TELEMETRY", plist)
        self.assertIn("DO_NOT_TRACK", plist)
        features = (root / "features.py").read_text()
        tagger = (root / "tagger.py").read_text()
        self.assertIn('os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")', features)
        self.assertIn('os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")', tagger)


if __name__ == "__main__":
    unittest.main()
