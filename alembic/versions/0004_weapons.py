"""Add weapons and player_round_weapons tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── All CS2 weapons, grenades, equipment, and knives ───────────────────────────
#
# Defindex reference: https://github.com/michel-pi/csgo-items-parser (CS:GO/CS2 native indices)
# Categories: pistol, rifle, sniper, smg, heavy, shotgun, melee, grenade, armor,
#             utility, equipment, explosive, gloves
# Slot: 0=primary, 1=pistol, 2=melee, 4=equipment (zeus/taser), 5=grenade,
#       8=armor, 9=defuse, 10=c4
#
# cost: default CS2 buy-menu price in USD. Items with cost=0 are not purchasable.

WEAPON_SEED_DATA = [
    # ── Pistols (slot 1) ───────────────────────────────────────────────────
    {"defindex": 1,   "weapon_key": "desert_eagle",      "display_name": "Desert Eagle",       "category": "pistol",  "slot": 1, "cost": 700},
    {"defindex": 2,   "weapon_key": "dual_berettas",      "display_name": "Dual Berettas",       "category": "pistol",  "slot": 1, "cost": 300},
    {"defindex": 3,   "weapon_key": "five_seven",          "display_name": "Five-SeveN",          "category": "pistol",  "slot": 1, "cost": 500},
    {"defindex": 4,   "weapon_key": "glock_18",           "display_name": "Glock-18",            "category": "pistol",  "slot": 1, "cost": 200},
    {"defindex": 30,  "weapon_key": "tec_9",               "display_name": "Tec-9",               "category": "pistol",  "slot": 1, "cost": 500},
    {"defindex": 32,  "weapon_key": "hkp2000",             "display_name": "P2000",               "category": "pistol",  "slot": 1, "cost": 200},
    {"defindex": 36,  "weapon_key": "p250",               "display_name": "P250",                 "category": "pistol",  "slot": 1, "cost": 300},
    {"defindex": 63,  "weapon_key": "cz75_auto",           "display_name": "CZ75 Auto",            "category": "pistol",  "slot": 1, "cost": 500},
    {"defindex": 64,  "weapon_key": "revolver",            "display_name": "Roteador",             "category": "pistol",  "slot": 1, "cost": 500},
    {"defindex": 61,  "weapon_key": "usp_silencer",         "display_name": "USP-S",                "category": "pistol",  "slot": 1, "cost": 200},
    # ── Primary Rifles (slot 0) ──────────────────────────────────────────────
    {"defindex": 7,   "weapon_key": "ak_47",              "display_name": "AK-47",               "category": "rifle",   "slot": 0, "cost": 2700},
    {"defindex": 8,   "weapon_key": "aug",                "display_name": "AUG",                  "category": "rifle",   "slot": 0, "cost": 3300},
    {"defindex": 10,  "weapon_key": "famas",              "display_name": "FAMAS",                "category": "rifle",   "slot": 0, "cost": 2050},
    {"defindex": 13,  "weapon_key": "galil_ar",            "display_name": "Galil AR",             "category": "rifle",   "slot": 0, "cost": 2000},
    {"defindex": 16,  "weapon_key": "m4a4",               "display_name": "M4A4",                 "category": "rifle",   "slot": 0, "cost": 3100},
    {"defindex": 60,  "weapon_key": "m4a1_s",             "display_name": "M4A1-S",               "category": "rifle",   "slot": 0, "cost": 2900},
    {"defindex": 39,  "weapon_key": "sg_553",             "display_name": "SG 553",               "category": "rifle",   "slot": 0, "cost": 3000},
    # ── Primary Snipers (slot 0) ────────────────────────────────────────────
    {"defindex": 9,   "weapon_key": "awp",                "display_name": "AWP",                  "category": "sniper",   "slot": 0, "cost": 4750},
    {"defindex": 11,  "weapon_key": "g3sg1",              "display_name": "G3SG1",                "category": "sniper",   "slot": 0, "cost": 5000},
    {"defindex": 38,  "weapon_key": "scar_20",             "display_name": "SCAR-20",              "category": "sniper",   "slot": 0, "cost": 5000},
    {"defindex": 40,  "weapon_key": "ssg_08",              "display_name": "SSG 08",              "category": "sniper",   "slot": 0, "cost": 1700},
    # ── Primary SMGs (slot 0) ───────────────────────────────────────────────
    {"defindex": 17,  "weapon_key": "mac_10",              "display_name": "MAC-10",               "category": "smg",     "slot": 0, "cost": 1050},
    {"defindex": 19,  "weapon_key": "p90",                 "display_name": "P90",                  "category": "smg",     "slot": 0, "cost": 2350},
    {"defindex": 23,  "weapon_key": "mp5_sd",              "display_name": "MP5-SD",               "category": "smg",     "slot": 0, "cost": 1500},
    {"defindex": 24,  "weapon_key": "ump_45",              "display_name": "UMP-45",               "category": "smg",     "slot": 0, "cost": 1200},
    {"defindex": 26,  "weapon_key": "pp_bizon",            "display_name": "PP-Bizon",              "category": "smg",     "slot": 0, "cost": 1400},
    {"defindex": 33,  "weapon_key": "mp7",                 "display_name": "MP7",                   "category": "smg",     "slot": 0, "cost": 1200},
    {"defindex": 34,  "weapon_key": "mp9",                 "display_name": "MP9",                   "category": "smg",     "slot": 0, "cost": 1000},
    # ── Primary Heavy / Shotguns (slot 0) ───────────────────────────────────
    {"defindex": 14,  "weapon_key": "m249",                "display_name": "M249",                 "category": "heavy",    "slot": 0, "cost": 4000},
    {"defindex": 25,  "weapon_key": "xm1014",              "display_name": "XM1014",                "category": "heavy",    "slot": 0, "cost": 2000},
    {"defindex": 27,  "weapon_key": "mag_7",               "display_name": "MAG-7",                "category": "heavy",    "slot": 0, "cost": 1200},
    {"defindex": 28,  "weapon_key": "negev",              "display_name": "Negev",                 "category": "heavy",    "slot": 0, "cost": 3000},
    {"defindex": 29,  "weapon_key": "sawed_off",           "display_name": "Sawed-Off",            "category": "heavy",    "slot": 0, "cost": 1200},
    # ── Equipment (slot 4) ───────────────────────────────────────────────────
    {"defindex": 31,  "weapon_key": "zeus_x27",            "display_name": "Zeus x27",            "category": "equipment","slot": 4, "cost": 200},
    # ── Grenades (slot 5) ───────────────────────────────────────────────────
    {"defindex": 43,  "weapon_key": "flashbang",          "display_name": "Flashbang",             "category": "grenade",  "slot": 5, "cost": 200},
    {"defindex": 44,  "weapon_key": "he_grenade",           "display_name": "HE Grenade",            "category": "grenade",  "slot": 5, "cost": 300},
    {"defindex": 45,  "weapon_key": "smoke_grenade",        "display_name": "Smoke Grenade",         "category": "grenade",  "slot": 5, "cost": 200},
    {"defindex": 46,  "weapon_key": "molotov",             "display_name": "Molotov",               "category": "grenade",  "slot": 5, "cost": 400},
    {"defindex": 47,  "weapon_key": "decoy",               "display_name": "Decoy Grenade",          "category": "grenade",  "slot": 5, "cost": 50},
    {"defindex": 48,  "weapon_key": "incendiary",           "display_name": "Incendiary Grenade",    "category": "grenade",  "slot": 5, "cost": 400},
    {"defindex": 68,  "weapon_key": "tag_grenade",         "display_name": "Tactical Awareness Grenade", "category": "grenade", "slot": 5, "cost": 200},
    {"defindex": 84,  "weapon_key": "snowball",             "display_name": "Snowball",               "category": "grenade",  "slot": 5, "cost": 50},
    # ── Armor / Utility (slots 8, 9) ─────────────────────────────────────────
    {"defindex": 50,  "weapon_key": "kevlar",               "display_name": "Kevlar Vest",          "category": "armor",    "slot": 8, "cost": 400},
    {"defindex": 51,  "weapon_key": "kevlar_helmet",        "display_name": "Kevlar + Helmet",       "category": "armor",    "slot": 8, "cost": 650},
    {"defindex": 55,  "weapon_key": "defuse_kit",           "display_name": "Defuse Kit",             "category": "utility",  "slot": 9, "cost": 400},
    # ── Explosive (slot 10, T side only) ──────────────────────────────────
    {"defindex": 49,  "weapon_key": "c4",                  "display_name": "C4 Explosive",           "category": "explosive","slot": 10, "cost": 0},
    # ── Melee / Knives (slot 2) ─────────────────────────────────────────────
    {"defindex": 42,  "weapon_key": "classic_knife",       "display_name": "Classic Knife",          "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 59,  "weapon_key": "knife_t",              "display_name": "Knife (T)",              "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 500, "weapon_key": "bayonet",              "display_name": "Bayonet",                "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 505, "weapon_key": "flip_knife",           "display_name": "Flip Knife",             "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 506, "weapon_key": "gut_knife",            "display_name": "Gut Knife",              "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 507, "weapon_key": "karambit",             "display_name": "Karambit",               "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 508, "weapon_key": "m9_bayonet",           "display_name": "M9 Bayonet",             "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 509, "weapon_key": "knife_tactical",        "display_name": "Tactical Knife",         "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 512, "weapon_key": "knife_falchion",       "display_name": "Falchion Knife",         "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 514, "weapon_key": "knife_survival_bowie", "display_name": "Survival Bowie",         "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 515, "weapon_key": "knife_butterfly",     "display_name": "Butterfly Knife",        "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 516, "weapon_key": "knife_push",            "display_name": "Shadow Daggers",          "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 519, "weapon_key": "knife_ursus",          "display_name": "Ursus Knife",            "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 520, "weapon_key": "knife_gypsy_jackknife","display_name": "Gypsy Jackknife",        "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 522, "weapon_key": "knife_stiletto",       "display_name": "Stiletto Knife",         "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 523, "weapon_key": "knife_widowmaker",    "display_name": "Widowmaker Knife",       "category": "melee",    "slot": 2, "cost": 0},
    {"defindex": 80,  "weapon_key": "knife_ghost",          "display_name": "Ghost Knife",            "category": "melee",    "slot": 2, "cost": 0},
    # ── Gloves / Agents (slot 2, cosmetic) ─────────────────────────────────
    {"defindex": 5027, "weapon_key": "studded_bloodhound_gloves","display_name": "Studded Bloodhound Gloves","category": "gloves", "slot": 2, "cost": 0},
    {"defindex": 5028, "weapon_key": "t_gloves",            "display_name": "T Gloves",              "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5029, "weapon_key": "ct_gloves",            "display_name": "CT Gloves",              "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5030, "weapon_key": "sporty_gloves",        "display_name": "Sport Gloves",           "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5031, "weapon_key": "slick_gloves",         "display_name": "Slick Gloves",           "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5032, "weapon_key": "leather_handwraps",   "display_name": "Leather Handwraps",      "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5033, "weapon_key": "motorcycle_gloves",   "display_name": "Moto Gloves",            "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5034, "weapon_key": "specialist_gloves",   "display_name": "Specialist Gloves",      "category": "gloves",  "slot": 2, "cost": 0},
    {"defindex": 5035, "weapon_key": "studded_hydra_gloves","display_name": "Studded Hydra Gloves",   "category": "gloves",  "slot": 2, "cost": 0},
]


def upgrade() -> None:
    # ── weapons: reference table ─────────────────────────────────────────────
    op.create_table(
        "weapons",
        sa.Column("defindex", sa.SmallInteger(), primary_key=True, nullable=False),
        sa.Column("weapon_key", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("cost", sa.SmallInteger(), nullable=False, server_default="0"),
        schema="csda",
    )
    op.create_index("ix_weapons_key", "weapons", ["weapon_key"], schema="csda", unique=True)
    op.create_index("ix_weapons_category", "weapons", ["category"], schema="csda")

    # Seed the weapons table
    for w in WEAPON_SEED_DATA:
        op.execute(
            sa.text(
                "INSERT INTO csda.weapons (defindex, weapon_key, display_name, category, slot, cost) "
                "VALUES (:defindex, :key, :dname, :cat, :slot, :cost)"
            ).bindparams(
                defindex=w["defindex"],
                key=w["weapon_key"],
                dname=w["display_name"],
                cat=w["category"],
                slot=w["slot"],
                cost=w["cost"],
            )
        )

    # ── player_round_weapons ─────────────────────────────────────────────────
    op.create_table(
        "player_round_weapons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), sa.ForeignKey("csda.matches.id"), nullable=False),
        sa.Column("round_number", sa.SmallInteger(), nullable=False),
        sa.Column("steam_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("csda.players.id"), nullable=True),
        sa.Column("weapon_key", sa.Text(), nullable=False),
        sa.Column("weapon_defindex", sa.SmallInteger(), sa.ForeignKey("csda.weapons.defindex"), nullable=True),
        sa.Column("is_equipped", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_purchased", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_dropped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acquired_at_tick", sa.Integer(), nullable=True),
        sa.Column("dropped_at_tick", sa.Integer(), nullable=True),
        sa.Column("purchase_cost", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "match_id", "round_number", "steam_id", "weapon_key",
            name="uq_prw_round_steam_weapon",
        ),
        schema="csda",
    )
    op.create_index("ix_prw_match_round", "player_round_weapons", ["match_id", "round_number"], schema="csda")
    op.create_index("ix_prw_steam_id", "player_round_weapons", ["steam_id"], schema="csda")


def downgrade() -> None:
    op.drop_index("ix_prw_steam_id", table_name="player_round_weapons", schema="csda")
    op.drop_index("ix_prw_match_round", table_name="player_round_weapons", schema="csda")
    op.drop_table("player_round_weapons", schema="csda")
    op.drop_table("weapons", schema="csda")
