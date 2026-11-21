"""Tests for app.state — state management, resource registry, and factories."""

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.state as state_mod
from app.state import (
    connect,
    create_plate,
    create_tip_rack,
    create_tube_rack,
    current_host,
    disconnect,
    get_lh,
    get_resource,
    is_connected,
    list_resources,
    register_resource,
    unregister_resource,
)


# ── Getters / guards ─────────────────────────────────────────────────────


class TestGetLh:
    def test_raises_503_when_disconnected(self):
        with pytest.raises(HTTPException) as exc_info:
            get_lh()
        assert exc_info.value.status_code == 503

    def test_returns_lh_when_connected(self, mock_lh):
        assert get_lh() is mock_lh


class TestIsConnected:
    def test_false_when_disconnected(self):
        assert is_connected() is False

    def test_true_when_connected(self, mock_lh):
        assert is_connected() is True


class TestCurrentHost:
    def test_none_when_disconnected(self):
        assert current_host() is None

    def test_returns_host_when_connected(self, mock_lh):
        assert current_host() == "fake-host"


# ── Resource registry ─────────────────────────────────────────────────────


class TestResourceRegistry:
    def test_register_and_get(self):
        resource = MagicMock()
        register_resource("my_plate", resource)
        assert get_resource("my_plate") is resource

    def test_get_unknown_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            get_resource("nonexistent")
        assert exc_info.value.status_code == 400

    def test_list_resources_returns_copy(self):
        resource = MagicMock()
        register_resource("res", resource)
        listing = list_resources()
        listing["extra"] = MagicMock()
        # Original registry should be unaffected
        assert "extra" not in list_resources()

    def test_list_resources_empty(self):
        assert list_resources() == {}

    def test_unregister_removes_entry(self):
        resource = MagicMock()
        register_resource("to_remove", resource)
        unregister_resource("to_remove")
        with pytest.raises(HTTPException):
            get_resource("to_remove")

    def test_unregister_missing_is_noop(self):
        unregister_resource("does_not_exist")  # should not raise


# ── Resource factories (real PLR imports) ────────────────────────────────


class TestCreatePlate:
    def test_valid_plate_type(self):
        plate = create_plate("agilent_96_wellplate_150uL_Vb", "my_plate")
        assert plate.name == "my_plate"

    def test_bogus_plate_type_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            create_plate("TotallyFakePlateXYZ", "p")
        assert exc_info.value.status_code == 400


class TestCreateTipRack:
    def test_valid_tip_rack(self):
        tr = create_tip_rack("opentrons_96_filtertiprack_200ul", "tips1")
        assert tr.name == "tips1"
        assert "TipRack" in type(tr).__name__


class TestCreateTubeRack:
    def test_valid_tube_rack(self):
        tr = create_tube_rack(
            "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap", "tubes1"
        )
        assert tr.name == "tubes1"
        assert "TubeRack" in type(tr).__name__


# ── Deck config loading ──────────────────────────────────────────────────


class TestLoadDeckConfig:
    def test_loads_yaml_and_assigns(self, tmp_path, mock_lh):
        cfg = textwrap.dedent("""\
            deck:
              - slot: 1
                type: tip_rack
                ot_name: "opentrons_96_filtertiprack_200ul"
                name: "tips"
              - slot: 2
                type: plate
                ot_name: "agilent_96_wellplate_150uL_Vb"
                name: "plate"
        """)
        cfg_file = tmp_path / "deck.yaml"
        cfg_file.write_text(cfg)

        state_mod._load_deck_config(mock_lh, cfg_file)

        assert get_resource("tips") is not None
        assert get_resource("plate") is not None

    def test_skips_unknown_type(self, tmp_path, mock_lh, caplog):
        cfg = textwrap.dedent("""\
            deck:
              - slot: 3
                type: mystery_gadget
                ot_name: "whatever"
                name: "gadget"
        """)
        cfg_file = tmp_path / "deck.yaml"
        cfg_file.write_text(cfg)

        state_mod._load_deck_config(mock_lh, cfg_file)

        with pytest.raises(HTTPException):
            get_resource("gadget")


# ── Connect / Disconnect ─────────────────────────────────────────────────


