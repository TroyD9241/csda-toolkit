"""Tests for position classifier."""

import pytest
from csda_toolkit.classifiers.position_classifier import (
    MAP_BOUNDS,
    classify_position,
    classify_player_frames,
    get_position_description,
    PositionClassification,
)


class TestClassifyPosition:
    """Test position classification from x/y/z coordinates."""

    def test_dust2_long_a_classified(self):
        # Approximate long_a coordinates on dust2
        result = classify_position(x=-1300, y=-2500, z=0, map_name="dust2", side="t")
        assert result.position_code == "long_a"
        assert result.zone == "long_a"
        assert result.confidence > 0

    def test_dust2_mid_classified(self):
        result = classify_position(x=-1200, y=-900, z=0, map_name="dust2", side="ct")
        assert result.position_code == "mid"

    def test_dust2_b_tunnels_classified(self):
        result = classify_position(x=1100, y=1800, z=0, map_name="dust2", side="t")
        assert result.position_code == "b_tunnels"

    def test_mirage_a_site_classified(self):
        result = classify_position(x=-700, y=-200, z=0, map_name="mirage", side="ct")
        assert result.position_code == "a_site"

    def test_mirage_mid_classified(self):
        result = classify_position(x=-1100, y=200, z=0, map_name="mirage", side="t")
        assert result.position_code == "mid"

    def test_mirage_b_site_classified(self):
        result = classify_position(x=1200, y=1300, z=0, map_name="mirage", side="t")
        assert result.position_code == "b_site"

    def test_inferno_banana_classified(self):
        result = classify_position(x=0, y=800, z=0, map_name="inferno", side="t")
        assert result.position_code == "banana"

    def test_nuke_a_site_upper_classified(self):
        result = classify_position(x=0, y=-1800, z=100, map_name="nuke", side="ct")
        assert result.position_code == "a_site_upper"

    def test_overpass_monster_classified(self):
        result = classify_position(x=200, y=-600, z=0, map_name="overpass", side="ct")
        assert result.position_code == "monster"

    def test_ancient_donut_classified(self):
        result = classify_position(x=-1000, y=-100, z=0, map_name="ancient", side="t")
        assert result.position_code == "donut"

    def test_ancient_b_site_classified(self):
        result = classify_position(x=1400, y=900, z=0, map_name="ancient", side="t")
        assert result.position_code == "b_site"

    def test_unknown_map_returns_unknown_position(self):
        result = classify_position(x=0, y=0, z=0, map_name="de_xyz", side="t")
        assert result.position_code == "unknown"
        assert result.confidence == 0.0

    def test_unknown_position_returns_unknown_code(self):
        # Coordinates clearly outside any defined zone
        result = classify_position(x=99999, y=99999, z=99999, map_name="dust2", side="t")
        assert result.position_code == "unknown"
        assert result.confidence == 0.0

    def test_side_is_preserved(self):
        ct = classify_position(x=-1300, y=-2500, z=0, map_name="dust2", side="ct")
        t = classify_position(x=-1300, y=-2500, z=0, map_name="dust2", side="t")
        assert ct.side == "ct"
        assert t.side == "t"

    def test_steam_id_passed_through(self):
        result = classify_position(
            x=-1300, y=-2500, z=0,
            map_name="dust2", side="t", steam_id=76561198012345678
        )
        assert result.steam_id == 76561198012345678

    def test_tick_passed_through(self):
        result = classify_position(x=-1300, y=-2500, z=0, map_name="dust2", side="t", tick=52480)
        assert result.tick == 52480

    def test_coordinates_passed_through(self):
        result = classify_position(x=1.5, y=2.7, z=3.3, map_name="dust2", side="ct")
        assert result.x == 1.5
        assert result.y == 2.7
        assert result.z == 3.3

    def test_confidence_is_positive(self):
        result = classify_position(x=-1300, y=-2500, z=0, map_name="dust2", side="t")
        assert result.confidence > 0
        assert result.confidence <= 1.0

    def test_confidence_near_center_higher(self):
        # Point near center of long_a box
        center = classify_position(x=-1300, y=-2450, z=0, map_name="dust2", side="t")
        # Point near edge of long_a box
        edge = classify_position(x=-1700, y=-2500, z=0, map_name="dust2", side="t")
        assert center.confidence >= edge.confidence

    def test_nuke_squeaky_classified(self):
        result = classify_position(x=-400, y=-1300, z=0, map_name="nuke", side="t")
        assert result.position_code == "squeaky"

    def test_overpass_water_classified(self):
        result = classify_position(x=-600, y=1100, z=0, map_name="overpass", side="t")
        assert result.position_code == "water"

    def test_inferno_a_site_classified(self):
        # True a_site on inferno is around x=-1700 to -1900, y=-200 to 100
        result = classify_position(x=-1800, y=-100, z=0, map_name="inferno", side="ct")
        assert result.position_code == "a_site"


