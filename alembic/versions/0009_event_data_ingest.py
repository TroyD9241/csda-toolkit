"""Migration 0009: Event data ingest.

Tables for: damage_events, player_blinds, grenade_detonations,
inferno_events, grenade_trajectories, player_round_stats, bomb_events.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── damage_events ─────────────────────────────────────────────────────────
    op.create_table(
        "damage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("attacker_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("attacker_name", sa.Text(), nullable=False),
        sa.Column("victim_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("victim_name", sa.Text(), nullable=False),
        sa.Column("weapon", sa.Text(), nullable=False),
        sa.Column("dmg_health", sa.SmallInteger(), nullable=False),
        sa.Column("dmg_armor", sa.SmallInteger(), nullable=False),
        sa.Column("hitgroup", sa.SmallInteger(), nullable=False),
        sa.Column("health", sa.SmallInteger(), nullable=False),
        sa.Column("armor", sa.SmallInteger(), nullable=False),
        sa.Column("hitgroup_name", sa.Text(), nullable=False),
        sa.Column("attacker_last_place_name", sa.Text(), nullable=False),
        sa.Column("victim_last_place_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_damage_match_tick", "damage_events", ["match_id", "tick"], schema="csda")
    op.create_index("ix_damage_match_round", "damage_events", ["match_id", "round_number"], schema="csda")

    # ── player_blinds ─────────────────────────────────────────────────────────
    op.create_table(
        "player_blinds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("attacker_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("attacker_name", sa.Text(), nullable=False),
        sa.Column("victim_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("victim_name", sa.Text(), nullable=False),
        sa.Column("blind_duration", sa.Numeric(6, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_blind_match_tick", "player_blinds", ["match_id", "tick"], schema="csda")

    # ── grenade_detonations ───────────────────────────────────────────────────
    op.create_table(
        "grenade_detonations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("grenade_type", sa.Text(), nullable=False),
        sa.Column("player_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("x", sa.Numeric(10, 2), nullable=True),
        sa.Column("y", sa.Numeric(10, 2), nullable=True),
        sa.Column("z", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_gd_match_tick", "grenade_detonations", ["match_id", "tick"], schema="csda")
    op.create_index("ix_gd_match_round", "grenade_detonations", ["match_id", "round_number"], schema="csda")

    # ── inferno_events ────────────────────────────────────────────────────────
    op.create_table(
        "inferno_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("player_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=False),
        sa.Column("x", sa.Numeric(10, 2), nullable=True),
        sa.Column("y", sa.Numeric(10, 2), nullable=True),
        sa.Column("z", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_inf_match_tick", "inferno_events", ["match_id", "tick"], schema="csda")

    # ── grenade_trajectories ─────────────────────────────────────────────────
    op.create_table(
        "grenade_trajectories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("grenade_entity_id", sa.Integer(), nullable=False),
        sa.Column("grenade_type", sa.Text(), nullable=False),
        sa.Column("thrower_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("thrower_name", sa.Text(), nullable=False),
        sa.Column("x", sa.Numeric(10, 2), nullable=False),
        sa.Column("y", sa.Numeric(10, 2), nullable=False),
        sa.Column("z", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_gt_match_tick", "grenade_trajectories", ["match_id", "tick"], schema="csda")
    op.create_index("ix_gt_entity", "grenade_trajectories", ["match_id", "grenade_entity_id"], schema="csda")

    # ── player_round_stats ───────────────────────────────────────────────────
    op.create_table(
        "player_round_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False),
        sa.Column("kills", sa.SmallInteger(), nullable=False),
        sa.Column("assists", sa.SmallInteger(), nullable=False),
        sa.Column("deaths", sa.SmallInteger(), nullable=False),
        sa.Column("damage", sa.SmallInteger(), nullable=False),
        sa.Column("headshot_kills", sa.SmallInteger(), nullable=False),
        sa.Column("cash_earned", sa.Integer(), nullable=False),
        sa.Column("equipment_value", sa.SmallInteger(), nullable=False),
        sa.Column("utility_damage", sa.SmallInteger(), nullable=False),
        sa.Column("enemies_flashed", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_prs_match_round_steam", "player_round_stats", ["match_id", "round_number", "steam_id"], schema="csda")

    # ── bomb_events ────────────────────────────────────────────────────────────
    op.create_table(
        "bomb_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("tick", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("player_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("player_name", sa.Text(), nullable=True),
        sa.Column("site", sa.Text(), nullable=True),
        sa.Column("has_kit", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_be_match_tick", "bomb_events", ["match_id", "tick"], schema="csda")


def downgrade() -> None:
    op.drop_table("bomb_events", schema="csda")
    op.drop_table("player_round_stats", schema="csda")
    op.drop_table("grenade_trajectories", schema="csda")
    op.drop_table("inferno_events", schema="csda")
    op.drop_table("grenade_detonations", schema="csda")
    op.drop_table("player_blinds", schema="csda")
    op.drop_table("damage_events", schema="csda")
