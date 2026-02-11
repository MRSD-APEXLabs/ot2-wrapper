"""Tests for app.models — Pydantic model validation and defaults."""

import pytest
from pydantic import ValidationError

from app.models import (
    AspirateRequest,
    ConnectRequest,
    Coordinate,
    DispenseRequest,
    DropTipsRequest,
    PickUpTipsRequest,
    PlateRequest,
    ReturnTipsRequest,
    TipRackRequest,
    TubeRackRequest,
)


class TestCoordinate:
    def test_defaults_to_zero(self):
        c = Coordinate()
        assert c.x == 0.0
        assert c.y == 0.0
        assert c.z == 0.0

    def test_custom_values(self):
        c = Coordinate(x=1.5, y=-2.0, z=3.3)
        assert c.x == 1.5
        assert c.y == -2.0
        assert c.z == 3.3


class TestConnectRequest:
    def test_all_optional(self):
        r = ConnectRequest()
        assert r.host is None
        assert r.port is None
        assert r.traversal_height is None
        assert r.deck_config_path is None


class TestPickUpTipsRequest:
    def test_valid(self):
        r = PickUpTipsRequest(resource_name="tips1", well_indices=[0, 1])
        assert r.resource_name == "tips1"
        assert r.offsets is None

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            PickUpTipsRequest(resource_name="tips1")  # missing well_indices


class TestAspirateRequest:
    def test_valid_with_optionals(self):
        r = AspirateRequest(
            resource_name="plate",
            well_indices=[0],
            volumes=[50.0],
            offsets=[Coordinate(z=1.0)],
        )
        assert r.flow_rates is None
        assert r.offsets[0].z == 1.0

    def test_missing_volumes(self):
        with pytest.raises(ValidationError):
            AspirateRequest(resource_name="plate", well_indices=[0])


class TestDropTipsRequest:
    def test_all_optional(self):
        r = DropTipsRequest()
        assert r.resource_name is None
        assert r.well_indices is None
        assert r.offsets is None


class TestTubeRackRequest:
    def test_tubes_optional(self):
        r = TubeRackRequest(ot_name="rack", name="my_rack")
        assert r.tubes is None
