"""Initial schema — all 7 migrations combined.

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS csda")

    # ── 0001_initial ──────────────────────────────────────────────────────
    op.create_table(
        "demo_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("demo_filename", sa.Text(), nullable=False),
        sa.Column("demo_checksum", sa.Text(), nullable=False),
        sa.Column("parser_name", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("last_known_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("demo_file_id", sa.Integer(), sa.ForeignKey("csda.demo_files.id"), nullable=True),
        sa.Column("map_name", sa.Text(), nullable=False),
        sa.Column("tick_rate", sa.Integer(), nullable=False),
        sa.Column("server_name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("canonical_match_json", sa.JSON(), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("played_at_source", sa.Text(), nullable=True),
        sa.Column("played_at_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("start_tick", sa.Integer(), nullable=False),
        sa.Column("end_tick", sa.Integer(), nullable=True),
        sa.Column("winner_side", sa.Text(), nullable=True),
        sa.Column("end_reason", sa.Text(), nullable=True),
        sa.Column("score_t", sa.SmallInteger(), nullable=False),
        sa.Column("score_ct", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "kills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("kill_index", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("killer_match_player_index", sa.SmallInteger(), nullable=True),
        sa.Column("killer_name_raw", sa.Text(), nullable=False),
        sa.Column("victim_match_player_index", sa.SmallInteger(), nullable=True),
        sa.Column("victim_name_raw", sa.Text(), nullable=False),
        sa.Column("assister_match_player_index", sa.SmallInteger(), nullable=True),
        sa.Column("assister_name_raw", sa.Text(), nullable=True),
        sa.Column("weapon_name", sa.Text(), nullable=False),
        sa.Column("is_headshot", sa.Boolean(), nullable=False),
        sa.Column("is_wallbang", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "external_match_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_match_id", sa.Text(), nullable=False),
        sa.Column("linked_by", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "analyst_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=True),
        sa.Column("tick", sa.Integer(), nullable=True),
        sa.Column("match_player_index", sa.SmallInteger(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )

    # ── 0002_team_context ─────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=True),
        sa.Column("country_code", sa.Text(), nullable=True),
        sa.Column("is_provisional", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("team_type", sa.Text(), nullable=True),
        sa.Column("parent_team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "external_team_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_team_id", sa.Text(), nullable=False),
        sa.Column("external_name", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_team_id"),
        schema="csda",
    )
    op.create_table(
        "team_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("alias_normalized", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("team_type", sa.Text(), nullable=True),
        sa.Column("is_org_relationship", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "alias_normalized", "source"),
        schema="csda",
    )
    op.create_table(
        "match_contexts",
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("context_provider", sa.Text(), nullable=False),
        sa.Column("play_environment", sa.Text(), nullable=False),
        sa.Column("is_structured_team_play", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("tier_estimate", sa.SmallInteger(), nullable=True),
        sa.Column("analysis_pool", sa.Text(), nullable=False),
        sa.Column("classification_source", sa.Text(), nullable=False),
        sa.Column("classification_version", sa.Text(), nullable=True),
        sa.Column("event_name", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("match_id"),
        schema="csda",
    )

    # ── 0003_lineups_roster_history ───────────────────────────────────────
    op.create_table(
        "lineups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lineup_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("player_count", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "lineup_players",
        sa.Column("lineup_id", sa.Integer(), sa.ForeignKey("csda.lineups.id"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("csda.players.id"), nullable=False),
        sa.Column("slot_index", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("lineup_id", "player_id"),
        schema="csda",
    )
    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("csda.players.id"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("membership_type", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.add_column(
        "matches",
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        schema="csda",
    )
    op.add_column(
        "matches",
        sa.Column("played_at_source", sa.Text(), nullable=True),
        schema="csda",
    )
    op.add_column(
        "matches",
        sa.Column("played_at_confidence", sa.Numeric(4, 3), nullable=True),
        schema="csda",
    )

    # ── 0005_classification ───────────────────────────────────────────────
    op.create_table(
        "classifier_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classifier_name", sa.Text(), nullable=False),
        sa.Column("classifier_version", sa.Text(), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "round_classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classifier_run_id", sa.Integer(), sa.ForeignKey("csda.classifier_runs.id"), nullable=False),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("csda.rounds.id"), nullable=False),
        sa.Column("label_name", sa.Text(), nullable=False),
        sa.Column("label_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classifier_run_id", "round_id", "label_name"),
        schema="csda",
    )
    op.create_table(
        "player_situation_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classifier_run_id", sa.Integer(), sa.ForeignKey("csda.classifier_runs.id"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("csda.players.id"), nullable=False),
        sa.Column("lineup_id", sa.Integer(), sa.ForeignKey("csda.lineups.id"), nullable=True),
        sa.Column("map_name", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("role_code", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "match_classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classifier_run_id", sa.Integer(), sa.ForeignKey("csda.classifier_runs.id"), nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("label_name", sa.Text(), nullable=False),
        sa.Column("label_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classifier_run_id", "match_id", "label_name"),
        schema="csda",
    )
    op.create_table(
        "match_event_qualifiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False, unique=True),
        sa.Column("network_type", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("crowd_level", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("crowd_consistency", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("crowd_notes", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )

    # Create match_teams (has FK to lineups, so after lineups)
    op.create_table(
        "match_teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("team_slot", sa.SmallInteger(), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=True),
        sa.Column("lineup_id", sa.Integer(), sa.ForeignKey("csda.lineups.id"), nullable=True),
        sa.Column("parent_team_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("starting_side", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("is_winner", sa.Boolean(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "team_slot"),
        schema="csda",
    )
    # Create match_players (FK to match_teams)
    op.create_table(
        "match_players",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("match_player_index", sa.SmallInteger(), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("csda.players.id"), nullable=True),
        sa.Column("match_team_id", sa.Integer(), sa.ForeignKey("csda.match_teams.id"), nullable=True),
        sa.Column("steam_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("team_side", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )

    # ── 0006_player_aliases ───────────────────────────────────────────────
    op.create_table(
        "player_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("is_canonical", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("steam_id", "alias", "source"),
        schema="csda",
    )

    # ── 0007_round_equipment_purchases_drops ──────────────────────────────
    op.create_table(
        "round_equipment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("equipment_value", sa.Integer(), nullable=False),
        sa.Column("weapons", sa.JSON(), nullable=True),
        sa.Column("armor", sa.Boolean(), nullable=False),
        sa.Column("helmet", sa.Boolean(), nullable=False),
        sa.Column("defuse_kit", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "round_purchases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("weapon_name", sa.Text(), nullable=False),
        sa.Column("weapon_category", sa.Text(), nullable=True),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_table(
        "weapon_drops",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("weapon_name", sa.Text(), nullable=False),
        sa.Column("dropped_by_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("dropped_by_name", sa.Text(), nullable=True),
        sa.Column("picked_up_by_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("picked_up_by_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )


def downgrade() -> None:
    op.drop_table("weapon_drops", schema="csda")
    op.drop_table("round_purchases", schema="csda")
    op.drop_table("round_equipment", schema="csda")
    op.drop_table("player_aliases", schema="csda")
    op.drop_table("match_players", schema="csda")
    op.drop_table("match_teams", schema="csda")
    op.drop_table("match_event_qualifiers", schema="csda")
    op.drop_table("match_classifications", schema="csda")
    op.drop_table("player_situation_roles", schema="csda")
    op.drop_table("round_classifications", schema="csda")
    op.drop_table("classifier_runs", schema="csda")
    op.drop_table("team_memberships", schema="csda")
    op.drop_table("lineup_players", schema="csda")
    op.drop_table("lineups", schema="csda")
    op.drop_table("match_contexts", schema="csda")
    op.drop_table("team_aliases", schema="csda")
    op.drop_table("external_team_links", schema="csda")
    op.drop_table("teams", schema="csda")
    op.drop_table("analyst_notes", schema="csda")
    op.drop_table("external_match_links", schema="csda")
    op.drop_table("kills", schema="csda")
    op.drop_table("rounds", schema="csda")
    op.drop_table("matches", schema="csda")
    op.drop_table("players", schema="csda")
    op.drop_table("demo_files", schema="csda")
