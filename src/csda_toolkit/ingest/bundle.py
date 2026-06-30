"""IngestBundle — maps raw demoparser output → domain models → DB records.

Orchestrates the full pipeline:
  1. Parse demo via DemoParser → domain objects
  2. Batch-insert into Postgres via SQLAlchemy
  3. Returns ingest summary
"""

import bisect
import logging
import math
import os
import re
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func, case, text
from sqlalchemy.orm import Session

from csda_toolkit.db.database import Database
from csda_toolkit.db.models import (
    DemoFile as DemoFileModel,
    EventSeries as EventSeriesModel,
    Match as MatchModel,
    Player as PlayerModel,
    MatchPlayer as MatchPlayerModel,
    Round as RoundModel,
    Kill as KillModel,
    RoundEquipment,
    RoundPurchase,
    RoundSideMap,
    Team as TeamModel,
    MatchTeam as MatchTeamModel,
    PlayerAlias,
    PlayerRoundWeapon,
    Weapon as WeaponModel,
    BombEvent as BombEventModel,
    DamageEvent as DamageEventModel,
    PlayerBlind as PlayerBlindModel,
    GrenadeDetonation as GrenadeDetonationModel,
    InfernoEvent as InfernoEventModel,
    PlayerRoundStats as PlayerRoundStatsModel,
    WeaponDrop as WeaponDropModel,
    WeaponFire as WeaponFireModel,
    PlayerBulletHit as PlayerBulletHitModel,
    PlayerSpawn as PlayerSpawnModel,
    PlayerJump as PlayerJumpModel,
    PlayerFootstep as PlayerFootstepModel,
    ChatMessage as ChatMessageModel,
    RoundMVP as RoundMVPModel,
    ItemEquip as ItemEquipModel,
    PlayerPing as PlayerPingModel,
    BuyTimeEvent as BuyTimeEventModel,
    GrenadeTrajectorySummary as GrenadeTrajectorySummaryModel,
)
from csda_toolkit.domain.models import (
    DemoFile as DemoFileDomain,
    Kill as KillDomain,
    Match as MatchDomain,
    MatchTeam as MatchTeamDomain,
    Player as PlayerDomain,
    Round as RoundDomain,
    PlayerEquipment,
    PurchaseEvent,
    SideAssignment,
    BombEvent,
    DamageEvent,
    PlayerBlind,
    GrenadeDetonation,
    InfernoEvent,
    GrenadeTrajectory,
)
from csda_toolkit.parsing.parser import CsdaParser
from csda_toolkit.parsing.constants import normalize_weapon_name, weapon_category, defindex_to_weapon, WEAPON_DEFINDEX_TO_NAME

# Maps item_name strings from item_purchase events to canonical weapon keys.
# Covers non-standard names that don't normalize cleanly through standard rules.
_ITEM_NAME_TO_WEAPON_KEY: dict[str, str] = {
    "Kevlar & Helmet": "kevlar_helmet",
    "Kevlar Vest": "kevlar",
    "Defuse Kit": "defuse_kit",
    "HE Grenade": "he_grenade",
    "High Explosive Grenade": "he_grenade",
    "Incendiary Grenade": "incendiary",
    "Tactical Awareness Grenade": "tag_grenade",
    "Smoke Grenade": "smoke_grenade",
    "Flashbang": "flashbang",
    "Decoy Grenade": "decoy",
    "Molotov": "molotov",
    "Zeus x27": "zeus_x27",
    "AWP": "awp",
    "AK-47": "ak_47",
    "M4A4": "m4a4",
    "M4A1-S": "m4a1_s",
    "Galil AR": "galil_ar",
    "FAMAS": "famas",
    "SG 553": "sg_553",
    "SSG 08": "ssg_08",
    "G3SG1": "g3sg1",
    "SCAR-20": "scar_20",
    "MP5-SD": "mp5_sd",
    "PP-Bizon": "pp_bizon",
    "UMP-45": "ump_45",
    "MAC-10": "mac_10",
    "MAG-7": "mag_7",
    "Sawed-Off": "sawed_off",
    "Roteador": "revolver",
    "Five-SeveN": "five_seven",
    "Tec-9": "tec_9",
    "Desert Eagle": "desert_eagle",
    "Dual Berettas": "dual_berettas",
    "Glock-18": "glock_18",
    "P2000": "hkp2000",
    "P250": "p250",
    "CZ75 Auto": "cz75_auto",
    "Tactical Suppressor": "taser",
    "C4 Explosive": "c4",
}


def _normalize_item_name(item_name: str) -> str:
    """Normalize an item_name from item_purchase event to a canonical weapon_key."""
    # Direct lookup first
    if item_name in _ITEM_NAME_TO_WEAPON_KEY:
        return _ITEM_NAME_TO_WEAPON_KEY[item_name]
    # Fall back to general normalization
    return normalize_weapon_name(item_name)

logger = logging.getLogger(__name__)


def _parse_series_from_demo_path(demo_path: str) -> tuple[str, str, str, int]:
    """Parse team names, series type, and map number from a demo filename.

    Filename patterns supported:

      Full event slug:
        {event_slug}-{team_a_slug}-vs-{team_b_slug}-bo{boN}[-{extra}]-m{map_number}[-{map_name}].dem
        Example: blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks-m1-mirage.dem
        → team_a="vitality", team_b="fut", series_type="bo3", map_number=1

      Short form (team-vs-team-m{map_number}[-{map_name}].dem):
        {team_a_slug}-vs-{team_b_slug}-m{map_number}[-{map_name}].dem
        Example: vitality-vs-fut-m1-mirage.dem
        → team_a="vitality", team_b="fut", series_type="bo3", map_number=1

    Heuristic for short form: map_name is known (mirage, dust2, nuke, inferno, overpass,
    anubis, vertigo). Everything BEFORE -m{map_number} is "teamA-vs-teamB".
    Split on "-vs-" to separate team slugs.

    Returns (team_a_slug, team_b_slug, series_type, map_number).
    """
    basename = os.path.basename(demo_path)
    name = os.path.splitext(basename)[0]

    # Default
    team_a = "unknown"
    team_b = "unknown"
    series_type = "bo3"
    map_number = 1

    # Known map names — used to detect where map portion begins in short filenames
    KNOWN_MAPS = {
        "mirage", "dust2", "d2", "nuke", "inferno", "overpass",
        "anubis", "vertigo", "ancient", "cache", "cobblestone", "tuscan",
    }

    # Extract map number: -m1-, -m2-, etc.
    m_map = re.search(r'-m(\d+)(?:-|$)', name)
    if m_map:
        try:
            map_number = int(m_map.group(1))
        except ValueError:
            pass

    # Extract series type: -bo1-, -bo3-, -bo5-, etc.
    m_bo = re.search(r'-bo(\d+)(?:-|$)', name)
    if m_bo:
        series_type = f"bo{m_bo.group(1)}"

    # Find "-vs-" separator
    m_vs = re.search(r'-vs-', name)
    if not m_vs:
        return team_a, team_b, series_type, map_number

    before_vs = name[:m_vs.start()]   # e.g. "vitality" or "blast-rivals-2026-season-1-vitality"
    after_vs = name[m_vs.end():]       # e.g. "fut-m1-mirage" or "fut-bo3-9RYfK-...-m1-mirage"

    # Extract team_b: first hyphen-separated token of after_vs
    # e.g. "fut-m1-mirage" → "fut"
    team_b = after_vs.split('-')[0]

    # For team_a: we need everything before "-vs-" minus any trailing event slug parts.
    # For full event slugs: "blast-rivals-2026-season-1-vitality" → "vitality"
    # For short form: "vitality" → "vitality"
    parts_before = before_vs.split('-')
    if len(parts_before) == 1:
        team_a = parts_before[0]
    else:
        # Multiple parts — last part is likely the team slug
        # (team slugs are typically the last 1-2 tokens before -vs-)
        # Heuristic: if the last part looks like a map name, take the second-to-last
        if parts_before[-1].lower() in KNOWN_MAPS or re.match(r'^m\d+$', parts_before[-1]):
            team_a = parts_before[-2] if len(parts_before) >= 2 else parts_before[-1]
        else:
            team_a = parts_before[-1]

    return team_a, team_b, series_type, map_number


