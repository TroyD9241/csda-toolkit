"""Tests for the role taxonomy module."""

import pytest
from csda_toolkit.classifiers.role_taxonomy import (
    BROAD_ROLES,
    MAPS,
    MAP_POSITIONS,
    MAP_ZONES,
    ROLE_DESCRIPTIONS,
    ROLE_POSITION_PREFERENCES,
    ZONE_ROLES,
    RoleClassificationResult,
)


class TestBroadRoles:
    """Broad role taxonomy is well-formed."""

    def test_all_roles_have_descriptions(self):
        """Every role in BROAD_ROLES has a non-empty description."""
        for role in BROAD_ROLES:
            assert role in ROLE_DESCRIPTIONS, f"Missing description for role: {role}"
            assert ROLE_DESCRIPTIONS[role].strip(), f"Empty description for role: {role}"

    def test_role_descriptions_unique(self):
        """Role descriptions are not all identical (sanity check)."""
        descriptions = list(ROLE_DESCRIPTIONS.values())
        assert len(set(descriptions)) > 1, "All role descriptions are identical"

    def test_no_empty_role_codes(self):
        """No role code is empty or whitespace."""
        for role in BROAD_ROLES:
            assert role.strip() == role, f"Role has whitespace: '{role}'"
            assert role, f"Empty role code found in BROAD_ROLES"


class TestMaps:
    """Map list is complete and internally consistent."""

    def test_all_maps_have_positions(self):
        """Every map in MAPS has at least one entry in MAP_POSITIONS."""
        for m in MAPS:
            assert m in MAP_POSITIONS, f"Map '{m}' has no positions defined"
            assert MAP_POSITIONS[m], f"Map '{m}' has empty positions dict"

    def test_all_positions_have_required_fields(self):
        """Every position dict has name, zone, ct_positions, t_positions."""
        for map_name, positions in MAP_POSITIONS.items():
            for pos_code, pos_data in positions.items():
                assert "name" in pos_data, f"{map_name}/{pos_code}: missing 'name'"
                assert "zone" in pos_data, f"{map_name}/{pos_code}: missing 'zone'"
                assert "ct_positions" in pos_data, f"{map_name}/{pos_code}: missing 'ct_positions'"
                assert "t_positions" in pos_data, f"{map_name}/{pos_code}: missing 't_positions'"
                assert isinstance(pos_data["ct_positions"], list), f"{map_name}/{pos_code}: ct_positions not a list"
                assert isinstance(pos_data["t_positions"], list), f"{map_name}/{pos_code}: t_positions not a list"

    def test_position_zone_matches_its_key(self):
        """Each position's 'zone' field matches its dictionary key."""
        for map_name, positions in MAP_POSITIONS.items():
            for pos_code, pos_data in positions.items():
                assert pos_data["zone"] == pos_code, (
                    f"{map_name}/{pos_code}: zone='{pos_data['zone']}' != key '{pos_code}'"
                )

    def test_map_zones_keys_match_maps(self):
        """MAP_ZONES entries only reference maps that exist in MAP_POSITIONS."""
        for map_name, zones in MAP_ZONES.items():
            assert map_name in MAP_POSITIONS, f"MAP_ZONES references unknown map '{map_name}'"

    def test_map_zones_values_are_valid_positions(self):
        """MAP_ZONES entries only reference keys that exist in MAP_POSITIONS."""
        for map_name, zones in MAP_ZONES.items():
            for zone in zones:
                assert zone in MAP_POSITIONS[map_name], (
                    f"MAP_ZONES[{map_name}] references '{zone}' which is not a position key"
                )


class TestRolePositionPreferences:
    """Role → position preference rules are well-formed."""

    def test_all_preference_roles_valid(self):
        """Every role in ROLE_POSITION_PREFERENCES is a valid broad role."""
        for role, map_prefs in ROLE_POSITION_PREFERENCES.items():
            assert role in BROAD_ROLES, f"Preference references unknown role: '{role}'"

    def test_all_preference_maps_valid(self):
        """Every map in role preferences is a valid map."""
        for role, map_prefs in ROLE_POSITION_PREFERENCES.items():
            for map_name in map_prefs:
                assert map_name in MAPS, f"Role '{role}' references unknown map: '{map_name}'"

    def test_all_preference_positions_valid(self):
        """Every preferred position exists in MAP_POSITIONS for that map."""
        for role, map_prefs in ROLE_POSITION_PREFERENCES.items():
            for map_name, positions in map_prefs.items():
                for pos in positions:
                    assert pos in MAP_POSITIONS[map_name], (
                        f"Role '{role}' on '{map_name}' references "
                        f"unknown position: '{pos}'"
                    )


