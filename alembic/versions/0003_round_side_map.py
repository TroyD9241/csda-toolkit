"""Add round_side_map table — per-round per-team-side assignments.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "round_side_map",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("team_slot", sa.SmallInteger(), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("overtime_index", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("side", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "team_slot", "round_number", "overtime_index", name="uq_round_side_map"),
        schema="csda",
    )
    op.create_index(
        "ix_round_side_map_match_team",
        "round_side_map",
        ["match_id", "team_slot"],
        schema="csda",
    )


def downgrade() -> None:
    op.drop_index("ix_round_side_map_match_team", table_name="round_side_map", schema="csda")
    op.drop_table("round_side_map", schema="csda")
