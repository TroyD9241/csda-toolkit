"""Add steam_id columns to kills table for player tracking.

Adds:
- killer_steam_id (nullable BigInteger)
- victim_steam_id (nullable BigInteger)
- assister_steam_id (nullable BigInteger)
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kills", sa.Column("killer_steam_id", sa.BigInteger(), nullable=True))
    op.add_column("kills", sa.Column("victim_steam_id", sa.BigInteger(), nullable=True))
    op.add_column("kills", sa.Column("assister_steam_id", sa.BigInteger(), nullable=True))

    # Indexes for join performance
    op.create_index(
        "ix_csda_kills_killer_steam_id", "kills", ["killer_steam_id"],
        unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_csda_kills_victim_steam_id", "kills", ["victim_steam_id"],
        unique=False, if_not_exists=True
    )
    op.create_index(
        "ix_csda_kills_assister_steam_id", "kills", ["assister_steam_id"],
        unique=False, if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_csda_kills_assister_steam_id", table_name="kills")
    op.drop_index("ix_csda_kills_victim_steam_id", table_name="kills")
    op.drop_index("ix_csda_kills_killer_steam_id", table_name="kills")
    op.drop_column("kills", "assister_steam_id")
    op.drop_column("kills", "victim_steam_id")
    op.drop_column("kills", "killer_steam_id")
