"""Tests for DB ORM models (no live DB required)."""

import ast

import pytest
from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# Import the models directly to check they exist and are usable
from csda_toolkit.db.models import (
    Base,
    Classification,
    ClassifierRun,
    DemoFile,
    Event,
    EventSeries,
    Kill,
    Lineup,
    LineupPlayer,
    Match,
    MatchClassification,
    MatchContext,
    MatchEventQualifier,
    MatchPlayer,
    Player,
    PlayerAlias,
    PlayerCareerProfile,
    PlayerRoleQualitySnapshot,
    PlayerRoundKeyframe,
    PlayerRoundMovementSummary,
    PlayerRoundZoneTransition,
    Round,
    RoundClassification,
    RoundEquipment,
    RoundPurchase,
    Team,
    TeamAlias,
    TeamMembership,
    WeaponDrop,
)


class TestORMModelsExist:
    """ORM models are correctly defined and use declarative base."""

    def test_base_is_declarative(self):
        """Base has __tablename__ available for all models."""
        assert hasattr(Base, "metadata")

    def test_all_expected_models_importable(self):
        """All models listed above import without error."""
        # If this test file runs to here, all imports succeeded
        assert Base is not None

    def test_event_model(self):
        assert hasattr(Event, "__tablename__")
        assert Event.__tablename__ == "events"
        assert hasattr(Event, "extra_data")  # was: metadata, renamed

    def test_event_series_model(self):
        assert hasattr(EventSeries, "__tablename__")
        assert EventSeries.__tablename__ == "event_series"

    def test_match_model(self):
        assert hasattr(Match, "__tablename__")
        assert Match.__tablename__ == "matches"

    def test_match_context_model(self):
        assert hasattr(MatchContext, "__tablename__")
        assert MatchContext.__tablename__ == "match_contexts"

    def test_classification_model(self):
        assert hasattr(Classification, "__tablename__")
        assert Classification.__tablename__ == "classifications"
        # Polymorphic columns exist
        assert hasattr(Classification, "entity_type")
        assert hasattr(Classification, "entity_id")
        assert hasattr(Classification, "label_name")
        assert hasattr(Classification, "label_value")
        assert hasattr(Classification, "confidence")
        assert hasattr(Classification, "extra_data")  # was: metadata

    def test_classifier_run_model(self):
        assert hasattr(ClassifierRun, "__tablename__")
        assert ClassifierRun.__tablename__ == "classifier_runs"
        # Polymorphic columns
        assert hasattr(ClassifierRun, "scope_type")
        assert hasattr(ClassifierRun, "scope_id")
        assert hasattr(ClassifierRun, "match_id")  # nullable for backward compat

    def test_round_model(self):
        assert hasattr(Round, "__tablename__")
        assert Round.__tablename__ == "rounds"

    def test_player_model(self):
        assert hasattr(Player, "__tablename__")
        assert Player.__tablename__ == "players"

    def test_demo_file_model(self):
        assert hasattr(DemoFile, "__tablename__")
        assert DemoFile.__tablename__ == "demo_files"

    def test_kill_model(self):
        assert hasattr(Kill, "__tablename__")
        assert Kill.__tablename__ == "kills"

    def test_match_player_model(self):
        assert hasattr(MatchPlayer, "__tablename__")
        assert MatchPlayer.__tablename__ == "match_players"

    def test_team_model(self):
        assert hasattr(Team, "__tablename__")
        assert Team.__tablename__ == "teams"

    def test_lineup_model(self):
        assert hasattr(Lineup, "__tablename__")
        assert Lineup.__tablename__ == "lineups"

    def test_weapon_drop_model(self):
        assert hasattr(WeaponDrop, "__tablename__")
        assert WeaponDrop.__tablename__ == "weapon_drops"


class TestClassificationPolymorphic:
    """Classification model supports polymorphic entity typing."""

    def test_entity_type_column_exists(self):
        cols = {c.name for c in Classification.__table__.columns}
        assert "entity_type" in cols

    def test_entity_id_column_exists(self):
        cols = {c.name for c in Classification.__table__.columns}
        assert "entity_id" in cols

    def test_extra_data_is_the_python_attribute(self):
        """Classification uses extra_data Python attr (SQL col is 'metadata').

        SQLAlchemy's Base has a 'metadata' property, so we cannot simply
        check hasattr(Classification, 'metadata'). Instead verify extra_data exists
        and that the SQL column name is still 'metadata'.
        """
        assert hasattr(Classification, "extra_data"), (
            "Classification should have 'extra_data' Python attribute"
        )
        cols = {c.name for c in Classification.__table__.columns}
        assert "metadata" in cols, "SQL column should still be named 'metadata'"


