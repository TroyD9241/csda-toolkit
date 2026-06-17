"""Event-specific parsers for all 46 CS2 game events.

Each function returns a list of typed dataclass instances from
``csda_toolkit.domain.models``.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from csda_toolkit.domain.models import (
    BombEvent,
    DamageEvent,
    FootstepEvent,
    GrenadeDetonation,
    InfernoEvent,
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
    WeaponFire,
    WeaponReload,
    WeaponZoom,
    WinPanelRound,
)
from csda_toolkit.parsing.constants import (
    ROUND_END_REASON,
    normalize_weapon_name,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _safe_int(val) -> Optional[int]:
    try:
        v = int(val)
        return v if v else None  # 0 is often not meaningful for IDs
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _steam_id(val) -> Optional[int]:
    """Convert string steam ID to int."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        # Already int
        if isinstance(val, int):
            return val
        # SteamID3 format [U:1:xxx] -> 765...
        s = str(val).strip()
        if s and s[0].isdigit():
            return int(s)
    except (ValueError, TypeError):
        pass
    return None


def _str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# ROUND EVENTS  (9 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_round_start(df: pd.DataFrame) -> list[dict]:
    """Return raw round_start data: fraglimit, objective, tick, timelimit."""
    records = df.to_dict(orient="records")
    for r in records:
        r.pop("tick", None)  # tick is implicit from context
    return records  # type: ignore


def parse_round_freeze_end(df: pd.DataFrame) -> list[int]:
    """Return list of freeze-end ticks."""
    return df["tick"].tolist()


def parse_round_end(df: pd.DataFrame) -> list[RoundEndReason]:
    """Parse round_end events."""
    results: list[RoundEndReason] = []
    for _, row in df.iterrows():
        reason = int(row.get("reason", 0))
        winner_side = {2: "t", 3: "ct"}.get(int(row.get("winner", 0)), "none")
        results.append(
            RoundEndReason(
                tick=int(row.get("tick", 0)),
                winner_side=winner_side,
                reason_code=reason,
                reason_name=ROUND_END_REASON.get(reason, "unknown"),
                message=_str(row.get("message", "")),
                player_count=int(row.get("player_count", 0)),
                total_rounds_played=int(row.get("total_rounds_played", 0))
                if "total_rounds_played" in df.columns
                else 0,
            )
        )
    return results


def parse_round_officially_ended(df: pd.DataFrame) -> list[int]:
    """Return list of officially-ended ticks."""
    return df["tick"].tolist()


def parse_round_mvp(df: pd.DataFrame) -> list[RoundMvp]:
    """Parse round_mvp events."""
    results: list[RoundMvp] = []
    for _, row in df.iterrows():
        results.append(
            RoundMvp(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                reason=int(row.get("reason", 0)),
                value=int(row.get("value", 0)),
                musickit_id=int(row.get("musickitid", 0)),
            )
        )
    return results


