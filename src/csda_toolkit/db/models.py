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
    and_,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, foreign, mapped_column, relationship


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
    round_side_maps: Mapped[list["RoundSideMap"]] = relationship(back_populates="match")
    player_round_weapons: Mapped[list["PlayerRoundWeapon"]] = relationship(
        back_populates="match"
    )
    damage_events: Mapped[list["DamageEvent"]] = relationship(back_populates="match")
    player_blinds: Mapped[list["PlayerBlind"]] = relationship(back_populates="match")
    grenade_detonations: Mapped[list["GrenadeDetonation"]] = relationship(back_populates="match")
    inferno_events: Mapped[list["InfernoEvent"]] = relationship(back_populates="match")
    grenade_trajectories: Mapped[list["GrenadeTrajectory"]] = relationship(back_populates="match")
    player_round_stats: Mapped[list["PlayerRoundStats"]] = relationship(back_populates="match")
    bomb_events: Mapped[list["BombEvent"]] = relationship(back_populates="match")
    player_round_keyframes: Mapped[list["PlayerRoundKeyframe"]] = relationship(
        back_populates="match"
    )
    player_round_zone_transitions: Mapped[list["PlayerRoundZoneTransition"]] = relationship(
        back_populates="match"
    )
    player_round_movement_summaries: Mapped[list["PlayerRoundMovementSummary"]] = relationship(
        back_populates="match"
    )
    player_role_quality_snapshots: Mapped[list["PlayerRoleQualitySnapshot"]] = relationship(
        back_populates="match"
    )


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
        back_populates="player",
        primaryjoin="Player.steam_id == PlayerAlias.steam_id",
        foreign_keys="PlayerAlias.steam_id",
    )
    player_round_weapons: Mapped[list["PlayerRoundWeapon"]] = relationship(
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
    # NOTE: Kill↔Round composite relationship (match_id+round_number) is not
    # modeled as an ORM relationship due to the lack of a FK. Use explicit
    # query joins to access kills per round:
    #   s.query(Kill).join(Round, and_(Kill.match_id==Round.match_id,
    #                                  Kill.round_number==Round.round_number))
    kills: Mapped[list["Kill"]] = relationship(
        primaryjoin=(
            "and_("
            "Round.match_id == foreign(Kill.match_id), "
            "Round.round_number == Kill.round_number)"
        ),
        viewonly=True,
    )
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
    killer_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    victim_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    assister_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="kills")
    # NOTE: Round relationship not modeled — use explicit join by
    # (match_id, round_number). See Round.kills note above.


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
    match_teams: Mapped[list["MatchTeam"]] = relationship(
        back_populates="team",
        foreign_keys="MatchTeam.team_id",  # disambiguate from parent_team_id FK
    )
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
    entity_id: Mapped[int] = mapped_column(BigInteger)  # holds 64-bit Steam IDs and other entity IDs
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


class RoundSideMap(Base):
    """Per-round per-team-side assignment for a match.

    Tracks which side (t/ct) each team slot was on for every round,
    including overtime rounds. Derived from player_frame data at
    round start tick.

    overtime_index: 0 = regulation, 1..N = overtime round pairs
    """
    __tablename__ = "round_side_map"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "team_slot", "round_number", "overtime_index",
            name="uq_round_side_map",
        ),
        Index("ix_round_side_map_match_team", "match_id", "team_slot"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    team_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    overtime_index: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    side: Mapped[str] = mapped_column(Text, nullable=False)  # 't' or 'ct'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="round_side_maps")


class Weapon(Base):
    """Reference table for all CS2 weapons and equipment.

    Populated via migration seed. Defindex is the CS2 item definition index.
    weapon_key is the canonical internal name used across the toolkit.

    Damage stats sourced from https://cs2damage.com/weapons/
    """
    __tablename__ = "weapons"
    __table_args__ = {"schema": "csda"}

    defindex: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    weapon_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)  # pistol, rifle, sniper, smg, heavy, grenade, armor, utility, equipment, melee, gloves, explosive
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0=primary, 1=pistol, 2=melee, 4=equipment, 5=grenade, 8=armor, 9=defuse, 10=c4
    cost: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # USD buy menu price
    # Damage stats (https://cs2damage.com/weapons/)
    damage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    armor_penetration: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)  # percentage e.g. 77.5
    rpm: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # rounds per minute
    magazine_size: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    head_damage_armored: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # headshot damage vs armored opponent
    chest_damage_armored: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)  # chest damage vs armored opponent

    player_round_weapons: Mapped[list["PlayerRoundWeapon"]] = relationship(
        primaryjoin="Weapon.defindex == foreign(PlayerRoundWeapon.weapon_defindex)",
        viewonly=True,
    )