class TestZoneRoles:
    """Zone roles are tactical groupings, distinct from map positions."""

    def test_all_zones_have_descriptions(self):
        """Every zone in ZONE_ROLES has a non-empty description."""
        for zone, description in ZONE_ROLES.items():
            assert description.strip(), f"Zone '{zone}' has empty description"

    def test_zone_keys_are_strings(self):
        """All zone keys are non-empty strings."""
        for zone in ZONE_ROLES:
            assert isinstance(zone, str), f"Zone key is not a string: {type(zone)}"
            assert zone.strip(), "Empty zone key found"

    def test_zone_roles_distinct_from_map_zones(self):
        """ZONE_ROLES are tactical role labels, different from MAP_POSITIONS zone codes.

        MAP_POSITIONS zones are map-specific (e.g. 'long_a', 'mid').
        ZONE_ROLES are tactical groupings (e.g. 'a_anchor', 'entry').
        They should NOT overlap — this confirms we are not conflating the two taxonomies.
        """
        all_map_zones = set()
        for positions in MAP_POSITIONS.values():
            for pos_data in positions.values():
                all_map_zones.add(pos_data["zone"])

        overlap = ZONE_ROLES.keys() & all_map_zones
        assert not overlap, (
            f"ZONE_ROLES and MAP_POSITIONS zone codes overlap: {overlap}. "
            "They are separate taxonomies and should not share keys."
        )


class TestRoleClassificationResult:
    """RoleClassificationResult dataclass produces correct classification dicts."""

    def test_to_classifications_basic(self):
        """Basic output contains all three label axes."""
        result = RoleClassificationResult(
            steam_id=123456,
            map_name="dust2",
            side="t",
            broad_role="entry",
            map_position="short_a",
            zone_role="entry",
            confidence=0.85,
        )
        labels = result.to_classifications()

        # Should produce 3 labels: role_broad, role_map_dust2, role_zone
        assert len(labels) == 3

        label_names = {l["label_name"] for l in labels}
        assert label_names == {"role_broad", "role_map_dust2", "role_zone"}

        for lbl in labels:
            assert lbl["entity_type"] == "player"
            assert lbl["entity_id"] == 123456
            assert lbl["confidence"] == 0.85

    def test_to_classifications_with_secondary_role(self):
        """Secondary role adds a fourth label."""
        result = RoleClassificationResult(
            steam_id=999,
            map_name="mirage",
            side="ct",
            broad_role="awper",
            map_position="mid",
            zone_role="sniper_lane",
            secondary_role="second_awper",
            confidence=0.9,
        )
        labels = result.to_classifications()

        label_names = {l["label_name"] for l in labels}
        assert label_names == {
            "role_broad",
            "role_map_mirage",
            "role_zone",
            "role_secondary",
        }
        secondary = next(l for l in labels if l["label_name"] == "role_secondary")
        assert secondary["label_value"] == "second_awper"

    def test_to_classifications_role_values(self):
        """Role values are correctly set on each label."""
        result = RoleClassificationResult(
            steam_id=111,
            map_name="inferno",
            side="ct",
            broad_role="anchor",
            map_position="a_site",
            zone_role="a_anchor",
            confidence=0.7,
        )
        labels = result.to_classifications()

        by_name = {l["label_name"]: l["label_value"] for l in labels}
        assert by_name["role_broad"] == "anchor"
        assert by_name["role_map_inferno"] == "a_site"
        assert by_name["role_zone"] == "a_anchor"

    def test_metadata_passed_through(self):
        """Metadata dict is preserved on the result object."""
        result = RoleClassificationResult(
            steam_id=1,
            map_name="dust2",
            side="t",
            broad_role="lurker",
            map_position="mid",
            zone_role="flanker",
            metadata={"kills": 5},
        )
        assert result.metadata == {"kills": 5}