def parse_cs_win_panel_round(df: pd.DataFrame) -> list[WinPanelRound]:
    """Parse cs_win_panel_round — round conclusion summary panel."""
    results: list[WinPanelRound] = []
    for _, row in df.iterrows():
        results.append(
            WinPanelRound(
                tick=int(row.get("tick", 0)),
                final_event=int(row.get("final_event", 0)),
                funfact_token=_str(row.get("funfact_token", "")),
                funfact_player=int(row.get("funfact_player", 0)),
                funfact_data1=int(row.get("funfact_data1", 0)),
                funfact_data2=int(row.get("funfact_data2", 0)),
                funfact_data3=int(row.get("funfact_data3", 0)),
                show_timer_attack=_bool(row.get("show_timer_attack", False)),
                show_timer_defend=_bool(row.get("show_timer_defend", False)),
                timer_time=int(row.get("timer_time", 0)),
            )
        )
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYER EVENTS  (8 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_player_death(df: pd.DataFrame) -> list[Kill]:
    """Parse player_death events (34 columns of rich data)."""
    results: list[Kill] = []
    for _, row in df.iterrows():
        results.append(
            Kill(
                tick=int(row.get("tick", 0)),
                round_number=int(row.get("total_rounds_played", 0))
                if "total_rounds_played" in df.columns
                else 0,
                killer_steam_id=_steam_id(row.get("attacker_steamid")),
                killer_name=_str(row.get("attacker_name")),
                killer_team=_str(row.get("attacker_team_name", "")),
                killer_last_place_name=_str(row.get("attacker_last_place_name", "")),
                victim_steam_id=_steam_id(row.get("user_steamid")),
                victim_name=_str(row.get("user_name")),
                victim_team=_str(row.get("user_team_name", "")),
                victim_last_place_name=_str(row.get("user_last_place_name", "")),
                assister_steam_id=_steam_id(row.get("assister_steamid")),
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
                noscope=_bool(row.get("noscope", False)),
                assistedflash=_bool(row.get("assistedflash", False)),
                dominated=_bool(row.get("dominated", False)),
                revenge=_bool(row.get("revenge", False)),
                wipe=_bool(row.get("wipe", False)),
                distance=_safe_float(row.get("distance")),
                dmg_health=int(row.get("dmg_health", 0)),
                dmg_armor=int(row.get("dmg_armor", 0)),
                hitgroup=int(row.get("hitgroup", -1)),
            )
        )
    return results


def parse_player_hurt(df: pd.DataFrame) -> list[DamageEvent]:
    """Parse player_hurt events."""
    results: list[DamageEvent] = []
    for _, row in df.iterrows():
        results.append(
            DamageEvent(
                tick=int(row.get("tick", 0)),
                round_number=int(row.get("total_rounds_played", 0))
                if "total_rounds_played" in df.columns
                else 0,
                attacker_steam_id=_steam_id(row.get("attacker_steamid")),
                attacker_name=_str(row.get("attacker_name")),
                victim_steam_id=_steam_id(row.get("user_steamid")),
                victim_name=_str(row.get("user_name")),
                weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
                dmg_health=int(row.get("dmg_health", 0)),
                dmg_armor=int(row.get("dmg_armor", 0)),
                hitgroup=int(row.get("hitgroup", -1)),
                health=int(row.get("health", 0)),
                armor=int(row.get("armor", 0)),
                hitgroup_name={
                    -1: "invalid", 0: "generic", 1: "head", 2: "chest",
                    3: "stomach", 4: "left_arm", 5: "right_arm",
                    6: "left_leg", 7: "right_leg", 8: "neck", 9: "gear",
                }.get(int(row.get("hitgroup", -1)), "unknown"),
            )
        )
    return results


def parse_player_blind(df: pd.DataFrame) -> list[PlayerBlind]:
    """Parse player_blind events."""
    results: list[PlayerBlind] = []
    for _, row in df.iterrows():
        results.append(
            PlayerBlind(
                tick=int(row.get("tick", 0)),
                attacker_steam_id=_steam_id(row.get("attacker_steamid")),
                attacker_name=_str(row.get("attacker_name")),
                victim_steam_id=_steam_id(row.get("user_steamid")),
                victim_name=_str(row.get("user_name")),
                blind_duration=_safe_float(row.get("blind_duration", 0.0)),
            )
        )
    return results


def parse_player_spawn(df: pd.DataFrame) -> list[PlayerSpawn]:
    """Parse player_spawn events."""
    results: list[PlayerSpawn] = []
    for _, row in df.iterrows():
        results.append(
            PlayerSpawn(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_player_jump(df: pd.DataFrame) -> list[PlayerJump]:
    """Parse player_jump events."""
    results: list[PlayerJump] = []
    for _, row in df.iterrows():
        results.append(
            PlayerJump(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_player_footstep(df: pd.DataFrame) -> list[FootstepEvent]:
    """Parse player_footstep events."""
    results: list[FootstepEvent] = []
    for _, row in df.iterrows():
        results.append(
            FootstepEvent(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_player_disconnect(df: pd.DataFrame) -> list[dict]:
    """Return raw player_disconnect data."""
    return df.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# WEAPON EVENTS  (6 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_weapon_fire(df: pd.DataFrame) -> list[WeaponFire]:
    """Parse weapon_fire events."""
    results: list[WeaponFire] = []
    for _, row in df.iterrows():
        results.append(
            WeaponFire(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                weapon=normalize_weapon_name(_str(row.get("weapon", ""))),
                silenced=_bool(row.get("silenced", False)),
            )
        )
    return results


def parse_weapon_reload(df: pd.DataFrame) -> list[WeaponReload]:
    """Parse weapon_reload events."""
    results: list[WeaponReload] = []
    for _, row in df.iterrows():
        results.append(
            WeaponReload(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_weapon_zoom(df: pd.DataFrame) -> list[WeaponZoom]:
    """Parse weapon_zoom events."""
    results: list[WeaponZoom] = []
    for _, row in df.iterrows():
        results.append(
            WeaponZoom(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_item_equip(df: pd.DataFrame) -> list[ItemEquip]:
    """Parse item_equip events (player equips a weapon)."""
    results: list[ItemEquip] = []
    for _, row in df.iterrows():
        results.append(
            ItemEquip(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                defindex=int(row.get("defindex", 0)),
                item=_str(row.get("item", "")),
                canzoom=_bool(row.get("canzoom", False)),
                hassilencer=_bool(row.get("hassilencer", False)),
                issilenced=_bool(row.get("issilenced", False)),
                ispainted=_bool(row.get("ispainted", False)),
                hastracers=_bool(row.get("hastracers", False)),
                weptype=_str(row.get("weptype", "")),
            )
        )
    return results


def parse_item_pickup(df: pd.DataFrame) -> list[ItemPickup]:
    """Parse item_pickup events."""
    results: list[ItemPickup] = []
    for _, row in df.iterrows():
        results.append(
            ItemPickup(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                item=_str(row.get("item", "")),
                defindex=int(row.get("defindex", 0)),
                silent=_bool(row.get("silent", False)),
            )
        )
    return results


def parse_fire_bullets(df: pd.DataFrame) -> list[dict]:
    """Return raw fire_bullets data (shot-level detail)."""
    return df.to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════════
# BOMB EVENTS  (7 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_bomb_planted(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="planted",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                site=_str(row.get("site", "")),
            )
        )
    return results


def parse_bomb_beginplant(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="begin_plant",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                site=_str(row.get("site", "")),
            )
        )
    return results


def parse_bomb_defused(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="defused",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                site=_str(row.get("site", "")),
            )
        )
    return results


def parse_bomb_begindefuse(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="begin_defuse",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                has_kit=_bool(row.get("haskit", False)),
            )
        )
    return results


def parse_bomb_exploded(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="exploded",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                site=_str(row.get("site", "")),
            )
        )
    return results


def parse_bomb_dropped(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="dropped",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


def parse_bomb_pickup(df: pd.DataFrame) -> list[BombEvent]:
    results: list[BombEvent] = []
    for _, row in df.iterrows():
        results.append(
            BombEvent(
                tick=int(row.get("tick", 0)),
                event_type="pickup",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
            )
        )
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# GRENADE EVENTS  (6 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_hegrenade_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    results: list[GrenadeDetonation] = []
    for _, row in df.iterrows():
        results.append(
            GrenadeDetonation(
                tick=int(row.get("tick", 0)),
                grenade_type="hegrenade",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


def parse_flashbang_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    results: list[GrenadeDetonation] = []
    for _, row in df.iterrows():
        results.append(
            GrenadeDetonation(
                tick=int(row.get("tick", 0)),
                grenade_type="flashbang",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


def parse_smokegrenade_detonate(df: pd.DataFrame) -> list[GrenadeDetonation]:
    results: list[GrenadeDetonation] = []
    for _, row in df.iterrows():
        results.append(
            GrenadeDetonation(
                tick=int(row.get("tick", 0)),
                grenade_type="smoke",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


def parse_smokegrenade_expired(df: pd.DataFrame) -> list[GrenadeDetonation]:
    results: list[GrenadeDetonation] = []
    for _, row in df.iterrows():
        results.append(
            GrenadeDetonation(
                tick=int(row.get("tick", 0)),
                grenade_type="smoke_expired",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


def parse_inferno_startburn(df: pd.DataFrame) -> list[InfernoEvent]:
    results: list[InfernoEvent] = []
    for _, row in df.iterrows():
        results.append(
            InfernoEvent(
                tick=int(row.get("tick", 0)),
                event_type="start_burn",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


def parse_inferno_expire(df: pd.DataFrame) -> list[InfernoEvent]:
    results: list[InfernoEvent] = []
    for _, row in df.iterrows():
        results.append(
            InfernoEvent(
                tick=int(row.get("tick", 0)),
                event_type="expire",
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                x=_safe_float(row.get("x")),
                y=_safe_float(row.get("y")),
                z=_safe_float(row.get("z")),
            )
        )
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH / MISC EVENTS  (6 events)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_begin_new_match(df: pd.DataFrame) -> list[int]:
    """Return list of ticks for begin_new_match."""
    return df["tick"].tolist()


def parse_cs_win_panel_match(df: pd.DataFrame) -> list[MatchPanel]:
    """Parse cs_win_panel_match — match conclusion."""
    return [MatchPanel(tick=int(row["tick"])) for _, row in df.iterrows()]


def parse_buytime_ended(df: pd.DataFrame) -> list[int]:
    return df["tick"].tolist()


def parse_round_announce_match_start(df: pd.DataFrame) -> list[int]:
    return df["tick"].tolist()


def parse_rank_update(df: pd.DataFrame) -> list[RankUpdate]:
    results: list[RankUpdate] = []
    for _, row in df.iterrows():
        results.append(
            RankUpdate(
                tick=int(row.get("tick", 0)),
                player_steam_id=_steam_id(row.get("user_steamid")),
                player_name=_str(row.get("user_name")),
                rank_old=int(row.get("rank_old", 0)),
                rank_new=int(row.get("rank_new", 0)),
                rank_change=int(row.get("rank_change", 0)),
                num_wins=int(row.get("num_wins", 0)),
                rank_type_id=int(row.get("rank_type_id", 0)),
            )
        )
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# DISPATCH TABLE
# ═══════════════════════════════════════════════════════════════════════════════

ALL_EVENT_PARSERS: dict[str, tuple[str, callable]] = {
    # Round
    "round_start": ("raw", parse_round_start),
    "round_freeze_end": ("ticks", parse_round_freeze_end),
    "round_end": ("round_end", parse_round_end),
    "round_officially_ended": ("ticks", parse_round_officially_ended),
    "round_mvp": ("round_mvp", parse_round_mvp),
    "round_poststart": ("raw", None),
    "round_prestart": ("raw", None),
    "cs_win_panel_round": ("win_panel_round", parse_cs_win_panel_round),
    "cs_round_start_beep": ("raw", None),
    "cs_round_final_beep": ("raw", None),
    "cs_pre_restart": ("raw", None),
    # Player
    "player_death": ("kill", parse_player_death),
    "player_hurt": ("damage", parse_player_hurt),
    "player_blind": ("player_blind", parse_player_blind),
    "player_spawn": ("player_spawn", parse_player_spawn),
    "player_jump": ("player_jump", parse_player_jump),
    "player_footstep": ("footstep", parse_player_footstep),
    "player_disconnect": ("raw", parse_player_disconnect),
    "other_death": ("raw", None),
    # Weapon
    "weapon_fire": ("weapon_fire", parse_weapon_fire),
    "weapon_reload": ("weapon_reload", parse_weapon_reload),
    "weapon_zoom": ("weapon_zoom", parse_weapon_zoom),
    "item_equip": ("item_equip", parse_item_equip),
    "item_pickup": ("item_pickup", parse_item_pickup),
    "fire_bullets": ("raw", parse_fire_bullets),
    # Bomb
    "bomb_planted": ("bomb", parse_bomb_planted),
    "bomb_beginplant": ("bomb", parse_bomb_beginplant),
    "bomb_defused": ("bomb", parse_bomb_defused),
    "bomb_begindefuse": ("bomb", parse_bomb_begindefuse),
    "bomb_exploded": ("bomb", parse_bomb_exploded),
    "bomb_dropped": ("bomb", parse_bomb_dropped),
    "bomb_pickup": ("bomb", parse_bomb_pickup),
    # Grenade
    "hegrenade_detonate": ("grenade", parse_hegrenade_detonate),
    "flashbang_detonate": ("grenade", parse_flashbang_detonate),
    "smokegrenade_detonate": ("grenade", parse_smokegrenade_detonate),
    "smokegrenade_expired": ("grenade", parse_smokegrenade_expired),
    "inferno_startburn": ("grenade", parse_inferno_startburn),
    "inferno_expire": ("grenade", parse_inferno_expire),
    # Match
    "begin_new_match": ("begin_match", parse_begin_new_match),
    "cs_win_panel_match": ("match_panel", parse_cs_win_panel_match),
    "buytime_ended": ("ticks", parse_buytime_ended),
    "round_announce_match_start": ("ticks", parse_round_announce_match_start),
    "rank_update": ("rank_update", parse_rank_update),
    "hltv_versioninfo": ("raw", None),
    "server_cvar": ("raw", None),
}
