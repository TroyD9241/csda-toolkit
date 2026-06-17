"""SQLAlchemy 2.0 ORM models for csda-toolkit.

Replicates all 7 migrations from the CSDEMOANALYZER Postgres schema.
All tables live in the ``csda`` schema.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Migration 0001: Initial schema ──────────────────────────────────────────


class DemoFile(Base):
    __tablename__ = "demo_files"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demo_filename: Mapped[str] = mapped_column(Text)
    demo_checksum: Mapped[str] = mapped_column(Text)
    parser_name: Mapped[str] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped[Optional["Match"]] = relationship(back_populates="demo_file")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demo_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.demo_files.id"), nullable=True
    )
    map_name: Mapped[str] = mapped_column(Text)
    tick_rate: Mapped[int] = mapped_column(Integer)
    server_name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    canonical_match_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    played_at_source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    played_at_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    series_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.event_series.id"), nullable=True
    )
    map_number: Mapped[int] = mapped_column(Integer, default=0)

    demo_file: Mapped[Optional["DemoFile"]] = relationship(back_populates="match")
    rounds: Mapped[list["Round"]] = relationship(back_populates="match")
    kills: Mapped[list["Kill"]] = relationship(back_populates="match")
    match_players: Mapped[list["MatchPlayer"]] = relationship(back_populates="match")
    match_teams: Mapped[list["MatchTeam"]] = relationship(back_populates="match")
    series: Mapped[Optional["EventSeries"]] = relationship(back_populates="matches")
    match_context: Mapped[Optional["MatchContext"]] = relationship(
        back_populates="match", uselist=False
    )
    external_match_links: Mapped[list["ExternalMatchLink"]] = relationship(
        back_populates="match"
    )
    analyst_notes: Mapped[list["AnalystNote"]] = relationship(back_populates="match")
    classifier_runs: Mapped[list["ClassifierRun"]] = relationship(
        back_populates="match"
    )
    match_classifications: Mapped[list["MatchClassification"]] = relationship(
        back_populates="match"
    )
    match_event_qualifier: Mapped[Optional["MatchEventQualifier"]] = relationship(
        back_populates="match", uselist=False
    )
    round_equipment: Mapped[list["RoundEquipment"]] = relationship(
        back_populates="match"
    )
    round_purchases: Mapped[list["RoundPurchase"]] = relationship(
        back_populates="match"
    )
    weapon_drops: Mapped[list["WeaponDrop"]] = relationship(back_populates="match")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    last_known_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    match_players: Mapped[list["MatchPlayer"]] = relationship(back_populates="player")
    lineup_players: Mapped[list["LineupPlayer"]] = relationship(
        back_populates="player"
    )
    team_memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="player"
    )
    player_situation_roles: Mapped[list["PlayerSituationRole"]] = relationship(
        back_populates="player"
    )
    player_aliases: Mapped[list["PlayerAlias"]] = relationship(
        back_populates="player"
    )


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    match_player_index: Mapped[int] = mapped_column(SmallInteger)
    player_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.players.id"), nullable=True
    )
    match_team_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.match_teams.id"), nullable=True
    )
    steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    display_name: Mapped[str] = mapped_column(Text)
    team_side: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="match_players")
    player: Mapped[Optional["Player"]] = relationship(back_populates="match_players")
    match_team: Mapped[Optional["MatchTeam"]] = relationship(
        back_populates="match_players"
    )


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer)
    start_tick: Mapped[int] = mapped_column(Integer)
    end_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    winner_side: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    end_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_t: Mapped[int] = mapped_column(SmallInteger)
    score_ct: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="rounds")
    kills: Mapped[list["Kill"]] = relationship(back_populates="round")
    round_classifications: Mapped[list["RoundClassification"]] = relationship(
        back_populates="round"
    )


class Kill(Base):
    __tablename__ = "kills"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer)
    kill_index: Mapped[int] = mapped_column(Integer)
    tick: Mapped[int] = mapped_column(Integer)
    killer_match_player_index: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    killer_name_raw: Mapped[str] = mapped_column(Text)
    victim_match_player_index: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    victim_name_raw: Mapped[str] = mapped_column(Text)
    assister_match_player_index: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    assister_name_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weapon_name: Mapped[str] = mapped_column(Text)
    is_headshot: Mapped[bool] = mapped_column(Boolean)
    is_wallbang: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="kills")
    round: Mapped["Round"] = relationship(back_populates="kills")


class ExternalMatchLink(Base):
    __tablename__ = "external_match_links"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text)
    external_match_id: Mapped[str] = mapped_column(Text)
    linked_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="external_match_links")


class AnalystNote(Base):
    __tablename__ = "analyst_notes"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    match_player_index: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    scope: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="analyst_notes")


# ── Migration 0002: Events and series ───────────────────────────────────────


class Event(Base):
    __tablename__ = "events"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, default="")
    tier: Mapped[int] = mapped_column(SmallInteger, default=0)
    region: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="unknown")
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    series: Mapped[list["EventSeries"]] = relationship(back_populates="event")


class EventSeries(Base):
    __tablename__ = "event_series"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.events.id"), nullable=False
    )
    series_type: Mapped[str] = mapped_column(Text, default="")
    round_name: Mapped[str] = mapped_column(Text, default="")
    team_a_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=True
    )
    team_b_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=True
    )
    team_a_name: Mapped[str] = mapped_column(Text, default="")
    team_b_name: Mapped[str] = mapped_column(Text, default="")
    team_a_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    team_b_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    map_veto_json: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    event: Mapped["Event"] = relationship(back_populates="series")
    matches: Mapped[list["Match"]] = relationship(back_populates="series")
    team_a: Mapped[Optional["Team"]] = relationship(foreign_keys=[team_a_id])
    team_b: Mapped[Optional["Team"]] = relationship(foreign_keys=[team_b_id])


# ── Migration 0003: Teams and match context ─────────────────────────────────


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(Text)
    slug: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_provisional: Mapped[bool] = mapped_column(Boolean, default=False)
    team_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_team_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parent_team: Mapped[Optional["Team"]] = relationship(
        "Team", remote_side="Team.id", back_populates="child_teams"
    )
    child_teams: Mapped[list["Team"]] = relationship(
        "Team", back_populates="parent_team"
    )
    external_links: Mapped[list["ExternalTeamLink"]] = relationship(
        back_populates="team"
    )
    aliases: Mapped[list["TeamAlias"]] = relationship(back_populates="team")
    match_teams: Mapped[list["MatchTeam"]] = relationship(back_populates="team")
    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team"
    )


class ExternalTeamLink(Base):
    __tablename__ = "external_team_links"
    __table_args__ = (
        UniqueConstraint("provider", "external_team_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text)
    external_team_id: Mapped[str] = mapped_column(Text)
    external_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    team: Mapped["Team"] = relationship(back_populates="external_links")


class TeamAlias(Base):
    __tablename__ = "team_aliases"
    __table_args__ = (
        UniqueConstraint("team_id", "alias_normalized", "source"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=False
    )
    alias: Mapped[str] = mapped_column(Text)
    alias_normalized: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    team_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_org_relationship: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    team: Mapped["Team"] = relationship(back_populates="aliases")


class MatchTeam(Base):
    __tablename__ = "match_teams"
    __table_args__ = (
        UniqueConstraint("match_id", "team_slot"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    team_slot: Mapped[int] = mapped_column(SmallInteger)
    team_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=True
    )
    lineup_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.lineups.id"), nullable=True
    )
    parent_team_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(Text)
    starting_side: Mapped[str] = mapped_column(Text, default="unknown")
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_winner: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="match_teams")
    team: Mapped[Optional["Team"]] = relationship(
        back_populates="match_teams", foreign_keys=[team_id]
    )
    parent_org: Mapped[Optional["Team"]] = relationship(
        "Team", foreign_keys=[parent_team_id]
    )
    lineup: Mapped[Optional["Lineup"]] = relationship(back_populates="match_teams")
    match_players: Mapped[list["MatchPlayer"]] = relationship(
        back_populates="match_team"
    )


class MatchContext(Base):
    __tablename__ = "match_contexts"
    __table_args__ = {"schema": "csda"}

    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), primary_key=True
    )
    context_provider: Mapped[str] = mapped_column(Text)
    play_environment: Mapped[str] = mapped_column(Text)
    is_structured_team_play: Mapped[bool] = mapped_column(Boolean, default=False)
    tier_estimate: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    analysis_pool: Mapped[str] = mapped_column(Text)
    classification_source: Mapped[str] = mapped_column(Text)
    classification_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.events.id"), nullable=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="match_context")
    event: Mapped[Optional["Event"]] = relationship()


# ── Migration 0004: Lineups and roster history ──────────────────────────────


class Lineup(Base):
    __tablename__ = "lineups"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lineup_hash: Mapped[str] = mapped_column(Text, unique=True)
    player_count: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lineup_players: Mapped[list["LineupPlayer"]] = relationship(
        back_populates="lineup"
    )
    match_teams: Mapped[list["MatchTeam"]] = relationship(back_populates="lineup")


class LineupPlayer(Base):
    __tablename__ = "lineup_players"
    __table_args__ = {"schema": "csda"}

    lineup_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.lineups.id"), primary_key=True
    )
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.players.id"), primary_key=True
    )
    slot_index: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    lineup: Mapped["Lineup"] = relationship(back_populates="lineup_players")
    player: Mapped["Player"] = relationship(back_populates="lineup_players")


class TeamMembership(Base):
    __tablename__ = "team_memberships"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.teams.id"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.players.id"), nullable=False
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    membership_type: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped["Team"] = relationship(back_populates="memberships")
    player: Mapped["Player"] = relationship(back_populates="team_memberships")


# ── Migration 0005: Team type hierarchy (alters teams — already in Team model)


# ── Migration 0006: Classification pipeline ─────────────────────────────────


class ClassifierRun(Base):
    __tablename__ = "classifier_runs"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_name: Mapped[str] = mapped_column(Text)
    classifier_version: Mapped[str] = mapped_column(Text)
    match_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(Text, default="match")
    scope_id: Mapped[int] = mapped_column(Integer, default=0)
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    match: Mapped[Optional["Match"]] = relationship(back_populates="classifier_runs")
    round_classifications: Mapped[list["RoundClassification"]] = relationship(
        back_populates="classifier_run"
    )
    player_situation_roles: Mapped[list["PlayerSituationRole"]] = relationship(
        back_populates="classifier_run"
    )
    match_classifications: Mapped[list["MatchClassification"]] = relationship(
        back_populates="classifier_run"
    )
    classifications: Mapped[list["Classification"]] = relationship(
        back_populates="classifier_run"
    )


class RoundClassification(Base):
    __tablename__ = "round_classifications"
    __table_args__ = (
        UniqueConstraint("classifier_run_id", "round_id", "label_name"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.classifier_runs.id"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.rounds.id"), nullable=False
    )
    label_name: Mapped[str] = mapped_column(Text)
    label_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    classifier_run: Mapped["ClassifierRun"] = relationship(
        back_populates="round_classifications"
    )
    round: Mapped["Round"] = relationship(back_populates="round_classifications")


class PlayerSituationRole(Base):
    __tablename__ = "player_situation_roles"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.classifier_runs.id"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.players.id"), nullable=False
    )
    lineup_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.lineups.id"), nullable=True
    )
    map_name: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)
    role_code: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    classifier_run: Mapped["ClassifierRun"] = relationship(
        back_populates="player_situation_roles"
    )
    player: Mapped["Player"] = relationship(back_populates="player_situation_roles")


class MatchClassification(Base):
    __tablename__ = "match_classifications"
    __table_args__ = (
        UniqueConstraint("classifier_run_id", "match_id", "label_name"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.classifier_runs.id"), nullable=False
    )
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    label_name: Mapped[str] = mapped_column(Text)
    label_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    classifier_run: Mapped["ClassifierRun"] = relationship(
        back_populates="match_classifications"
    )
    match: Mapped["Match"] = relationship(back_populates="match_classifications")


class Classification(Base):
    __tablename__ = "classifications"
    __table_args__ = (
        Index("ix_classifications_entity", "entity_type", "entity_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classifier_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.classifier_runs.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(Integer)
    label_name: Mapped[str] = mapped_column(Text)
    label_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    classifier_run: Mapped["ClassifierRun"] = relationship(
        back_populates="classifications"
    )


class MatchEventQualifier(Base):
    __tablename__ = "match_event_qualifiers"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), unique=True, nullable=False
    )
    network_type: Mapped[str] = mapped_column(Text, default="unknown")
    crowd_level: Mapped[str] = mapped_column(Text, default="unknown")
    crowd_consistency: Mapped[str] = mapped_column(Text, default="unknown")
    crowd_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, default="unknown")
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="match_event_qualifier")


# ── Migration 0007: Player aliases ──────────────────────────────────────────


class PlayerAlias(Base):
    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint("steam_id", "alias", "source"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[int] = mapped_column(BigInteger)
    alias: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="player_aliases",
        foreign_keys=[steam_id],
        primaryjoin="PlayerAlias.steam_id == Player.steam_id")


# ── Migration 0008: Round equipment, purchases, and weapon drops ────────────


class RoundEquipment(Base):
    __tablename__ = "round_equipment"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer)
    steam_id: Mapped[int] = mapped_column(BigInteger)
    player_name: Mapped[str] = mapped_column(Text)
    equipment_value: Mapped[int] = mapped_column(Integer)
    weapons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    armor: Mapped[bool] = mapped_column(Boolean)
    helmet: Mapped[bool] = mapped_column(Boolean)
    defuse_kit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="round_equipment")


class RoundPurchase(Base):
    __tablename__ = "round_purchases"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer)
    tick: Mapped[int] = mapped_column(Integer)
    steam_id: Mapped[int] = mapped_column(BigInteger)
    player_name: Mapped[str] = mapped_column(Text)
    weapon_name: Mapped[str] = mapped_column(Text)
    weapon_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="round_purchases")


class WeaponDrop(Base):
    __tablename__ = "weapon_drops"
    __table_args__ = {"schema": "csda"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer)
    tick: Mapped[int] = mapped_column(Integer)
    weapon_name: Mapped[str] = mapped_column(Text)
    dropped_by_steam_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    dropped_by_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    picked_up_by_steam_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    picked_up_by_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="weapon_drops")
