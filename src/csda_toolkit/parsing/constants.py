"""Lookup tables, enums, and weapon definitions for CS2 demo parsing."""

from enum import IntEnum


# ── Teams ───────────────────────────────────────────────────────────────────

class TeamNum(IntEnum):
    UNASSIGNED = 0
    SPECTATOR = 1
    TERRORIST = 2
    COUNTER_TERRORIST = 3


TEAM_NUM_TO_SIDE = {
    0: "none",
    1: "none",
    2: "t",
    3: "ct",
}

TEAM_NUM_TO_NAME = {
    0: "unassigned",
    1: "spectator",
    2: "terrorist",
    3: "counter_terrorist",
}


# ── Round end reasons (CS2) ────────────────────────────────────────────────

ROUND_END_REASON: dict[int, str] = {
    0: "unknown",
    1: "target_killed",         # Target successfully killed
    2: "vip_escaped",           # VIP escaped
    3: "vip_killed",            # VIP killed
    4: "terrorists_escaped",    # Terrorists escaped
    5: "ct_stopped_escape",     # CTs prevented escape
    6: "terrorists_surrendered",
    7: "ct_reached_hostage",
    8: "bomb_detonated",
    9: "bomb_defused",
    10: "ct_prevented_bomb",
    11: "terrorists_all_killed",
    12: "cts_all_killed",
    13: "target_saved",
    14: "hostage_not_rescued",
    15: "terrorists_not_escaped",
    16: "vip_not_escaped",
    17: "game_start",
    18: "tie",
    19: "draw",
}


# ── Hit groups ──────────────────────────────────────────────────────────────

HITGROUP: dict[int, str] = {
    -1: "invalid",
    0: "generic",
    1: "head",
    2: "chest",
    3: "stomach",
    4: "left_arm",
    5: "right_arm",
    6: "left_leg",
    7: "right_leg",
    8: "neck",
    9: "gear",
}


# ── Weapon definitions ──────────────────────────────────────────────────────

WEAPON_DEFINDEX_TO_NAME: dict[int, str] = {
    # Primary weapons
    1: "desert_eagle",
    2: "dual_berettas",
    3: "five_seven",
    4: "glock_18",
    7: "ak_47",
    8: "aug",
    9: "awp",
    10: "famas",
    11: "g3sg1",
    13: "galil_ar",
    14: "m249",
    16: "m4a4",
    17: "mac_10",
    19: "p90",
    23: "mp5_sd",
    24: "ump_45",
    25: "xm1014",
    26: "pp_bizon",
    27: "mag_7",
    28: "negev",
    29: "sawed_off",
    30: "tec_9",
    31: "zeus_x27",
    32: "p2000",
    33: "mp7",
    34: "mp9",
    35: "nova",
    36: "p250",
    37: "scar_20",
    38: "sg_553",
    39: "ssg_08",
    40: "usp_s",
    41: "knife",
    42: "knife",
    # Grenades & equipment (defindices 43-57)
    43: "flashbang",
    44: "he_grenade",
    45: "smoke_grenade",
    46: "molotov",
    47: "decoy",
    48: "incendiary",
    49: "c4",
    50: "kevlar",
    51: "kevlar_helmet",
    52: "heavyassaultsuit",
    54: "night_rescue",
    55: "defuse_kit",
    56: "rescue_kit",
    57: "medi_shot",
    59: "knife_t",
    60: "m4a1_s",
    61: "usp_s",
    63: "cz75_auto",
    64: "revolver",
    # Alternative names (some overlap with above — kept for compatibility)
    62: "m4a1_s",
    65: "five_seven",
    66: "glock_18",
    67: "p2000",
    68: "desert_eagle",
    69: "dual_berettas",
    70: "five_seven",
    71: "glock_18",
    72: "ak_47",
    73: "aug",
    74: "famas",
    75: "g3sg1",
    76: "galil_ar",
    77: "galil_ar",
    78: "m249",
    79: "m4a4",
    80: "mac_10",
    81: "p90",
    82: "ump_45",
    83: "xm1014",
    84: "pp_bizon",
    85: "mag_7",
    86: "negev",
    87: "sawed_off",
    88: "tec_9",
    89: "zeus_x27",
    90: "p2000",
    91: "mp7",
    92: "mp9",
    93: "nova",
    94: "p250",
    95: "scar_20",
    96: "sg_553",
    97: "ssg_08",
    98: "awp",
    99: "m4a1_s",
    # Knife defindices (500+)
    500: "bayonet",
    503: "classic_knife",
    505: "flip_knife",
    506: "gut_knife",
    507: "karambit",
    508: "m9_bayonet",
    509: "huntsman_knife",
    512: "falchion_knife",
    514: "bowie_knife",
    515: "butterfly_knife",
    516: "shadow_daggers",
    517: "paracord_knife",
    518: "survival_knife",
    519: "ursus_knife",
    520: "navaja_knife",
    521: "nomad_knife",
    522: "stiletto_knife",
    523: "talon_knife",
    525: "skeleton_knife",
    526: "kukri_knife",
}

