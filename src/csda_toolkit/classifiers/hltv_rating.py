"""HLTV3 Rating — reverse-engineered from ML analysis of official formula.

Reference: HLTV 3.0 (photo from @n3c1k / x.com)

Formula:
    rating = 0.1358
           + 0.4941 * eKPR
           + 0.3795 * (1 - eDPR)
           + 0.4280 * (eADR / 100)
           + 0.2602 * (eKAST / 100)
           + 0.03748 * Swing_pct
           + 0.0241 * MK_R

Where:
- eKPR  = eco-adjusted Kills Per Round
- eDPR  = eco-adjusted Deaths Per Round
- eADR  = eco-adjusted Average Damage per Round
- eKAST = eco-adjusted % of rounds with K/A/S/T (0-100)
- Swing_pct = round swing averaged per round, expressed as percentage (0-100)
- MK_R  = multi-kills per round (2+ kills in rapid succession)

For now, e-prefixed values are taken as raw per-round stats. Full implementation
would adjust for buy-type economy context.

Round Swing:
    Swing = (1/R) * Σ(K * ΔWP)
    K ≈ 64 (scaling constant)
    ΔWP = win_prob(after) - win_prob(before)  [from player-count grid]

Win-probability grid (recovered table):
    5v5≈50%, 5v4≈60%, 5v3≈72%, 5v2≈85%, 5v1≈94%
    4v4≈50%, 4v3≈60%, 4v2≈75%, 4v1≈88%
    3v3≈50%, 3v2≈62%, 3v1≈78%
    2v2≈50%, 2v1≈65%
    1v1≈50%, 1v0≈100%
"""

import math
from dataclasses import dataclass


# ── Win-probability grid ───────────────────────────────────────────────────────
# [players_alive_on_your_side][opponents_alive]
# Symmetric: your 3 vs opp 2 = opp's 2 vs your 3 → same probability
WIN_PROB_GRID: list[list[float]] = [
    # 0     1     2     3     4     5  (opponents alive)
    [0.000, 0.00, 0.00, 0.00, 0.00, 0.00],  # 0 you
    [0.000, 0.50, 0.65, 0.78, 0.88, 0.94],  # 1 you
    [0.000, 0.35, 0.50, 0.62, 0.75, 0.88],  # 2 you
    [0.000, 0.22, 0.38, 0.50, 0.60, 0.72],  # 3 you
    [0.000, 0.12, 0.25, 0.40, 0.50, 0.60],  # 4 you
    [0.000, 0.06, 0.15, 0.28, 0.40, 0.50],  # 5 you  ← FIXED: was backwards
]


def win_prob(my_alive: int, opp_alive: int) -> float:
    """Look up win probability from the grid."""
    my_alive = max(0, min(5, my_alive))
    opp_alive = max(0, min(5, opp_alive))
    return WIN_PROB_GRID[my_alive][opp_alive]


def compute_round_swing(
    kills: list,
    steam_id: int,
    steam_to_side: dict[int, str],
    round_start: int,
    round_end: int,
) -> float:
    """Compute Swing for a player in one round.

    Swing = Σ(K * ΔWP)
    For each kill the player made:
        ΔWP = win_prob(after) - win_prob(before)
    Uses all kills in the round to track alive state correctly.
    """
    K = 64.0

    # ALL kills in the round (to track alive state)
    all_round_kills = [
        k for k in kills
        if round_start < k.tick <= round_end
    ]

    player_round_kills = [
        k for k in all_round_kills
        if k.killer_steam_id == steam_id
    ]

    if not player_round_kills:
        return 0.0

    player_side = steam_to_side.get(steam_id)
    if player_side is None:
        return 0.0

    # Collect all players who appear in any kill in the round
    all_steam_ids: set[int] = set()
    for k in all_round_kills:
        if k.killer_steam_id:
            all_steam_ids.add(k.killer_steam_id)
        if k.victim_steam_id:
            all_steam_ids.add(k.victim_steam_id)

    # Initialize: everyone in the round starts alive
    alive: dict[int, bool] = {sid: True for sid in all_steam_ids}
    swing_sum = 0.0

    for k in sorted(all_round_kills, key=lambda x: x.tick):
        my_alive_before = sum(
            1 for sid in all_steam_ids
            if alive.get(sid, False) and steam_to_side.get(sid) == player_side
        )
        opp_alive_before = sum(
            1 for sid in all_steam_ids
            if alive.get(sid, False) and steam_to_side.get(sid) != player_side
        )

        # Apply the kill (victim dies)
        victim = k.victim_steam_id
        if victim in alive:
            alive[victim] = False

        my_alive_after = sum(
            1 for sid in all_steam_ids
            if alive.get(sid, False) and steam_to_side.get(sid) == player_side
        )
        opp_alive_after = sum(
            1 for sid in all_steam_ids
            if alive.get(sid, False) and steam_to_side.get(sid) != player_side
        )

        # Only accumulate swing for this player's own kills
        if k.killer_steam_id == steam_id:
            # GRID returns OPPONENT win probability, so we flip:
            # Kill reduces opp_wp → my win chance increases → positive swing
            opp_wp_before = win_prob(my_alive_before, opp_alive_before)
            opp_wp_after = win_prob(my_alive_after, opp_alive_after)
            swing_sum += K * (opp_wp_before - opp_wp_after)

    return swing_sum


# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class HltvRoundSignals:
    """All per-round signals needed to compute HLTV3 rating for one player in one round."""
    steam_id: int
    round_number: int

    # Core stats
    kills: int
    deaths: int
    rounds_played: int        # total rounds in match (denominator for per-round rates)
    adr: float                # average damage per round (dealt)
    dpr: float                # average damage received per round
    assists: int              # total assists (for APR)
    headshot_kills: int

    # KAST
    kast_rounds: int          # rounds where player had K/A/S/T

    # Economy-adjusted (raw per-round for now; full impl adjusts by buy type)
    eKPR: float              # eco-adjusted KPR
    eDPR: float              # eco-adjusted DPR
    eADR: float             # eco-adjusted ADR
    eKAST: float            # eco-adjusted KAST%

    # Contextual
    swing_pct: float         # round swing as percentage (0-100)
    mk_per_round: float     # multi-kills per round


@dataclass
class HltvRoundRating:
    """HLTV3 rating components for one round."""
    steam_id: int
    round_number: int
    kpr: float
    dpr: float
    adr: float
    kast: float
    apr: float
    swing_pct: float
    mk_per_round: float
    rating: float


# ── Core computation ───────────────────────────────────────────────────────────


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_hltv_rating(signals: HltvRoundSignals) -> HltvRoundRating:
    """Compute HLTV3 rating for a player in one round.

    Formula:
        rating = 0.1358
               + 0.4941 * eKPR
               + 0.3795 * (1 - eDPR)
               + 0.4280 * (eADR / 100)
               + 0.2602 * eKAST          # eKAST is already a 0-1 ratio (e.g., 0.789 for 78.9%)
               + 0.03748 * Swing_pct
               + 0.0241 * MK_R
    """
    r = signals
    n = r.rounds_played if r.rounds_played > 0 else 1

    kpr = r.kills / n
    apr = r.assists / n
    kast = r.kast_rounds / n if r.kast_rounds > 0 else 0.0

    rating = (
        0.1358
        + 0.4941 * r.eKPR
        + 0.3795 * (1.0 - r.eDPR)
        + 0.4280 * (r.eADR / 100.0)
        + 0.2602 * r.eKAST
        + 0.03748 * r.swing_pct
        + 0.0241 * r.mk_per_round
    )

    return HltvRoundRating(
        steam_id=r.steam_id,
        round_number=r.round_number,
        kpr=round(kpr, 3),
        dpr=round(r.dpr, 3),
        adr=round(r.adr, 3),
        kast=round(kast, 3),
        apr=round(apr, 3),
        swing_pct=round(r.swing_pct, 3),
        mk_per_round=round(r.mk_per_round, 3),
        rating=round(rating, 3),
    )


def compute_match_rating(round_ratings: list[HltvRoundRating]) -> float:
    """Average of per-round ratings. HLTV match rating = mean of all per-round ratings."""
    if not round_ratings:
        return 0.0
    return round(sum(r.rating for r in round_ratings) / len(round_ratings), 3)


# ── Utility damage helpers ───────────────────────────────────────────────────

# Utility weapons tracked for utility_damage_to_opponents filter.
# These are the grenade types whose damage appears in m_iUtilityDamage in PRS
# (and in dmg_health on DamageEvent rows with these weapon strings).
_UTILITY_WEAPON_PREFIXES = (
    "hegrenade", "flashbang", "smokegrenade", "molotov", "incendiary",
    "decoy", "inferno",
)


def is_utility_weapon(weapon: str) -> bool:
    """True if the weapon string identifies a thrown utility (grenade/molotov/etc)."""
    if not weapon:
        return False
    return weapon.lower().startswith(_UTILITY_WEAPON_PREFIXES)


def compute_utility_dmg_to_opponents(
    damage_events,
    steam_to_side: dict,
    target_sid: int,
) -> int:
    """Sum utility damage dealt by target_sid to opponents (excludes self/teammate).

    Filters DamageEvent rows where:
      - attacker is target_sid
      - victim is a different player (no self-damage)
      - victim is on the opposite team (no teammate damage)
      - weapon is a thrown utility (grenade/molotov/etc)

    Note: DamageEvent.dmg_health is RAW and not HP-capped, so this may overshoot
    HLTV's capped damage for players with frequent overkill. Pair with HP-capping
    when victim-HP state is reliably available.
    """
    total = 0
    for ev in damage_events:
        if ev.attacker_steam_id != target_sid:
            continue
        if not ev.victim_steam_id:
            continue
        if ev.attacker_steam_id == ev.victim_steam_id:
            continue  # no self-damage
        a_side = steam_to_side.get(ev.attacker_steam_id)
        v_side = steam_to_side.get(ev.victim_steam_id)
        if a_side is None or v_side is None or a_side == v_side:
            continue  # no teammate damage
        if not is_utility_weapon(ev.weapon or ""):
            continue
        total += ev.dmg_health or 0
    return total
