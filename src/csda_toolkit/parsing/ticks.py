"""Tick-level data extraction from the 904 available tick fields.

Provides functions to extract per-player state (position, health, equipment,
money, stats) and game rules state at specific ticks or all ticks.
"""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
from demoparser2 import DemoParser

from csda_toolkit.domain.models import (
    GameRulesFrame,
    PlayerFrame,
    PlayerMoney,
    PlayerRoundStats,
)

# ── Field group definitions ─────────────────────────────────────────────────

# CCSPlayerPawn fields — per-player world state
PAWN_FIELDS = [
    "CCSPlayerPawn.m_vecX",
    "CCSPlayerPawn.m_vecY",
    "CCSPlayerPawn.m_vecZ",
    "CCSPlayerPawn.m_angEyeAngles",
    "CCSPlayerPawn.m_iHealth",
    "CCSPlayerPawn.m_ArmorValue",
    "CCSPlayerPawn.m_bIsScoped",
    "CCSPlayerPawn.m_bIsWalking",
    "CCSPlayerPawn.m_bIsDefusing",
    "CCSPlayerPawn.m_bInBuyZone",
    "CCSPlayerPawn.m_bInBombZone",
    "CCSPlayerPawn.m_iShotsFired",
    "CCSPlayerPawn.m_flFlashDuration",
    "CCSPlayerPawn.m_flVelocityModifier",
    "CCSPlayerPawn.m_flDuckAmount",
    "CCSPlayerPawn.m_unCurrentEquipmentValue",
    "CCSPlayerPawn.m_unFreezetimeEndEquipmentValue",
    "CCSPlayerPawn.m_unRoundStartEquipmentValue",
    "CCSPlayerPawn.m_bHasHelmet",
    "CCSPlayerPawn.m_bHasDefuser",
    "CCSPlayerPawn.m_bIsBuyMenuOpen",
]

# CCSPlayerController fields — per-player identity/connection
CONTROLLER_FIELDS = [
    "CCSPlayerController.m_steamID",
    "CCSPlayerController.m_iszPlayerName",
    "CCSPlayerController.m_iTeamNum",
    "CCSPlayerController.m_bPawnIsAlive",
    "CCSPlayerController.m_iScore",
    "CCSPlayerController.m_iMVPs",
    "CCSPlayerController.m_iPing",
    "CCSPlayerController.m_iCompetitiveRanking",
    "CCSPlayerController.m_iCompetitiveWins",
    "CCSPlayerController.m_szClan",
    "CCSPlayerController.m_iConnected",
]

# ActionTrackingServices — cumulative per-round stats
ACTION_FIELDS = [
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iKills",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iAssists",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDeaths",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDamage",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iHeadShotKills",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iCashEarned",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEquipmentValue",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iUtilityDamage",
    "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEnemiesFlashed",
]

# InGameMoneyServices — money tracking
MONEY_FIELDS = [
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount",
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount",
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound",
    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iTotalCashSpent",
]

# Game rules fields
RULES_FIELDS = [
    "CCSGameRulesProxy.CCSGameRules.m_totalRoundsPlayed",
    "CCSGameRulesProxy.CCSGameRules.m_bRoundInProgress",
    "CCSGameRulesProxy.CCSGameRules.m_bFreezePeriod",
    "CCSGameRulesProxy.CCSGameRules.m_bBombPlanted",
    "CCSGameRulesProxy.CCSGameRules.m_bBombDropped",
    "CCSGameRulesProxy.CCSGameRules.m_bHasMatchStarted",
    "CCSGameRulesProxy.CCSGameRules.m_bWarmupPeriod",
    "CCSGameRulesProxy.CCSGameRules.m_iRoundWinStatus",
    "CCSGameRulesProxy.CCSGameRules.m_eRoundWinReason",
    "CCSGameRulesProxy.CCSGameRules.m_bCTCantBuy",
    "CCSGameRulesProxy.CCSGameRules.m_bTCantBuy",
    "CCSGameRulesProxy.CCSGameRules.m_bCTTimeOutActive",
    "CCSGameRulesProxy.CCSGameRules.m_bTerroristTimeOutActive",
    "CCSGameRulesProxy.CCSGameRules.m_bIsValveDS",
    "CCSGameRulesProxy.CCSGameRules.m_bIsHltvActive",
    "CCSGameRulesProxy.CCSGameRules.m_iMatchStats_PlayersAlive_CT",
    "CCSGameRulesProxy.CCSGameRules.m_iMatchStats_PlayersAlive_T",
    "CCSGameRulesProxy.CCSGameRules.m_iNumConsecutiveCTLoses",
    "CCSGameRulesProxy.CCSGameRules.m_iNumConsecutiveTerroristLoses",
    "CCSGameRulesProxy.CCSGameRules.m_iRoundTime",
    "CCSGameRulesProxy.CCSGameRules.m_bGamePaused",
    "CCSGameRulesProxy.CCSGameRules.m_nOvertimePlaying",
]

