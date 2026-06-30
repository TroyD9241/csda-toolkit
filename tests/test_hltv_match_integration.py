"""Match-level HLTV 3.0 rating test (no per-round averaging).

Since the exact HLTV swing% formula is undocumented, this test sets swing to 0
and treats the result as a baseline for our own analysis.

Formula:
    rating = 0.1358 + 0.4941*eKPR + 0.3795*(1-eDPR) + 0.4280*(eADR/100)
           + 0.2602*eKAST + 0.03748*Swing% + 0.0241*MK/R

Run with:  py test_hltv_rating.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select
from collections import defaultdict
from csda_toolkit.db.database import Database
from csda_toolkit.db.models import Kill, Round, MatchPlayer, PlayerRoundStats

DB_URL = os.environ.get("DATABASE_URL", "postgresql://csda:csda@localhost:5432/csda")
db = Database(DB_URL)

TRADE_WINDOW_TICKS = 320  # ~5 sec at 64 tick

# HLTV reference (Map 1, Mirage)
HLTV_REF = {
    'mezii':    {'kd': '17-9', 'mks': 5, 'kast': 78.9, 'swing': 11.65, 'adr': 89.8, 'rating': 1.81},
    'apEX':     {'kd': '15-10', 'mks': 4, 'kast': 78.9, 'swing': 1.51,  'adr': 96.2, 'rating': 1.26},
    'ropz':     {'kd': '15-10', 'mks': 3, 'kast': 78.9, 'swing': 1.06,  'adr': 87.5, 'rating': 1.22},
    'flameZ':   {'kd': '14-12', 'mks': 3, 'kast': 78.9, 'swing': 0.73,  'adr': 79.2, 'rating': 1.06},
    'ZywOo':    {'kd': '16-14', 'mks': 4, 'kast': 73.7, 'swing': -1.63, 'adr': 71.9, 'rating': 0.92},
    'dem0n':    {'kd': '17-13', 'mks': 5, 'kast': 89.5, 'swing': 4.84,  'adr': 96.1, 'rating': 1.70},
    'dziugss':  {'kd': '10-15', 'mks': 3, 'kast': 68.4, 'swing': -4.78, 'adr': 69.9, 'rating': 0.86},
    'Krabeni':  {'kd': '11-17', 'mks': 2, 'kast': 63.2, 'swing': -6.23, 'adr': 68.1, 'rating': 0.80},
    'cmtry':    {'kd': '11-17', 'mks': 3, 'kast': 42.1, 'swing': -3.27, 'adr': 54.7, 'rating': 0.74},
    'coolio':   {'kd': '6-15',  'mks': 0, 'kast': 57.9, 'swing': -3.87, 'adr': 47.2, 'rating': 0.65},
}


def parse_kd(s):
    k, d = s.split('-')
    return int(k), int(d)


def count_kast_rounds(kills, player_steam_id, steam_to_side, rounds):
    kast = 0
    for rd in rounds:
        rs, re = rd.start_tick, rd.end_tick or rd.start_tick + 99999
        ps = steam_to_side.get(player_steam_id)
        if not ps:
            continue
        pk = [k for k in kills if k.killer_steam_id == player_steam_id and rs < k.tick <= re]
        pd = [k for k in kills if k.victim_steam_id == player_steam_id and rs < k.tick <= re]
        pa = [k for k in kills if k.assister_steam_id == player_steam_id and rs < k.tick <= re]
        if pk or pa:
            kast += 1
            continue
        if not pd:
            kast += 1
            continue
        # Traded: teammate killed your killer within window
        dt = max(k.tick for k in pd)
        vkiller = pd[0].killer_steam_id
        avenged = any(
            k for k in kills
            if k.victim_steam_id == vkiller
            and steam_to_side.get(k.killer_steam_id) == ps
            and k.killer_steam_id != player_steam_id
            and dt < k.tick <= min(re, dt + TRADE_WINDOW_TICKS)
        )
        if avenged:
            kast += 1
    return kast


def count_mk_rounds(kills, player_steam_id, rounds):
    """Count rounds with multi-kills (2+ kills)."""
    mk = 0
    for rd in rounds:
        rs, re = rd.start_tick, rd.end_tick or rd.start_tick + 99999
        n = sum(1 for k in kills if k.killer_steam_id == player_steam_id and rs < k.tick <= re)
        if n >= 2:
            mk += 1
    return mk


def main():
    print("=== Match-Level HLTV 3.0 Rating Test (Map 1: Mirage) ===\n")

    with db.session() as session:
        match_id = 1
        kills = session.execute(select(Kill).where(Kill.match_id == match_id).order_by(Kill.tick)).scalars().all()
        rounds = session.execute(select(Round).where(Round.match_id == match_id).order_by(Round.round_number)).scalars().all()
        player_stats = session.execute(select(PlayerRoundStats).where(PlayerRoundStats.match_id == match_id)).scalars().all()

        player_names: dict[int, str] = {}
        steam_to_side: dict[int, str] = {}
        for mp in session.execute(select(MatchPlayer).where(MatchPlayer.match_id == match_id)).scalars().all():
            sid = mp.steam_id
            player_names[sid] = mp.display_name or f"steam_{sid}"
            if mp.team_side:
                steam_to_side[sid] = mp.team_side.lower()

        # K/D/assists from Kill table
        kill_count: dict[int, int] = defaultdict(int)
        death_count: dict[int, int] = defaultdict(int)
        for k in kills:
            if k.killer_steam_id: kill_count[k.killer_steam_id] += 1
            if k.victim_steam_id: death_count[k.victim_steam_id] += 1

        # PRS damage (max cumulative = total match damage)
        prs_by_player: dict[int, list[PlayerRoundStats]] = defaultdict(list)
        for ps in player_stats:
            prs_by_player[ps.steam_id].append(ps)
        for sid in prs_by_player:
            prs_by_player[sid].sort(key=lambda p: p.round_number)

        R = float(len(rounds))

        print(f"{'Player':10s} {'OursRtg':>8s} {'HLTV':>6s} {'Diff':>7s} | "
              f"{'eKPR':>5s} {'eDPR':>5s} {'eADR':>6s} {'eKAST':>6s} {'MKs':>4s} {'HLTV_MK':>7s}")
        print("-" * 100)

        results = []
        for name, ref in sorted(HLTV_REF.items(), key=lambda x: x[1]['rating'], reverse=True):
            sid = next((s for s, n in player_names.items() if n.lower() == name.lower()), None)
            if not sid:
                print(f"{name}: NOT FOUND IN DB")
                continue

            # Match-level stats
            kills_n = kill_count.get(sid, 0)
            deaths_n = death_count.get(sid, 0)
            prs_rows = prs_by_player.get(sid, [])
            # ADR from PRS weapon damage (m_iDamage from ActionTrackingServices)
            # Most reliable cross-match baseline. See adr_filtered_util.py for
            # utility_damage helpers and the self-damage filter (available for
            # future use; not applied here due to cross-match overshoot issues).
            damage_total = max((ps.damage or 0) for ps in prs_rows) if prs_rows else 0
            kast_rounds = count_kast_rounds(kills, sid, steam_to_side, rounds)
            mk_rounds = count_mk_rounds(kills, sid, rounds)

            # Match-level inputs
            eKPR = kills_n / R
            eDPR = deaths_n / R
            eADR = damage_total / R
            eKAST = kast_rounds / R  # 0-1 ratio
            mk_per_r = mk_rounds / R  # multi-kill rounds / total rounds

            # Match-level rating (single application, no per-round averaging)
            # NOTE: swing set to 0 since exact formula is unknown; user treats rating as baseline
            rating = (
                0.1358
                + 0.4941 * eKPR
                + 0.3795 * (1.0 - eDPR)
                + 0.4280 * (eADR / 100.0)
                + 0.2602 * eKAST
                + 0.03748 * 0.0   # swing = 0 (baseline only)
                + 0.0241 * mk_per_r
            )

            # Sanity check: what if we use HLTV's reported swing directly?
            rating_with_swing = rating + 0.03748 * ref['swing']

            diff = rating - ref['rating']
            diff_with_swing = rating_with_swing - ref['rating']
            hltv_mks = ref['mks']
            mk_diff = mk_rounds - hltv_mks

            results.append((name, rating, ref, diff, eKPR, eDPR, eADR, eKAST, mk_rounds, mk_diff, rating_with_swing, diff_with_swing))
            print(f"{name[:10]:10s} {rating:>8.3f} {ref['rating']:>6.2f} {diff:>+7.3f} | "
                  f"{eKPR:>5.3f} {eDPR:>5.3f} {eADR:>6.1f} {eKAST:>6.3f} {mk_rounds:>4d} {hltv_mks:>7d} ({mk_diff:+d})")

        # Summary
        print()
        print("=" * 80)
        print("SUMMARY (swing=0 baseline)")
        print("=" * 80)
        abs_diffs = [abs(r[3]) for r in results]
        abs_diffs_with_swing = [abs(r[11]) for r in results]
        print(f"Mean abs diff vs HLTV (swing=0):        {sum(abs_diffs)/len(abs_diffs):.3f}")
        print(f"Mean abs diff vs HLTV (with HLTV swing): {sum(abs_diffs_with_swing)/len(abs_diffs_with_swing):.3f}")
        print(f"Max abs diff (swing=0):                 {max(abs_diffs):.3f}")
        print(f"Max abs diff (with HLTV swing):         {max(abs_diffs_with_swing):.3f}")
        print()
        print("Per-player with HLTV swing (sanity check):")
        for r in results:
            name, rating, ref, diff, eKPR, eDPR, eADR, eKAST, mk_rounds, mk_diff, rating_with_swing, diff_with_swing = r
            print(f"  {name[:10]:10s}: base={rating:.3f}  with_swing={rating_with_swing:.3f}  HLTV={ref['rating']:.2f}  (swing={ref['swing']:+.2f}%)")
        print()
        print("Known gaps vs HLTV:")
        print("  • Swing% not computed (real HLTV uses signed win-prob deltas; we don't have exact formula)")
        print("  • ADR: PRS damage for mezii is 82.9 vs HLTV 89.8 (PRS undercounts)")
        print("  • KAST traded: cmtry/coolio have 1-3 overcounted rounds")


if __name__ == "__main__":
    main()
