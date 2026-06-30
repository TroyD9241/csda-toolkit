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
from csda_toolkit.db.models import (
    Kill, Round, MatchPlayer, PlayerRoundStats, DamageEvent, PlayerBlind,
)
from csda_toolkit.classifiers.hltv_rating import (
    compute_hltv_rating, compute_match_rating, compute_round_swing,
    HltvRoundSignals,
)

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
        damage_events_all = session.execute(
            select(DamageEvent).where(DamageEvent.match_id == match_id).order_by(DamageEvent.tick)
        ).scalars().all()
        blind_events_all = session.execute(
            select(PlayerBlind).where(PlayerBlind.match_id == match_id).order_by(PlayerBlind.tick)
        ).scalars().all()

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
        awp_kill_count: dict[int, int] = defaultdict(int)
        for k in kills:
            if k.killer_steam_id: kill_count[k.killer_steam_id] += 1
            if k.victim_steam_id: death_count[k.victim_steam_id] += 1
            if k.killer_steam_id and k.weapon_name and "awp" in k.weapon_name.lower():
                awp_kill_count[k.killer_steam_id] += 1

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
            damage_total = max((ps.damage or 0) for ps in prs_rows) if prs_rows else 0
            kast_rounds = count_kast_rounds(kills, sid, steam_to_side, rounds)
            mk_rounds = count_mk_rounds(kills, sid, rounds)
            awp_kills = awp_kill_count.get(sid, 0)

            # ── Three ADR scaling approaches ──────────────────────────────
            # Base ADR from PRS (no scaling)
            adr_base = damage_total / R

            # Approach 1: Global scale 1.12
            GLOBAL_SCALE = 1.12
            adr_global = adr_base * GLOBAL_SCALE

            # Approach 2: Per-role scale (simple AWP detection)
            # AWPer (has 2+ AWP kills): 1.14, Rifler/Support (default): 1.10
            ROLE_SCALE_AWP = 1.14
            ROLE_SCALE_DEFAULT = 1.10
            if awp_kills >= 2:
                role_scale = ROLE_SCALE_AWP
                role_label = "AWPer"
            else:
                role_scale = ROLE_SCALE_DEFAULT
                role_label = "Rifler"
            adr_per_role = adr_base * role_scale

            # Approach 3: Hybrid (base + utility bonus, then scale)
            UTILITY_BONUS_ADR = 5.0   # fixed +5 ADR
            HYBRID_SCALE = 1.09
            adr_hybrid = (adr_base + UTILITY_BONUS_ADR) * HYBRID_SCALE

            # ── Swing computation with credit splitting ────────────────────
            # Sum K*ΔWP*credit_share across all rounds, then divide by R.
            # K=64 (per recovered formula); killer_credit=0.5 by default.
            swing_total = 0.0
            all_player_sids = list(steam_to_side.keys())
            for rd in rounds:
                rs, re = rd.start_tick, rd.end_tick or rd.start_tick + 99999
                swing_total += compute_round_swing(
                    kills, sid, steam_to_side, rs, re,
                    damage_events=damage_events_all,
                    blind_events=blind_events_all,
                    killer_credit=0.5,
                    all_player_sids=all_player_sids,
                )
            # Convert to %: per recovered formula swing ≈ (1/R) * Σ(K*ΔWP)
            # K=64 with ΔWP in 0-1 range gives values in 0-64; HLTV swing%
            # is in 0-100 range, so multiply by (100/64) for % units.
            computed_swing_pct = (swing_total / R) * (100.0 / 64.0)

            # Match-level inputs (use global scale as the "primary" ADR)
            eKPR = kills_n / R
            eDPR = deaths_n / R
            eKAST = kast_rounds / R
            mk_per_r = mk_rounds / R

            # Compute ratings for all 3 ADR approaches (swing=0 for all)
            def _rating_with_adr(adr_val, swing_val=0.0):
                return (
                    0.1358
                    + 0.4941 * eKPR
                    + 0.3795 * (1.0 - eDPR)
                    + 0.4280 * (adr_val / 100.0)
                    + 0.2602 * eKAST
                    + 0.03748 * swing_val
                    + 0.0241 * mk_per_r
                )

            # Approach 0: raw PRS (no scaling)
            rating_raw = _rating_with_adr(adr_base)
            # Approach 1: global scale
            rating_global = _rating_with_adr(adr_global)
            # Approach 2: per-role scale
            rating_per_role = _rating_with_adr(adr_per_role)
            # Approach 3: hybrid
            rating_hybrid = _rating_with_adr(adr_hybrid)

            # Rating with computed swing (credit-splitting, K=64)
            rating_global_our_swing = _rating_with_adr(adr_global, computed_swing_pct)
            rating_raw_our_swing = _rating_with_adr(adr_base, computed_swing_pct)

            # Primary "display" rating uses global scale
            rating = rating_global
            eADR = adr_global
            rating_with_swing = rating + 0.03748 * ref['swing']
            rating_global_swing = rating_global + 0.03748 * ref['swing']
            rating_hybrid_swing = rating_hybrid + 0.03748 * ref['swing']
            rating_per_role_swing = rating_per_role + 0.03748 * ref['swing']

            diff = rating - ref['rating']
            diff_with_swing = rating_with_swing - ref['rating']
            hltv_mks = ref['mks']
            mk_diff = mk_rounds - hltv_mks

            results.append((
                name, rating, ref, diff, eKPR, eDPR, eADR, eKAST, mk_rounds, mk_diff,
                rating_with_swing, diff_with_swing,
                adr_base, adr_global, adr_per_role, adr_hybrid,
                role_label, awp_kills,
                rating_raw, rating_global, rating_per_role, rating_hybrid,
                rating_raw + 0.03748 * ref['swing'],
                rating_global_swing, rating_per_role_swing, rating_hybrid_swing,
                computed_swing_pct,
                rating_global_our_swing,
                rating_raw_our_swing,
            ))
            print(f"{name[:10]:10s} {rating:>8.3f} {ref['rating']:>6.2f} {diff:>+7.3f} | "
                  f"{eKPR:>5.3f} {eDPR:>5.3f} {eADR:>6.1f} {eKAST:>6.3f} {mk_rounds:>4d} {hltv_mks:>7d} ({mk_diff:+d})")

        # Summary — index legend:
        # 0=name, 1=rating, 2=ref, 3=diff, 4-7=stats, 8-9=MK,
        # 10-11=with_swing, 12-15=ADRs, 16-17=role/awp,
        # 18=raw_rating, 19=global_rating, 20=per_role_rating, 21=hybrid_rating,
        # 22=raw+swing, 23=global+swing, 24=per_role+swing, 25=hybrid+swing
        print()
        print("=" * 100)
        print("SUMMARY — 4 ADR APPROACHES")
        print("=" * 100)
        adr_approaches = [
            ("raw PRS",    18, 22),  # raw_rating, raw+swing
            ("global *1.12", 19, 23),
            ("per-role",   20, 24),
            ("hybrid",     21, 25),
        ]
        print("Without HLTV swing:")
        for label, ridx, _ in adr_approaches:
            abs_diffs = [abs(r[ridx] - r[2]['rating']) for r in results]
            print(f"  {label:14s}: mean abs diff={sum(abs_diffs)/len(abs_diffs):.3f}  max={max(abs_diffs):.3f}")
        print("With HLTV swing:")
        for label, _, sidx in adr_approaches:
            abs_diffs = [abs(r[sidx] - r[2]['rating']) for r in results]
            print(f"  {label:14s}: mean abs diff={sum(abs_diffs)/len(abs_diffs):.3f}  max={max(abs_diffs):.3f}")

        print()
        print("Per-player ADR comparison:")
        print(f"{'Player':10s} {'Role':>7s} {'AWP':>4s} {'PRS':>7s} {'glob*1.12':>10s} {'per-role':>9s} {'hybrid':>8s} {'HLTV':>6s}")
        print("-" * 80)
        for r in results:
            name = r[0]
            role = r[16]
            awp = r[17]
            base_adr = r[12]
            global_adr = r[13]
            pr_adr = r[14]
            hyb_adr = r[15]
            hltv_adr = r[2]['adr']
            print(f"{name[:10]:10s} {role:>7s} {awp:>4d} {base_adr:>7.1f} {global_adr:>10.1f} {pr_adr:>9.1f} {hyb_adr:>8.1f} {hltv_adr:>6.1f}")

        # Index legend (updated):
        # 0=name, 1=rating, 2=ref, 3=diff, 4-7=stats, 8-9=MK,
        # 10-11=with_swing, 12-15=ADRs, 16-17=role/awp,
        # 18=raw_rating, 19=global_rating, 20=per_role_rating, 21=hybrid_rating,
        # 22=raw+swing, 23=global+swing, 24=per_role+swing, 25=hybrid+swing,
        # 26=computed_swing_pct, 27=global_our_swing, 28=raw_our_swing
        print()
        print("=" * 100)
        print("SWING COMPARISON (credit-splitting, K=64, 50% killer credit)")
        print("=" * 100)
        print(f"{'Player':10s} {'Ours':>8s} {'HLTV':>8s} {'Diff':>7s} {'Rtg_our_sw':>10s} {'Rtg_HLTV_sw':>11s} {'Diff':>7s}")
        print("-" * 80)
        swing_diffs = []
        rating_diffs = []
        for r in results:
            name = r[0]
            our_swing = r[26]
            hltv_swing = r[2]['swing']
            our_rating = r[27]  # global + our computed swing
            hltv_rating = r[2]['rating']
            swing_d = our_swing - hltv_swing
            rating_d = our_rating - hltv_rating
            swing_diffs.append(abs(swing_d))
            rating_diffs.append(abs(rating_d))
            print(f"{name[:10]:10s} {our_swing:>+8.2f} {hltv_swing:>+8.2f} {swing_d:>+7.2f} {our_rating:>10.3f} {hltv_rating:>11.2f} {rating_d:>+7.3f}")
        print()
        print(f"Swing mean abs diff:  {sum(swing_diffs)/len(swing_diffs):.2f}%")
        print(f"Rating mean abs diff: {sum(rating_diffs)/len(rating_diffs):.3f} (with OUR computed swing vs HLTV)")

        print()
        print("Per-player rating with HLTV swing (sanity check):")
        print(f"{'Player':10s} {'raw':>6s} {'glob*1.12':>10s} {'per-role':>9s} {'hybrid':>8s} {'HLTV':>6s}")
        print("-" * 60)
        for r in results:
            name = r[0]
            rraw = r[22]
            rg = r[23]
            rpr = r[24]
            rh = r[25]
            hltv = r[2]['rating']
            print(f"{name[:10]:10s} {rraw:>6.2f} {rg:>10.2f} {rpr:>9.2f} {rh:>8.2f} {hltv:>6.2f}")

        print()
        print("Known gaps vs HLTV:")
        print("  • Swing% not computed (real HLTV uses signed win-prob deltas; we don't have exact formula)")
        print("  • KAST traded: cmtry/coolio have 1-3 overcounted rounds")
        print("  • ADR scaling: 3 approaches tested (global *1.12, per-role, hybrid base+5 *1.09)")


if __name__ == "__main__":
    main()