class TestClassifierRunPolymorphic:
    """ClassifierRun supports event/series/match scope types."""

    def test_scope_type_column_exists(self):
        cols = {c.name for c in ClassifierRun.__table__.columns}
        assert "scope_type" in cols

    def test_scope_id_column_exists(self):
        cols = {c.name for c in ClassifierRun.__table__.columns}
        assert "scope_id" in cols

    def test_match_id_is_nullable(self):
        """match_id is nullable for backward compatibility with event/series scope."""
        cols = {c.name: c for c in ClassifierRun.__table__.columns}
        match_id_col = cols["match_id"]
        assert match_id_col.nullable, "match_id must be nullable"


class TestEventExtraData:
    """Event.extra_data replaces the reserved 'metadata' column name."""

    def test_event_extra_data_exists(self):
        """Event uses extra_data Python attr (SQL col is 'metadata')."""
        assert hasattr(Event, "extra_data")
        cols = {c.name for c in Event.__table__.columns}
        assert "metadata" in cols  # SQL column name unchanged


class TestMovementModels:
    """New movement storage models are correctly defined."""

    def test_player_round_keyframe(self):
        assert PlayerRoundKeyframe.__tablename__ == "player_round_keyframes"
        cols = {c.name for c in PlayerRoundKeyframe.__table__.columns}
        assert {"match_id", "round_number", "steam_id", "tick", "x", "y", "z", "side"}.issubset(cols)

    def test_player_round_zone_transition(self):
        assert PlayerRoundZoneTransition.__tablename__ == "player_round_zone_transitions"
        cols = {c.name for c in PlayerRoundZoneTransition.__table__.columns}
        assert {"match_id", "round_number", "steam_id", "tick", "zone", "zone_category"}.issubset(cols)

    def test_player_round_movement_summary(self):
        assert PlayerRoundMovementSummary.__tablename__ == "player_round_movement_summaries"
        cols = {c.name for c in PlayerRoundMovementSummary.__table__.columns}
        assert {"match_id", "round_number", "steam_id", "total_distance", "avg_speed",
                "time_in_site", "zone_transition_count"}.issubset(cols)

    def test_movement_models_have_match_relationship(self):
        """Movement models back-populate to Match."""
        rel_names = {r.key for r in Match.__mapper__.relationships}
        assert "player_round_keyframes" in rel_names
        assert "player_round_zone_transitions" in rel_names
        assert "player_round_movement_summaries" in rel_names


class TestRoleQualitySnapshot:
    """PlayerRoleQualitySnapshot stores all 5 role quality profiles per match."""

    def test_table_name(self):
        assert PlayerRoleQualitySnapshot.__tablename__ == "player_role_quality_snapshots"

    def test_scope_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"match_id", "steam_id", "map_name", "side"}.issubset(cols)

    def test_role_classification_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"broad_role", "map_position", "zone_role", "secondary_role", "role_confidence"}.issubset(cols)

    def test_entry_quality_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"entry_quality_score", "entry_attempts", "successful_entries",
                "entry_kill_rate", "flash_pop_kills", "opening_duel_wins"}.issubset(cols)

    def test_awp_quality_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"awp_quality_score", "awp_rounds", "first_pick_rounds",
                "opening_pick_rate", "ct_hold_picks", "awper_profile_json"}.issubset(cols)

    def test_support_quality_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"support_quality_score", "support_rounds", "trade_opportunities",
                "successful_trades", "trade_success_rate", "support_profile_json"}.issubset(cols)

    def test_rifler_quality_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"rifler_quality_score", "rifler_rounds", "multi_kill_rounds",
                "headshot_rate", "ct_site_anchor_rounds", "rifler_profile_json"}.issubset(cols)

    def test_lurker_quality_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"lurker_quality_score", "lurk_attempts", "solo_kills",
                "rotation_cut_kills", "clutch_rounds", "lurker_profile_json"}.issubset(cols)

    def test_profile_json_columns(self):
        cols = {c.name for c in PlayerRoleQualitySnapshot.__table__.columns}
        assert {"entry_profile_json", "awper_profile_json", "support_profile_json",
                "rifler_profile_json", "lurker_profile_json"}.issubset(cols)

    def test_match_relationship(self):
        rel_names = {r.key for r in Match.__mapper__.relationships}
        assert "player_role_quality_snapshots" in rel_names

    def test_unique_constraint(self):
        """One row per (match_id, steam_id, map_name, side)."""
        ucs = {uc.name for uc in PlayerRoleQualitySnapshot.__table__.constraints
                if hasattr(uc, "name")}
        assert "uq_prqs_match_steam_map_side" in ucs


