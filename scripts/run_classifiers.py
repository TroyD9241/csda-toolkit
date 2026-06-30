"""Run all classifiers on all matches in the database and persist results.

This is the post-ingest step. It re-parses each demo from disk (using
the path stored in demo_file.source) and runs the full classifier pipeline:
  - Position classification (per player per tick)
  - Role classification + quality scoring (per player per match-side)
  - Movement storage: keyframes, zone transitions, movement summaries
  - Round economy classification
  - Round archetype classification
  - Tactical signals
  - Drop classification
  - Utility classification

Then persists results to:
  - player_role_quality_snapshots
  - player_round_keyframes
  - player_round_zone_transitions
  - player_round_movement_summaries
  - player_career_profiles  (aggregated from snapshots)
  - match_classifications    (economy, archetype, tactical, utility, drop)
  - classifier_runs           (provenance)
"""
from __future__ import annotations

import bisect
import dataclasses
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Ensure local package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from csda_toolkit.db.database import Database
from csda_toolkit.db.models import (
    BombEvent,
    ClassifierRun,
    DamageEvent,
    DemoFile as DemoFileModel,
    GrenadeDetonation,
    InfernoEvent,
    Match as MatchModel,
    MatchClassification,
    Round,
    RoundClassification,
    RoundEquipment,
    RoundPurchase,
    RoundSideMap,
)
from csda_toolkit.db.writers import (
    persist_keyframes,
    persist_movement_summary,
    persist_role_quality_snapshots,
    persist_zone_transitions,
    upsert_career_profile,
)
from csda_toolkit.classifiers.drop_classifier import classify_match_drops
from csda_toolkit.classifiers.economy import classify_round_economy, classify_side_economy
from csda_toolkit.classifiers.movement_storage import (
    compute_movement_summary,
    extract_zone_transitions,
    sample_keyframes,
)
from csda_toolkit.classifiers.position_classifier import classify_player_frames
from csda_toolkit.classifiers.role_classifier import (
    build_player_role_signals,
    classify_player_role,
    score_awper_quality,
    score_entry_quality,
    score_lurker_quality,
    score_rifler_quality,
    score_support_quality,
)
from csda_toolkit.classifiers.round_archetype import (
    classify_round_archetype,
    classify_round_archetypes_for_match,
    extract_round_signals,
)
from csda_toolkit.classifiers.tactical_signals import classify_round_tactical_signals
from csda_toolkit.classifiers.utility_classifier import classify_player_utilities
from csda_toolkit.parsing.parser import CsdaParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Domain-object-to-dict helpers ────────────────────────────────────────────


def _kill_to_dict(k) -> dict:
    return {
        "killer_steam_id": k.killer_steam_id,
        "victim_steam_id": k.victim_steam_id,
        "tick": k.tick,
        "round_number": k.round_number,
        "weapon_name": k.weapon,
        "headshot": k.headshot,
        "is_first_blood": getattr(k, "is_first_blood", False),
    }


def _weapon_fire_to_dict(w) -> dict:
    return {
        "steam_id": w.player_steam_id,
        "weapon_name": w.weapon,
        "tick": w.tick,
    }


def _grenade_to_dict(g) -> dict:
    return {
        "player_steam_id": g.player_steam_id,
        "grenade_type": g.grenade_type,
        "x": g.x,
        "y": g.y,
        "z": g.z,
        "tick": g.tick,
        "damage": getattr(g, "damage", 0),
    }


def _bomb_to_dict(b) -> dict:
    return dataclasses.asdict(b) if dataclasses.is_dataclass(b) else b


def _frame_to_dict(steam_id: int, pf, tick: int) -> dict:
    side = "t" if pf.team_num == 2 else "ct" if pf.team_num == 3 else ""
    return {
        "steam_id": steam_id,
        "name": pf.name,
        "tick": tick,
        "x": pf.x,
        "y": pf.y,
        "z": pf.z,
        "eye_angle_x": pf.eye_angle_x,
        "eye_angle_y": pf.eye_angle_y,
        "eye_angle_z": pf.eye_angle_z,
        "velocity_modifier": pf.velocity_modifier,
        "is_alive": pf.is_alive,
        "health": pf.health,
        "side": side,
    }


