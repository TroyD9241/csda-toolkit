"""Ingest just mirage map - debug version."""
import os
import time

from sqlalchemy import select

from csda_toolkit.db.database import Database
from csda_toolkit.db.models import (
    DemoFile as DemoFileModel,
    Match as MatchModel,
    Player as PlayerModel,
    Team as TeamModel,
    Round as RoundModel,
    Kill as KillModel,
)
from csda_toolkit.parsing.parser import CsdaParser

DEMO = r"C:\Users\Troy\csda-toolkit\demos\blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks\vitality-vs-fut-m1-mirage.dem"
DB_URL = os.environ.get("DATABASE_URL", "postgresql://csda:csda@localhost:5432/csda")
print(f"DB: {DB_URL}")
print(f"Demo: {DEMO}")

db = Database(DB_URL)

# Step 1: parse
print("\n[1] Parsing demo...")
t0 = time.time()
parser = CsdaParser(DEMO)
match_domain = parser.parse_match()
print(f"  parse_match() done in {time.time()-t0:.1f}s")
print(f"  Rounds: {len(match_domain.rounds)}, Kills: {len(match_domain.kills)}, Players: {len(match_domain.players)}")

# Step 2: insert demo_file
print("\n[2] Inserting demo_file...")
t1 = time.time()
with db.session() as session:
    df = DemoFileModel(
        demo_filename=match_domain.demo_file.demo_filename,
        demo_checksum=match_domain.demo_file.demo_checksum,
        parser_name=match_domain.demo_file.parser_name,
        parser_version=match_domain.demo_file.parser_version,
        source=match_domain.demo_file.source,
    )
    session.add(df)
    session.flush()
    print(f"  demo_file id={df.id} in {time.time()-t1:.1f}s")

    # Step 3: insert teams
    print("\n[3] Inserting teams...")
    t2 = time.time()
    team_map = {}
    for team_domain in match_domain.teams:
        existing = session.execute(
            select(TeamModel).where(TeamModel.display_name == team_domain.display_name)
        ).scalar_one_or_none()
        if existing:
            tm = existing
        else:
            tm = TeamModel(display_name=team_domain.display_name)
            session.add(tm)
            session.flush()
        team_map[team_domain.team_slot] = tm.id
    print(f"  Teams: {team_map} in {time.time()-t2:.1f}s")

    # Step 4: insert players
    print("\n[4] Inserting players...")
    t3 = time.time()
    player_map = {}
    for player_domain in match_domain.players:
        existing = session.execute(
            select(PlayerModel).where(PlayerModel.steam_id == player_domain.steam_id)
        ).scalar_one_or_none()
        if existing:
            pm = existing
            if existing.last_known_name != player_domain.name:
                existing.last_known_name = player_domain.name
        else:
            pm = PlayerModel(steam_id=player_domain.steam_id, last_known_name=player_domain.name)
            session.add(pm)
            session.flush()
        player_map[player_domain.steam_id] = pm.id
    print(f"  Players: {len(player_map)} in {time.time()-t3:.1f}s")

    # Step 5: insert match
    print("\n[5] Inserting match...")
    t4 = time.time()
    from datetime import datetime
    mm = MatchModel(
        demo_file_id=df.id,
        map_name=match_domain.map_name,
        tick_rate=match_domain.tick_rate,
        server_name=match_domain.server_name,
        source=match_domain.source,
        played_at=match_domain.played_at or datetime.utcnow(),
    )
    session.add(mm)
    session.flush()
    print(f"  match id={mm.id} in {time.time()-t4:.1f}s")

    # Step 6: insert rounds
    print("\n[6] Inserting rounds...")
    t5 = time.time()
    for rd in match_domain.rounds:
        rm = RoundModel(
            match_id=mm.id,
            round_number=rd.round_number,
            start_tick=rd.start_tick,
            end_tick=rd.end_tick,
            winner_side=rd.winner_side,
            end_reason=rd.end_reason,
            score_t=rd.score_t,
            score_ct=rd.score_ct,
        )
        session.add(rm)
    session.flush()
    print(f"  {len(match_domain.rounds)} rounds in {time.time()-t5:.1f}s")

    # Step 7: insert kills
    print("\n[7] Inserting kills...")
    t6 = time.time()
    for idx, kd in enumerate(match_domain.kills):
        km = KillModel(
            match_id=mm.id,
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
        )
        session.add(km)
    session.flush()
    print(f"  {len(match_domain.kills)} kills in {time.time()-t6:.1f}s")

    # Step 8: round_side_map
    print("\n[8] RoundSideMap...")
    t7 = time.time()
    from csda_toolkit.db.models import RoundSideMap
    from csda_toolkit.ingest.bundle import _compute_side_assignments
    side_assignments = _compute_side_assignments(match_domain)
    for sa_ in side_assignments:
        rsm = RoundSideMap(
            match_id=mm.id,
            team_slot=sa_.team_slot,
            round_number=sa_.round_number,
            overtime_index=sa_.overtime_index,
            side=sa_.side,
        )
        session.add(rsm)
    session.flush()
    print(f"  {len(side_assignments)} side map rows in {time.time()-t7:.1f}s")

    # Step 9: parse_ticks for equipment (known to be slow)
    print("\n[9] parse_ticks for equipment...")
    import bisect
    round_tick_starts = [rd.start_tick for rd in match_domain.rounds]
    round_tick_ends = [rd.end_tick or rd.start_tick + 99999 for rd in match_domain.rounds]
    round_numbers = [rd.round_number for rd in match_domain.rounds]

    freeze_end_ticks = [rd.freeze_end_tick for rd in match_domain.rounds if rd.freeze_end_tick]
    print(f"  {len(freeze_end_ticks)} freeze_end_ticks")

    try:
        t8 = time.time()
        re_df = parser.raw.parse_event("round_end", other=["round"])
        round_end_ticks = sorted(t for t in re_df["tick"].tolist() if t > 0)
        print(f"  round_end_ticks: {len(round_end_ticks)} in {time.time()-t8:.1f}s")
    except Exception as e:
        print(f"  round_end error: {e}")
        round_end_ticks = []

    if round_end_ticks and freeze_end_ticks:
        print("  Calling parse_ticks (this can be slow)...")
        t9 = time.time()
        try:
            unique_ticks = sorted(set(freeze_end_ticks))
            tick_data = parser._parser.parse_ticks(
                wanted_props=[
                    "CCSPlayerPawn.m_ArmorValue",
                    "CCSPlayerPawn.m_unFreezetimeEndEquipmentValue",
                    "CCSPlayerPawn.m_unCurrentEquipmentValue",
                    "CCSPlayerController.m_bPawnHasHelmet",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount",
                    "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound",
                    "active_weapon_name",
                    "item_def_idx",
                ],
                ticks=unique_ticks,
            )
            print(f"  parse_ticks done: {tick_data.shape} in {time.time()-t9:.1f}s")
        except Exception as e:
            print(f"  parse_ticks failed: {e}")
    else:
        print("  Skipping parse_ticks (no data)")

    # Step 10: item_purchases
    print("\n[10] Item purchases...")
    t10 = time.time()
    try:
        purchase_df = parser.raw.parse_event(
            "item_purchase",
            player=["steamid", "name"],
            other=["item_name", "cost", "inventory_slot", "total_rounds_played"],
        )
        print(f"  {len(purchase_df)} purchases in {time.time()-t10:.1f}s")
    except Exception as e:
        print(f"  purchases failed: {e}")

    # Step 11: item_pickups
    print("\n[11] Item pickups...")
    t11 = time.time()
    try:
        pickups = parser.item_pickups()
        print(f"  {len(pickups)} pickups in {time.time()-t11:.1f}s")
    except Exception as e:
        print(f"  pickups failed: {e}")

    # Step 12: bomb_events
    print("\n[12] Bomb events...")
    t12 = time.time()
    try:
        bombs = parser.bomb_events()
        print(f"  {len(bombs)} bomb events in {time.time()-t12:.1f}s")
    except Exception as e:
        print(f"  bomb_events failed: {e}")

    # Step 13: grenades
    print("\n[13] Grenades...")
    t13 = time.time()
    try:
        grenades = parser.grenades()
        print(f"  {len(grenades)} grenades in {time.time()-t13:.1f}s")
    except Exception as e:
        print(f"  grenades failed: {e}")

    # Step 14: inferno_events
    print("\n[14] Inferno events...")
    t14 = time.time()
    try:
        infernos = parser.inferno_events()
        print(f"  {len(infernos)} infernos in {time.time()-t14:.1f}s")
    except Exception as e:
        print(f"  inferno_events failed: {e}")

    # Step 15: player_blinds
    print("\n[15] Player blinds...")
    t15 = time.time()
    try:
        blinds = parser.player_blinds()
        print(f"  {len(blinds)} blinds in {time.time()-t15:.1f}s")
    except Exception as e:
        print(f"  player_blinds failed: {e}")

    # Step 16: damage
    print("\n[16] Damage events...")
    t16 = time.time()
    try:
        damage = parser.damage()
        print(f"  {len(damage)} damage events in {time.time()-t16:.1f}s")
    except Exception as e:
        print(f"  damage failed: {e}")

    # Step 17: grenade_trajectories
    print("\n[17] Grenade trajectories...")
    t17 = time.time()
    try:
        trajs = parser.grenade_trajectories()
        print(f"  {len(trajs)} trajectories in {time.time()-t17:.1f}s")
    except Exception as e:
        print(f"  grenade_trajectories failed: {e}")

    # Step 18: player_round_stats (known hang without specific ticks)
    print("\n[18] Player round stats...")
    print("  WARNING: player_round_stats() without specific_ticks parses ALL ticks - SKIPPING")
    print("  This is the root cause of the hang. Fix needed in bundle.py")

print("\n[ALL DONE]")
print(f"  Total time: {time.time()-t0:.1f}s")
