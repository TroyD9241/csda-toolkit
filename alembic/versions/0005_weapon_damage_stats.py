"""Add damage stats columns to weapons table and fix prices.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-17

Source: https://cs2damage.com/weapons/
Prices from cs2damage.com used as authoritative (may differ from tournament rules).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Updated prices and new damage stats from cs2damage.com
# Columns: defindex, weapon_key, display_name, category, slot, cost, damage, armor_penetration,
#           rpm, magazine_size, head_damage_armored, chest_damage_armored
WEAPON_DATA = [
    # ── Pistols ─────────────────────────────────────────────────────────────
    {"defindex": 4,   "weapon_key": "glock_18",        "display_name": "Glock-18",            "category": "pistol",  "slot": 1, "cost": 200,  "damage": 30,  "armor_penetration": 47.0,  "rpm": 400, "magazine_size": 20, "head_damage_armored": 56,  "chest_damage_armored": 14},
    {"defindex": 61,  "weapon_key": "usp_silencer",     "display_name": "USP-S",               "category": "pistol",  "slot": 1, "cost": 200,  "damage": 35,  "armor_penetration": 50.5, "rpm": 352, "magazine_size": 12, "head_damage_armored": 70,  "chest_damage_armored": 17},
    {"defindex": 32,  "weapon_key": "hkp2000",          "display_name": "P2000",               "category": "pistol",  "slot": 1, "cost": 200,  "damage": 35,  "armor_penetration": 50.5, "rpm": 352, "magazine_size": 13, "head_damage_armored": 70,  "chest_damage_armored": 17},
    {"defindex": 36,  "weapon_key": "p250",             "display_name": "P250",                "category": "pistol",  "slot": 1, "cost": 300,  "damage": 38,  "armor_penetration": 63.5, "rpm": 352, "magazine_size": 13, "head_damage_armored": 96,  "chest_damage_armored": 24},
    {"defindex": 3,   "weapon_key": "five_seven",       "display_name": "Five-SeveN",         "category": "pistol",  "slot": 1, "cost": 500,  "damage": 32,  "armor_penetration": 91.15,"rpm": 400, "magazine_size": 20, "head_damage_armored": 116, "chest_damage_armored": 29},
    {"defindex": 30,  "weapon_key": "tec_9",            "display_name": "Tec-9",              "category": "pistol",  "slot": 1, "cost": 500,  "damage": 33,  "armor_penetration": 90.6, "rpm": 500, "magazine_size": 18, "head_damage_armored": 119, "chest_damage_armored": 29},
    {"defindex": 2,   "weapon_key": "dual_berettas",   "display_name": "Dual Berettas",      "category": "pistol",  "slot": 1, "cost": 300,  "damage": 38,  "armor_penetration": 52.0, "rpm": 500, "magazine_size": 30, "head_damage_armored": 79,  "chest_damage_armored": 19},
    {"defindex": 63,  "weapon_key": "cz75_auto",        "display_name": "CZ75 Auto",           "category": "pistol",  "slot": 1, "cost": 500,  "damage": 31,  "armor_penetration": 77.65,"rpm": 600, "magazine_size": 12, "head_damage_armored": 96,  "chest_damage_armored": 24},
    {"defindex": 1,   "weapon_key": "desert_eagle",     "display_name": "Desert Eagle",       "category": "pistol",  "slot": 1, "cost": 700,  "damage": 63,  "armor_penetration": 93.2, "rpm": 267, "magazine_size": 7,  "head_damage_armored": 234, "chest_damage_armored": 58},
    {"defindex": 64,  "weapon_key": "revolver",         "display_name": "R8 Revolver",        "category": "pistol",  "slot": 1, "cost": 600,  "damage": 86,  "armor_penetration": 93.2, "rpm": 120, "magazine_size": 8,  "head_damage_armored": 320, "chest_damage_armored": 80},
    # ── Rifles ──────────────────────────────────────────────────────────────
    {"defindex": 7,   "weapon_key": "ak_47",           "display_name": "AK-47",              "category": "rifle",   "slot": 0, "cost": 2700, "damage": 36,  "armor_penetration": 77.5, "rpm": 600, "magazine_size": 30, "head_damage_armored": 111, "chest_damage_armored": 27},
    {"defindex": 16,  "weapon_key": "m4a4",            "display_name": "M4A4",                "category": "rifle",   "slot": 0, "cost": 3100, "damage": 33,  "armor_penetration": 70.0, "rpm": 667, "magazine_size": 30, "head_damage_armored": 92,  "chest_damage_armored": 23},
    {"defindex": 60,  "weapon_key": "m4a1_s",          "display_name": "M4A1-S",             "category": "rifle",   "slot": 0, "cost": 2900, "damage": 38,  "armor_penetration": 70.0, "rpm": 600, "magazine_size": 20, "head_damage_armored": 106, "chest_damage_armored": 26},
    {"defindex": 8,   "weapon_key": "aug",              "display_name": "AUG",                "category": "rifle",   "slot": 0, "cost": 3300, "damage": 28,  "armor_penetration": 90.0, "rpm": 667, "magazine_size": 30, "head_damage_armored": 100, "chest_damage_armored": 25},
    {"defindex": 39,  "weapon_key": "sg_553",          "display_name": "SG 553",              "category": "rifle",   "slot": 0, "cost": 3000, "damage": 30,  "armor_penetration": 100.0,"rpm": 667, "magazine_size": 30, "head_damage_armored": 120, "chest_damage_armored": 30},
    {"defindex": 10,  "weapon_key": "famas",           "display_name": "FAMAS",               "category": "rifle",   "slot": 0, "cost": 2050, "damage": 30,  "armor_penetration": 70.0, "rpm": 667, "magazine_size": 25, "head_damage_armored": 84,  "chest_damage_armored": 21},
    {"defindex": 13,  "weapon_key": "galil_ar",         "display_name": "Galil AR",            "category": "rifle",   "slot": 0, "cost": 1800, "damage": 30,  "armor_penetration": 77.5, "rpm": 667, "magazine_size": 30, "head_damage_armored": 93,  "chest_damage_armored": 23},
    # ── Snipers ────────────────────────────────────────────────────────────
    {"defindex": 9,   "weapon_key": "awp",             "display_name": "AWP",                 "category": "sniper",   "slot": 0, "cost": 4750, "damage": 115, "armor_penetration": 97.5, "rpm": 41,  "magazine_size": 5,  "head_damage_armored": 448, "chest_damage_armored": 112},
    {"defindex": 40,  "weapon_key": "ssg_08",           "display_name": "SSG 08",              "category": "sniper",   "slot": 0, "cost": 1700, "damage": 88,  "armor_penetration": 85.0, "rpm": 48,  "magazine_size": 10, "head_damage_armored": 299, "chest_damage_armored": 74},
    {"defindex": 38,  "weapon_key": "scar_20",          "display_name": "SCAR-20",            "category": "sniper",   "slot": 0, "cost": 5000, "damage": 80,  "armor_penetration": 82.5, "rpm": 240, "magazine_size": 20, "head_damage_armored": 264, "chest_damage_armored": 66},
    {"defindex": 11,  "weapon_key": "g3sg1",           "display_name": "G3SG1",               "category": "sniper",   "slot": 0, "cost": 5000, "damage": 80,  "armor_penetration": 82.5, "rpm": 240, "magazine_size": 20, "head_damage_armored": 264, "chest_damage_armored": 66},
    # ── SMGs ────────────────────────────────────────────────────────────────
    {"defindex": 17,  "weapon_key": "mac_10",           "display_name": "MAC-10",               "category": "smg",      "slot": 0, "cost": 1050, "damage": 29,  "armor_penetration": 57.5, "rpm": 800, "magazine_size": 30, "head_damage_armored": 66,  "chest_damage_armored": 16},
    {"defindex": 34,  "weapon_key": "mp9",              "display_name": "MP9",                 "category": "smg",      "slot": 0, "cost": 1250, "damage": 26,  "armor_penetration": 60.0, "rpm": 857, "magazine_size": 30, "head_damage_armored": 62,  "chest_damage_armored": 15},
    {"defindex": 33,  "weapon_key": "mp7",             "display_name": "MP7",                 "category": "smg",      "slot": 0, "cost": 1500, "damage": 29,  "armor_penetration": 62.5, "rpm": 750, "magazine_size": 30, "head_damage_armored": 72,  "chest_damage_armored": 18},
    {"defindex": 24,  "weapon_key": "ump_45",          "display_name": "UMP-45",               "category": "smg",      "slot": 0, "cost": 1200, "damage": 35,  "armor_penetration": 65.0, "rpm": 667, "magazine_size": 25, "head_damage_armored": 91,  "chest_damage_armored": 22},
    {"defindex": 19,  "weapon_key": "p90",              "display_name": "P90",                 "category": "smg",      "slot": 0, "cost": 2350, "damage": 26,  "armor_penetration": 69.0, "rpm": 857, "magazine_size": 50, "head_damage_armored": 71,  "chest_damage_armored": 17},
    {"defindex": 26,  "weapon_key": "pp_bizon",         "display_name": "PP-Bizon",           "category": "smg",      "slot": 0, "cost": 1400, "damage": 27,  "armor_penetration": 47.5, "rpm": 750, "magazine_size": 64, "head_damage_armored": 51,  "chest_damage_armored": 12},
    {"defindex": 23,  "weapon_key": "mp5_sd",           "display_name": "MP5-SD",               "category": "smg",      "slot": 0, "cost": 1500, "damage": 27,  "armor_penetration": 62.5, "rpm": 750, "magazine_size": 30, "head_damage_armored": 67,  "chest_damage_armored": 16},
    # ── Heavy / Shotguns ──────────────────────────────────────────────────
    {"defindex": 35,  "weapon_key": "nova",             "display_name": "Nova",                "category": "heavy",    "slot": 0, "cost": 1050, "damage": 26,  "armor_penetration": 50.0, "rpm": 68,  "magazine_size": 8,  "head_damage_armored": 52,  "chest_damage_armored": 13},
    {"defindex": 25,  "weapon_key": "xm1014",           "display_name": "XM1014",              "category": "heavy",    "slot": 0, "cost": 2000, "damage": 20,  "armor_penetration": 50.0, "rpm": 171, "magazine_size": 7,  "head_damage_armored": 40,  "chest_damage_armored": 10},
    {"defindex": 27,  "weapon_key": "mag_7",            "display_name": "MAG-7",               "category": "heavy",    "slot": 0, "cost": 1300, "damage": 30,  "armor_penetration": 75.0, "rpm": 71,  "magazine_size": 5,  "head_damage_armored": 90,  "chest_damage_armored": 22},
    {"defindex": 28,  "weapon_key": "negev",           "display_name": "Negev",                "category": "heavy",    "slot": 0, "cost": 1700, "damage": 35,  "armor_penetration": 75.0, "rpm": 800, "magazine_size": 150,"head_damage_armored": 105, "chest_damage_armored": 26},
    {"defindex": 29,  "weapon_key": "sawed_off",        "display_name": "Sawed-Off",          "category": "heavy",    "slot": 0, "cost": 1100, "damage": 32,  "armor_penetration": 75.0, "rpm": 68,  "magazine_size": 7,  "head_damage_armored": 96,  "chest_damage_armored": 24},
    {"defindex": 14,  "weapon_key": "m249",             "display_name": "M249",                "category": "heavy",    "slot": 0, "cost": 5200, "damage": 32,  "armor_penetration": 80.0, "rpm": 750, "magazine_size": 100,"head_damage_armored": 102, "chest_damage_armored": 25},
    # ── Equipment ──────────────────────────────────────────────────────────
    {"defindex": 31,  "weapon_key": "zeus_x27",         "display_name": "Zeus x27",            "category": "equipment","slot": 4, "cost": 200,  "damage": 195, "armor_penetration": 100.0,"rpm": 0,   "magazine_size": 1,  "head_damage_armored": 780, "chest_damage_armored": 195},
    # ── Grenades ─────────────────────────────────────────────────────────
    {"defindex": 43,  "weapon_key": "flashbang",        "display_name": "Flashbang",           "category": "grenade",  "slot": 5, "cost": 200,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 44,  "weapon_key": "he_grenade",       "display_name": "HE Grenade",         "category": "grenade",  "slot": 5, "cost": 300,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 45,  "weapon_key": "smoke_grenade",    "display_name": "Smoke Grenade",      "category": "grenade",  "slot": 5, "cost": 200,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 46,  "weapon_key": "molotov",          "display_name": "Molotov",             "category": "grenade",  "slot": 5, "cost": 400,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 47,  "weapon_key": "decoy",            "display_name": "Decoy Grenade",        "category": "grenade",  "slot": 5, "cost": 50,   "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 48,  "weapon_key": "incendiary",        "display_name": "Incendiary Grenade",  "category": "grenade",  "slot": 5, "cost": 400,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 68,  "weapon_key": "tag_grenade",      "display_name": "Tactical Awareness Grenade","category": "grenade","slot": 5,"cost": 200,"damage": 0, "armor_penetration": 0.0, "rpm": 0, "magazine_size": 1, "head_damage_armored": 0, "chest_damage_armored": 0},
    {"defindex": 84,  "weapon_key": "snowball",          "display_name": "Snowball",             "category": "grenade",  "slot": 5, "cost": 50,   "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 1,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    # ── Armor / Utility ───────────────────────────────────────────────────
    {"defindex": 50,  "weapon_key": "kevlar",            "display_name": "Kevlar Vest",        "category": "armor",    "slot": 8, "cost": 400,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 51,  "weapon_key": "kevlar_helmet",     "display_name": "Kevlar + Helmet",   "category": "armor",    "slot": 8, "cost": 650,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 55,  "weapon_key": "defuse_kit",        "display_name": "Defuse Kit",          "category": "utility",  "slot": 9, "cost": 400,  "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    # ── Explosive ────────────────────────────────────────────────────────
    {"defindex": 49,  "weapon_key": "c4",               "display_name": "C4 Explosive",        "category": "explosive", "slot": 10,"cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    # ── Melee / Knives ──────────────────────────────────────────────────
    {"defindex": 42,  "weapon_key": "classic_knife",     "display_name": "Classic Knife",      "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 59,  "weapon_key": "knife_t",           "display_name": "Knife (T)",           "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 500, "weapon_key": "bayonet",           "display_name": "Bayonet",             "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 505, "weapon_key": "flip_knife",       "display_name": "Flip Knife",         "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 506, "weapon_key": "gut_knife",         "display_name": "Gut Knife",           "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 507, "weapon_key": "karambit",         "display_name": "Karambit",            "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 508, "weapon_key": "m9_bayonet",        "display_name": "M9 Bayonet",          "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 509, "weapon_key": "knife_tactical",    "display_name": "Tactical Knife",     "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 512, "weapon_key": "knife_falchion",   "display_name": "Falchion Knife",      "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 514, "weapon_key": "knife_survival_bowie","display_name": "Survival Bowie",    "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 515, "weapon_key": "knife_butterfly",   "display_name": "Butterfly Knife",     "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 516, "weapon_key": "knife_push",         "display_name": "Shadow Daggers",       "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 519, "weapon_key": "knife_ursus",       "display_name": "Ursus Knife",        "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 520, "weapon_key": "knife_gypsy_jackknife","display_name": "Gypsy Jackknife",  "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 522, "weapon_key": "knife_stiletto",     "display_name": "Stiletto Knife",      "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 523, "weapon_key": "knife_widowmaker",  "display_name": "Widowmaker Knife",   "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    {"defindex": 80,  "weapon_key": "knife_ghost",        "display_name": "Ghost Knife",         "category": "melee",    "slot": 2, "cost": 0,    "damage": 34,  "armor_penetration": 85.0, "rpm": 120, "magazine_size": 0,  "head_damage_armored": 115, "chest_damage_armored": 28},
    # ── Gloves ───────────────────────────────────────────────────────────
    {"defindex": 5027,"weapon_key": "studded_bloodhound_gloves","display_name": "Studded Bloodhound Gloves","category": "gloves","slot": 2,"cost": 0, "damage": 0, "armor_penetration": 0.0, "rpm": 0, "magazine_size": 0, "head_damage_armored": 0, "chest_damage_armored": 0},
    {"defindex": 5028,"weapon_key": "t_gloves",           "display_name": "T Gloves",             "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5029,"weapon_key": "ct_gloves",          "display_name": "CT Gloves",           "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5030,"weapon_key": "sporty_gloves",      "display_name": "Sport Gloves",        "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5031,"weapon_key": "slick_gloves",       "display_name": "Slick Gloves",         "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5032,"weapon_key": "leather_handwraps", "display_name": "Leather Handwraps",  "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5033,"weapon_key": "motorcycle_gloves",  "display_name": "Moto Gloves",         "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5034,"weapon_key": "specialist_gloves",  "display_name": "Specialist Gloves",   "category": "gloves",   "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
    {"defindex": 5035,"weapon_key": "studded_hydra_gloves","display_name": "Studded Hydra Gloves","category": "gloves",  "slot": 2, "cost": 0,    "damage": 0,   "armor_penetration": 0.0,   "rpm": 0,   "magazine_size": 0,  "head_damage_armored": 0,   "chest_damage_armored": 0},
]


def upgrade() -> None:
    # Add damage stat columns
    op.add_column("weapons", sa.Column("damage", sa.SmallInteger(), nullable=True, server_default="0"))
    op.add_column("weapons", sa.Column("armor_penetration", sa.Numeric(5, 2), nullable=True, server_default="0"))
    op.add_column("weapons", sa.Column("rpm", sa.SmallInteger(), nullable=True, server_default="0"))
    op.add_column("weapons", sa.Column("magazine_size", sa.SmallInteger(), nullable=True, server_default="0"))
    op.add_column("weapons", sa.Column("head_damage_armored", sa.SmallInteger(), nullable=True, server_default="0"))
    op.add_column("weapons", sa.Column("chest_damage_armored", sa.SmallInteger(), nullable=True, server_default="0"))

    # Replace all weapon data with authoritative cs2damage.com values
    # First delete all existing rows
    op.execute(sa.text("DELETE FROM csda.weapons"))

    # Insert all weapons with damage stats
    for w in WEAPON_DATA:
        op.execute(
            sa.text(
                "INSERT INTO csda.weapons "
                "(defindex, weapon_key, display_name, category, slot, cost, "
                "damage, armor_penetration, rpm, magazine_size, head_damage_armored, chest_damage_armored) "
                "VALUES (:defindex, :key, :dname, :cat, :slot, :cost, "
                ":damage, :armor_pen, :rpm, :mag, :head, :chest)"
            ).bindparams(
                defindex=w["defindex"],
                key=w["weapon_key"],
                dname=w["display_name"],
                cat=w["category"],
                slot=w["slot"],
                cost=w["cost"],
                damage=w["damage"],
                armor_pen=w["armor_penetration"],
                rpm=w["rpm"],
                mag=w["magazine_size"],
                head=w["head_damage_armored"],
                chest=w["chest_damage_armored"],
            )
        )


def downgrade() -> None:
    op.drop_column("weapons", "chest_damage_armored")
    op.drop_column("weapons", "head_damage_armored")
    op.drop_column("weapons", "magazine_size")
    op.drop_column("weapons", "rpm")
    op.drop_column("weapons", "armor_penetration")
    op.drop_column("weapons", "damage")