class TestConnect:
    async def test_sets_lh_and_host(self):
        with patch.object(state_mod, "OTDeck"), \
             patch.object(state_mod, "OpentronsOT2Backend"), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            mock_instance = AsyncMock()
            MockLH.return_value = mock_instance

            await connect("10.0.0.1", port=31950)

            assert state_mod._lh is mock_instance
            assert state_mod._host == "10.0.0.1"
            mock_instance.setup.assert_awaited_once()

    async def test_reuses_a_healthy_session(self, mock_lh):
        state_mod._session_key = ("10.0.0.1", 31950, 120.0, None)
        with patch.object(state_mod.ot_api, "run_id", "run-1"), \
             patch.object(state_mod.ot_api.runs, "get_run",
                          return_value={"status": "idle", "current": True}), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            reused = await connect("10.0.0.1", port=31950)

        assert reused is True
        assert state_mod._lh is mock_lh
        MockLH.assert_not_called()
        mock_lh.stop.assert_not_awaited()

    @pytest.mark.parametrize("run", [
        {"status": "stopped", "current": True},
        {"status": "failed", "current": True},
        {"status": "idle", "current": False},
        Exception("404 run not found"),  # OT-2 rebooted
    ])
    async def test_rebuilds_a_dead_session(self, mock_lh, run):
        state_mod._session_key = ("10.0.0.1", 31950, 120.0, None)
        get_run = MagicMock(side_effect=run) if isinstance(run, Exception) \
            else MagicMock(return_value=run)
        with patch.object(state_mod.ot_api, "run_id", "run-1"), \
             patch.object(state_mod.ot_api.runs, "get_run", get_run), \
             patch.object(state_mod, "OTDeck"), \
             patch.object(state_mod, "OpentronsOT2Backend"), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            new_lh = AsyncMock()
            MockLH.return_value = new_lh
            reused = await connect("10.0.0.1", port=31950)

        assert reused is False
        mock_lh.stop.assert_awaited_once()
        assert state_mod._lh is new_lh
        new_lh.setup.assert_awaited_once()

    async def test_rebuilds_when_settings_change(self, mock_lh):
        state_mod._session_key = ("10.0.0.1", 31950, 120.0, None)
        with patch.object(state_mod.ot_api, "run_id", "run-1"), \
             patch.object(state_mod.ot_api.runs, "get_run",
                          return_value={"status": "idle", "current": True}), \
             patch.object(state_mod, "OTDeck"), \
             patch.object(state_mod, "OpentronsOT2Backend"), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            MockLH.return_value = AsyncMock()
            reused = await connect("10.0.0.2", port=31950)

        assert reused is False
        assert state_mod._host == "10.0.0.2"
        mock_lh.stop.assert_awaited_once()

    async def test_rebuilds_when_deck_config_is_edited(self, mock_lh, tmp_path):
        cfg = tmp_path / "deck.yaml"
        cfg.write_text("deck: []\n")
        state_mod._session_key = ("10.0.0.1", 31950, 120.0, (str(cfg), -1.0))  # older mtime
        with patch.object(state_mod.ot_api, "run_id", "run-1"), \
             patch.object(state_mod.ot_api.runs, "get_run",
                          return_value={"status": "idle", "current": True}), \
             patch.object(state_mod, "OTDeck"), \
             patch.object(state_mod, "OpentronsOT2Backend"), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            MockLH.return_value = AsyncMock()
            reused = await connect("10.0.0.1", port=31950, deck_config_path=cfg)

        assert reused is False

    async def test_failed_stop_of_the_old_session_does_not_block_the_rebuild(self, mock_lh):
        mock_lh.stop.side_effect = Exception("robot unreachable")
        with patch.object(state_mod.ot_api, "run_id", None), \
             patch.object(state_mod, "OTDeck"), \
             patch.object(state_mod, "OpentronsOT2Backend"), \
             patch.object(state_mod, "LiquidHandler") as MockLH:
            new_lh = AsyncMock()
            MockLH.return_value = new_lh
            await connect("10.0.0.1", port=31950)

        assert state_mod._lh is new_lh


class TestDisconnect:
    async def test_clears_state(self, mock_lh):
        register_resource("r", MagicMock())
        await disconnect()

        assert state_mod._lh is None
        assert state_mod._host is None
        assert list_resources() == {}
        mock_lh.stop.assert_awaited_once()

    async def test_raises_503_if_not_connected(self):
        with pytest.raises(HTTPException) as exc_info:
            await disconnect()
        assert exc_info.value.status_code == 503
