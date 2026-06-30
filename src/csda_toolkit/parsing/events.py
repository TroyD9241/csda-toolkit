"""Event-specific parsers for all 46 CS2 game events.

Every column reference has been verified against a real test demo.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from csda_toolkit.domain.models import (
    BombEvent,
    DamageEvent,
    FootstepEvent,
    GrenadeDetonation,
    GrenadeTrajectory,
    HltvVersionInfo,
    InfernoEvent,
    ItemDrop,
    ItemEquip,
    ItemPickup,
    Kill,
    MatchPanel,
    OtherDeath,
    PlayerBlind,
    PlayerJump,
    PlayerSpawn,
    RankUpdate,
    RoundEndReason,
    RoundMvp,
    RoundStartEvent,
    SkinData,
    TickEvent,
    WeaponFire,
    WeaponReload,
    WeaponZoom,
    WinPanelRound,
)
from csda_toolkit.parsing.constants import ROUND_END_REASON, normalize_weapon_name

# Hitgroup name → ID mapping (our fork returns string names like "head" instead of int IDs)
HITGROUP_NAMES_TO_IDS: dict[str, int] = {
    "generic": 0, "head": 1, "chest": 2, "stomach": 3,
    "left_arm": 4, "right_arm": 5, "left_leg": 6, "right_leg": 7,
    "neck": 8, "gear": 9,
}
# Reverse: ID → name
HITGROUP_IDS_TO_NAMES: dict[int, str] = {v: k for k, v in HITGROUP_NAMES_TO_IDS.items()}

# Round-end reason: fork name → upstream ID mapping
# Our fork returns string names like "bomb_defused", "ct_killed" instead of int IDs
ROUND_END_REASON_FORK_TO_ID: dict[str, int] = {
    "unknown": 0, "target_killed": 1, "vip_escaped": 2, "vip_killed": 3,
    "terrorists_escaped": 4, "ct_stopped_escape": 5, "terrorists_surrendered": 6,
    "ct_reached_hostage": 7,
    "bomb_exploded": 8, "bomb_detonated": 8,  # fork uses "bomb_exploded"
    "bomb_defused": 9,
    "ct_prevented_bomb": 10,
    "t_killed": 11, "terrorists_all_killed": 11,  # fork uses "t_killed"
    "ct_killed": 12, "cts_all_killed": 12,  # fork uses "ct_killed"
    "target_saved": 13, "hostage_not_rescued": 14,
    "terrorists_not_escaped": 15, "vip_not_escaped": 16,
    "game_start": 17, "tie": 18, "draw": 19,
}

# Winner-side mapping for our fork (which returns "CT"/"T" strings)
WINNER_FORK_TO_SIDE: dict[str, str] = {"CT": "ct", "T": "t"}
WINNER_FORK_TO_INT: dict[str, int] = {"CT": 3, "T": 2}


def _int(val) -> Optional[int]:
    try: return int(val)
    except (ValueError, TypeError): return None

def _sid(val) -> Optional[int]:
    if val is None or (isinstance(val, float) and pd.isna(val)): return None
    try: return int(float(val)) if isinstance(val, (int, float)) else int(val)
    except: return None

def _str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)): return ""
    return str(val)

def _bool(val) -> bool:
    if isinstance(val, bool): return val
    if isinstance(val, (int, float)): return bool(val)
    s = str(val).lower().strip()
    return s in ("true", "1", "yes")

def _flt(val) -> Optional[float]:
    try: return float(val)
    except: return None

def _hitgroup_id(val) -> int:
    """Convert hitgroup value to integer ID.
    Our fork returns string names (e.g. 'head'), but we also accept int IDs."""
    if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
        return int(val)
    if isinstance(val, str):
        return HITGROUP_NAMES_TO_IDS.get(val, -1)
    return -1

def _hitgroup_name(val) -> str:
    """Convert hitgroup value to human-readable name.
    Our fork returns names directly; if it's an int ID, look it up."""
    if isinstance(val, str) and not val.isdigit():
        # Already a name string
        return val if val in HITGROUP_NAMES_TO_IDS else "unknown"
    # It's an ID number
    return HITGROUP_IDS_TO_NAMES.get(int(val) if isinstance(val, str) else val, "unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUND EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_round_freeze_end(df: pd.DataFrame) -> list[int]:
    return df["tick"].tolist()


# ── Tick-marker parsers (events with only a tick column) ─────────────────


def _tick_marker(df: pd.DataFrame, event_type: str) -> list[TickEvent]:
    return [TickEvent(event_type=event_type, tick=int(r["tick"])) for _, r in df.iterrows()]


def parse_begin_new_match(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "begin_new_match")


def parse_buytime_ended(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "buytime_ended")


def parse_cs_pre_restart(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "cs_pre_restart")


def parse_cs_round_final_beep(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "cs_round_final_beep")


def parse_cs_round_start_beep(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "cs_round_start_beep")


def parse_round_announce_match_start(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "round_announce_match_start")


def parse_round_officially_ended(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "round_officially_ended")


def parse_round_poststart(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "round_poststart")


def parse_round_prestart(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "round_prestart")


def parse_round_time_warning(df: pd.DataFrame) -> list[TickEvent]:
    return _tick_marker(df, "round_time_warning")


# ── Events with extra fields ─────────────────────────────────────────────


def parse_round_start(df: pd.DataFrame) -> list[RoundStartEvent]:
    """Columns: fraglimit, objective, tick, timelimit"""
    results = []
    for _, row in df.iterrows():
        results.append(RoundStartEvent(
            tick=int(row["tick"]),
            frag_limit=int(row.get("fraglimit", 0)),
            objective=_str(row.get("objective", "")),
            time_limit=int(row.get("timelimit", 0)),
        ))
    return results


def parse_hltv_versioninfo(df: pd.DataFrame) -> list[HltvVersionInfo]:
    """Columns: tick, version"""
    return [HltvVersionInfo(tick=int(r["tick"]), version=int(r.get("version", 0))) for _, r in df.iterrows()]


def parse_cs_win_panel_match(df: pd.DataFrame) -> list[MatchPanel]:
    """Columns: tick"""
    return [MatchPanel(tick=int(r["tick"])) for _, r in df.iterrows()]


def parse_player_footstep(df: pd.DataFrame) -> list[FootstepEvent]:
    """Columns: tick, user_name, user_steamid"""
    return [FootstepEvent(tick=int(r["tick"]), player_steam_id=_sid(r.get("user_steamid")), player_name=_str(r.get("user_name"))) for _, r in df.iterrows()]


def parse_other_death(df: pd.DataFrame) -> list[OtherDeath]:
    """19 columns from other_death event:
    attacker_last_place_name, attacker_name, attacker_steamid, attacker_team_name,
    attackerblind, ct_team_name, headshot, noscope, otherid, othertype, penetrated,
    t_team_name, thrusmoke, tick, total_rounds_played, weapon, weapon_fauxitemid,
    weapon_itemid, weapon_originalowner_xuid"""
    results = []
    for _, row in df.iterrows():
        results.append(OtherDeath(
            tick=int(row["tick"]),
            attacker_steam_id=_sid(row.get("attacker_steamid")),
            attacker_name=_str(row.get("attacker_name")),
            attackerblind=_bool(row.get("attackerblind", False)),
            headshot=_bool(row.get("headshot", False)),
            noscope=_bool(row.get("noscope", False)),
            penetrated=int(row.get("penetrated", 0)),
            thrusmoke=_bool(row.get("thrusmoke", False)),
            weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
            othertype=_str(row.get("othertype", "")),
        ))
    return results


def parse_round_end(df: pd.DataFrame) -> list[RoundEndReason]:
    """Columns (our fork): reason, round, tick, winner
    Fork returns string reasons (e.g. "bomb_defused") and winner ("CT"/"T")."""
    results = []
    for _, row in df.iterrows():
        raw_reason = row.get("reason")
        if raw_reason is None or (isinstance(raw_reason, float) and pd.isna(raw_reason)):
            reason_code = 0
            reason_name = "unknown"
        elif isinstance(raw_reason, str) and not raw_reason.isdigit():
            reason_code = ROUND_END_REASON_FORK_TO_ID.get(raw_reason, 0)
            reason_name = raw_reason
        else:
            reason_code = int(raw_reason)
            reason_name = ROUND_END_REASON.get(reason_code, "unknown")

        raw_winner = row.get("winner")
        if isinstance(raw_winner, str):
            winner_side = WINNER_FORK_TO_SIDE.get(raw_winner, "none")
        elif isinstance(raw_winner, (int, float)):
            winner_side = {2: "t", 3: "ct"}.get(int(raw_winner), "none")
        else:
            winner_side = "none"

        results.append(RoundEndReason(
            tick=int(row["tick"]),
            winner_side=winner_side,
            reason_code=reason_code,
            reason_name=reason_name,
            message=_str(row.get("message", "")),
            player_count=int(row.get("player_count", 0)),
        ))
    return results


def parse_round_mvp(df: pd.DataFrame) -> list[RoundMvp]:
    """Columns: musickitid, musickitmvps, nomusic, reason, tick, user_name, user_steamid, value"""
    results = []
    for _, row in df.iterrows():
        results.append(RoundMvp(
            tick=int(row["tick"]),
            player_steam_id=_sid(row.get("user_steamid")),
            player_name=_str(row.get("user_name")),
            reason=int(row.get("reason", 0)),
            value=int(row.get("value", 0)),
            musickit_id=int(row.get("musickitid", 0)),
        ))
    return results


def parse_cs_win_panel_round(df: pd.DataFrame) -> list[WinPanelRound]:
    """Columns: final_event, funfact_data1-3, funfact_player, funfact_token,
    show_timer_attack, show_timer_defend, tick, timer_time"""
    results = []
    for _, row in df.iterrows():
        results.append(WinPanelRound(
            tick=int(row["tick"]),
            final_event=int(row.get("final_event", 0)),
            funfact_token=_str(row.get("funfact_token")),
            funfact_player=int(row.get("funfact_player", 0)),
            funfact_data1=int(row.get("funfact_data1", 0)),
            funfact_data2=int(row.get("funfact_data2", 0)),
            funfact_data3=int(row.get("funfact_data3", 0)),
            show_timer_attack=_bool(row.get("show_timer_attack", False)),
            show_timer_defend=_bool(row.get("show_timer_defend", False)),
            timer_time=int(row.get("timer_time", 0)),
        ))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYER EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_player_death(df: pd.DataFrame) -> list[Kill]:
    """34 columns with player+other extras:
    assistedflash, assister_last_place_name, assister_name, assister_steamid,
    assister_team_name, attacker_last_place_name, attacker_name, attacker_steamid,
    attacker_team_name, attackerblind, ct_team_name, distance, dmg_armor, dmg_health,
    dominated, headshot, hitgroup, noreplay, noscope, penetrated, revenge,
    t_team_name, thrusmoke, tick, total_rounds_played, user_last_place_name,
    user_name, user_steamid, user_team_name, weapon, weapon_fauxitemid,
    weapon_itemid, weapon_originalowner_xuid, wipe"""
    results = []
    for _, row in df.iterrows():
        results.append(Kill(
            tick=int(row["tick"]),
            round_number=int(row.get("total_rounds_played", 0)),
            killer_steam_id=_sid(row.get("attacker_steamid")),
            killer_name=_str(row.get("attacker_name")),
            killer_team=_str(row.get("attacker_team_name", "")),
            killer_last_place_name=_str(row.get("attacker_last_place_name", "")),
            victim_steam_id=_sid(row.get("user_steamid")),
            victim_name=_str(row.get("user_name")),
            victim_team=_str(row.get("user_team_name", "")),
            victim_last_place_name=_str(row.get("user_last_place_name", "")),
            assister_steam_id=_sid(row.get("assister_steamid")),
            assister_name=_str(row.get("assister_name")),
            assister_team=_str(row.get("assister_team_name", "")),
            assister_last_place_name=_str(row.get("assister_last_place_name", "")),
            weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
            weapon_item_id=_str(row.get("weapon_itemid", "")),
            weapon_faux_item_id=_str(row.get("weapon_fauxitemid", "")),
            weapon_original_owner_xuid=_str(row.get("weapon_originalowner_xuid", "")),
            headshot=_bool(row.get("headshot", False)),
            penetrated=int(row.get("penetrated", 0)),
            thrusmoke=_bool(row.get("thrusmoke", False)),
            attackerblind=_bool(row.get("attackerblind", False)),
            attackerinair=_bool(row.get("attackerinair", False)),
            noscope=_bool(row.get("noscope", False)),
            assistedflash=_bool(row.get("assistedflash", False)),
            dominated=_bool(row.get("dominated", False)),
            revenge=_bool(row.get("revenge", False)),
            wipe=_bool(row.get("wipe", False)),
            distance=_flt(row.get("distance")),
            dmg_health=int(row.get("dmg_health", 0)),
            dmg_armor=int(row.get("dmg_armor", 0)),
            hitgroup=_hitgroup_id(row.get("hitgroup")),
            hitgroup_name=_hitgroup_name(row.get("hitgroup")),
        ))
    return results


def parse_player_hurt(df: pd.DataFrame) -> list[DamageEvent]:
    """18 columns with player+other extras:
    armor, attacker_last_place_name, attacker_name, attacker_steamid,
    attacker_team_name, ct_team_name, dmg_armor, dmg_health, health, hitgroup,
    t_team_name, tick, total_rounds_played, user_last_place_name, user_name,
    user_steamid, user_team_name, weapon"""
    results = []
    for _, row in df.iterrows():
        results.append(DamageEvent(
            tick=int(row["tick"]),
            round_number=int(row.get("total_rounds_played", 0)),
            attacker_steam_id=_sid(row.get("attacker_steamid")),
            attacker_name=_str(row.get("attacker_name")),
            victim_steam_id=_sid(row.get("user_steamid")),
            victim_name=_str(row.get("user_name")),
            weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
            dmg_health=int(row.get("dmg_health", 0)),
            dmg_armor=int(row.get("dmg_armor", 0)),
            hitgroup=_hitgroup_id(row.get("hitgroup")),
            health=int(row.get("health", 0)),
            armor=int(row.get("armor", 0)),
            hitgroup_name=_hitgroup_name(row.get("hitgroup")),
            attacker_last_place_name=_str(row.get("attacker_last_place_name", "")),
            victim_last_place_name=_str(row.get("user_last_place_name", "")),
        ))
    return results


def parse_player_blind(df: pd.DataFrame) -> list[PlayerBlind]:
    """Columns: attacker_name, attacker_steamid, blind_duration, entityid, tick,
    user_name, user_steamid"""
    results = []
    for _, row in df.iterrows():
        results.append(PlayerBlind(
            tick=int(row["tick"]),
            attacker_steam_id=_sid(row.get("attacker_steamid")),
            attacker_name=_str(row.get("attacker_name")),
            victim_steam_id=_sid(row.get("user_steamid")),
            victim_name=_str(row.get("user_name")),
            blind_duration=float(row.get("blind_duration", 0.0)),
        ))
    return results


def parse_player_spawn(df: pd.DataFrame) -> list[PlayerSpawn]:
    """Columns: tick, user_name, user_steamid"""
    return [PlayerSpawn(tick=int(r["tick"]), player_steam_id=_sid(r.get("user_steamid")), player_name=_str(r.get("user_name"))) for _, r in df.iterrows()]


def parse_player_jump(df: pd.DataFrame) -> list[PlayerJump]:
    """Columns: tick, user_name, user_steamid"""
    return [PlayerJump(tick=int(r["tick"]), player_steam_id=_sid(r.get("user_steamid")), player_name=_str(r.get("user_name"))) for _, r in df.iterrows()]


def parse_player_disconnect(df: pd.DataFrame) -> list[dict]:
    """Columns: PlayerID, name, networkid, reason, tick, user_name, user_steamid, xuid"""
    return df.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# WEAPON EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_weapon_fire(df: pd.DataFrame) -> list[WeaponFire]:
    """Columns: silenced, tick, user_name, user_steamid, weapon"""
    results = []
    for _, row in df.iterrows():
        results.append(WeaponFire(
            tick=int(row["tick"]),
            player_steam_id=_sid(row.get("user_steamid")),
            player_name=_str(row.get("user_name")),
            weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
            silenced=_bool(row.get("silenced", False)),
        ))
    return results


def parse_weapon_reload(df: pd.DataFrame) -> list[WeaponReload]:
    """Columns: tick, user_name, user_steamid"""
    return [WeaponReload(tick=int(r["tick"]), player_steam_id=_sid(r.get("user_steamid")), player_name=_str(r.get("user_name"))) for _, r in df.iterrows()]


def parse_weapon_zoom(df: pd.DataFrame) -> list[WeaponZoom]:
    """Columns: tick, user_name, user_steamid"""
    return [WeaponZoom(tick=int(r["tick"]), player_steam_id=_sid(r.get("user_steamid")), player_name=_str(r.get("user_name"))) for _, r in df.iterrows()]


def parse_item_equip(df: pd.DataFrame) -> list[ItemEquip]:
    """Columns: canzoom, defindex, hassilencer, hastracers, ispainted, issilenced,
    item, tick, user_name, user_steamid, weptype"""
    results = []
    for _, row in df.iterrows():
        results.append(ItemEquip(
            tick=int(row["tick"]),
            player_steam_id=_sid(row.get("user_steamid")),
            player_name=_str(row.get("user_name")),
            defindex=int(row.get("defindex", 0)),
            item=_str(row.get("item", "")),
            canzoom=_bool(row.get("canzoom", False)),
            hassilencer=_bool(row.get("hassilencer", False)),
            issilenced=_bool(row.get("issilenced", False)),
            ispainted=_bool(row.get("ispainted", False)),
            hastracers=_bool(row.get("hastracers", False)),
            weptype=_str(row.get("weptype", "")),
        ))
    return results


def parse_item_pickup(df: pd.DataFrame) -> list[ItemPickup]:
    """Columns: defindex, item, silent, tick, user_name, user_steamid"""
    results = []
    for _, row in df.iterrows():
        results.append(ItemPickup(
            tick=int(row["tick"]),
            player_steam_id=_sid(row.get("user_steamid")),
            player_name=_str(row.get("user_name")),
            item=_str(row.get("item", "")),
            defindex=int(row.get("defindex", 0)),
            silent=_bool(row.get("silent", False)),
        ))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# BOMB EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _bomb_event(row, etype: str, has_site=True, has_kit=False) -> BombEvent:
    return BombEvent(
        tick=int(row["tick"]),
        event_type=etype,
        player_steam_id=_sid(row.get("user_steamid")),
        player_name=_str(row.get("user_name")),
        site=_str(row.get("site", "")) if has_site else None,
        has_kit=_bool(row.get("haskit", False)) if has_kit else None,
    )

def parse_bomb_planted(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: site, tick, user_name, user_steamid"""
    return [_bomb_event(r, "planted") for _, r in df.iterrows()]

def parse_bomb_beginplant(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: site, tick, user_name, user_steamid"""
    return [_bomb_event(r, "begin_plant") for _, r in df.iterrows()]

def parse_bomb_defused(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: site, tick, user_name, user_steamid"""
    return [_bomb_event(r, "defused") for _, r in df.iterrows()]

def parse_bomb_begindefuse(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: haskit, tick, user_name, user_steamid"""
    return [_bomb_event(r, "begin_defuse", has_site=False, has_kit=True) for _, r in df.iterrows()]

def parse_bomb_exploded(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: site, tick, user_name, user_steamid"""
    return [_bomb_event(r, "exploded") for _, r in df.iterrows()]

def parse_bomb_dropped(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: entindex, tick, user_name, user_steamid"""
    return [_bomb_event(r, "dropped", has_site=False) for _, r in df.iterrows()]

def parse_bomb_pickup(df: pd.DataFrame) -> list[BombEvent]:
    """Columns: tick, user_name, user_steamid"""
    return [_bomb_event(r, "pickup", has_site=False) for _, r in df.iterrows()]


# ═══════════════════════════════════════════════════════════════════════════════
# GRENADE EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _grenade(row, gtype: str) -> GrenadeDetonation:
    return GrenadeDetonation(
        tick=int(row["tick"]),
        grenade_type=gtype,
        player_steam_id=_sid(row.get("user_steamid")),
        player_name=_str(row.get("user_name")),
        x=_flt(row.get("x")), y=_flt(row.get("y")), z=_flt(row.get("z")),
    )

def parse_hegrenade_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    """Columns: entityid, tick, user_name, user_steamid, x, y, z"""
    return [_grenade(r, "hegrenade") for _, r in df.iterrows()]

def parse_flashbang_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    return [_grenade(r, "flashbang") for _, r in df.iterrows()]

def parse_smokegrenade_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    return [_grenade(r, "smoke") for _, r in df.iterrows()]

def parse_smokegrenade_expired(df: pd.DataFrame) -> list[GrenadeDetonation]:
    return [_grenade(r, "smoke_expired") for _, r in df.iterrows()]


def _inferno(row, etype: str) -> InfernoEvent:
    return InfernoEvent(
        tick=int(row["tick"]),
        event_type=etype,
        player_steam_id=_sid(row.get("user_steamid")),
        player_name=_str(row.get("user_name")),
        x=_flt(row.get("x")), y=_flt(row.get("y")), z=_flt(row.get("z")),
    )

def parse_inferno_startburn(df: pd.DataFrame) -> list[InfernoEvent]:
    """Columns: entityid, tick, user_name, user_steamid, x, y, z"""
    return [_inferno(r, "start_burn") for _, r in df.iterrows()]

def parse_inferno_expire(df: pd.DataFrame) -> list[InfernoEvent]:
    return [_inferno(r, "expire") for _, r in df.iterrows()]


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH / MISC
# ═══════════════════════════════════════════════════════════════════════════════

def parse_rank_update(df: pd.DataFrame) -> list[RankUpdate]:
    """Columns: num_wins, rank_change, rank_new, rank_old, rank_type_id, tick,
    user_name, user_steamid"""
    results = []
    for _, row in df.iterrows():
        results.append(RankUpdate(
            tick=int(row["tick"]),
            player_steam_id=_sid(row.get("user_steamid")),
            player_name=_str(row.get("user_name")),
            rank_old=int(row.get("rank_old", 0)),
            rank_new=int(row.get("rank_new", 0)),
            rank_change=int(row.get("rank_change", 0)),
            num_wins=int(row.get("num_wins", 0)),
            rank_type_id=int(row.get("rank_type_id", 0)),
        ))
    return results


# ── Raw passthrough (not parsed into domain models) ──────────────────────────

def parse_bullet_details(df: pd.DataFrame) -> list[dict]:
    """Return raw fire_bullets data."""
    return df.to_dict(orient="records")

# Alias used by parser.py
parse_fire_bullets = parse_bullet_details


def parse_server_cvar(df: pd.DataFrame) -> list[dict]:
    """Columns: name, tick, value"""
    return df.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# SKINS / ITEM DROPS / GRENADE TRAJECTORIES
# ═══════════════════════════════════════════════════════════════════════════════


def parse_skins(df: pd.DataFrame) -> list[SkinData]:
    """Columns: def_index, item_id, paint_index, paint_seed, paint_wear, steamid, custom_name"""
    results = []
    for _, row in df.iterrows():
        results.append(SkinData(
            def_index=int(row.get("def_index", 0)),
            item_id=int(row.get("item_id", 0)),
            paint_index=int(row.get("paint_index", 0)),
            paint_seed=int(row.get("paint_seed", 0)),
            paint_wear=int(row.get("paint_wear", 0)),
            steam_id=int(row.get("steamid", 0)),
            custom_name=_str(row.get("custom_name")),
        ))
    return results


def parse_item_drops(df: pd.DataFrame) -> list[ItemDrop]:
    """Columns: account_id, def_index, dropreason, inventory, item_id,
    paint_index, paint_seed, paint_wear, custom_name"""
    results = []
    for _, row in df.iterrows():
        results.append(ItemDrop(
            account_id=int(row.get("account_id", 0)),
            def_index=int(row.get("def_index", 0)),
            drop_reason=int(row.get("dropreason", 0)),
            inventory=int(row.get("inventory", 0)),
            item_id=int(row.get("item_id", 0)),
            paint_index=int(row.get("paint_index", 0)),
            paint_seed=int(row.get("paint_seed", 0)),
            paint_wear=int(row.get("paint_wear", 0)),
            custom_name=_str(row.get("custom_name")),
        ))
    return results


def parse_grenade_trajectories(df: pd.DataFrame) -> list[GrenadeTrajectory]:
    """Columns (our fork): grenade_type, grenade_entity_id, x, y, z, tick, steamid, name"""
    results = []
    for _, row in df.iterrows():
        results.append(GrenadeTrajectory(
            tick=int(row.get("tick", 0)),
            x=float(row.get("x", 0.0)),
            y=float(row.get("y", 0.0)),
            z=float(row.get("z", 0.0)),
            grenade_type=_str(row.get("grenade_type")),
            grenade_entity_id=int(row.get("grenade_entity_id", 0)),
            thrower_steam_id=_int(row.get("steamid")) or 0,
            thrower_name=_str(row.get("name")),
        ))
    return results