class PlayerRoundWeapon(Base):
    """What weapon(s) each player has in each round.

    Tracks both equipped weapons (from player frame tick data) and purchased
    weapons (from item_purchase events). Dropped weapons are marked separately.
    """
    __tablename__ = "player_round_weapons"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "round_number", "steam_id", "weapon_key",
            name="uq_prw_round_steam_weapon",
        ),
        Index("ix_prw_match_round", "match_id", "round_number"),
        Index("ix_prw_steam_id", "steam_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    steam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    player_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("csda.players.id"), nullable=True
    )
    weapon_key: Mapped[str] = mapped_column(Text, nullable=False)
    weapon_defindex: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )  # informational only — not FK; use weapon_key as canonical identifier
    is_equipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_purchased: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_dropped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acquired_at_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dropped_at_tick: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purchase_cost: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_round_weapons")
    player: Mapped[Optional["Player"]] = relationship(back_populates="player_round_weapons")
    weapon: Mapped[Optional["Weapon"]] = relationship(
        primaryjoin="PlayerRoundWeapon.weapon_defindex == foreign(Weapon.defindex)",
        viewonly=True,
        foreign_keys=[weapon_defindex],
    )


# ── Migration 0009: Event data ingest (grenades, damage, blinds, stats) ────────


class DamageEvent(Base):
    """Grenade and bullet damage events (player_hurt).

    attacker_last_place_name / victim_last_place_name are CS2's internal map
    zone labels (e.g. 'Long A', 'BombsiteA', 'Mid'). No bounding-box inference needed.
    """
    __tablename__ = "damage_events"
    __table_args__ = (
        Index("ix_damage_match_tick", "match_id", "tick"),
        Index("ix_damage_match_round", "match_id", "round_number"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    tick: Mapped[int] = mapped_column(Integer)
    round_number: Mapped[int] = mapped_column(SmallInteger)
    attacker_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    attacker_name: Mapped[str] = mapped_column(Text)
    victim_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    victim_name: Mapped[str] = mapped_column(Text)
    weapon: Mapped[str] = mapped_column(Text)
    dmg_health: Mapped[int] = mapped_column(SmallInteger)
    dmg_armor: Mapped[int] = mapped_column(SmallInteger)
    hitgroup: Mapped[int] = mapped_column(SmallInteger)
    health: Mapped[int] = mapped_column(SmallInteger)
    armor: Mapped[int] = mapped_column(SmallInteger)
    hitgroup_name: Mapped[str] = mapped_column(Text)
    attacker_last_place_name: Mapped[str] = mapped_column(Text)
    victim_last_place_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="damage_events")


class BombEvent(Base):
    """Bomb-related events: plant, defuse, explode, dropped, picked up."""
    __tablename__ = "bomb_events"
    __table_args__ = (
        Index("ix_be_match_tick", "match_id", "tick"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    tick: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(Text)  # planted | defused | exploded | dropped | pickup
    player_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    player_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    site: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # A | B
    has_kit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="bomb_events")


class PlayerBlind(Base):
    """Flashbang blind events (player_blind)."""
    __tablename__ = "player_blinds"
    __table_args__ = (
        Index("ix_blind_match_tick", "match_id", "tick"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    tick: Mapped[int] = mapped_column(Integer)
    attacker_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    attacker_name: Mapped[str] = mapped_column(Text)
    victim_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    victim_name: Mapped[str] = mapped_column(Text)
    blind_duration: Mapped[float] = mapped_column(Numeric(6, 3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_blinds")


class GrenadeDetonation(Base):
    """Grenade detonation events (he, flash, smoke expire).

    x/y/z is the landing/detonation position.
    """
    __tablename__ = "grenade_detonations"
    __table_args__ = (
        Index("ix_gd_match_tick", "match_id", "tick"),
        Index("ix_gd_match_round", "match_id", "round_number"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger)
    tick: Mapped[int] = mapped_column(Integer)
    grenade_type: Mapped[str] = mapped_column(Text)
    player_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    player_name: Mapped[str] = mapped_column(Text)
    x: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    y: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    z: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="grenade_detonations")


class InfernoEvent(Base):
    """Molotov/incendiary start_burn and expire events.

    x/y/z is the fire's position.
    """
    __tablename__ = "inferno_events"
    __table_args__ = (
        Index("ix_inf_match_tick", "match_id", "tick"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    tick: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(Text)  # start_burn | expire
    player_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    player_name: Mapped[str] = mapped_column(Text)
    x: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    y: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    z: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="inferno_events")


class GrenadeTrajectory(Base):
    """Individual trajectory points for grenades in flight.

    Each grenade throw produces multiple trajectory points (path through air).
    grenade_entity_id groups points belonging to the same throw.
    """
    __tablename__ = "grenade_trajectories"
    __table_args__ = (
        Index("ix_gt_match_tick", "match_id", "tick"),
        Index("ix_gt_entity", "match_id", "grenade_entity_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger)
    tick: Mapped[int] = mapped_column(Integer)
    grenade_entity_id: Mapped[int] = mapped_column(Integer)
    grenade_type: Mapped[str] = mapped_column(Text)
    thrower_steam_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    thrower_name: Mapped[str] = mapped_column(Text)
    x: Mapped[float] = mapped_column(Numeric(10, 2))
    y: Mapped[float] = mapped_column(Numeric(10, 2))
    z: Mapped[float] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="grenade_trajectories")


class PlayerRoundStats(Base):
    """Per-player cumulative stats at a tick (from ActionTrackingServices).

    Snapshot of kills/assists/deaths/damage/utility at a specific tick.
    """
    __tablename__ = "player_round_stats"
    __table_args__ = (
        Index("ix_prs_match_round_steam", "match_id", "round_number", "steam_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger)
    tick: Mapped[int] = mapped_column(Integer)
    steam_id: Mapped[int] = mapped_column(BigInteger)
    kills: Mapped[int] = mapped_column(SmallInteger)
    assists: Mapped[int] = mapped_column(SmallInteger)
    deaths: Mapped[int] = mapped_column(SmallInteger)
    damage: Mapped[int] = mapped_column(Integer)
    headshot_kills: Mapped[int] = mapped_column(Integer)
    cash_earned: Mapped[int] = mapped_column(Integer)
    equipment_value: Mapped[int] = mapped_column(Integer)
    utility_damage: Mapped[int] = mapped_column(Integer)
    enemies_flashed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_round_stats")


# ── Movement & Position Storage ──────────────────────────────────────────────


class PlayerRoundKeyframe(Base):
    """Sampled player position at a tick within a round.

    Sampled every 1000 ticks (~8s). Used for movement heatmaps, average positions,
    and path reconstruction.
    """
    __tablename__ = "player_round_keyframes"
    __table_args__ = (
        Index("ix_prk_match_round_steam_tick", "match_id", "round_number", "steam_id", "tick"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    steam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    player_name: Mapped[str] = mapped_column(Text)
    tick: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[float] = mapped_column(Numeric(10, 2))
    y: Mapped[float] = mapped_column(Numeric(10, 2))
    z: Mapped[float] = mapped_column(Numeric(10, 2))
    eye_angle_x: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    eye_angle_y: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    eye_angle_z: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    velocity_modifier: Mapped[float] = mapped_column(Numeric(4, 3), default=1.0)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    health: Mapped[int] = mapped_column(SmallInteger, default=100)
    side: Mapped[str] = mapped_column(Text, default="")  # "t" or "ct"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_round_keyframes")


class PlayerRoundZoneTransition(Base):
    """A player's zone change within a round, tracked via CS2 last_place_name.

    Includes the zone at round start (first observed) and each subsequent transition.
    Zone categories are inferred via categorize_zone() (site | mid | spawn | connector | unknown).
    """
    __tablename__ = "player_round_zone_transitions"
    __table_args__ = (
        Index("ix_przt_match_round_steam", "match_id", "round_number", "steam_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    steam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    player_name: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text, default="")  # "t" or "ct"
    tick: Mapped[int] = mapped_column(Integer, nullable=False)  # tick when zone was entered
    zone: Mapped[str] = mapped_column(Text)  # CS2 zone name e.g. 'Long A', 'BombsiteA'
    zone_category: Mapped[str] = mapped_column(Text)  # site | mid | spawn | connector | unknown
    is_start_zone: Mapped[bool] = mapped_column(Boolean, default=False)  # first zone in round
    is_end_zone: Mapped[bool] = mapped_column(Boolean, default=False)   # zone at round end
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_round_zone_transitions")


class PlayerRoundMovementSummary(Base):
    """Aggregated movement statistics per player per round.

    Derived from PlayerRoundKeyframe samples (distance/speed) and
    PlayerRoundZoneTransition (zone occupancy).
    """
    __tablename__ = "player_round_movement_summaries"
    __table_args__ = (
        UniqueConstraint("match_id", "round_number", "steam_id", name="uq_prms_round_steam"),
        Index("ix_prms_match_steam", "match_id", "steam_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    steam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    player_name: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text, default="")

    # Distance and speed
    total_distance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)  # world units
    avg_speed: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)         # units/sec
    max_speed: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)         # peak

    # Zone time (seconds)
    time_in_site: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)
    time_in_mid: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)
    time_in_spawn: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)
    time_in_connector: Mapped[float] = mapped_column(Numeric(8, 2), default=0.0)

    # Zone transitions
    zone_transition_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    unique_zones_visited: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Combat activity
    damage_dealt: Mapped[int] = mapped_column(SmallInteger, default=0)
    kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    deaths: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Derived
    movement_score: Mapped[float] = mapped_column(
        Numeric(4, 3), default=0.0
    )  # avg_speed / 200, capped at 1.0

    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_round_movement_summaries")


# ── Role Quality Profiles ─────────────────────────────────────────────────────


class PlayerRoleQualitySnapshot(Base):
    """Per-player per-(match, map, side) snapshot of all role quality profiles.

    Populated by build_player_role_signals() and score_*_quality() functions.
    Each row represents one player's quality signals across one map+side in one match.

    The JSON columns (entry_frag, awper, support, rifler, lurker) store the raw
    Profile dataclass fields. Use the score_*_quality() functions to compute
    the scalar quality scores.
    """
    __tablename__ = "player_role_quality_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "match_id", "steam_id", "map_name", "side",
            name="uq_prqs_match_steam_map_side",
        ),
        Index("ix_prqs_match_steam", "match_id", "steam_id"),
        {"schema": "csda"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("csda.matches.id"), nullable=False
    )
    steam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    player_name: Mapped[str] = mapped_column(Text)

    # Scope
    map_name: Mapped[str] = mapped_column(Text)
    side: Mapped[str] = mapped_column(Text)  # "t" or "ct"

    # Role classification (from classify_player_role)
    broad_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    map_position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zone_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secondary_role: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # Entry fragger quality
    entry_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    entry_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    successful_entries: Mapped[int] = mapped_column(SmallInteger, default=0)
    entry_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    flash_pop_kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    opening_duel_wins: Mapped[int] = mapped_column(SmallInteger, default=0)
    rounds_survived_post_entry: Mapped[int] = mapped_column(SmallInteger, default=0)
    entry_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # AWP quality
    awp_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    awp_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    first_pick_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    opening_pick_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    ct_hold_picks: Mapped[int] = mapped_column(SmallInteger, default=0)
    ct_survived_after_pick: Mapped[int] = mapped_column(SmallInteger, default=0)
    t_first_pick_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    awper_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Support quality
    support_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    support_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    trade_opportunities: Mapped[int] = mapped_column(SmallInteger, default=0)
    successful_trades: Mapped[int] = mapped_column(SmallInteger, default=0)
    trade_success_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    flash_assisted_kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    utility_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    economy_sacrifice_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    support_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Rifler quality
    rifler_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    rifler_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    multi_kill_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    multi_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    rifler_trade_kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    headshot_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    ct_site_anchor_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    ct_survived_anchor: Mapped[int] = mapped_column(SmallInteger, default=0)
    rifler_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Lurker quality
    lurker_quality_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    lurk_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    solo_kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    solo_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    rotation_cut_kills: Mapped[int] = mapped_column(SmallInteger, default=0)
    survived_lurk_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    clutch_rounds: Mapped[int] = mapped_column(SmallInteger, default=0)
    clutch_rounds_won: Mapped[int] = mapped_column(SmallInteger, default=0)
    lurker_profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="player_role_quality_snapshots")


# ── Player Career Profile ─────────────────────────────────────────────────────


class PlayerCareerProfile(Base):
    """Comprehensive career-level aggregates for a player across all matches.

    This is a denormalized data warehouse table — updated by aggregating
    PlayerRoleQualitySnapshot, Kill, MatchPlayer, and PlayerRoundStats rows.

    All rates are rounded to 3 decimal places. JSON columns store per-map
    and per-role breakdowns for stats not worth a dedicated column.

    Updated incrementally: each new match played triggers an update of this row.
    """
    __tablename__ = "player_career_profiles"
    __table_args__ = (
        UniqueConstraint("steam_id", name="uq_pcp_steam_id"),
        Index("ix_pcp_steam_id", "steam_id"),
        Index("ix_pcp_last_updated", "last_updated"),
        {"schema": "csda"},
    )

    # Identity
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    steam_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text)

    # ── Match/round totals ──────────────────────────────────────────────────
    matches_played: Mapped[int] = mapped_column(Integer, default=0)
    rounds_played: Mapped[int] = mapped_column(Integer, default=0)
    rounds_won: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    maps_played: Mapped[int] = mapped_column(SmallInteger, default=0)

    # ── Core K/D stats ─────────────────────────────────────────────────────
    total_kills: Mapped[int] = mapped_column(Integer, default=0)
    total_deaths: Mapped[int] = mapped_column(Integer, default=0)
    kd_ratio: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    total_assists: Mapped[int] = mapped_column(Integer, default=0)
    headshot_kills: Mapped[int] = mapped_column(Integer, default=0)
    headshot_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    # ── Per-round rates ────────────────────────────────────────────────────
    kast_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )  # fraction of rounds with a kill/assist/survive/trade
    adrd: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 2), nullable=True
    )  # average damage per round dealt

    # ── Role distribution (fraction of rounds with that as primary role) ───
    role_entry_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_awper_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_support_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_rifler_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_lurker_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_igl_rounds: Mapped[int] = mapped_column(Integer, default=0)
    role_secondary_rounds: Mapped[int] = mapped_column(Integer, default=0)

    # ── Role quality averages ──────────────────────────────────────────────
    entry_quality_avg: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    awp_quality_avg: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    support_quality_avg: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    rifler_quality_avg: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    lurker_quality_avg: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # ── Entry fragger career ───────────────────────────────────────────────
    total_entry_attempts: Mapped[int] = mapped_column(Integer, default=0)
    total_successful_entries: Mapped[int] = mapped_column(Integer, default=0)
    entry_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    total_flash_pop_kills: Mapped[int] = mapped_column(Integer, default=0)
    flash_pop_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    total_opening_duel_wins: Mapped[int] = mapped_column(Integer, default=0)
    opening_duel_win_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    entry_survived_post_entry: Mapped[int] = mapped_column(Integer, default=0)
    entry_survival_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # ── AWP career ────────────────────────────────────────────────────────
    total_awp_rounds: Mapped[int] = mapped_column(Integer, default=0)
    total_first_pick_rounds: Mapped[int] = mapped_column(Integer, default=0)
    opening_pick_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    ct_hold_picks_total: Mapped[int] = mapped_column(Integer, default=0)
    ct_survived_after_pick_total: Mapped[int] = mapped_column(Integer, default=0)
    ct_survival_after_pick_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # ── Support career ────────────────────────────────────────────────────
    total_support_rounds: Mapped[int] = mapped_column(Integer, default=0)
    total_trade_opportunities: Mapped[int] = mapped_column(Integer, default=0)
    total_successful_trades: Mapped[int] = mapped_column(Integer, default=0)
    trade_success_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    total_flash_assisted_kills: Mapped[int] = mapped_column(Integer, default=0)
    utility_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    economy_sacrifice_rounds: Mapped[int] = mapped_column(Integer, default=0)

    # ── Rifler career ─────────────────────────────────────────────────────
    total_rifler_rounds: Mapped[int] = mapped_column(Integer, default=0)
    total_multi_kill_rounds: Mapped[int] = mapped_column(Integer, default=0)
    multi_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    rifler_trade_kills_total: Mapped[int] = mapped_column(Integer, default=0)
    rifler_trade_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    avg_headshot_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    ct_anchor_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    ct_survived_anchor_total: Mapped[int] = mapped_column(Integer, default=0)
    ct_anchor_survival_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # ── Lurker career ────────────────────────────────────────────────────
    total_lurk_attempts: Mapped[int] = mapped_column(Integer, default=0)
    total_solo_kills: Mapped[int] = mapped_column(Integer, default=0)
    solo_kill_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    total_rotation_cut_kills: Mapped[int] = mapped_column(Integer, default=0)
    survived_lurk_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    lurk_survival_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    clutch_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    clutch_rounds_won_total: Mapped[int] = mapped_column(Integer, default=0)
    clutch_win_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # ── Movement ─────────────────────────────────────────────────────────
    avg_distance_per_round: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    avg_speed_per_round: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    avg_zone_transitions_per_round: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)

    # ── Economy ──────────────────────────────────────────────────────────
    avg_equipment_value: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    eco_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    force_rounds_total: Mapped[int] = mapped_column(Integer, default=0)
    full_buy_rounds_total: Mapped[int] = mapped_column(Integer, default=0)

    # ── Utility totals ───────────────────────────────────────────────────
    total_flashes_thrown: Mapped[int] = mapped_column(Integer, default=0)
    total_smokes_thrown: Mapped[int] = mapped_column(Integer, default=0)
    total_he_detonations: Mapped[int] = mapped_column(Integer, default=0)
    total_molly_detonations: Mapped[int] = mapped_column(Integer, default=0)
    total_enemies_flashed: Mapped[int] = mapped_column(Integer, default=0)
    total_utility_damage: Mapped[int] = mapped_column(Integer, default=0)

    # ── JSON breakdowns (flexible, no dedicated column needed) ────────────
    per_map_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    """{
      "dust2": {"kills": N, "deaths": N, "rounds": N, "win_rate": 0.xx, "entry_rate": 0.xx},
      ...
    }"""
    per_weapon_stats: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    """{
      "ak47": {"kills": N, "deaths": N, "rounds": N, "hs_rate": 0.xx},
      "awp": {"kills": N, "rounds": N},
      ...
    }"""
    recent_form: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    """{"last_5": {"kd": 1.xx, "win_rate": 0.xx}, "last_10": {...}, "last_20": {...}}"""
    peak_ratings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    """{"highest_kd_match": 2.34, "highest_adrd_match": 98.5, "most_kills_match": 38}"""

    # ── Temporal ────────────────────────────────────────────────────────
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