class TestClassifyPlayerFrames:
    """Test batch classification from a list of PlayerFrame dicts."""

    def test_empty_list(self):
        result = classify_player_frames([], "dust2")
        assert result == []

    def test_single_frame(self):
        frames = [{"steam_id": 123, "x": -1300, "y": -2500, "z": 0, "side": "t", "tick": 1000}]
        result = classify_player_frames(frames, "dust2")
        assert len(result) == 1
        assert result[0].position_code == "long_a"
        assert result[0].steam_id == 123

    def test_multiple_frames_multiple_positions(self):
        frames = [
            {"steam_id": 1, "x": -1300, "y": -2500, "z": 0, "side": "t", "tick": 1000},
            {"steam_id": 2, "x": 1100, "y": 1800, "z": 0, "side": "t", "tick": 1000},
        ]
        result = classify_player_frames(frames, "dust2")
        codes = {r.position_code for r in result}
        assert "long_a" in codes
        assert "b_tunnels" in codes


class TestGetPositionDescription:
    """Test human-readable descriptions."""

    def test_existing_position(self):
        desc = get_position_description("dust2", "long_a")
        assert desc != ""
        assert "Long A" in desc or "corridor" in desc.lower()

    def test_unknown_position_returns_empty(self):
        desc = get_position_description("dust2", "xyz_unknown")
        assert desc == ""


class TestMapBounds:
    """Test that MAP_BOUNDS is well-formed."""

    def test_all_maps_have_positions(self):
        for map_name in ["dust2", "mirage", "inferno", "nuke", "overpass", "ancient"]:
            assert map_name in MAP_BOUNDS
            assert len(MAP_BOUNDS[map_name]) > 0

    def test_each_position_has_required_fields(self):
        for map_name, positions in MAP_BOUNDS.items():
            for pos_key, bounds in positions.items():
                assert "x_min" in bounds
                assert "x_max" in bounds
                assert "y_min" in bounds
                assert "y_max" in bounds
                assert bounds["x_min"] < bounds["x_max"]
                assert bounds["y_min"] < bounds["y_max"]

    def test_positions_cover_a_site(self):
        # Maps that use "a_site" as the key
        for map_name in ["mirage", "inferno", "overpass", "ancient"]:
            assert "a_site" in MAP_BOUNDS[map_name], f"{map_name} missing a_site"
        # dust2 uses long_a/short_a instead of a_site
        assert "long_a" in MAP_BOUNDS["dust2"]
        # nuke uses a_site_upper
        assert "a_site_upper" in MAP_BOUNDS["nuke"]

    def test_positions_cover_mid_or_equivalent(self):
        # Each map should have a mid-like position
        for map_name in ["dust2", "mirage", "inferno", "overpass", "ancient"]:
            mids = ["mid", "donut", "monster", "connector"]
            has_mid = any(m in MAP_BOUNDS[map_name] for m in mids)
            assert has_mid, f"{map_name} should have a mid-like position"
        # nuke has ramp + outside which serve as mid-control equivalent
        assert "ramp" in MAP_BOUNDS["nuke"]
