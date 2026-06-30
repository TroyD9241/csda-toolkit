"""Persistence functions for classifier output into SQLAlchemy models.

These functions translate classifier dataclass output into database rows.
They are additive — existing data is not overwritten unless explicitly deleted first.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from csda_toolkit.db.models import (
    Match,
    PlayerCareerProfile,
    PlayerRoundKeyframe,
    PlayerRoundMovementSummary,
    PlayerRoundZoneTransition,
    PlayerRoleQualitySnapshot,
)
from csda_toolkit.classifiers.role_classifier import (
    EntryFraggerProfile,
    PlayerRoleSignals,
    RoleClassificationResult,
    score_entry_quality,
    score_awper_quality,
    score_lurker_quality,
    score_rifler_quality,
    score_support_quality,
)


# ── Role Quality Snapshot ─────────────────────────────────────────────────────


def persist_role_quality_snapshots(
    session: Session,
    match_id: int,
    steam_id: int,
    player_name: str,
    map_name: str,
    side: str,
    role_result: RoleClassificationResult,
    signals: PlayerRoleSignals,
) -> PlayerRoleQualitySnapshot:
    """Build and persist a PlayerRoleQualitySnapshot for one player in one match.

    Parameters
    ----------
    session : Session
        SQLAlchemy session
    match_id : int
        Match primary key
    steam_id : int
        Player Steam ID
    player_name : str
        Display name at time of match
    map_name : str
        e.g. "dust2", "mirage"
    side : str
        "t" or "ct"
    role_result : RoleClassificationResult
        Output of classify_player_role()
    signals : PlayerRoleSignals
        Output of build_player_role_signals(), with all role profiles populated

    Returns
    -------
    PlayerRoleQualitySnapshot
        The persisted row
    """
    ep = signals.entry_frag
    ap = signals.awper
    sp = signals.support
    rp = signals.rifler
    lp = signals.lurker

    # Compute quality scores
    entry_score = score_entry_quality(ep) if ep else None
    awp_score = score_awper_quality(ap) if ap else None
    support_score = score_support_quality(sp) if sp else None
    rifler_score = score_rifler_quality(rp) if rp else None
    lurker_score = score_lurker_quality(lp) if lp else None

    snapshot = PlayerRoleQualitySnapshot(
        match_id=match_id,
        steam_id=steam_id,
        player_name=player_name,
        map_name=map_name,
        side=side,
        broad_role=role_result.broad_role,
        map_position=role_result.map_position,
        zone_role=role_result.zone_role,
        secondary_role=role_result.secondary_role,
        role_confidence=role_result.confidence,
        # Entry
        entry_quality_score=entry_score,
        entry_attempts=ep.entry_attempts if ep else 0,
        successful_entries=ep.successful_entries if ep else 0,
        entry_kill_rate=_rate(ep.successful_entries, ep.entry_attempts) if ep else None,
        flash_pop_kills=ep.flash_pop_kills if ep else 0,
        opening_duel_wins=ep.opening_duel_wins if ep else 0,
        rounds_survived_post_entry=ep.rounds_survived_post_entry if ep else 0,
        entry_profile_json=_profile_to_json(ep) if ep else None,
        # AWP
        awp_quality_score=awp_score,
        awp_rounds=ap.awp_rounds if ap else 0,
        first_pick_rounds=ap.first_pick_rounds if ap else 0,
        opening_pick_rate=_rate(ap.first_pick_rounds, ap.awp_rounds) if ap else None,
        ct_hold_picks=ap.ct_hold_picks if ap else 0,
        ct_survived_after_pick=ap.ct_survived_after_pick if ap else 0,
        t_first_pick_rounds=ap.t_first_pick_rounds if ap else 0,
        awper_profile_json=_profile_to_json(ap) if ap else None,
        # Support
        support_quality_score=support_score,
        support_rounds=sp.support_rounds if sp else 0,
        trade_opportunities=sp.trade_opportunities if sp else 0,
        successful_trades=sp.successful_trades if sp else 0,
        trade_success_rate=_rate(sp.successful_trades, sp.trade_opportunities) if sp else None,
        flash_assisted_kills=sp.flash_assisted_kills if sp else 0,
        utility_rounds=sp.utility_rounds if sp else 0,
        economy_sacrifice_rounds=sp.economy_sacrifice_rounds if sp else 0,
        support_profile_json=_profile_to_json(sp) if sp else None,
        # Rifler
        rifler_quality_score=rifler_score,
        rifler_rounds=rp.rifler_rounds if rp else 0,
        multi_kill_rounds=rp.multi_kill_rounds if rp else 0,
        multi_kill_rate=_rate(rp.multi_kill_rounds, rp.rifler_rounds) if rp else None,
        rifler_trade_kills=rp.trade_kills if rp else 0,
        headshot_rate=rp.headshot_rate if rp else None,
        ct_site_anchor_rounds=rp.ct_site_anchor_rounds if rp else 0,
        ct_survived_anchor=rp.ct_survived_anchor if rp else 0,
        rifler_profile_json=_profile_to_json(rp) if rp else None,
        # Lurker
        lurker_quality_score=lurker_score,
        lurk_attempts=lp.lurk_attempts if lp else 0,
        solo_kills=lp.solo_kills if lp else 0,
        solo_kill_rate=_rate(lp.solo_kills, lp.lurk_attempts) if lp else None,
        rotation_cut_kills=lp.rotation_cut_kills if lp else 0,
        survived_lurk_rounds=lp.survived_lurk_rounds if lp else 0,
        clutch_rounds=lp.clutch_rounds if lp else 0,
        clutch_rounds_won=lp.clutch_rounds_won if lp else 0,
        lurker_profile_json=_profile_to_json(lp) if lp else None,
    )

    session.add(snapshot)
    session.flush()
    return snapshot


# ── Movement Storage ───────────────────────────────────────────────────────────


def persist_keyframes(
    session: Session,
    match_id: int,
    keyframes: Sequence[PlayerRoundKeyframe],
) -> list[PlayerRoundKeyframe]:
    """Bulk-persist PlayerRoundKeyframe rows.

    Parameters
    ----------
    session : Session
    match_id : int
    keyframes : sequence of PlayerRoundKeyframe dataclasses from movement_storage

    Returns
    -------
    list of persisted PlayerRoundKeyframe rows
    """
    rows = [
        PlayerRoundKeyframe(
            match_id=match_id,
            round_number=kf.round_number,
            steam_id=kf.steam_id,
            player_name=kf.player_name,
            tick=kf.tick,
            x=kf.x,
            y=kf.y,
            z=kf.z,
            eye_angle_x=kf.eye_angle_x,
            eye_angle_y=kf.eye_angle_y,
            eye_angle_z=kf.eye_angle_z,
            velocity_modifier=kf.velocity_modifier,
            is_alive=kf.is_alive,
            health=kf.health,
            side=kf.side,
        )
        for kf in keyframes
    ]
    session.add_all(rows)
    session.flush()
    return rows


def persist_zone_transitions(
    session: Session,
    match_id: int,
    transitions: Sequence[PlayerRoundZoneTransition],
) -> list[PlayerRoundZoneTransition]:
    """Bulk-persist PlayerRoundZoneTransition rows.

    Parameters
    ----------
    session : Session
    match_id : int
    transitions : sequence of PlayerRoundZoneTransition dataclasses from movement_storage

    Returns
    -------
    list of persisted PlayerRoundZoneTransition rows
    """
    rows = [
        PlayerRoundZoneTransition(
            match_id=match_id,
            round_number=zt.round_number,
            steam_id=zt.steam_id,
            player_name=zt.player_name,
            side=zt.side,
            tick=zt.tick,
            zone=zt.zone,
            zone_category=zt.zone_category,
            is_start_zone=getattr(zt, "is_start_zone", False),
            is_end_zone=getattr(zt, "is_end_zone", False),
        )
        for zt in transitions
    ]
    session.add_all(rows)
    session.flush()
    return rows


def persist_movement_summary(
    session: Session,
    match_id: int,
    summary: PlayerRoundMovementSummary,
) -> PlayerRoundMovementSummary:
    """Persist a PlayerRoundMovementSummary row.

    Parameters
    ----------
    session : Session
    match_id : int
    summary : PlayerRoundMovementSummary dataclass from movement_storage

    Returns
    -------
    PlayerRoundMovementSummary: the persisted row
    """
    row = PlayerRoundMovementSummary(
        match_id=match_id,
        round_number=summary.round_number,
        steam_id=summary.steam_id,
        player_name=summary.player_name,
        side=summary.side,
        total_distance=summary.total_distance,
        avg_speed=summary.avg_speed,
        max_speed=summary.max_speed,
        time_in_site=summary.time_in_site,
        time_in_mid=summary.time_in_mid,
        time_in_spawn=summary.time_in_spawn,
        time_in_connector=summary.time_in_connector,
        zone_transition_count=summary.zone_transition_count,
        unique_zones_visited=summary.unique_zones_visited,
        damage_dealt=summary.damage_dealt,
        kills=summary.kills,
        deaths=summary.deaths,
        movement_score=summary.movement_score,
        extra_data=summary.metadata,
    )
    session.add(row)
    session.flush()
    return row


# ── Helpers ───────────────────────────────────────────────────────────────────


def _rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


def _avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(float(v) for v in values) / len(values), 3)


def _profile_to_json(profile) -> Optional[dict]:
    """Serialize a role Profile dataclass to a dict for JSON storage."""
    if profile is None:
        return None
    import dataclasses

    result = dataclasses.asdict(profile)
    # Remove steam_id from JSON (already stored as column)
    result.pop("steam_id", None)
    return result


# ── Player Career Profile ─────────────────────────────────────────────────────


def upsert_career_profile(
    session: Session,
    steam_id: int,
    display_name: str,
    snapshot_rows: Sequence[PlayerRoleQualitySnapshot],
) -> PlayerCareerProfile:
    """Insert or update a PlayerCareerProfile from a sequence of role quality snapshots.

    This is an *incremental* upsert: it reads the existing row (if any), then adds
    the new snapshot data. Callers should pass only snapshots since the last update
    to avoid double-counting.

    Parameters
    ----------
    session : Session
    steam_id : int
    display_name : str
        Most recent display name from MatchPlayer
    snapshot_rows : Sequence[PlayerRoleQualitySnapshot]
        Role quality snapshot rows for this player since last career profile update.
        Pass an empty list to load existing row without adding new data.

    Returns
    -------
    PlayerCareerProfile
        The upserted row
    """
    import datetime as dt

    # Fetch existing row or create new one
    existing = session.query(PlayerCareerProfile).filter_by(steam_id=steam_id).first()

    if existing:
        pcp = existing
        pcp.display_name = display_name
        n_existing_matches = pcp.matches_played
        existing_per_map = dict(existing.per_map_stats or {})
        existing_recent = dict(existing.recent_form or {})
        existing_peaks = dict(existing.peak_ratings or {})
    else:
        pcp = PlayerCareerProfile(steam_id=steam_id, display_name=display_name)
        session.add(pcp)
        # Initialize all integer counters to 0 (defaults only apply at INSERT time)
        pcp.matches_played = 0
        pcp.rounds_played = 0
        pcp.rounds_won = 0
        pcp.maps_played = 0
        pcp.total_kills = 0
        pcp.total_deaths = 0
        pcp.total_assists = 0
        pcp.headshot_kills = 0
        pcp.role_entry_rounds = 0
        pcp.role_awper_rounds = 0
        pcp.role_support_rounds = 0
        pcp.role_rifler_rounds = 0
        pcp.role_lurker_rounds = 0
        pcp.role_igl_rounds = 0
        pcp.role_secondary_rounds = 0
        pcp.total_entry_attempts = 0
        pcp.total_successful_entries = 0
        pcp.total_flash_pop_kills = 0
        pcp.total_opening_duel_wins = 0
        pcp.entry_survived_post_entry = 0
        pcp.total_awp_rounds = 0
        pcp.total_first_pick_rounds = 0
        pcp.ct_hold_picks_total = 0
        pcp.ct_survived_after_pick_total = 0
        pcp.total_support_rounds = 0
        pcp.total_trade_opportunities = 0
        pcp.total_successful_trades = 0
        pcp.total_flash_assisted_kills = 0
        pcp.utility_rounds_total = 0
        pcp.economy_sacrifice_rounds = 0
        pcp.total_rifler_rounds = 0
        pcp.total_multi_kill_rounds = 0
        pcp.rifler_trade_kills_total = 0
        pcp.ct_anchor_rounds_total = 0
        pcp.ct_survived_anchor_total = 0
        pcp.total_lurk_attempts = 0
        pcp.total_solo_kills = 0
        pcp.total_rotation_cut_kills = 0
        pcp.survived_lurk_rounds_total = 0
        pcp.clutch_rounds_total = 0
        pcp.clutch_rounds_won_total = 0
        pcp.eco_rounds_total = 0
        pcp.force_rounds_total = 0
        pcp.full_buy_rounds_total = 0
        pcp.total_flashes_thrown = 0
        pcp.total_smokes_thrown = 0
        pcp.total_he_detonations = 0
        pcp.total_molly_detonations = 0
        pcp.total_enemies_flashed = 0
        pcp.total_utility_damage = 0
        n_existing_matches = 0
        existing_per_map = {}
        existing_recent = {}
        existing_peaks = {}

    # ── Accumulate raw counters ────────────────────────────────────────────
    n_new = len(snapshot_rows)
    new_matches = 0
    new_rounds = 0

    entry_scores: list[float] = []
    awp_scores: list[float] = []
    support_scores: list[float] = []
    rifler_scores: list[float] = []
    lurker_scores: list[float] = []

    for row in snapshot_rows:
        # Track new matches/rounds (one increment per distinct match_id)
        new_matches += 1
        new_rounds += 1  # one snapshot per match-side, approximates 1 round

        # Role distribution — write directly to pcp columns
        br = row.broad_role or "unknown"
        if br == "entry":
            pcp.role_entry_rounds += 1
        elif br == "awper":
            pcp.role_awper_rounds += 1
        elif br == "support":
            pcp.role_support_rounds += 1
        elif br == "rifler":
            pcp.role_rifler_rounds += 1
        elif br == "lurker":
            pcp.role_lurker_rounds += 1
        elif br == "igl":
            pcp.role_igl_rounds += 1
        else:
            pcp.role_secondary_rounds += 1

        # Entry fragger
        if row.entry_quality_score is not None:
            pcp.total_entry_attempts += row.entry_attempts
            pcp.total_successful_entries += row.successful_entries
            pcp.total_flash_pop_kills += row.flash_pop_kills
            pcp.total_opening_duel_wins += row.opening_duel_wins
            pcp.entry_survived_post_entry += row.rounds_survived_post_entry
            entry_scores.append(row.entry_quality_score)

        # AWP
        if row.awp_quality_score is not None:
            pcp.total_awp_rounds += row.awp_rounds
            pcp.total_first_pick_rounds += row.first_pick_rounds
            pcp.ct_hold_picks_total += row.ct_hold_picks
            pcp.ct_survived_after_pick_total += row.ct_survived_after_pick
            awp_scores.append(row.awp_quality_score)

        # Support
        if row.support_quality_score is not None:
            pcp.total_support_rounds += row.support_rounds
            pcp.total_trade_opportunities += row.trade_opportunities
            pcp.total_successful_trades += row.successful_trades
            pcp.total_flash_assisted_kills += row.flash_assisted_kills
            pcp.utility_rounds_total += row.utility_rounds
            pcp.economy_sacrifice_rounds += row.economy_sacrifice_rounds
            support_scores.append(row.support_quality_score)

        # Rifler
        if row.rifler_quality_score is not None:
            pcp.total_rifler_rounds += row.rifler_rounds
            pcp.total_multi_kill_rounds += row.multi_kill_rounds
            pcp.rifler_trade_kills_total += row.rifler_trade_kills
            pcp.ct_anchor_rounds_total += row.ct_site_anchor_rounds
            pcp.ct_survived_anchor_total += row.ct_survived_anchor
            rifler_scores.append(row.rifler_quality_score)

        # Lurker
        if row.lurker_quality_score is not None:
            pcp.total_lurk_attempts += row.lurk_attempts
            pcp.total_solo_kills += row.solo_kills
            pcp.total_rotation_cut_kills += row.rotation_cut_kills
            pcp.survived_lurk_rounds_total += row.survived_lurk_rounds
            pcp.clutch_rounds_total += row.clutch_rounds
            pcp.clutch_rounds_won_total += row.clutch_rounds_won
            lurker_scores.append(row.lurker_quality_score)

        # Per-map aggregation
        map_name = row.map_name or "unknown"
        if map_name not in existing_per_map:
            existing_per_map[map_name] = {
                "kills": 0, "deaths": 0, "rounds": 0, "wins": 0,
                "entry_attempts": 0, "successful_entries": 0,
            }
        m = existing_per_map[map_name]
        m["rounds"] += 1
        m["kills"] += 0  # snapshot doesn't have kills — caller should enrich separately
        # Enrich entry stats per map from snapshot
        if row.entry_quality_score is not None:
            m["entry_attempts"] += row.entry_attempts
            m["successful_entries"] += row.successful_entries

    # ── Update cumulative counters ──────────────────────────────────────────
    pcp.matches_played += new_matches
    pcp.rounds_played += new_rounds
    # rounds_won: caller should separately update; default to rounds_played as placeholder

    # ── Compute rate fields ─────────────────────────────────────────────────
    # Entry fragger
    pcp.entry_kill_rate = _rate(pcp.total_successful_entries, pcp.total_entry_attempts)
    pcp.flash_pop_rate = _rate(pcp.total_flash_pop_kills, pcp.total_entry_attempts)
    pcp.opening_duel_win_rate = _rate(pcp.total_opening_duel_wins, pcp.total_entry_attempts)
    pcp.entry_survival_rate = _rate(pcp.entry_survived_post_entry, pcp.total_entry_attempts)

    # AWP
    pcp.opening_pick_rate = _rate(pcp.total_first_pick_rounds, pcp.total_awp_rounds)
    pcp.ct_survival_after_pick_rate = _rate(pcp.ct_survived_after_pick_total, pcp.ct_hold_picks_total)

    # Support
    pcp.trade_success_rate = _rate(pcp.total_successful_trades, pcp.total_trade_opportunities)

    # Rifler
    pcp.multi_kill_rate = _rate(pcp.total_multi_kill_rounds, pcp.total_rifler_rounds)
    pcp.ct_anchor_survival_rate = _rate(pcp.ct_survived_anchor_total, pcp.ct_anchor_rounds_total)
    pcp.rifler_trade_rate = _rate(pcp.rifler_trade_kills_total, pcp.total_rifler_rounds)

    # Lurker
    pcp.solo_kill_rate = _rate(pcp.total_solo_kills, pcp.total_lurk_attempts)
    pcp.lurk_survival_rate = _rate(pcp.survived_lurk_rounds_total, pcp.total_lurk_attempts)
    pcp.clutch_win_rate = _rate(pcp.clutch_rounds_won_total, pcp.clutch_rounds_total)

    # Core K/D (snapshot doesn't carry kills/deaths — caller must enrich from Kill rows)
    pcp.kd_ratio = _rate(pcp.total_kills, pcp.total_deaths)
    pcp.headshot_rate = _rate(pcp.headshot_kills, pcp.total_kills) if pcp.total_kills else None
    pcp.win_rate = _rate(pcp.rounds_won, pcp.rounds_played) if pcp.rounds_played else None

    # Role quality averages
    pcp.entry_quality_avg = _avg(entry_scores)
    pcp.awp_quality_avg = _avg(awp_scores)
    pcp.support_quality_avg = _avg(support_scores)
    pcp.rifler_quality_avg = _avg(rifler_scores)
    pcp.lurker_quality_avg = _avg(lurker_scores)

    # ── Movement averages from PlayerRoundMovementSummary ────────────────────
    mov_rows = (
        session.query(PlayerRoundMovementSummary)
        .filter_by(steam_id=steam_id)
        .all()
    )
    if mov_rows:
        n_mov = len(mov_rows)
        pcp.avg_distance_per_round = _avg([r.total_distance for r in mov_rows])
        pcp.avg_speed_per_round = _avg([r.avg_speed for r in mov_rows])
        pcp.avg_zone_transitions_per_round = _avg(
            [r.zone_transition_count for r in mov_rows]
        )

    # ── JSON breakdowns ─────────────────────────────────────────────────────
    pcp.per_map_stats = existing_per_map if existing_per_map else None
    pcp.recent_form = existing_recent if existing_recent else None
    pcp.peak_ratings = existing_peaks if existing_peaks else None

    # ── Temporal fields ─────────────────────────────────────────────────────
    now = dt.datetime.now(dt.timezone.utc)
    if pcp.first_seen_at is None:
        pcp.first_seen_at = now
    pcp.last_updated = now
    if pcp.created_at is None:
        pcp.created_at = now

    session.flush()
    return pcp
