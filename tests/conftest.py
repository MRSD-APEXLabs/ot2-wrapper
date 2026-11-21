"""Shared fixtures for OT-2 wrapper tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pylabrobot.resources.opentrons import OTDeck

import app.state as state_mod


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset module-level state globals after every test."""
    yield
    state_mod._lh = None
    state_mod._host = None
    state_mod._session_key = None
    state_mod._resources.clear()


@pytest.fixture()
def mock_lh():
    """Inject a MagicMock LiquidHandler into app.state and return it."""
    lh = MagicMock()
    lh.setup = AsyncMock()
    lh.stop = AsyncMock()
    lh.deck = OTDeck()
    state_mod._lh = lh
    state_mod._host = "fake-host"
    return lh


@pytest.fixture()
def ot_deck():
    """Provide a real OTDeck instance."""
    return OTDeck()
