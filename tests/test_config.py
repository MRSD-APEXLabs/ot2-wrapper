"""Tests for app.config — Settings defaults and env loading."""

import os
from unittest.mock import patch

from app.config import Settings


class TestSettingsDefaults:
    def test_default_values(self):
        s = Settings()
        assert s.ot2_host == "localhost"
        assert s.ot2_port == 31950
        assert s.ot2_traversal_height == 120.0
        assert s.deck_config_path is None


class TestSettingsFromEnv:
    def test_loads_from_env(self):
        env = {
            "OT2_HOST": "192.168.1.50",
            "OT2_PORT": "8080",
            "OT2_TRAVERSAL_HEIGHT": "200.5",
            "DECK_CONFIG_PATH": "/tmp/deck.yaml",
        }
        with patch.dict(os.environ, env, clear=False):
            s = Settings()
        assert s.ot2_host == "192.168.1.50"
        assert s.ot2_port == 8080
        assert s.ot2_traversal_height == 200.5
        assert str(s.deck_config_path) == "/tmp/deck.yaml"

    def test_partial_env_override(self):
        with patch.dict(os.environ, {"OT2_HOST": "robot.local"}, clear=False):
            s = Settings()
        assert s.ot2_host == "robot.local"
        assert s.ot2_port == 31950  # default preserved