# Team fields
TEAM_FIELDS = [
    "CCSTeam.m_iScore",
    "CCSTeam.m_szTeamname",
    "CCSTeam.m_szClanTeamname",
    "CCSTeam.m_scoreFirstHalf",
    "CCSTeam.m_scoreSecondHalf",
    "CCSTeam.m_scoreOvertime",
    "CCSTeam.m_numMapVictories",
    "CCSTeam.m_iTeamNum",
    "CCSTeam.m_bSurrendered",
]

# ── Conversion helpers ──────────────────────────────────────────────────────


def _get_val(df: pd.DataFrame, i: int, col: str):
    """Get a value from a DataFrame cell, handling NaN and missing columns."""
    if col not in df.columns:
        return None
    val = df.iloc[i][col]
    if isinstance(val, float) and pd.isna(val):
        return None
    return val


def _int_val(df, i, col, default=0) -> int:
    val = _get_val(df, i, col)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _float_val(df, i, col, default=0.0) -> float:
    val = _get_val(df, i, col)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _bool_val(df, i, col, default=False) -> bool:
    val = _get_val(df, i, col)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return default


def _str_val(df, i, col, default="") -> str:
    val = _get_val(df, i, col)
    if val is None:
        return default
    return str(val)


# ── Player frame extraction ─────────────────────────────────────────────────


def extract_player_frames(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
) -> list[PlayerFrame]:
    """Extract per-player world state at given ticks (or all ticks).

    Returns a flat list of PlayerFrame dataclasses.
    """
    df = parser.parse_ticks(PAWN_FIELDS, ticks=ticks)
    if df.empty:
        return []

    frames: list[PlayerFrame] = []
    for i in range(len(df)):
        tick = int(df.iloc[i]["tick"])
        sid = int(df.iloc[i]["steamid"])

        # Eye angles come as a list [x, y, z]
        eye = _get_val(df, i, "CCSPlayerPawn.m_angEyeAngles") or [0, 0, 0]

        frames.append(
            PlayerFrame(
                tick=tick,
                steam_id=sid,
                name=_str_val(df, i, "name"),
                x=_float_val(df, i, "CCSPlayerPawn.m_vecX"),
                y=_float_val(df, i, "CCSPlayerPawn.m_vecY"),
                z=_float_val(df, i, "CCSPlayerPawn.m_vecZ"),
                eye_angle_x=float(eye[0]) if isinstance(eye, (list, tuple)) else 0.0,
                eye_angle_y=float(eye[1]) if isinstance(eye, (list, tuple)) else 0.0,
                eye_angle_z=float(eye[2]) if isinstance(eye, (list, tuple)) else 0.0,
                health=_int_val(df, i, "CCSPlayerPawn.m_iHealth"),
                armor=_int_val(df, i, "CCSPlayerPawn.m_ArmorValue"),
                is_scoped=_bool_val(df, i, "CCSPlayerPawn.m_bIsScoped"),
                is_walking=_bool_val(df, i, "CCSPlayerPawn.m_bIsWalking"),
                is_defusing=_bool_val(df, i, "CCSPlayerPawn.m_bIsDefusing"),
                in_buy_zone=_bool_val(df, i, "CCSPlayerPawn.m_bInBuyZone"),
                in_bomb_zone=_bool_val(df, i, "CCSPlayerPawn.m_bInBombZone"),
                shots_fired=_int_val(df, i, "CCSPlayerPawn.m_iShotsFired"),
                flash_duration=_float_val(df, i, "CCSPlayerPawn.m_flFlashDuration"),
                velocity_modifier=_float_val(df, i, "CCSPlayerPawn.m_flVelocityModifier"),
                duck_amount=_float_val(df, i, "CCSPlayerPawn.m_flDuckAmount"),
                current_equip_value=_int_val(df, i, "CCSPlayerPawn.m_unCurrentEquipmentValue"),
                freezetime_end_equip_value=_int_val(df, i, "CCSPlayerPawn.m_unFreezetimeEndEquipmentValue"),
                round_start_equip_value=_int_val(df, i, "CCSPlayerPawn.m_unRoundStartEquipmentValue"),
                has_defuser=_bool_val(df, i, "CCSPlayerPawn.m_bHasDefuser"),
                has_helmet=_bool_val(df, i, "CCSPlayerPawn.m_bHasHelmet"),
            )
        )

    return frames


