"""Tests for app.config — Settings defaults and YAML loading."""

from unittest.mock import patch

from app.config import Settings


class TestSettingsDefaults:
    def test_default_values(self):
        with patch("app.config._load", return_value={}):
            s = Settings()
        assert s.ot2_host == "localhost"
        assert s.ot2_port == 31950
        assert s.ot2_traversal_height == 120.0
        assert s.deck_config_path is None


class TestSettingsFromYaml:
    def test_loads_from_yaml(self):
        data = {
            "robot": {
                "host": "192.168.1.50",
                "port": 8080,
                "traversal_height": 200.5,
            }
        }
        with patch("app.config._load", return_value=data), \
             patch("app.config._CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = True
            s = Settings()
        assert s.ot2_host == "192.168.1.50"
        assert s.ot2_port == 8080
        assert s.ot2_traversal_height == 200.5

    def test_partial_yaml_override(self):
        data = {"robot": {"host": "robot.local"}}
        with patch("app.config._load", return_value=data):
            s = Settings()
        assert s.ot2_host == "robot.local"
        assert s.ot2_port == 31950  # default preserved