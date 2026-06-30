"""Add created_at column to all tables missing it.

Several tables were migrated without server_default timestamps.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLES_MISSING_CREATED_AT = [
    "demo_files",
    "round_side_map",
    "weapons",
    "round_classifications",
    "player_situation_roles",
    "match_classifications",
    "classifier_runs",
]


def upgrade() -> None:
    for table in TABLES_MISSING_CREATED_AT:
        op.add_column(
            table,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            schema="csda",
        )


def downgrade() -> None:
    for table in reversed(TABLES_MISSING_CREATED_AT):
        op.drop_column(table, "created_at", schema="csda")