class TestPlayerCareerProfile:
    """PlayerCareerProfile is the comprehensive career-level data warehouse table."""

    def test_table_name(self):
        assert PlayerCareerProfile.__tablename__ == "player_career_profiles"

    def test_identity_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"steam_id", "display_name"}.issubset(cols)

    def test_match_totals_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"matches_played", "rounds_played", "rounds_won", "win_rate", "maps_played"}.issubset(cols)

    def test_kd_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_kills", "total_deaths", "kd_ratio", "total_assists",
                "headshot_kills", "headshot_rate"}.issubset(cols)

    def test_rate_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"kast_rate", "adrd"}.issubset(cols)

    def test_role_distribution_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"role_entry_rounds", "role_awper_rounds", "role_support_rounds",
                "role_rifler_rounds", "role_lurker_rounds", "role_igl_rounds"}.issubset(cols)

    def test_role_quality_avg_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"entry_quality_avg", "awp_quality_avg", "support_quality_avg",
                "rifler_quality_avg", "lurker_quality_avg"}.issubset(cols)

    def test_entry_career_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_entry_attempts", "total_successful_entries", "entry_kill_rate",
                "total_flash_pop_kills", "flash_pop_rate", "total_opening_duel_wins",
                "opening_duel_win_rate", "entry_survived_post_entry", "entry_survival_rate"}.issubset(cols)

    def test_awp_career_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_awp_rounds", "total_first_pick_rounds", "opening_pick_rate",
                "ct_hold_picks_total", "ct_survived_after_pick_total"}.issubset(cols)

    def test_support_career_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_support_rounds", "total_trade_opportunities", "total_successful_trades",
                "trade_success_rate", "total_flash_assisted_kills", "economy_sacrifice_rounds"}.issubset(cols)

    def test_rifler_career_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_rifler_rounds", "total_multi_kill_rounds", "multi_kill_rate",
                "rifler_trade_kills_total", "avg_headshot_rate",
                "ct_anchor_rounds_total", "ct_survived_anchor_total"}.issubset(cols)

    def test_lurker_career_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_lurk_attempts", "total_solo_kills", "solo_kill_rate",
                "total_rotation_cut_kills", "survived_lurk_rounds_total",
                "clutch_rounds_total", "clutch_rounds_won_total", "clutch_win_rate"}.issubset(cols)

    def test_movement_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"avg_distance_per_round", "avg_speed_per_round",
                "avg_zone_transitions_per_round"}.issubset(cols)

    def test_economy_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"avg_equipment_value", "eco_rounds_total",
                "force_rounds_total", "full_buy_rounds_total"}.issubset(cols)

    def test_utility_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"total_flashes_thrown", "total_smokes_thrown", "total_he_detonations",
                "total_molly_detonations", "total_enemies_flashed",
                "total_utility_damage"}.issubset(cols)

    def test_json_breakdown_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"per_map_stats", "per_weapon_stats", "recent_form",
                "peak_ratings"}.issubset(cols)

    def test_temporal_columns(self):
        cols = {c.name for c in PlayerCareerProfile.__table__.columns}
        assert {"first_seen_at", "last_updated", "created_at"}.issubset(cols)

    def test_steam_id_unique_constraint(self):
        """One row per steam_id."""
        ucs = {uc.name for uc in PlayerCareerProfile.__table__.constraints
                if hasattr(uc, "name")}
        assert "uq_pcp_steam_id" in ucs
