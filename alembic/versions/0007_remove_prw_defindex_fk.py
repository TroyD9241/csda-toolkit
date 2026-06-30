"""Remove FK constraint from player_round_weapons.weapon_defindex.

The weapon_defindex column is informational; weapon_key is the canonical identifier.
Not all defindices from item_pickup events are seeded in the weapons table
(e.g., exotic knife skins). Making weapon_defindex a plain nullable column avoids
FK violations while preserving the data.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the FK constraint and recreate as plain column
    op.execute(
        "ALTER TABLE csda.player_round_weapons "
        "ALTER COLUMN weapon_defindex DROP DEFAULT"
    )
    # Drop FK if it exists (may fail if already dropped, use IF EXISTS in raw SQL)
    try:
        op.execute(
            "ALTER TABLE csda.player_round_weapons "
            "DROP CONSTRAINT player_round_weapons_weapon_defindex_fkey"
        )
    except Exception:
        pass  # Already dropped or doesn't exist


def downgrade() -> None:
    # No downgrade — we intentionally removed the FK
    pass