# Categorization for economy analysis
WEAPON_CATEGORY = {
    # Rifles
    "ak_47": "rifle", "m4a4": "rifle", "m4a1_s": "rifle", "m4a1_silencer": "rifle",
    "aug": "rifle", "sg_553": "rifle", "galil_ar": "rifle", "famas": "rifle",
    # Snipers
    "awp": "sniper", "ssg_08": "sniper", "scar_20": "sniper", "g3sg1": "sniper",
    # SMGs
    "mp9": "smg", "mp7": "smg", "mp5_sd": "smg", "mac_10": "smg",
    "p90": "smg", "pp_bizon": "smg", "ump_45": "smg",
    # Pistols
    "usp_s": "pistol", "usp_silencer": "pistol", "glock_18": "pistol",
    "p2000": "pistol", "hkp2000": "pistol", "p250": "pistol",
    "five_seven": "pistol", "tec_9": "pistol", "cz75_auto": "pistol",
    "desert_eagle": "pistol", "deagle": "pistol", "revolver": "pistol",
    "dual_elites": "pistol", "elite": "pistol", "dual_berettas": "pistol",
    # Heavy
    "nova": "heavy", "xm1014": "heavy", "mag_7": "heavy",
    "m249": "heavy", "negev": "heavy", "sawed_off": "heavy",
    # Equipment (Zeus/Taser)
    "zeus_x27": "equipment", "taser": "equipment",
    # Grenades
    "flashbang": "grenade", "he_grenade": "grenade", "smoke_grenade": "grenade",
    "molotov": "grenade", "decoy": "grenade", "incendiary": "grenade",
    "tag_grenade": "grenade", "snowball": "grenade",
    # Armor
    "kevlar": "armor", "kevlar_helmet": "armor",
    # Utility (defuse kit, rescue kit, medi-shot)
    "defuse_kit": "utility", "rescue_kit": "utility", "medi_shot": "utility",
    "night_rescue": "utility",
    # Explosive (C4)
    "c4": "explosive",
    # Knives / Melee
    "bayonet": "melee", "classic_knife": "melee", "flip_knife": "melee",
    "gut_knife": "melee", "karambit": "melee", "m9_bayonet": "melee",
    "huntsman_knife": "melee", "falchion_knife": "melee", "bowie_knife": "melee",
    "butterfly_knife": "melee", "shadow_daggers": "melee", "paracord_knife": "melee",
    "survival_knife": "melee", "nomad_knife": "melee", "stiletto_knife": "melee",
    "talon_knife": "melee", "skeleton_knife": "melee",
    "knife": "melee", "knife_t": "melee", "knife_tactical": "melee", "knife_push": "melee",
    "knife_falchion": "melee", "knife_survival_bowie": "melee",
    "knife_ghost": "melee",
    # Gloves
    "studded_bloodhound_gloves": "gloves", "t_gloves": "gloves", "ct_gloves": "gloves",
    "sporty_gloves": "gloves", "slick_gloves": "gloves", "leather_handwraps": "gloves",
    "motorcycle_gloves": "gloves", "specialist_gloves": "gloves", "studded_hydra_gloves": "gloves",
}

# Weapon names (for game event "weapon" field mapping)
WEAPON_EVENT_NAME_TO_KEY = {
    "weapon_ak47": "ak_47",
    "weapon_m4a1": "m4a4",
    "weapon_m4a1_silencer": "m4a1_s",
    "weapon_usp_silencer": "usp_s",
    "weapon_glock": "glock_18",
    "weapon_hkp2000": "p2000",
    "weapon_deagle": "desert_eagle",
    "weapon_elite": "dual_berettas",
    "weapon_fiveseven": "five_seven",
    "weapon_tec9": "tec_9",
    "weapon_mac10": "mac_10",
    "weapon_ump45": "ump_45",
    "weapon_bizon": "pp_bizon",
    "weapon_mag7": "mag_7",
    "weapon_sawedoff": "sawed_off",
    "weapon_taser": "zeus_x27",
    "weapon_scar20": "scar_20",
    "weapon_sg556": "sg_553",
    "weapon_ssg08": "ssg_08",
    "weapon_mp5sd": "mp5_sd",
    "weapon_p250er": "p250",
}


def normalize_weapon_name(raw: str) -> str:
    """Normalize weapon names from game events to canonical keys.

    Handles formats like 'weapon_ak47', 'ak47', 'AK-47' -> 'ak_47'.
    """
    name = raw.lower().replace("-", "_").replace(" ", "_")
    if name.startswith("weapon_"):
        name = name[7:]
    # Game event name -> canonical key
    if name in WEAPON_EVENT_NAME_TO_KEY:
        return WEAPON_EVENT_NAME_TO_KEY[name]
    # Already a canonical key
    if name in WEAPON_CATEGORY:
        return name
    # Try direct lookup
    for canon_key, event_key in WEAPON_EVENT_NAME_TO_KEY.items():
        if name == event_key or name == canon_key:
            return canon_key if name == canon_key else event_key
    return name


def weapon_category(weapon: str) -> str:
    """Return weapon category (rifle, smg, pistol, etc.)."""
    key = normalize_weapon_name(weapon)
    return WEAPON_CATEGORY.get(key, "unknown")


def defindex_to_weapon(defindex: int) -> str:
    """Map item definition index to canonical weapon name."""
    return WEAPON_DEFINDEX_TO_NAME.get(defindex, f"unknown_{defindex}")


# ── Site names ──────────────────────────────────────────────────────────────

BOMB_SITE: dict[int, str] = {
    183: "A",
    184: "B",
    185: "A",  # alternate
}


# ── Smoke grenade colors ────────────────────────────────────────────────────

SMOKE_COLORS: dict[str, str] = {
    "0.31 0.38 0.22": "green",
    "0.67 0.18 0.24": "red",
    "0.73 0.73 0.73": "grey",
    "0.25 0.25 0.25": "black",
    "0.60 0.80 0.92": "blue",
    "0.94 0.90 0.55": "yellow",
    "0.98 0.50 0.45": "orange",
    "0.96 0.75 0.82": "pink",
    "0.80 0.49 0.80": "purple",
    "0.00 0.86 0.87": "cyan",
}
