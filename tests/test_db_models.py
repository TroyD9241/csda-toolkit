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