def extract_controller_frames(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
) -> list[PlayerFrame]:
    """Extract controller-level data (team, identity, alive status).

    Returns PlayerFrame objects with controller fields populated.
    """
    df = parser.parse_ticks(CONTROLLER_FIELDS, ticks=ticks)
    if df.empty:
        return []

    frames: list[PlayerFrame] = []
    for i in range(len(df)):
        tick = int(df.iloc[i]["tick"])
        sid = int(df.iloc[i]["steamid"])

        frames.append(
            PlayerFrame(
                tick=tick,
                steam_id=sid,
                name=_str_val(df, i, "CCSPlayerController.m_iszPlayerName"),
                team_num=_int_val(df, i, "CCSPlayerController.m_iTeamNum"),
                is_alive=_bool_val(df, i, "CCSPlayerController.m_bPawnIsAlive"),
                score=_int_val(df, i, "CCSPlayerController.m_iScore"),
                mvps=_int_val(df, i, "CCSPlayerController.m_iMVPs"),
                ping=_int_val(df, i, "CCSPlayerController.m_iPing"),
                competitive_ranking=_int_val(df, i, "CCSPlayerController.m_iCompetitiveRanking"),
                competitive_wins=_int_val(df, i, "CCSPlayerController.m_iCompetitiveWins"),
                clan=_str_val(df, i, "CCSPlayerController.m_szClan"),
            )
        )

    return frames


def extract_player_round_stats(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
    round_end_ticks: Optional[dict[int, int]] = None,
) -> list[PlayerRoundStats]:
    """Extract per-round cumulative stats from ActionTrackingServices.

    Args:
        parser: DemoParser instance.
        ticks: Optional explicit tick list. If None, uses demoparser default.
        round_end_ticks: Optional mapping of round_number -> end_tick.
            When provided, extracts PRS at round end ticks and assigns
            round_number correctly. Falls back to the last available tick
            before the next round's start if end_tick is unavailable.

    Returns:
        List of PlayerRoundStats with round_number set when round_end_ticks
        is provided.
    """
    if round_end_ticks is not None:
        # Use round end ticks for snapshot selection
        sorted_rounds = sorted(round_end_ticks.items(), key=lambda x: x[1])
        end_ticks = [et for _, et in sorted_rounds]
        df = parser.parse_ticks(ACTION_FIELDS, ticks=end_ticks)
        if df.empty:
            return []

        # Build mapping: end_tick -> round_number
        tick_to_round: dict[int, int] = {et: rn for rn, et in sorted_rounds}

        stats: list[PlayerRoundStats] = []
        for i in range(len(df)):
            tick = int(df.iloc[i]["tick"])
            sid = int(df.iloc[i]["steamid"])
            # Find the round this tick belongs to
            # First try exact match
            round_num = tick_to_round.get(tick)
            if round_num is None:
                # Fallback: find the closest end_tick that is <= this tick
                closest = None
                for et, rn in sorted_rounds:
                    if et <= tick:
                        closest = rn
                    else:
                        break
                round_num = closest if closest is not None else 0

            stats.append(
                PlayerRoundStats(
                    tick=tick,
                    steam_id=sid,
                    round_number=round_num,
                    kills=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iKills"),
                    assists=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iAssists"),
                    deaths=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDeaths"),
                    damage=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDamage"),
                    headshot_kills=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iHeadShotKills"),
                    cash_earned=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iCashEarned"),
                    equipment_value=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEquipmentValue"),
                    utility_damage=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iUtilityDamage"),
                    enemies_flashed=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEnemiesFlashed"),
                )
            )
        return stats

    # Legacy path: no round_end_ticks provided
    df = parser.parse_ticks(ACTION_FIELDS, ticks=ticks)
    if df.empty:
        return []

    stats: list[PlayerRoundStats] = []
    for i in range(len(df)):
        tick = int(df.iloc[i]["tick"])
        sid = int(df.iloc[i]["steamid"])

        stats.append(
            PlayerRoundStats(
                tick=tick,
                steam_id=sid,
                round_number=0,  # caller must assign from round boundaries
                kills=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iKills"),
                assists=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iAssists"),
                deaths=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDeaths"),
                damage=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iDamage"),
                headshot_kills=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iHeadShotKills"),
                cash_earned=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iCashEarned"),
                equipment_value=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEquipmentValue"),
                utility_damage=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iUtilityDamage"),
                enemies_flashed=_int_val(df, i, "CCSPlayerController.CCSPlayerController_ActionTrackingServices.m_iEnemiesFlashed"),
            )
        )

    return stats


