"""Tests for domain model dataclasses."""

import pytest
from csda_toolkit.domain.models import (
    Classification,
    Event,
    EventSeries,
    Match,
    MatchContext,
    RoleClassification,
)


class TestRoleClassification:
    """RoleClassification dataclass."""

    def test_basic_construction(self):
        rc = RoleClassification(
            player_steam_id=123456,
            map_name="dust2",
            side="t",
            broad_role="entry",
            map_position="short_a",
            zone_role="entry",
            confidence=0.85,
        )
        assert rc.player_steam_id == 123456
        assert rc.map_name == "dust2"
        assert rc.side == "t"
        assert rc.broad_role == "entry"
        assert rc.map_position == "short_a"
        assert rc.zone_role == "entry"
        assert rc.secondary_role is None
        assert rc.confidence == 0.85

    def test_with_secondary_role(self):
        rc = RoleClassification(
            player_steam_id=999,
            map_name="mirage",
            side="ct",
            broad_role="awper",
            map_position="mid",
            zone_role="sniper_lane",
            secondary_role="second_awper",
            confidence=0.9,
        )
        assert rc.secondary_role == "second_awper"

    def test_role_code_property(self):
        """role_code returns broad_role_map_position format."""
        rc = RoleClassification(
            player_steam_id=1,
            map_name="dust2",
            side="t",
            broad_role="lurker",
            map_position="mid",
            zone_role="flanker",
        )
        assert rc.role_code == "lurker_mid"

    def test_metadata_dict(self):
        rc = RoleClassification(
            player_steam_id=3,
            map_name="nuke",
            side="t",
            broad_role="support",
            map_position="outside",
            zone_role="utility",
            metadata={"kills": 5, "assists": 2},
        )
        assert rc.metadata["kills"] == 5
        assert rc.metadata["assists"] == 2

    def test_confidence_default(self):
        """confidence defaults to 0.0 when not provided."""
        rc = RoleClassification(
            player_steam_id=5,
            map_name="inferno",
            side="ct",
            broad_role="anchor",
            map_position="a_site",
            zone_role="a_anchor",
        )
        assert rc.confidence == 0.0


class TestClassification:
    """Classification dataclass."""

    def test_basic_construction(self):
        c = Classification(
            entity_type="match",
            entity_id=100,
            label_name="map_name",
            label_value="dust2",
            confidence=1.0,
        )
        assert c.entity_type == "match"
        assert c.entity_id == 100
        assert c.label_name == "map_name"
        assert c.label_value == "dust2"
        assert c.confidence == 1.0
        assert c.metadata == {}

    def test_with_metadata(self):
        c = Classification(
            entity_type="player",
            entity_id=123456,
            label_name="role_broad",
            label_value="entry",
            confidence=0.78,
            metadata={"source": "kmeans", "k": 5},
        )
        assert c.metadata["source"] == "kmeans"
        assert c.metadata["k"] == 5

    def test_classifier_run_id_field(self):
        """classifier_run_id is a field on Classification."""
        c = Classification(
            classifier_run_id=42,
            entity_type="player",
            entity_id=111,
            label_name="buy_type",
            label_value="full_buy",
        )
        assert c.classifier_run_id == 42


class TestEvent:
    """Event dataclass."""

    def test_basic_construction(self):
        e = Event(name="BLAST Rivals 2026")
        assert e.name == "BLAST Rivals 2026"

    def test_all_fields(self):
        e = Event(
            name="BLAST Rivals 2026",
            slug="blast-rivals-2026",
            tier=1,
            region="EU",
            source="hltv",
        )
        assert e.tier == 1
        assert e.region == "EU"
        assert e.source == "hltv"
        assert e.slug == "blast-rivals-2026"

    def test_metadata_optional(self):
        e = Event(name="ESL Pro League")
        assert e.metadata == {}
        assert e.tier == 0


class TestEventSeries:
    """EventSeries dataclass."""

    def test_basic_construction(self):
        es = EventSeries(
            event_id=1,
            series_type="bo3",
            team_a_name="Vitality",
            team_b_name="FUT",
        )
        assert es.event_id == 1
        assert es.series_type == "bo3"
        assert es.team_a_name == "Vitality"
        assert es.team_b_name == "FUT"

    def test_defaults(self):
        es = EventSeries(event_id=1)
        assert es.series_type == ""
        assert es.team_a_id == 0
        assert es.team_b_id == 0


class TestMatch:
    """Match dataclass."""

    def test_basic_construction(self):
        m = Match(map_name="dust2", tick_rate=128)
        assert m.map_name == "dust2"
        assert m.tick_rate == 128

    def test_fields(self):
        m = Match(
            map_name="mirage",
            tick_rate=64,
            series_id=1,
            map_number=2,
            server_name="VALVE",
        )
        assert m.series_id == 1
        assert m.map_number == 2
        assert m.server_name == "VALVE"


class TestMatchContext:
    """MatchContext dataclass."""

    def test_basic_construction(self):
        mc = MatchContext(
            context_provider="cli",
            event_name="BLAST Rivals",
        )
        assert mc.context_provider == "cli"
        assert mc.event_name == "BLAST Rivals"

    def test_defaults(self):
        mc = MatchContext()
        assert mc.tier_estimate is None
        assert mc.event_id == 0
        assert mc.is_structured_team_play is False