class IngestResult:
    """Summary of an ingest operation."""

    def __init__(self, match_id: Optional[int] = None) -> None:
        self.match_id = match_id
        self.players_created: int = 0
        self.rounds_created: int = 0
        self.kills_created: int = 0
        self.teams_created: int = 0
        self.sides_created: int = 0
        self.weapons_created: int = 0
        self.equipment_created: int = 0
        self.errors: list[str] = []

    def __repr__(self) -> str:
        return (
            f"IngestResult(match_id={self.match_id}, "
            f"players={self.players_created}, rounds={self.rounds_created}, "
            f"kills={self.kills_created}, teams={self.teams_created}, "
            f"sides={self.sides_created}, weapons={self.weapons_created}, "
            f"equipment={self.equipment_created})"
        )


class IngestBundle:
    """Pipeline: parse demo → domain models → DB persistence."""

    def __init__(self, db: Database, demo_path: str):
        self.db = db
        self.demo_path = demo_path
        self._parser = CsdaParser(demo_path)

    def run(self) -> IngestResult:
        """Execute the full ingest pipeline.

        Idempotency: uses SHA256 of the demo file content to detect duplicates.
        If the hash already exists in demo_files, the ingest is skipped.
        Use force=True to bypass.
        """
        result = IngestResult()

        # 0. Idempotency check: compute file hash, check DB
        import hashlib
        with open(self.demo_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        existing_id = None
        with self.db.session() as session:
            existing = session.execute(
                select(DemoFileModel).where(
                    DemoFileModel.demo_checksum == file_hash
                )
            ).scalar_one_or_none()
            if existing and not getattr(self, "_force", False):
                existing_mid = existing.match.id if existing.match else 0
                logger.info(
                    "Demo already ingested: sha256=%s... (match_id=%d). Skipping. Use force=True to re-ingest.",
                    file_hash[:16], existing_mid,
                )
                result.match_id = existing_mid
                result.errors.append("skipped: duplicate sha256")
                return result
            existing_id = existing.match.id if existing and existing.match else None

        # Store the hash for use in _insert_demo_file
        self._file_hash = file_hash

        try:
            with self.db.session() as session:
                # 1. Parse match from demo
                match_domain = self._parser.parse_match()



                # 2. Resolve or create EventSeries for this matchup
                # Parse series info from demo filename: team names, bo type, map number
                team_a_slug, team_b_slug, series_type, map_number = _parse_series_from_demo_path(self.demo_path)

                # Create/find teams by slug name
                team_a_model = self._upsert_team_by_name(session, team_a_slug)
                team_b_model = self._upsert_team_by_name(session, team_b_slug)
                session.flush()

                # Find or create EventSeries for this (team_a, team_b, series_type) combo.
                # A matchup between the same two teams in the same format gets one series
                # covering all maps (bo3 = 3 maps, bo5 = 5 maps, etc.)
                series_model = self._find_or_create_series(
                    session,
                    event_id=1,  # Default event; HLTV adapter populates real event_id later
                    series_type=series_type,
                    team_a_id=team_a_model.id if team_a_model else None,
                    team_b_id=team_b_model.id if team_b_model else None,
                    team_a_name=team_a_slug,
                    team_b_name=team_b_slug,
                )
                session.flush()
                series_id = series_model.id

                # 3. Persist demo_file record
                demo_file_model = self._insert_demo_file(session, match_domain.demo_file)
                session.flush()

                # 4. Persist teams (create or resolve)
                team_map = {}  # team_slot -> TeamModel.id
                for team_domain in match_domain.teams:
                    team_model = self._upsert_team(session, team_domain)
                    session.flush()
                    team_map[team_domain.team_slot] = team_model.id
                    result.teams_created += 1

                # 5. Persist players (create or resolve by steam_id)
                player_map = {}  # steam_id -> PlayerModel.id
                for player_domain in match_domain.players:
                    player_model = self._upsert_player(session, player_domain)
                    session.flush()
                    player_map[player_domain.steam_id] = player_model.id
                    result.players_created += 1

                # 6. Persist match record
                match_model = MatchModel(
                    demo_file_id=demo_file_model.id if demo_file_model else None,
                    series_id=series_id,
                    map_number=map_number,
                    map_name=match_domain.map_name,
                    tick_rate=match_domain.tick_rate,
                    server_name=match_domain.server_name,
                    source=match_domain.source,
                    played_at=match_domain.played_at or datetime.utcnow(),
                )
                session.add(match_model)
                session.flush()
                result.match_id = match_model.id

                # 5b. Load weapons table into weapon_key → defindex lookup
                weapon_key_to_defindex: dict[str, int] = {}
                weapons_rows = session.execute(
                    select(WeaponModel.weapon_key, WeaponModel.defindex)
                ).all()
                for row in weapons_rows:
                    weapon_key_to_defindex[row.weapon_key] = row.defindex

                # 7. Link teams to match
                for team_slot, team_id in team_map.items():
                    match_team = MatchTeamModel(
                        match_id=match_model.id,
                        team_id=team_id,
                        team_slot=team_slot,
                        display_name=_get_team_name_for_slot(match_domain, team_slot),
                    )
                    session.add(match_team)

                # 8. Link players to match
                # Build steam_id → (match_player_index, match_player_id) lookup as we go
                steam_to_mp_idx: dict[int, int] = {}  # steam_id -> match_player_index
                steam_to_mp_id: dict[int, int] = {}   # steam_id -> match_player DB id
                for idx, player_domain in enumerate(match_domain.players):
                    player_id = player_map.get(player_domain.steam_id)
                    if player_id:
                        mp = MatchPlayerModel(
                            match_id=match_model.id,
                            match_player_index=idx,
                            player_id=player_id,
                            match_team_id=None,  # filled in step 6b after team inference
                            display_name=player_domain.name,
                            steam_id=player_domain.steam_id,
                        )
                        session.add(mp)
                        session.flush()  # get the DB id
                        steam_to_mp_idx[player_domain.steam_id] = idx
                        steam_to_mp_id[player_domain.steam_id] = mp.id
                        result.players_created += 1

                # 7b. Infer teams from events and update match_players + match_teams
                # IMPORTANT: players swap sides in overtimes, so we can ONLY use round 0
                # (first regulation round) to infer initial team rosters.
                # Strategy: for each player, use their FIRST event in round 0.
                # - If their first event is as a killer: their side = killer_team
                # - If their first event is as a victim: their side = OPPOSITE of killer's team
                # - If their first event is as an assister: their side = killer_team (same team as killer)
                # Fallback: if no round 0 event, try round 1. If still none, assign majority.
                player_first_side: dict[int, str] = {}  # steam_id -> "CT" or "TERRORIST"

                def _infer_from_round(target_round: int) -> None:
                    for kd in match_domain.kills:
                        if kd.round_number > target_round:
                            break
                        if kd.round_number != target_round:
                            continue
                        if kd.killer_steam_id and kd.killer_steam_id not in player_first_side:
                            player_first_side[kd.killer_steam_id] = kd.killer_team
                        if kd.victim_steam_id and kd.victim_steam_id not in player_first_side:
                            player_first_side[kd.victim_steam_id] = (
                                "CT" if kd.killer_team == "TERRORIST" else "TERRORIST"
                            )
                        if kd.assister_steam_id and kd.assister_steam_id not in player_first_side:
                            player_first_side[kd.assister_steam_id] = kd.killer_team

                _infer_from_round(0)
                # Fallback: try round 1 for any player still without a side
                all_steam_ids = {p.steam_id for p in match_domain.players if p.steam_id}
                missing = all_steam_ids - player_first_side.keys()
                if missing:
                    _infer_from_round(1)
                # Final fallback: assign majority side to any remaining players
                still_missing = all_steam_ids - player_first_side.keys()
                if still_missing and player_first_side:
                    ct_count = sum(1 for s in player_first_side.values() if s == "CT")
                    t_count = sum(1 for s in player_first_side.values() if s == "TERRORIST")
                    majority = "CT" if ct_count >= t_count else "TERRORIST"
                    for sid in still_missing:
                        player_first_side[sid] = majority
                        logger.debug(
                            "Player %d had no round 0/1 events; assigned majority side %s",
                            sid, majority,
                        )

                ct_steam_ids = {sid for sid, side in player_first_side.items() if side == "CT"}
                t_steam_ids = {sid for sid, side in player_first_side.items() if side == "TERRORIST"}

                # Create match_teams for inferred CT and T
                # Use generic names — HLTV adapter will override with org names later
                mt_ct = MatchTeamModel(
                    match_id=match_model.id,
                    team_slot=1,
                    display_name="Team CT",
                    starting_side="ct",
                )
                session.add(mt_ct)
                session.flush()
                mt_t = MatchTeamModel(
                    match_id=match_model.id,
                    team_slot=2,
                    display_name="Team T",
                    starting_side="t",
                )
                session.add(mt_t)
                session.flush()
                # NOTE: match_teams.score and is_winner populated after step 9
                # (rounds insert), when the final score is available.

                # Update match_players with team assignments and build index lookup
                for sid in ct_steam_ids:
                    mp_id = steam_to_mp_id.get(sid)
                    if mp_id:
                        session.execute(
                            MatchPlayerModel.__table__.update()
                            .where(MatchPlayerModel.id == mp_id)
                            .values(match_team_id=mt_ct.id, team_side="ct")
                        )
                for sid in t_steam_ids:
                    mp_id = steam_to_mp_id.get(sid)
                    if mp_id:
                        session.execute(
                            MatchPlayerModel.__table__.update()
                            .where(MatchPlayerModel.id == mp_id)
                            .values(match_team_id=mt_t.id, team_side="t")
                        )
                result.teams_created = 2

                # 9. Persist rounds
                for rd in match_domain.rounds:
                    round_model = RoundModel(
                        match_id=match_model.id,
                        round_number=rd.round_number,
                        start_tick=rd.start_tick,
                        end_tick=rd.end_tick,
                        winner_side=rd.winner_side,
                        end_reason=rd.end_reason,
                        score_t=rd.score_t,
                        score_ct=rd.score_ct,
                    )
                    session.add(round_model)
                    result.rounds_created += 1

                # 9b. Populate match_teams.score and is_winner from round wins
                # (demoparser's round.score_t/score_ct are 0 in these demos;
                # compute from per-round winner_side instead)
                round_wins = session.execute(
                    select(
                        func.sum(case((RoundModel.winner_side == "ct", 1), else_=0)).label("ct_wins"),
                        func.sum(case((RoundModel.winner_side == "t", 1), else_=0)).label("t_wins"),
                    )
                    .where(RoundModel.match_id == match_model.id)
                ).one()
                ct_wins = int(round_wins.ct_wins or 0)
                t_wins = int(round_wins.t_wins or 0)
                session.execute(
                    MatchTeamModel.__table__.update()
                    .where(MatchTeamModel.id == mt_ct.id)
                    .values(score=ct_wins, is_winner=(ct_wins > t_wins) if (ct_wins or t_wins) else None)
                )
                session.execute(
                    MatchTeamModel.__table__.update()
                    .where(MatchTeamModel.id == mt_t.id)
                    .values(score=t_wins, is_winner=(t_wins > ct_wins) if (ct_wins or t_wins) else None)
                )

                  # 8b. Build tick → round_number lookup for pickup assignment
                round_tick_starts: list[int] = []
                round_tick_ends: list[int] = []
                round_numbers: list[int] = []
                for rd in match_domain.rounds:
                    round_tick_starts.append(rd.start_tick)
                    round_tick_ends.append(rd.end_tick or rd.start_tick + 99999)
                    round_numbers.append(rd.round_number)

                # 8c. Compute and persist round side assignments
                side_assignments = _compute_side_assignments(match_domain)
                for sa_ in side_assignments:
                    rsm = RoundSideMap(
                        match_id=match_model.id,
                        team_slot=sa_.team_slot,
                        round_number=sa_.round_number,
                        overtime_index=sa_.overtime_index,
                        side=sa_.side,
                    )
                    session.add(rsm)
                    result.sides_created += 1

                # 10. Persist kills
                for idx, kd in enumerate(match_domain.kills):
                    kill_model = KillModel(
                        match_id=match_model.id,
                        round_number=kd.round_number,
                        kill_index=idx,
                        tick=kd.tick,
                        killer_name_raw=kd.killer_name,
                        victim_name_raw=kd.victim_name,
                        assister_name_raw=kd.assister_name or "",
                        weapon_name=kd.weapon,
                        is_headshot=kd.headshot,
                        is_wallbang=bool(kd.penetrated > 0),
                        killer_steam_id=kd.killer_steam_id,
                        victim_steam_id=kd.victim_steam_id,
                        assister_steam_id=kd.assister_steam_id,
                        killer_match_player_index=steam_to_mp_idx.get(kd.killer_steam_id) if kd.killer_steam_id else None,
                        victim_match_player_index=steam_to_mp_idx.get(kd.victim_steam_id) if kd.victim_steam_id else None,
                        assister_match_player_index=steam_to_mp_idx.get(kd.assister_steam_id) if kd.assister_steam_id else None,
                    )
                    session.add(kill_model)
                    result.kills_created += 1

                # 11. Persist round equipment at freezetime end using parse_ticks
                # Properties to extract: armor, helmet, defuse kit, equipment value, cash
                EQUIPMENT_PROPS = [
                    "CCSPlayerPawn.m_ArmorValue",
                    "CCSPlayerPawn.m_unFreezetimeEndEquipmentValue",
                    "CCSPlayerPawn.m_unCurrentEquipmentValue",
                    "CCSPlayerController.m_bPawnHasHelmet",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound",
                    "active_weapon_name",
                    "item_def_idx",
                ]

                # Build round_end tick list for tick->round mapping.
                # round_end.tick=0 is the initial state; filter it out.
                try:
                    re_df = self._parser.raw.parse_event("round_end", other=["round"])
                    round_end_ticks = sorted(t for t in re_df["tick"].tolist() if t > 0)
                except Exception:
                    round_end_ticks = []

                # Build sorted list of freeze_end_ticks (used for query ticks only)
                freeze_end_ticks: list[int] = [
                    rd.freeze_end_tick for rd in match_domain.rounds if rd.freeze_end_tick
                ]

                # --- PRE-COMPUTE: purchase lookup and defuse kit tracking ---
                # user_team_name correctly reflects the player's actual side per round.
                # Only CT players can buy defuse kits. Track net count (bought - sold).
                # Also index purchases by (steamid, round_number) for weapons JSON lookup.
                # round N (1-indexed) has total_rounds_played = N - 1.
                if freeze_end_ticks:
                    purchase_df = self._parser.raw.parse_event(
                        "item_purchase",
                        player=["steamid", "team_name"],
                        other=["item_name", "was_sold", "total_rounds_played"],
                    )
                    if len(purchase_df) > 0:
                        purchase_df = purchase_df.sort_values("tick")

                    # Index purchases by (steamid, round_number) for weapons lookup
                    # Also build cumulative defuse_net as we iterate in tick order
                    purchase_by_sr: dict[tuple[int, int], list[dict]] = {}
                    defuse_net: dict[int, int] = {}  # steam_id -> net defuse kit count
                    for _, row in purchase_df.iterrows():
                        item_name = str(row.get("item_name", ""))
                        sid = int(row.get("steamid", 0) or 0)
                        user_team = str(row.get("user_team_name", "")).strip().upper()
                        sold = bool(row.get("was_sold", False))
                        trp = int(row.get("total_rounds_played", -1))
                        tick_val = int(row["tick"])

                        # Index for weapons lookup: round_number = total_rounds_played + 1
                        if sid != 0:
                            key = (sid, trp + 1)
                            if key not in purchase_by_sr:
                                purchase_by_sr[key] = []
                            purchase_by_sr[key].append(item_name)

                        # Defuse kit tracking: only CT players
                        if "defuse" in item_name.lower() and user_team == "CT" and sid != 0:
                            delta = -1 if sold else 1
                            defuse_net[sid] = defuse_net.get(sid, 0) + delta
                else:
                    purchase_by_sr = {}
                    defuse_net = {}

                if round_end_ticks and freeze_end_ticks:
                    try:
                        # Get equipment state at each unique freeze_end_tick
                        unique_ticks = sorted(set(freeze_end_ticks))
                        tick_data = self._parser._parser.parse_ticks(
                            wanted_props=EQUIPMENT_PROPS,
                            ticks=unique_ticks,
                        )

                        # Fix column names: itertuples converts dots to underscores
                        col_map = {col: col.replace(".", "_") for col in tick_data.columns}
                        tick_data = tick_data.rename(columns=col_map)

                        # Group tick_data by tick and sort ticks ascending
                        tick_groups: dict[int, list] = {}
                        for _, row in tick_data.iterrows():
                            tv = int(row["tick"])
                            if tv not in tick_groups:
                                tick_groups[tv] = []
                            tick_groups[tv].append(row)

                        for tick_val in sorted(tick_groups.keys()):
                            rn_idx = bisect.bisect_right(round_end_ticks, tick_val)
                            rn = match_domain.rounds[rn_idx].round_number if 0 <= rn_idx < len(match_domain.rounds) else 0
                            if rn == 0:
                                continue

                            # Assign equipment for all players at this tick
                            for row in tick_groups[tick_val]:
                                sid = int(row.get("steamid", 0) or 0)
                                if sid == 0:
                                    continue

                                player_name = str(row.get("name", "") or "")

                                # Equipment value: prefer freezetime-end value, fall back to current
                                feq = row.get("CCSPlayerPawn_m_unFreezetimeEndEquipmentValue", 0) or 0
                                ceq = row.get("CCSPlayerPawn_m_unCurrentEquipmentValue", 0) or 0
                                eq_value = feq or ceq or 0

                                # Armor: m_ArmorValue > 0 means armor is active
                                armor_val = row.get("CCSPlayerPawn_m_ArmorValue", 0) or 0
                                armor = bool(armor_val > 0)

                                # Helmet: from CCSPlayerController (not CCSPlayerPawn)
                                helmet_val = row.get("CCSPlayerController_m_bPawnHasHelmet", False)
                                helmet = bool(helmet_val)

                                # Defuse kit: from pre-computed cumulative net purchase count
                                defuse_kit = defuse_net.get(sid, 0) > 0

                                # Build weapons JSON: {weapon_name: {"defindex": X or None}}
                                # Include active_weapon (whatever is currently equipped, even knife)
                                # + ALL purchases for this round (kevlar, grenades, defuse, rifles, etc.)
                                # Note: at freezetime end, active_weapon may still be a knife even after
                                # a buy — the player hasn't auto-switched to the new weapon yet.
                                weapons_dict: dict[str, dict] = {}

                                # Active weapon from tick data (may be knife or grenade)
                                active_name = str(row.get("active_weapon_name", "") or "").strip()
                                active_defidx = int(row.get("item_def_idx", 0) or 0)
                                if active_name and active_defidx:
                                    weapons_dict[active_name] = {"defindex": active_defidx}

                                # Add ALL purchased weapons for this player in rounds 1..rn
                                # round N purchases have total_rounds_played = N - 1, stored at key (sid, N)
                                for purch_key in [(sid, r) for r in range(1, rn + 1)]:
                                    for item_name in purchase_by_sr.get(purch_key, []):
                                        if item_name and item_name not in weapons_dict:
                                            weapons_dict[item_name] = {}

                                eq_model = RoundEquipment(
                                    match_id=match_model.id,
                                    round_number=rn,
                                    steam_id=sid,
                                    player_name=player_name,
                                    equipment_value=eq_value,
                                    weapons=weapons_dict if weapons_dict else None,
                                    armor=armor,
                                    helmet=helmet,
                                    defuse_kit=defuse_kit,
                                )
                                session.add(eq_model)
                                result.equipment_created += 1
                    except Exception as e:
                        logger.warning("Equipment parsing failed (non-fatal): %s", e)

                # 12. Persist purchases and player_round_weapons (from item_purchase events)
                # Deduplicate PlayerRoundWeapon by (steam_id, round_number, weapon_key)
                seen_prw_keys: set[tuple] = set()
                try:
                    purchase_df = self._parser.raw.parse_event(
                        "item_purchase",
                        player=["steamid", "name"],
                        other=["item_name", "cost", "inventory_slot", "total_rounds_played"],
                    )
                    for _, row in purchase_df.iterrows():
                        sid = int(row.get("steamid", 0))
                        rn = int(row.get("total_rounds_played", 0))
                        tick = int(row.get("tick", 0))
                        item_name = str(row.get("item_name", "")).strip()
                        purchase_cost = int(row.get("cost", 0) or 0)

                        # Normalize item_name to weapon_key
                        weapon_key = _normalize_item_name(item_name)

                        # Skip if no valid steam_id
                        if sid == 0:
                            continue

                        # ── RoundPurchase (enriched) ──────────────────────────────
                        cat = weapon_category(weapon_key)
                        pu_model = RoundPurchase(
                            match_id=match_model.id,
                            round_number=rn,
                            tick=tick,
                            steam_id=sid,
                            player_name=str(row.get("name", "")),
                            weapon_name=weapon_key,
                            weapon_category=cat,
                            cost=purchase_cost,
                        )
                        session.add(pu_model)

                        # ── PlayerRoundWeapon ─────────────────────────────────────
                        # Skip non-weapon items (armor, defuse kits tracked separately)
                        if weapon_key in (
                            "kevlar", "kevlar_helmet", "defuse_kit",
                            "assaultsuit", "heavyassaultsuit",
                        ):
                            continue

                        # Deduplicate by (steam_id, round_number, weapon_key)
                        prw_key = (sid, rn, weapon_key)
                        if prw_key in seen_prw_keys:
                            continue
                        seen_prw_keys.add(prw_key)

                        prw = PlayerRoundWeapon(
                            match_id=match_model.id,
                            round_number=rn,
                            steam_id=sid,
                            player_id=player_map.get(sid),
                            weapon_key=weapon_key,
                            weapon_defindex=weapon_key_to_defindex.get(weapon_key),
                            is_equipped=True,
                            is_purchased=True,
                            is_dropped=False,
                            acquired_at_tick=tick,
                            purchase_cost=purchase_cost,
                        )
                        session.add(prw)
                        result.weapons_created += 1
                except Exception as e:
                    logger.warning("Purchase parsing failed (non-fatal): %s", e)

                # 13. Persist item pickups → PlayerRoundWeapon (is_purchased=False)
                try:
                    pickups = self._parser.item_pickups()
                    for pickup in pickups:
                        sid = pickup.player_steam_id or 0
                        if sid == 0:
                            continue

                        # Map defindex → weapon_key
                        weapon_key = defindex_to_weapon(pickup.defindex)
                        if weapon_key.startswith("unknown_"):
                            logger.debug("Unknown defindex %d at tick %d", pickup.defindex, pickup.tick)
                            continue

                        # Skip armor / utility — tracked separately
                        if weapon_key in (
                            "kevlar", "kevlar_helmet", "defuse_kit",
                            "heavyassaultsuit", "night_rescue", "rescue_kit", "medi_shot",
                        ):
                            continue

                        # Find which round this tick falls in
                        idx = bisect.bisect_right(round_tick_starts, pickup.tick) - 1
                        rn = round_numbers[idx] if 0 <= idx < len(round_numbers) else 0
                        if rn == 0:
                            logger.debug("Pickup at tick %d outside all rounds", pickup.tick)
                            continue

                        # Deduplicate against purchases (same steam_id+round+weapon)
                        prw_key = (sid, rn, weapon_key)
                        if prw_key in seen_prw_keys:
                            continue
                        seen_prw_keys.add(prw_key)

                        prw = PlayerRoundWeapon(
                            match_id=match_model.id,
                            round_number=rn,
                            steam_id=sid,
                            player_id=player_map.get(sid),
                            weapon_key=weapon_key,
                            weapon_defindex=pickup.defindex,
                            is_equipped=True,
                            is_purchased=False,
                            is_dropped=False,
                            acquired_at_tick=pickup.tick,
                            purchase_cost=0,
                        )
                        session.add(prw)
                        result.weapons_created += 1
                except Exception as e:
                    logger.warning("Item pickup parsing failed (non-fatal): %s", e)

                # 14. Persist bomb events (plant, defuse, explode, drop, pickup)
                try:
                    for ev in self._parser.bomb_events():
                        model = BombEventModel(
                            match_id=match_model.id,
                            tick=ev.tick,
                            event_type=ev.event_type,
                            player_steam_id=ev.player_steam_id,
                            player_name=ev.player_name or "",
                            site=ev.site,
                            has_kit=ev.has_kit,
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Bomb events ingest failed (non-fatal): %s", e)

                # 15. Persist grenade detonations (he, flash, smoke expire)
                try:
                    for ev in self._parser.grenades():
                        idx = bisect.bisect_right(round_tick_starts, ev.tick) - 1
                        rn = round_numbers[idx] if 0 <= idx < len(round_numbers) else 0
                        model = GrenadeDetonationModel(
                            match_id=match_model.id,
                            round_number=rn,
                            tick=ev.tick,
                            grenade_type=ev.grenade_type,
                            player_steam_id=ev.player_steam_id,
                            player_name=ev.player_name or "",
                            x=ev.x,
                            y=ev.y,
                            z=ev.z,
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Grenade detonation ingest failed (non-fatal): %s", e)

                # 16. Persist inferno events (molotov start_burn / expire)
                try:
                    for ev in self._parser.inferno_events():
                        model = InfernoEventModel(
                            match_id=match_model.id,
                            tick=ev.tick,
                            event_type=ev.event_type,
                            player_steam_id=ev.player_steam_id,
                            player_name=ev.player_name or "",
                            x=ev.x,
                            y=ev.y,
                            z=ev.z,
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Inferno event ingest failed (non-fatal): %s", e)

                # 17. Persist flashbang blind events
                # Build steam_id -> display_name map from the players table
                # for victim name lookup (demoparser doesn't always include victim_name)
                # Use raw SQL to avoid SQLAlchemy session caching issues
                player_name_map: dict[int, str] = {}
                for row in session.execute(text(
                    "SELECT steam_id, COALESCE(last_known_name, '') FROM csda.players"
                )).all():
                    player_name_map[row[0]] = row[1] or ""
                try:
                    for ev in self._parser.player_blinds():
                        victim_name = ev.victim_name or player_name_map.get(ev.victim_steam_id, "")
                        model = PlayerBlindModel(
                            match_id=match_model.id,
                            tick=ev.tick,
                            attacker_steam_id=ev.attacker_steam_id,
                            attacker_name=ev.attacker_name or "",
                            victim_steam_id=ev.victim_steam_id,
                            victim_name=victim_name,
                            blind_duration=ev.blind_duration,
                        )
                        session.add(model)
                    session.flush()
                except Exception as e:
                    logger.warning("Player blind ingest failed (non-fatal): %s", e)

                # 17b. Fallback: if player_blind is empty (parser didn't emit
                # the event), recover approximate blinds from flashbang_detonate
                # using a proximity heuristic. ~70-85% accuracy for swing credit.
                self._estimate_blinds_from_proximity(session, match_model.id)

                # 21. Persist additional batch events (weapon_fire, bullet_hit,
                # player_spawn, player_jump, player_footstep, chat, mvp,
                # item_equip, player_ping, buytime, weapon_drop,
                # grenade_trajectory_summaries)
                for ingest_fn in (
                    self._ingest_weapon_fires,
                    self._ingest_player_bullet_hits,
                    self._ingest_player_spawns,
                    self._ingest_player_jumps,
                    self._ingest_player_footsteps,
                    self._ingest_chat_messages,
                    self._ingest_round_mvps,
                    self._ingest_item_equips,
                    self._ingest_player_pings,
                    self._ingest_buytime_events,
                    self._ingest_weapon_drops,
                    self._ingest_grenade_trajectory_summaries,
                ):
                    n = ingest_fn(session, match_model.id)
                    if n:
                        session.commit()

                # 18. Persist damage events (player_hurt — includes utility damage)
                try:
                    for ev in self._parser.damage():
                        model = DamageEventModel(
                            match_id=match_model.id,
                            tick=ev.tick,
                            round_number=ev.round_number,
                            attacker_steam_id=ev.attacker_steam_id,
                            attacker_name=ev.attacker_name or "",
                            victim_steam_id=ev.victim_steam_id,
                            victim_name=ev.victim_name or "",
                            weapon=ev.weapon or "",
                            dmg_health=ev.dmg_health,
                            dmg_armor=ev.dmg_armor,
                            hitgroup=ev.hitgroup,
                            health=ev.health,
                            armor=ev.armor,
                            hitgroup_name=ev.hitgroup_name or "unknown",
                            attacker_last_place_name=ev.attacker_last_place_name or "",
                            victim_last_place_name=ev.victim_last_place_name or "",
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Damage event ingest failed (non-fatal): %s", e)

                # 19. Persist grenade trajectories (path through air per throw)
                # NOTE: ~1.8M rows per map causes 45s+ ingest time. Disabled for now.
                # TODO: Re-enable with bulk insert via session.add_all() in chunks of ~10k rows
                #       instead of one session.add() per row (current bottleneck).
                # try:
                #     for ev in self._parser.grenade_trajectories():
                #         idx = bisect.bisect_right(round_tick_starts, ev.tick) - 1
                #         rn = round_numbers[idx] if 0 <= idx < len(round_numbers) else 0
                #         model = GrenadeTrajectoryModel(
                #             match_id=match_model.id,
                #             round_number=rn,
                #             tick=ev.tick,
                #             grenade_entity_id=ev.grenade_entity_id,
                #             grenade_type=ev.grenade_type or "",
                #             thrower_steam_id=ev.thrower_steam_id or 0,
                #             thrower_name=ev.thrower_name or "",
                #             x=ev.x,
                #             y=ev.y,
                #             z=ev.z,
                #         )
                #         session.add(model)
                # except Exception as e:
                #     logger.warning("Grenade trajectory ingest failed (non-fatal): %s", e)

                # 20. Persist player round stats (kills/assists/deaths/damage/utility at tick)
                try:
                    for ev in self._parser.player_round_stats(specific_ticks=freeze_end_ticks):
                        idx = bisect.bisect_right(round_tick_starts, ev.tick) - 1
                        rn = round_numbers[idx] if 0 <= idx < len(round_numbers) else 0
                        model = PlayerRoundStatsModel(
                            match_id=match_model.id,
                            round_number=rn,
                            tick=ev.tick,
                            steam_id=ev.steam_id or 0,
                            kills=ev.kills,
                            assists=ev.assists,
                            deaths=ev.deaths,
                            damage=ev.damage,
                            headshot_kills=ev.headshot_kills,
                            cash_earned=ev.cash_earned,
                            equipment_value=ev.equipment_value,
                            utility_damage=ev.utility_damage,
                            enemies_flashed=ev.enemies_flashed,
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Player round stats ingest failed (non-fatal): %s", e)

                # 20. Persist weapon drop events (WeaponDropEvent — dropped_by / picked_up_by)
                try:
                    drops = self._parser.raw.parse_item_drops()
                    for row in drops.itertuples(index=False):
                        sid = int(getattr(row, 'steamid', 0) or 0)
                        # Use round from total_rounds_played if available
                        trp = int(getattr(row, 'total_rounds_played', 0) or 0)
                        model = WeaponDropModel(
                            match_id=match_model.id,
                            round_number=trp + 1,  # 1-indexed
                            tick=int(getattr(row, 'tick', 0) or 0),
                            weapon_name=str(getattr(row, 'def_index', 0) or ""),
                            dropped_by_steam_id=sid,
                            dropped_by_name=str(getattr(row, 'account_id', '') or ''),
                            picked_up_by_steam_id=None,
                            picked_up_by_name=None,
                        )
                        session.add(model)
                except Exception as e:
                    logger.warning("Weapon drop ingest failed (non-fatal): %s", e)

                logger.info("Ingest complete: %s", result)

        except Exception as e:
            result.errors.append(str(e))
            logger.error("Ingest failed: %s", e)
            raise

        return result

    # ── Internal helpers ─────────────────────────────────────────────────

    # ── Additional batch event ingests ────────────────────────────────────────

    def _ingest_weapon_fires(self, session, match_id: int) -> int:
        try:
            rows = [
                WeaponFireModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    shooter_steam_id=ev.shooter_steam_id,
                    shooter_name=ev.shooter_name or "",
                    weapon=getattr(ev, "weapon", ""),
                    silenced=getattr(ev, "silenced", False),
                )
                for ev in self._parser.weapon_fires()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Weapon fire ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_player_bullet_hits(self, session, match_id: int) -> int:
        try:
            rows = [
                PlayerBulletHitModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    shooter_steam_id=ev.shooter_steam_id,
                    shooter_name=ev.shooter_name or "",
                    target_entity_id=ev.target_entity_id,
                    penetrating_count=ev.penetrating_count,
                )
                for ev in self._parser.player_bullet_hits()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Player bullet hit ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_player_spawns(self, session, match_id: int) -> int:
        try:
            rows = [
                PlayerSpawnModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                )
                for ev in self._parser.player_spawns()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Player spawn ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_player_jumps(self, session, match_id: int) -> int:
        try:
            rows = [
                PlayerJumpModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                )
                for ev in self._parser.player_jumps()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Player jump ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_player_footsteps(self, session, match_id: int) -> int:
        try:
            rows = [
                PlayerFootstepModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                )
                for ev in self._parser.player_footsteps()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Player footstep ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_chat_messages(self, session, match_id: int) -> int:
        try:
            rows = [
                ChatMessageModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                    message=ev.message or "",
                    team_only=ev.team_only,
                )
                for ev in self._parser.chat_messages()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Chat message ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_round_mvps(self, session, match_id: int) -> int:
        try:
            rows = [
                RoundMVPModel(
                    match_id=match_id,
                    round_number=ev.round_number,
                    tick=ev.tick,
                    steam_id=ev.steam_id,
                    player_name=ev.player_name or "",
                    reason=getattr(ev, "reason", "") or "",
                    music_kit_id=getattr(ev, "music_kit_id", 0) or 0,
                )
                for ev in self._parser.round_mvps()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Round MVP ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_item_equips(self, session, match_id: int) -> int:
        try:
            rows = [
                ItemEquipModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                    weapon=ev.weapon or "",
                )
                for ev in self._parser.item_equips()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Item equip ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_player_pings(self, session, match_id: int) -> int:
        try:
            rows = [
                PlayerPingModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    steam_id=ev.player_steam_id,
                    player_name=ev.player_name or "",
                    is_world_ping=ev.is_world_ping,
                )
                for ev in self._parser.player_pings()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Player ping ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_buytime_events(self, session, match_id: int) -> int:
        try:
            rows = [
                BuyTimeEventModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    event_type=ev.event_type,
                )
                for ev in self._parser.buytime_events()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Buytime event ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_weapon_drops(self, session, match_id: int) -> int:
        try:
            rows = [
                WeaponDropModel(
                    match_id=match_id,
                    round_number=rd_round_number(self._parser.rounds(), ev.tick),
                    tick=ev.tick,
                    dropped_by_steam_id=ev.dropper_steam_id,
                    dropped_by_name=ev.dropper_name or "",
                    picked_up_by_steam_id=ev.picker_steam_id,
                    picked_up_by_name=ev.picker_name or "",
                    weapon_name=ev.weapon or "",
                )
                for ev in self._parser.weapon_drops()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Weapon drop ingest failed (non-fatal): %s", e)
            return 0

    def _ingest_grenade_trajectory_summaries(self, session, match_id: int) -> int:
        try:
            rows = [
                GrenadeTrajectorySummaryModel(
                    match_id=match_id,
                    round_number=ev.get("round_number", 0),
                    thrower_steam_id=ev.get("thrower_steam_id"),
                    thrower_name=ev.get("thrower_name", ""),
                    grenade_entity_id=ev.get("grenade_entity_id", 0),
                    grenade_type=ev.get("grenade_type", ""),
                    team=ev.get("team", ""),
                    throw_tick=ev.get("throw_tick", 0),
                    detonate_tick=ev.get("detonate_tick", 0),
                    duration_ticks=ev.get("duration_ticks", 0),
                    throw_pos_x=ev.get("throw_pos_x", 0),
                    throw_pos_y=ev.get("throw_pos_y", 0),
                    throw_pos_z=ev.get("throw_pos_z", 0),
                    detonate_pos_x=ev.get("detonate_pos_x", 0),
                    detonate_pos_y=ev.get("detonate_pos_y", 0),
                    detonate_pos_z=ev.get("detonate_pos_z", 0),
                    trajectory_points=ev.get("trajectory_points", "[]"),
                    max_distance=ev.get("max_distance", 0),
                    is_flash=ev.get("is_flash", False),
                )
                for ev in self._parser.grenade_trajectory_summaries()
            ]
            session.add_all(rows)
            return len(rows)
        except Exception as e:
            logger.warning("Grenade trajectory summary ingest failed (non-fatal): %s", e)
            return 0

    def _estimate_blinds_from_proximity(
        self,
        session: Session,
        match_id: int,
        flash_radius: float = 1000.0,
        max_blind: float = 5.5,
        min_blind: float = 0.3,
    ) -> int:
        """Fallback PlayerBlind recovery from flashbang_detonate (proximity heuristic).

        The demoparser for some demos emits 0 player_blind events even when
        flashbangs were thrown. This method recovers approximate blind data by:
          1. Checking if PlayerBlind already has rows for this match
          2. If empty, fetching all flashbang_detonate events
          3. Getting player positions at those ticks (parse_ticks)
          4. For each enemy within flash_radius of the detonation,
             inserting a PlayerBlind with distance-based duration.

        Accuracy: ~70-85% for credit splitting in swing models (no FOV check).

        Returns the number of heuristic blinds inserted.
        """
        from sqlalchemy import func as sqlfunc
        existing = session.execute(
            select(sqlfunc.count()).select_from(PlayerBlindModel).where(
                PlayerBlindModel.match_id == match_id
            )
        ).scalar()
        if existing and existing > 0:
            return 0  # real player_blind events exist; nothing to recover

        flashbangs = session.execute(
            select(GrenadeDetonationModel).where(
                GrenadeDetonationModel.match_id == match_id,
                GrenadeDetonationModel.grenade_type.ilike("flash%"),
            )
        ).scalars().all()
        if not flashbangs:
            return 0

        # Build steam_id -> team_side
        team_map: dict[int, str] = {}
        for mp in session.execute(
            select(MatchPlayerModel).where(MatchPlayerModel.match_id == match_id)
        ).scalars().all():
            if mp.team_side and mp.steam_id:
                team_map[mp.steam_id] = mp.team_side.lower()

        # Batch-fetch positions at all unique flash ticks
        flash_ticks = sorted({fb.tick for fb in flashbangs if fb.tick})
        try:
            pos_df = self._parser._parser.parse_ticks(
                wanted_props=[
                    "CCSPlayerPawn.m_vecX",
                    "CCSPlayerPawn.m_vecY",
                    "CCSPlayerPawn.m_vecZ",
                ],
                ticks=flash_ticks,
            )
        except Exception as e:
            logger.warning("Proximity-blind parse_ticks failed (non-fatal): %s", e)
            return 0

        positions: dict[int, dict[int, tuple[float, float, float]]] = {}
        for _, row in pos_df.iterrows():
            try:
                t = int(row["tick"])
                sid = int(row["steamid"])
                x, y, z = float(row["CCSPlayerPawn.m_vecX"]), float(row["CCSPlayerPawn.m_vecY"]), float(row["CCSPlayerPawn.m_vecZ"])
            except (KeyError, ValueError, TypeError):
                continue
            positions.setdefault(t, {})[sid] = (x, y, z)

        def _dist(x1, y1, z1, x2, y2, z2) -> float:
            x1, y1, z1, x2, y2, z2 = (float(v) for v in (x1, y1, z1, x2, y2, z2))
            return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)

        def _est_dur(d: float) -> float:
            if d >= flash_radius:
                return 0.0
            frac = 1.0 - (d / flash_radius)
            return min_blind + frac * (max_blind - min_blind)

        inserted = 0
        for fb in flashbangs:
            thrower_sid = fb.player_steam_id
            thrower_team = team_map.get(thrower_sid)
            if not thrower_team:
                continue
            tick_positions = positions.get(fb.tick, {})
            for victim_sid, (vx, vy, vz) in tick_positions.items():
                victim_team = team_map.get(victim_sid)
                if victim_team is None or victim_team == thrower_team:
                    continue
                d = _dist(fb.x, fb.y, fb.z, vx, vy, vz)
                dur = _est_dur(d)
                if dur <= 0:
                    continue
                # Look up victim name from players table (raw SQL avoids session caching)
                if not hasattr(self, '_victim_name_cache'):
                    self._victim_name_cache = {}
                if victim_sid not in self._victim_name_cache:
                    name_row = session.execute(text(
                        "SELECT COALESCE(last_known_name, '') FROM csda.players WHERE steam_id = :sid"
                    ), {"sid": victim_sid}).first()
                    self._victim_name_cache[victim_sid] = name_row[0] if name_row else ""

                session.add(PlayerBlindModel(
                    match_id=match_id,
                    tick=fb.tick,
                    attacker_steam_id=thrower_sid,
                    attacker_name=fb.player_name or "",
                    victim_steam_id=victim_sid,
                    victim_name=self._victim_name_cache[victim_sid],
                    blind_duration=round(dur, 2),
                    is_heuristic=True,
                ))
                inserted += 1

        if inserted:
            session.commit()
            logger.info("Proximity heuristic inserted %d PlayerBlind rows for match %d", inserted, match_id)
        return inserted

    def _insert_demo_file(
        self, session: Session, demo: Optional[DemoFileDomain]
    ) -> Optional[DemoFileModel]:
        if demo is None:
            return None
        # Use the SHA256 we computed in run() for idempotency, not the
        # parser's empty demo_checksum field.
        checksum = getattr(self, "_file_hash", demo.demo_checksum)
        model = DemoFileModel(
            demo_filename=demo.demo_filename,
            demo_checksum=checksum,
            parser_name=demo.parser_name,
            parser_version=demo.parser_version,
            source=demo.source,
        )
        session.add(model)
        return model

    def _upsert_player(self, session: Session, player: PlayerDomain) -> PlayerModel:
        """Find existing player by steam_id or create a new one."""
        existing = session.execute(
            select(PlayerModel).where(PlayerModel.steam_id == player.steam_id)
        ).scalar_one_or_none()

        if existing:
            # Update last_known_name if different
            if existing.last_known_name != player.name:
                existing.last_known_name = player.name
            return existing

        model = PlayerModel(
            steam_id=player.steam_id,
            last_known_name=player.name,
        )
        session.add(model)
        return model

    def _upsert_team(self, session: Session, team: MatchTeamDomain) -> TeamModel:
        """Find existing team by canonical name or create a new one."""
        existing = session.execute(
            select(TeamModel).where(TeamModel.canonical_name == team.display_name)
        ).scalar_one_or_none()

        if existing:
            return existing

        model = TeamModel(
            canonical_name=team.display_name,
            slug=team.display_name.lower().replace(" ", "-") if team.display_name else None,
        )
        session.add(model)
        return model

    def _upsert_team_by_name(self, session: Session, name: str) -> TeamModel:
        """Find existing team by canonical name or create a new one."""
        if not name or name == "unknown":
            existing = session.execute(
                select(TeamModel).where(TeamModel.canonical_name == "Unknown Team")
            ).scalar_one_or_none()
            if existing:
                return existing
            model = TeamModel(canonical_name="Unknown Team", slug="unknown")
            session.add(model)
            return model

        existing = session.execute(
            select(TeamModel).where(TeamModel.canonical_name == name)
        ).scalar_one_or_none()

        if existing:
            return existing

        model = TeamModel(canonical_name=name, slug=name.lower().replace(" ", "-"))
        session.add(model)
        return model

    def _find_or_create_series(
        self,
        session: Session,
        event_id: int,
        series_type: str,
        team_a_id: Optional[int],
        team_b_id: Optional[int],
        team_a_name: str,
        team_b_name: str,
    ) -> EventSeriesModel:
        """Find or create an EventSeries for this matchup.

        Strategy: look for an existing series between these two teams in this event.
        If none found, create a new one.

        For demo-only ingest (no HLTV event context), we match purely on
        (team_a_name, team_b_name, series_type) since we may not have a real event_id.
        """
        # Normalize team order: smaller team_id first for consistent lookup
        a_id, b_id = sorted([team_a_id or 0, team_b_id or 0])

        # Look for existing series with same teams and series type
        # NOTE: This finds ALL series between these teams, including past ones.
        # In a real system you'd also filter by event_id or date.
        # For demo ingest, we create a new series per BO3 demo bundle.
        existing = session.execute(
            select(EventSeriesModel).where(
                EventSeriesModel.team_a_id == a_id,
                EventSeriesModel.team_b_id == b_id,
                EventSeriesModel.series_type == series_type,
            )
        ).scalars().all()

        if existing:
            # Use the most recently created one (last in the list, assuming INSERT order)
            # This handles the case where all 3 maps of a BO3 share the same series
            return existing[-1]

        # Ensure event_id is valid — create a placeholder "Demo Event" if needed
        from csda_toolkit.db.models import Event as EventModel
        event = session.get(EventModel, event_id)
        if not event:
            # Try to find a "Demo Event"
            event = session.execute(
                select(EventModel).where(EventModel.name == "Demo Event")
            ).scalar_one_or_none()
            if not event:
                event = EventModel(
                    name="Demo Event",
                    slug="demo-event",
                    source="demo_ingest",
                )
                session.add(event)
                session.flush()
                # Use the new event's id (not necessarily 1)

        # Create new series
        series_model = EventSeriesModel(
            event_id=event.id,
            series_type=series_type,
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            source="demo_ingest",
        )
        session.add(series_model)
        return series_model


# ── Helpers ─────────────────────────────────────────────────────────────────


def rd_round_number(rounds, tick: int) -> int:
    """Return the round_number for a given tick by binary search on round starts."""
    if not rounds or tick is None:
        return 0
    starts = [r.start_tick for r in rounds if r.start_tick is not None]
    nums = [r.round_number for r in rounds if r.start_tick is not None]
    if not starts:
        return 0
    import bisect as _bisect
    idx = _bisect.bisect_right(starts, tick) - 1
    if idx < 0:
        return 0
    return nums[idx] if idx < len(nums) else 0


def _get_team_name_for_slot(match: MatchDomain, slot: int) -> str:
    for t in match.teams:
        if t.team_slot == slot:
            return t.display_name
    return f"Team {slot}"


def _guess_player_team_slot(match: MatchDomain, steam_id: int) -> Optional[int]:
    """Guess which team a player belongs to based on team player lists."""
    for t in match.teams:
        if steam_id in t.player_ids:
            return t.team_slot
    return None


def _compute_side_assignments(match_domain: MatchDomain) -> list[SideAssignment]:
    """Compute side assignment for each team slot in each round.

    CS2 BLAST format (12 rounds per half):
      - Rounds 1-12: team_slot 1 = CT, team_slot 2 = T  [first half]
      - Rounds 13-24: team_slot 1 = T, team_slot 2 = CT  [second half]
      - OT (rn > 24): 3 rounds on side A, 3 rounds on side B, first to 3 wins OT
        - OT1: team1 T side (rounds 25-27), team1 CT side (rounds 28-30)
        - OT2: team1 T side (rounds 31-33), team1 CT side (rounds 34-36)
        - Pattern: T, T, T, CT, CT, CT (for team 1)

    overtime_index: 0 for regulation, 1..N for overtime periods.
    team_slot 1 and team_slot 2 always have opposite sides in every round.
    """
    HALF_ROUNDS = 12  # rounds per half
    REGULATION_MAX = HALF_ROUNDS * 2  # 24 rounds max in regulation
    OT_ROUNDS_PER_SIDE = 3  # 3 rounds per side per OT period

    assignments: list[SideAssignment] = []

    for rd in match_domain.rounds:
        rn = rd.round_number  # 1-indexed from demoparser

        if rn <= REGULATION_MAX:
            overtime_index = 0
            # First half: rn 1-12, Second half: rn 13-24
            team1_is_ct = rn <= HALF_ROUNDS
            team1_side = "ct" if team1_is_ct else "t"
        else:
            # Overtime: 3 rounds on one side, then 3 rounds on the other
            # OT1: rounds 25-27 = team1 T, rounds 28-30 = team1 CT
            # OT2: rounds 31-33 = team1 T, rounds 34-36 = team1 CT
            # General: every 6 OT rounds (3T + 3CT) = 1 OT period
            ot_rounds_played = rn - REGULATION_MAX - 1  # 0-indexed
            ot_period = ot_rounds_played // OT_ROUNDS_PER_SIDE  # which side in the OT
            round_in_ot_period = ot_rounds_played % OT_ROUNDS_PER_SIDE  # position within that side's 3 rounds

            overtime_index = ot_period // 2 + 1  # period 0,1 = OT1; period 2,3 = OT2; etc.

            # Period 0: team1 plays T for 3 rounds (25-27), then CT for 3 (28-30)
            # Period 1: team1 plays T for 3 rounds (31-33), then CT for 3 (34-36)
            # So odd periods = first half of OT (T side), even periods = second half (CT side)
            team1_is_ct = ot_period % 2 == 1
            team1_side = "ct" if team1_is_ct else "t"

        assignments.append(SideAssignment(
            team_slot=1,
            round_number=rn,
            overtime_index=overtime_index,
            side=team1_side,
        ))
        assignments.append(SideAssignment(
            team_slot=2,
            round_number=rn,
            overtime_index=overtime_index,
            side="t" if team1_side == "ct" else "ct",
        ))

    return assignments
