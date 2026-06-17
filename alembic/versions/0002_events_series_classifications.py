"""Add events, event_series, match→series link, polymorphic classifications.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── events ─────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, server_default=""),
        sa.Column("tier", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("region", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )

    # ── event_series ───────────────────────────────────────────────────────
    op.create_table(
        "event_series",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("csda.events.id"), nullable=False),
        sa.Column("series_type", sa.Text(), nullable=False, server_default=""),
        sa.Column("round_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("team_a_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=True),
        sa.Column("team_b_id", sa.Integer(), sa.ForeignKey("csda.teams.id"), nullable=True),
        sa.Column("team_a_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("team_b_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("team_a_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("team_b_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("map_veto_json", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )

    # ── matches: add series_id and map_number ──────────────────────────────
    op.add_column(
        "matches",
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("csda.event_series.id"), nullable=True),
        schema="csda",
    )
    op.add_column(
        "matches",
        sa.Column("map_number", sa.Integer(), nullable=False, server_default="0"),
        schema="csda",
    )

    # ── match_contexts: add event_id ────────────────────────────────────────
    op.add_column(
        "match_contexts",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("csda.events.id"), nullable=True),
        schema="csda",
    )

    # ── classifier_runs: make match_id nullable, add scope_type + scope_id ──
    op.alter_column(
        "classifier_runs",
        "match_id",
        existing_type=sa.Integer(),
        nullable=True,
        schema="csda",
    )
    op.add_column(
        "classifier_runs",
        sa.Column("scope_type", sa.Text(), nullable=False, server_default="match"),
        schema="csda",
    )
    op.add_column(
        "classifier_runs",
        sa.Column("scope_id", sa.Integer(), nullable=False, server_default="0"),
        schema="csda",
    )

    # ── classifications: new unified polymorphic table ─────────────────────
    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classifier_run_id", sa.Integer(), sa.ForeignKey("csda.classifier_runs.id"), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("label_name", sa.Text(), nullable=False),
        sa.Column("label_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="csda",
    )
    op.create_index(
        "ix_classifications_entity",
        "classifications",
        ["entity_type", "entity_id"],
        schema="csda",
    )


def downgrade() -> None:
    # Reverse order of upgrade
    op.drop_index("ix_classifications_entity", table_name="classifications", schema="csda")
    op.drop_table("classifications", schema="csda")

    op.drop_column("classifier_runs", "scope_id", schema="csda")
    op.drop_column("classifier_runs", "scope_type", schema="csda")
    op.alter_column(
        "classifier_runs",
        "match_id",
        existing_type=sa.Integer(),
        nullable=False,
        schema="csda",
    )

    op.drop_column("match_contexts", "event_id", schema="csda")

    op.drop_column("matches", "map_number", schema="csda")
    op.drop_column("matches", "series_id", schema="csda")

    op.drop_table("event_series", schema="csda")
    op.drop_table("events", schema="csda")