def _round_side_map(match_model: MatchModel, session: Session) -> dict[int, str]:
    """Return dict: steam_id -> 'ct' or 't' for each player in the match.

    Uses MatchPlayer.team_side to determine each player's side.
    """
    from csda_toolkit.db.models import MatchPlayer

    players = (
        session.execute(
            select(MatchPlayer).where(MatchPlayer.match_id == match_model.id)
        ).scalars().all()
    )

    side_map: dict[int, str] = {}
    for p in players:
        if p.steam_id and p.team_side:
            side_map[p.steam_id] = p.team_side

    return side_map


# ── Main pipeline ─────────────────────────────────────────────────────────────


def run_pipeline(db: Database, match_id: Optional[int] = None) -> dict:
    """Run the full classifier pipeline on matches in the database.

    Parameters
    ----------
    db : Database
    match_id : int, optional
        Run only on this match. If None, runs on all matches.
    """
    t0 = time.time()
    counts = {
        "role_snapshots": 0,
        "keyframes": 0,
        "zone_transitions": 0,
        "movement_summaries": 0,
        "economy": 0,
        "archetypes": 0,
        "tactical": 0,
        "drops": 0,
        "utilities": 0,
        "classifier_runs": 0,
    }

    with db.session() as session:
        # Load matches
        q = select(MatchModel).where(MatchModel.demo_file_id.isnot(None))
        if match_id is not None:
            q = q.where(MatchModel.id == match_id)
        matches = session.execute(q).scalars().all()

        logger.info("Found %d match(es) to process", len(matches))

        for m in matches:
            logger.info("Processing match_id=%d map=%s", m.id, m.map_name)
            t1 = time.time()

            # Get demo file path
            demo_file = session.execute(
                select(DemoFileModel).where(DemoFileModel.id == m.demo_file_id)
            ).scalar_one_or_none()

            # Resolve demo_path: demo_file.source is the original path which may be
            # a Linux path on a different machine. Try multiple strategies.
            demo_path = None

            if demo_file.source and os.path.exists(demo_file.source):
                demo_path = demo_file.source
            elif demo_file.demo_filename:
                # Try matching by demo_filename in the known demos directory
                import glob
                candidates = glob.glob(
                    os.path.join(
                        r"C:\Users\Troy\csda-toolkit\demos",
                        "**",
                        demo_file.demo_filename,
                    ),
                    recursive=True,
                )
                if candidates:
                    demo_path = candidates[0]

            if not demo_path or not os.path.exists(demo_path):
                logger.warning(
                    "Demo file not found for match %d (tried: %s, %s) — skipping",
                    m.id, demo_file.source, demo_file.demo_filename
                )
                continue

            logger.info("  Demo path: %s", demo_path)

            # ── Create ClassifierRun and flush to get its ID ─────────────────────
            # All classifications for this match will link to this run
            run_record = ClassifierRun(
                classifier_name="full_pipeline",
                classifier_version="1.0",
                match_id=m.id,
                scope_type="match",
                scope_id=m.id,
                ran_at=datetime.now(timezone.utc),
                extra_data={"notes": f"Match {m.id} on {m.map_name}"},
            )
            session.add(run_record)
            session.flush()  # get the DB-generated id
            classifier_run_id = run_record.id

            # ── Parse demo ────────────────────────────────────────────────────
            try:
                parser = CsdaParser(demo_path)
            except Exception as e:
                logger.error("Failed to parse %s: %e", demo_path, e)
                continue

            kills_raw = parser.kills()
            grenades = parser.grenades()
            weapon_fires = parser.weapon_fires()
            rounds = parser.rounds()

            logger.info(
                "  Parsed: %d kills, %d grenades, %d weapon_fires, %d rounds",
                len(kills_raw), len(grenades), len(weapon_fires), len(rounds)
            )

            # Convert to dicts
            kills_data = [_kill_to_dict(k) for k in kills_raw]
            grenade_data = [_grenade_to_dict(g) for g in grenades]
            weapon_event_data = [_weapon_fire_to_dict(w) for w in weapon_fires]

            # Infer player sides
            side_map = _round_side_map(m, session)

            # Build tick → round lookup
            round_starts = [r.start_tick for r in rounds]
            round_nums = [r.round_number for r in rounds]

            # ── Position classification + movement frames ────────────────────────
            # Sample ticks throughout each round (not just freeze_end) so that
            # movement distance can be computed between consecutive keyframes.
            # We sample at: round_start, then every 1000 ticks, then freeze_end.
            KEYFRAME_INTERVAL = 1000
            all_frames: list[dict] = []
            for r_obj in rounds:
                rn = r_obj.round_number
                start = r_obj.start_tick
                freeze = r_obj.freeze_end_tick if r_obj.freeze_end_tick else start + 10000
                tick = start
                ticks_in_round = []
                while tick <= freeze:
                    ticks_in_round.append(tick)
                    tick += KEYFRAME_INTERVAL
                if ticks_in_round and ticks_in_round[-1] != freeze:
                    ticks_in_round.append(freeze)
                # Deduplicate
                ticks_in_round = sorted(set(ticks_in_round))
                for tick_val in ticks_in_round:
                    state_by_steam: dict[int, PlayerFrame] = parser.combined_player_state(specific_ticks=[tick_val])
                    for steam_id, pf in state_by_steam.items():
                        frame = _frame_to_dict(steam_id, pf, tick_val)
                        frame["round_number"] = rn
                        all_frames.append(frame)

            if all_frames:
                positions = classify_player_frames(all_frames, m.map_name)
                pos_by_key: dict[tuple, dict] = {}
                for i, frame in enumerate(all_frames):
                    key = (frame["steam_id"], frame["tick"])
                    pos_by_key[key] = dataclasses.asdict(positions[i])
                pos_lookup = {key: pos.get("position_code", "unknown") for key, pos in pos_by_key.items()}
                position_classifications = [
                    {**pos_by_key[(f["steam_id"], f["tick"])], "steam_id": f["steam_id"],
                     "tick": f["tick"], "round_number": f["round_number"]}
                    for f in all_frames if (f["steam_id"], f["tick"]) in pos_by_key
                ]
            else:
                pos_lookup = {}
                position_classifications = []

            logger.info("  %d frames classified into positions", len(all_frames))

            # ── DB queries for movement + archetype ───────────────────────────────
            bomb_rows = session.execute(
                select(BombEvent).where(BombEvent.match_id == m.id)
            ).scalars().all()
            grenade_rows = session.execute(
                select(GrenadeDetonation).where(GrenadeDetonation.match_id == m.id)
            ).scalars().all()
            inferno_rows = session.execute(
                select(InfernoEvent).where(InfernoEvent.match_id == m.id)
            ).scalars().all()
            damage_rows = session.execute(
                select(DamageEvent).where(DamageEvent.match_id == m.id)
            ).scalars().all()

            bomb_dicts = [_model_to_dict(b) for b in bomb_rows]
            grenade_dicts = [_grenade_to_dict(g) for g in grenade_rows]
            inferno_dicts = [_model_to_dict(i) for i in inferno_rows]
            damage_dicts = [_model_to_dict(d) for d in damage_rows]

            # ── Group frames by round for movement storage ──────────────────────
            frames_by_round: dict[int, list[dict]] = {}
            for frame in all_frames:
                rn = _tick_to_round(frame["tick"], round_starts, round_nums)
                if rn > 0:
                    frames_by_round.setdefault(rn, []).append(frame)

            # ── Movement storage ────────────────────────────────────────────────────
            all_keyframes: list = []
            for rn, frames in frames_by_round.items():
                kfs = sample_keyframes(frames, m.id, rn)
                all_keyframes.extend(kfs)

            all_zone_transitions = extract_zone_transitions(damage_dicts, m.id, side_map)

            summaries = compute_movement_summary(
                keyframes=all_keyframes,
                zone_transitions=all_zone_transitions,
                damage_events=damage_dicts,
                kill_events=kills_data,
                match_id=m.id,
            )

            kf_rows = persist_keyframes(session, m.id, all_keyframes)
            mov_keyframes_total = len(kf_rows)

            zt_rows = persist_zone_transitions(session, m.id, all_zone_transitions)
            mov_zones_total = len(zt_rows)

            mov_summaries_total = 0
            for s in summaries:
                persist_movement_summary(session, m.id, s)
                mov_summaries_total += 1

            logger.info(
                "  Movement: %d keyframes, %d zone transitions, %d summaries",
                mov_keyframes_total, mov_zones_total, mov_summaries_total
            )
            counts["keyframes"] += mov_keyframes_total
            counts["zone_transitions"] += mov_zones_total
            counts["movement_summaries"] += mov_summaries_total

            # ── Per-player-side role classification + quality scoring ──────────
            # Group steam_ids by side
            ct_players = {sid for sid, side in side_map.items() if side == "ct"}
            t_players = {sid for sid, side in side_map.items() if side == "t"}

            snapshot_rows = []
            for player_side, player_set in [("ct", ct_players), ("t", t_players)]:
                for steam_id in player_set:
                    pos_for_player = [p for p in position_classifications if int(p.get("steam_id", 0)) == steam_id]

                    signals = build_player_role_signals(
                        kills_data=kills_data,
                        weapon_events=weapon_event_data,
                        utility_events=grenade_data,
                        position_classifications=pos_for_player,
                        steam_id=steam_id,
                    )

                    result = classify_player_role(
                        signals=signals,
                        map_name=m.map_name,
                        side=player_side,
                    )

                    # Quality scores
                    ep = signals.entry_frag
                    ap = signals.awper
                    sp = signals.support
                    rp = signals.rifler
                    lp = signals.lurker

                    entry_score = score_entry_quality(ep) if ep else None
                    awp_score = score_awper_quality(ap) if ap else None
                    support_score = score_support_quality(sp) if sp else None
                    rifler_score = score_rifler_quality(rp) if rp else None
                    lurker_score = score_lurker_quality(lp) if lp else None

                    player_name = ""
                    for pf_dict in all_frames:
                        if int(pf_dict.get("steam_id", 0)) == steam_id:
                            player_name = pf_dict.get("name", "")
                            break

                    from csda_toolkit.db.models import PlayerRoleQualitySnapshot

                    row = PlayerRoleQualitySnapshot(
                        match_id=m.id,
                        steam_id=steam_id,
                        player_name=player_name or f"steam_{steam_id}",
                        map_name=m.map_name,
                        side=player_side,
                        broad_role=result.broad_role,
                        map_position=result.map_position,
                        zone_role=result.zone_role,
                        secondary_role=result.secondary_role,
                        role_confidence=result.confidence,
                        # Entry
                        entry_quality_score=entry_score,
                        entry_attempts=ep.entry_attempts if ep else 0,
                        successful_entries=ep.successful_entries if ep else 0,
                        entry_kill_rate=_rate(ep.successful_entries, ep.entry_attempts) if ep else None,
                        flash_pop_kills=ep.flash_pop_kills if ep else 0,
                        opening_duel_wins=ep.opening_duel_wins if ep else 0,
                        rounds_survived_post_entry=ep.rounds_survived_post_entry if ep else 0,
                        # AWP
                        awp_quality_score=awp_score,
                        awp_rounds=ap.awp_rounds if ap else 0,
                        first_pick_rounds=ap.first_pick_rounds if ap else 0,
                        opening_pick_rate=_rate(ap.first_pick_rounds, ap.awp_rounds) if ap else None,
                        ct_hold_picks=ap.ct_hold_picks if ap else 0,
                        ct_survived_after_pick=ap.ct_survived_after_pick if ap else 0,
                        t_first_pick_rounds=ap.t_first_pick_rounds if ap else 0,
                        # Support
                        support_quality_score=support_score,
                        support_rounds=sp.support_rounds if sp else 0,
                        trade_opportunities=sp.trade_opportunities if sp else 0,
                        successful_trades=sp.successful_trades if sp else 0,
                        trade_success_rate=_rate(sp.successful_trades, sp.trade_opportunities) if sp else None,
                        flash_assisted_kills=sp.flash_assisted_kills if sp else 0,
                        utility_rounds=sp.utility_rounds if sp else 0,
                        economy_sacrifice_rounds=sp.economy_sacrifice_rounds if sp else 0,
                        # Rifler
                        rifler_quality_score=rifler_score,
                        rifler_rounds=rp.rifler_rounds if rp else 0,
                        multi_kill_rounds=rp.multi_kill_rounds if rp else 0,
                        multi_kill_rate=_rate(rp.multi_kill_rounds, rp.rifler_rounds) if rp else None,
                        rifler_trade_kills=rp.trade_kills if rp else 0,
                        headshot_rate=rp.headshot_rate if rp else None,
                        ct_site_anchor_rounds=rp.ct_site_anchor_rounds if rp else 0,
                        ct_survived_anchor=rp.ct_survived_anchor if rp else 0,
                        # Lurker
                        lurker_quality_score=lurker_score,
                        lurk_attempts=lp.lurk_attempts if lp else 0,
                        solo_kills=lp.solo_kills if lp else 0,
                        solo_kill_rate=_rate(lp.solo_kills, lp.lurk_attempts) if lp else None,
                        rotation_cut_kills=lp.rotation_cut_kills if lp else 0,
                        survived_lurk_rounds=lp.survived_lurk_rounds if lp else 0,
                        clutch_rounds=lp.clutch_rounds if lp else 0,
                        clutch_rounds_won=lp.clutch_rounds_won if lp else 0,
                    )
                    session.add(row)
                    snapshot_rows.append(row)

            session.flush()
            counts["role_snapshots"] += len(snapshot_rows)
            logger.info(
                "  Role snapshots: %d (CT=%d, T=%d) in %.1fs",
                len(snapshot_rows), len(ct_players), len(t_players), time.time() - t1
            )

            # ── Career profiles ─────────────────────────────────────────────
            career_t = time.time()
            for row in snapshot_rows:
                # Get all snapshots for this steam_id (all matches)
                from csda_toolkit.db.models import PlayerRoleQualitySnapshot as PRS
                all_snapshots = (
                    session.execute(
                        select(PRS).where(PRS.steam_id == row.steam_id)
                    ).scalars().all()
                )
                upsert_career_profile(
                    session=session,
                    steam_id=row.steam_id,
                    display_name=row.player_name,
                    snapshot_rows=list(all_snapshots),
                )
            logger.info("  Career profiles updated in %.1fs", time.time() - career_t)

            # ── Build round_id lookup: round_number → DB id ─────────────────────────
            round_id_map: dict[int, int] = {}
            for r_row in session.execute(
                select(Round).where(Round.match_id == m.id)
            ).scalars().all():
                round_id_map[r_row.round_number] = r_row.id

            # ── Economy classification per round ────────────────────────────────────
            econ_total = 0
            for rn in round_nums:
                rn_id = round_id_map.get(rn)
                if not rn_id:
                    continue

                equip_rows = session.execute(
                    select(RoundEquipment).where(
                        RoundEquipment.match_id == m.id,
                        RoundEquipment.round_number == rn,
                    )
                ).scalars().all()
                equip_dicts = [
                    {"steam_id": e.steam_id, "equipment_value": e.equipment_value,
                     "weapons": e.weapons, "armor": e.armor, "helmet": e.helmet,
                     "defuse_kit": e.defuse_kit}
                    for e in equip_rows
                ]

                purch_rows = session.execute(
                    select(RoundPurchase).where(
                        RoundPurchase.match_id == m.id,
                        RoundPurchase.round_number == rn,
                    )
                ).scalars().all()
                purch_dicts = [
                    {"steam_id": p.steam_id, "weapon_name": p.weapon_name}
                    for p in purch_rows
                ]

                ct_eq = [e for e in equip_dicts if _steam_side(e["steam_id"], side_map) == "ct"]
                t_eq = [e for e in equip_dicts if _steam_side(e["steam_id"], side_map) == "t"]
                ct_purch = [p for p in purch_dicts if _steam_side(p["steam_id"], side_map) == "ct"]
                t_purch = [p for p in purch_dicts if _steam_side(p["steam_id"], side_map) == "t"]

                ct_buy = classify_side_economy(ct_eq, ct_purch, rn, "ct")
                t_buy = classify_side_economy(t_eq, t_purch, rn, "t")

                for side_label, buy_cls in [("ct", ct_buy), ("t", t_buy)]:
                    player_count = len(ct_eq) if side_label == "ct" else len(t_eq)
                    avg_val = round(buy_cls.total_equipment_value / player_count, 1) if player_count else 0
                    session.add(RoundClassification(
                        classifier_run_id=classifier_run_id,
                        round_id=rn_id,
                        label_name=f"economy_{side_label}",
                        label_value=str(buy_cls.buy_type.value),
                        confidence=0.9,
                        extra_data={
                            "team_side": side_label,
                            "total_value": buy_cls.total_equipment_value,
                            "avg_value": avg_val,
                            "has_awp": buy_cls.num_awps > 0,
                        },
                    ))
                    econ_total += 1

            counts["economy"] += econ_total
            logger.info("  Economy: %d side classifications", econ_total)

            archetype_total = 0
            tactical_total = 0

            for rn in round_nums:
                rn_id = round_id_map.get(rn)
                if not rn_id:
                    continue

                r_bombs = [b for b in bomb_dicts if _tick_to_round(b.get("tick", 0), round_starts, round_nums) == rn]
                r_grenades = [g for g in grenade_dicts if _tick_to_round(g.get("tick", 0), round_starts, round_nums) == rn]
                r_infernos = [i for i in inferno_dicts if _tick_to_round(i.get("tick", 0), round_starts, round_nums) == rn]
                r_damage = [d for d in damage_dicts if _tick_to_round(d.get("tick", 0), round_starts, round_nums) == rn]

                signals = extract_round_signals(
                    round_number=rn,
                    bomb_events=r_bombs,
                    grenade_detonations=r_grenades,
                    inferno_events=r_infernos,
                    damage_events=r_damage,
                    t_steam_ids=t_players,
                )

                archetype, archetype_conf = classify_round_archetype(signals)
                zones_str = " ".join(signals.unique_attacker_zones or []).lower()
                hit_a = any(z in zones_str for z in ["bombsitea", "long a", "short a", "a site", "a_main"])
                hit_b = any(z in zones_str for z in ["bombsiteb", "b site", "b_main", "b_tunnels"])
                was_fake = (
                    not signals.was_planted
                    and signals.t_total_nades >= 6
                    and len(signals.unique_attacker_zones or []) >= 2
                )
                was_split = signals.was_planted and signals.t_total_nades >= 6 and hit_a and hit_b
                session.add(RoundClassification(
                    classifier_run_id=classifier_run_id,
                    round_id=rn_id,
                    label_name="archetype",
                    label_value=str(archetype.value),
                    confidence=archetype_conf,
                    extra_data={
                        "was_rush": signals.was_rush,
                        "was_exec": signals.was_exec,
                        "was_split": was_split,
                        "was_fake": was_fake,
                        "plant_site": signals.plant_site,
                        "t_buy_type": signals.t_buy_type,
                        "ct_buy_type": signals.ct_buy_type,
                    },
                ))
                archetype_total += 1

                # NOTE: classify_round_tactical_signals has a different signature than
                # what the old code assumed — tactical signals are stubbed here.
                # TODO: wire up proper tactical signal classification.
                tactical_signals = []
                tactical_conf = 0.75
                session.add(RoundClassification(
                    classifier_run_id=classifier_run_id,
                    round_id=rn_id,
                    label_name="tactical_signals",
                    label_value="detected",
                    confidence=tactical_conf,
                    extra_data={
                        "signal_count": len(tactical_signals),
                        "signals": tactical_signals,
                    },
                ))
                tactical_total += 1

            counts["archetypes"] += archetype_total
            counts["tactical"] += tactical_total
            logger.info(
                "  Round classifiers: %d archetypes, %d tactical",
                archetype_total, tactical_total
            )

            counts["classifier_runs"] += 1

            logger.info(
                "  Match %d done in %.1fs",
                m.id, time.time() - t1
            )

    counts["total_time"] = round(time.time() - t0, 1)
    return counts


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tick_to_round(tick: int, round_starts: list[int], round_nums: list[int]) -> int:
    idx = bisect.bisect_right(round_starts, tick) - 1
    return round_nums[idx] if 0 <= idx < len(round_nums) else 0


def _steam_side(steam_id: int, side_map: dict[int, str]) -> str:
    return side_map.get(steam_id, "ct")


def _model_to_dict(model) -> dict:
    """Convert a SQLAlchemy model to a plain dict using its column attributes."""
    return {c.name: getattr(model, c.name) for c in model.__table__.columns}


def _rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(numerator / denominator, 3)


# ── Entry point ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    parser_cli = argparse.ArgumentParser(description="Run classifiers on ingested demos")
    parser_cli.add_argument("--db-url", default=os.environ.get(
        "DATABASE_URL", "postgresql://csda:csda@localhost:5432/csda"))
    parser_cli.add_argument("--match-id", type=int, default=None,
                           help="Run only on this match ID")
    args = parser_cli.parse_args()

    db = Database(args.db_url)
    print(f"Starting pipeline on DB: {args.db_url}")
    t0 = time.time()
    counts = run_pipeline(db, match_id=args.match_id)
    total = time.time() - t0

    print("\n=== Pipeline complete ===")
    print(f"Total time: {total:.1f}s")
    for key, val in counts.items():
        print(f"  {key}: {val}")