def validate_prs_cumulative(stats: list[PlayerRoundStats]) -> list[str]:
    """Validate PRS data for monotonicity and per-round delta sanity.

    Returns a list of warning strings (empty if all OK).
    """
    warnings = []
    by_player: dict[int, list[PlayerRoundStats]] = {}
    for s in stats:
        by_player.setdefault(s.steam_id, []).append(s)
    for sid, rows in by_player.items():
        rows.sort(key=lambda r: (r.round_number, r.tick))
        prev_damage = 0
        prev_round = 0
        for r in rows:
            if r.damage < prev_damage:
                warnings.append(
                    f"steam_id={sid} round={r.round_number} tick={r.tick}: "
                    f"damage DECREASED from {prev_damage} to {r.damage}"
                )
            if r.round_number > prev_round + 1 and prev_round > 0:
                warnings.append(
                    f"steam_id={sid} round jump: {prev_round} -> {r.round_number}"
                )
            prev_damage = r.damage
            prev_round = r.round_number
    return warnings


def extract_player_money(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
) -> list[PlayerMoney]:
    """Extract per-player money state from InGameMoneyServices."""
    df = parser.parse_ticks(MONEY_FIELDS, ticks=ticks)
    if df.empty:
        return []

    money: list[PlayerMoney] = []
    for i in range(len(df)):
        tick = int(df.iloc[i]["tick"])
        sid = int(df.iloc[i]["steamid"])

        money.append(
            PlayerMoney(
                tick=tick,
                steam_id=sid,
                account=_int_val(df, i, "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount"),
                start_account=_int_val(df, i, "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount"),
                cash_spent_this_round=_int_val(df, i, "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound"),
                total_cash_spent=_int_val(df, i, "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iTotalCashSpent"),
            )
        )

    return money


def extract_game_rules(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
) -> list[GameRulesFrame]:
    """Extract game rules state at given ticks.

    Note: game rules fields are server-wide, so the result will have one
    row per tick (not per player). The steamid/name columns are dummy values
    from the underlying parser.
    """
    df = parser.parse_ticks(RULES_FIELDS, ticks=ticks)
    if df.empty:
        return []

    frames: list[GameRulesFrame] = []
    # Deduplicate by tick — game rules are server-wide
    seen_ticks: set[int] = set()
    for i in range(len(df)):
        tick = int(df.iloc[i]["tick"])
        if tick in seen_ticks:
            continue
        seen_ticks.add(tick)

        win_status = _int_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_iRoundWinStatus")
        win_reason = _int_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_eRoundWinReason")

        frames.append(
            GameRulesFrame(
                tick=tick,
                total_rounds_played=_int_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_totalRoundsPlayed"),
                round_in_progress=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bRoundInProgress"),
                freezetime=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bFreezePeriod"),
                bomb_planted=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bBombPlanted"),
                bomb_dropped=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bBombDropped"),
                match_started=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bHasMatchStarted"),
                warmup=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bWarmupPeriod"),
                round_win_status=win_status,
                round_win_reason=win_reason,
                ct_cant_buy=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bCTCantBuy"),
                t_cant_buy=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bTCantBuy"),
                ct_timeout_active=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bCTTimeOutActive"),
                t_timeout_active=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bTerroristTimeOutActive"),
                is_valve_ds=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bIsValveDS"),
                is_hltv_active=_bool_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_bIsHltvActive"),
                ct_score=_int_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_iMatchStats_PlayersAlive_CT"),
                t_score=_int_val(df, i, "CCSGameRulesProxy.CCSGameRules.m_iMatchStats_PlayersAlive_T"),
            )
        )

    return frames


# ── Combined extraction ─────────────────────────────────────────────────────


def extract_all_player_state(
    parser: DemoParser,
    ticks: Optional[Sequence[int]] = None,
) -> dict[int, PlayerFrame]:
    """Extract combined player state (pawn + controller) at given ticks.

    Merges pawn and controller data into complete PlayerFrame objects.
    Returns dict mapping steam_id -> PlayerFrame for the given ticks.
    """
    pawn_frames = extract_player_frames(parser, ticks)
    controller_frames = extract_controller_frames(parser, ticks)

    # Index pawn frames by (tick, steam_id)
    pawn_by_key: dict[tuple[int, int], PlayerFrame] = {
        (f.tick, f.steam_id): f for f in pawn_frames
    }

    # Merge controller data into pawn frames
    result: dict[int, PlayerFrame] = {}
    for cf in controller_frames:
        key = (cf.tick, cf.steam_id)
        pf = pawn_by_key.get(key)
        if pf:
            # Merge: use pawn data as base, overlay controller fields
            pf.team_num = cf.team_num
            pf.is_alive = cf.is_alive
            pf.score = cf.score
            pf.mvps = cf.mvps
            pf.ping = cf.ping
            pf.competitive_ranking = cf.competitive_ranking
            pf.competitive_wins = cf.competitive_wins
            pf.clan = cf.clan
            if cf.name:
                pf.name = cf.name
            result[cf.steam_id] = pf
        else:
            result[cf.steam_id] = cf

    return result
