"""0011: Add grenade_trajectory_summaries table (compact grenade flight paths).

Replaces per-tick trajectory storage with a compact representation:
~12 key points per throw, plus throw/detonate positions, timing, and
max distance. Reduces data volume by 80-90%+ for full matches.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grenade_trajectory_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("thrower_steam_id", sa.BigInteger(), nullable=True),
        sa.Column("thrower_name", sa.Text(), nullable=False),
        sa.Column("grenade_entity_id", sa.Integer(), nullable=False),
        sa.Column("grenade_type", sa.Text(), nullable=False),
        sa.Column("team", sa.Text(), nullable=False, server_default=sa.text("")),
        sa.Column("throw_tick", sa.Integer(), nullable=False),
        sa.Column("detonate_tick", sa.Integer(), nullable=False),
        sa.Column("duration_ticks", sa.Integer(), nullable=False),
        sa.Column("throw_pos_x", sa.Numeric(10, 2), nullable=False),
        sa.Column("throw_pos_y", sa.Numeric(10, 2), nullable=False),
        sa.Column("throw_pos_z", sa.Numeric(10, 2), nullable=False),
        sa.Column("detonate_pos_x", sa.Numeric(10, 2), nullable=False),
        sa.Column("detonate_pos_y", sa.Numeric(10, 2), nullable=False),
        sa.Column("detonate_pos_z", sa.Numeric(10, 2), nullable=False),
        sa.Column("trajectory_points", sa.Text(), nullable=False),
        sa.Column("max_distance", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_flash", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["match_id"], ["csda.matches.id"], ),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index("ix_gts_match_thrower", "grenade_trajectory_summaries", ["match_id", "thrower_steam_id"], schema="csda")
    op.create_index("ix_gts_match_round", "grenade_trajectory_summaries", ["match_id", "round_number"], schema="csda")


def downgrade() -> None:
    op.drop_index("ix_gts_match_round", table_name="grenade_trajectory_summaries", schema="csda")
    op.drop_index("ix_gts_match_thrower", table_name="grenade_trajectory_summaries", schema="csda")
    op.drop_table("grenade_trajectory_summaries", schema="csda")
