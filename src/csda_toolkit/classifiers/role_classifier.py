"""Role classifier — infer player tactical role from signals across a match.

Role is NOT a static player attribute. It is classified per (player, map, side, match)
based on behavioral signals from kills, weapons, utility, and positions.

CLASSIFICATION AXES
===================
role_broad       — High-level identity: entry, awper, igl, rifler, lurker, support, etc.
role_map_{name}  — Map-specific position on map {name} (e.g. long_a, mid, banana)
role_zone        — Tactical zone: a_anchor, b_anchor, mid_control, flanker, etc.
role_secondary   — Optional modifier: second_awper, trade_fragger, second_caller, etc.

SIGNAL SOURCES
==============
1. Kills       — first kill (entry), AWP kill (awper), trade (rifler), lurk kill (lurker)
2. Weapons     — AWP frequency, rifle/smg mix, pistol (eco round)
3. Utility    — grenade count, flash assist, smoke zone
4. Position   — where player spends time (from position_classifier)
5. Economy    — buy type consistency (full buy = serious round, eco = save)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from csda_toolkit.classifiers.role_taxonomy import (
    BROAD_ROLES,
    ROLE_DESCRIPTIONS,
    MAPS,
    MAP_ZONES,
    MAP_POSITIONS,
    ROLE_POSITION_PREFERENCES,
    ZONE_ROLES,
    RoleClassificationResult,
)


# ── Signal weight constants ────────────────────────────────────────────────────

# Kill signals
ENTRY_KILL_BONUS    = 0.30   # First blood
AWP_KILL_BONUS     = 0.35   # Kill with AWP
LURK_KILL_BONUS    = 0.30   # Kill from isolated position
TRADE_KILL_BONUS   = 0.20   # Kill within 5s of teammate dying
IGL_LEAD_BONUS     = 0.25   # IGL gets credit for round win

# Position signals
POSITION_WEIGHT    = 0.20   # Weight for position preference match
ANCHOR_BONUS       = 0.25   # Staying on site at round start
ROTATOR_BONUS      = 0.20   # Moving between sites mid-round

# Utility signals
UTILITY_WEIGHT     = 0.15   # Weight for utility usage
FLASH_ASSIST_BONUS = 0.15   # Flashes that blind enemies (nearby flashbang)
HE_DAMAGE_BONUS    = 0.15   # HE grenade damage
SMOKE_ZONE_BONUS   = 0.10   # Smoking a key area

# Weapon signals
AWP_WEIGHT         = 0.35   # Primary weapon = AWP
RIFLE_WEIGHT       = 0.15   # Primary weapon = rifle
SUPPORT_WEAPON     = 0.15   # SMG/shotgun = support tendencies

# Minimum evidence thresholds
MIN_ENTRY_KILLS    = 3      # Minimum first-bloods to claim entry
MIN_AWP_KILLS      = 3      # Minimum AWP kills to claim awper
MIN_LURK_KILLS     = 2      # Minimum lurk kills to claim lurker
MIN_SUPPORT_EVENTS  = 5      # Minimum utility events to claim support
MIN_ROUNDS         = 5      # Minimum rounds to classify


# ── Input structures ───────────────────────────────────────────────────────────

@dataclass
class PlayerKillProfile:
    """Aggregated kill stats for one player across a match (or a map)."""
    steam_id: int
    total_kills: int = 0
    first_bloods: int = 0       # First kill in a round (core entry metric)
    awp_kills: int = 0
    lurk_kills: int = 0       # Kills from isolated/flanking positions
    trade_kills: int = 0     # Kills within 5s of teammate dying
    entry_kills: int = 0      # First into site (multi-kill rounds)
    trade_opportunities: int = 0  # Died within 8s of getting kill → enabled trade
    deaths: int = 0
    assists: int = 0


@dataclass
class PlayerWeaponProfile:
    """Weapon usage profile for one player."""
    steam_id: int
    awp_picks: int = 0
    rifle_picks: int = 0
    smg_picks: int = 0
    pistol_picks: int = 0
    shotgun_picks: int = 0
    total_rounds: int = 0


@dataclass
class PlayerUtilityProfile:
    """Utility usage profile for one player."""
    steam_id: int
    flashes_thrown: int = 0
    flashes_enemy_hit: int = 0    # Flashes that contributed to a kill
    he_detonations: int = 0
    he_damage_dealt: float = 0.0
    smokes_thrown: int = 0
    mollies_thrown: int = 0
    total_utility_score: float = 0.0


@dataclass
class PlayerPositionProfile:
    """Aggregated position profile for one player on one map."""
    steam_id: int
    map_name: str
    side: str
    position_counts: dict[str, int] = field(default_factory=dict)  # pos_key → count
    zone_counts: dict[str, int] = field(default_factory=dict)       # zone → count
    rounds_played: int = 0
    anchor_rounds: int = 0    # Rounds spent on same site at round start
    rotator_rounds: int = 0   # Rounds with position changes between sites


@dataclass
class PlayerEconomyProfile:
    """Buy pattern for one player."""
    steam_id: int
    full_buy_rounds: int = 0
    eco_rounds: int = 0
    force_rounds: int = 0
    avg_equipment_value: float = 0.0


@dataclass
class EntryFraggerProfile:
    """Entry fragger-specific quality metrics — how well a player performs the entry role.

    These metrics go beyond role *detection* to measure entry fragger *effectiveness*.
    All per-round metrics are computed over the full match.

    Quality signals
    ---------------
    entry_attempts : int
        Rounds where the player either (a) got the first kill, or (b) died first
        as the apparent first attacker. Denominator for entry success rate.
    successful_entries : int
        Entry attempts where player got at least one kill.
    entry_deaths_no_kill : int
        Entry attempts where player died WITHOUT getting a kill (bomb-site disaster).
    entry_kill_rate : float
        successful_entries / entry_attempts — core entry efficiency metric.
        Good: 40%+. Average: 25-40%. Below 25% = entry liability.
    flash_pop_kills : int
        Kills that were flash-assisted (teammate threw flash within 3s before kill).
        High flash-pop rate = coordinated entry duo with support player.
    opening_duel_wins : int
        Rounds where the player won the first duel (got first kill, no one else died first).
    opening_duel_win_rate : float
        opening_duel_wins / total_rounds. Top entries: 50%+.
    rounds_survived_post_entry : int
        Rounds where player got an entry kill AND survived the rest of the round.
        High = good positioning, not just a sacrificial lamb.
    avg_kills_per_entry_round : float
        total_kills_in_entry_rounds / rounds_with_entry_attempt.
        Above 1.0 = multi-kill entry potential.
    """
    steam_id: int
    entry_attempts: int = 0
    successful_entries: int = 0        # Got a kill in the entry attempt
    entry_deaths_no_kill: int = 0       # Died without getting the entry kill
    flash_pop_kills: int = 0            # Flash-assisted entry kills
    opening_duel_wins: int = 0          # Won the opening duel
    rounds_survived_post_entry: int = 0  # Survived after getting entry kill
    total_kills_in_entry_rounds: int = 0  # All kills in rounds with entry attempts
    rounds_with_entry_attempt: int = 0   # Rounds that had an entry attempt


@dataclass
class AwperProfile:
    """AWPer-specific quality metrics — how well a player performs the AWP role.

    Quality signals
    ---------------
    awp_rounds : int
        Total rounds where the player had an AWP equipped.
    first_pick_rounds : int
        Rounds where the AWP got the FIRST kill of the round (opening pick).
    opening_pick_rate : float
        first_pick_rounds / awp_rounds. Top AWPers: 35%+ (every ~3 rounds a first pick).
    ct_hold_picks : int
        CT-side rounds where AWP got a pick that held the site.
    ct_hold_rate : float
        ct_hold_picks / (CT-side awp_rounds). High = consistent site anchor.
    ct_survived_after_pick : int
        Rounds where AWP got a CT-side pick AND survived the round.
        "Get one, fall back" discipline — high = elite AWP.
    ct_survival_rate : float
        ct_survived_after_pick / ct_hold_picks. Top AWPers: 60%+.
    t_first_pick_rounds : int
        T-side rounds where AWP got the first kill during execute.
    t_first_pick_rate : float
        t_first_pick_rounds / (T-side awp_rounds). Top T-side AWPers: 25%+.
    t_survived_after_pick : int
        T-side rounds where AWP survived after getting first pick.
    t_survival_rate : float
        t_survived_after_pick / t_first_pick_rounds.
    awp_deaths_on_eco : int
        Rounds where AWP player died on eco/force — economic waste.
    awp_saves : int
        Rounds where AWP survived an lost round to keep the weapon.
    save_rate : float
        awp_saves / (lost rounds where AWP was alive). Top: 70%+.
    utility_synergy : int
        Rounds where teammate utility (flash/smoke) preceded an AWP kill.
        High = good at playing off teammates' flashes.
    """
    steam_id: int
    awp_rounds: int = 0
    first_pick_rounds: int = 0
    ct_hold_picks: int = 0
    ct_survived_after_pick: int = 0
    t_first_pick_rounds: int = 0
    t_survived_after_pick: int = 0
    awp_deaths_on_eco: int = 0
    awp_saves: int = 0
    utility_synergy: int = 0


@dataclass
class SupportProfile:
    """Support-specific quality metrics — how well a player enables their team.

    Quality signals
    ---------------
    support_rounds : int
        Total rounds classified as support (high utility, low kills).
    trade_kills : int
        Kills within ~5s of a teammate dying — the support bread-and-butter.
    successful_trades : int
        Trades that actually happened (teammate died then player got kill).
    trade_success_rate : float
        successful_trades / (trade_opportunities). Good: 70%+.
    trade_opportunities : int
        Rounds where a teammate died first — player was positioned to trade.
    flash_assisted_kills : int
        Kills that followed a teammate flash within 3s.
    flash_assist_rate : float
        flash_assisted_kills / kills. High = coordinated team player.
    utility_rounds : int
        Rounds where at least one utility was thrown.
    utility_effectiveness : float
        (smoke_rounds * 0.3 + flash_rounds * 0.5 + he_rounds * 0.2) / support_rounds.
    assist_rate : float
        Total assists / rounds. Support: 0.3+ per round.
    economy_sacrifice_rounds : int
        Rounds where player saved money (eco/force) so team could full-buy.
    entry_kills_when_needed : int
        Rounds where entry died and support got the trade (critical rounds).
    info_calls : int
        Rounds where player made rotation/utility calls (estimated via utility usage).
    """
    steam_id: int
    support_rounds: int = 0
    successful_trades: int = 0
    trade_opportunities: int = 0
    flash_assisted_kills: int = 0
    utility_rounds: int = 0
    smoke_rounds: int = 0
    flash_rounds: int = 0
    he_rounds: int = 0
    assist_rate: float = 0.0
    economy_sacrifice_rounds: int = 0
    entry_kills_when_needed: int = 0


@dataclass
class RiflerProfile:
    """Rifler-specific quality metrics — consistent fragging across all situations.

    Quality signals
    ---------------
    rifler_rounds : int
        Total rounds where player used a rifle (AK/M4/SG) as primary.
    multi_kill_rounds : int
        Rounds with 2+ kills — riflers who consistently multi-frag.
    multi_kill_rate : float
        multi_kill_rounds / rifler_rounds. Top riflers: 30%+.
    trade_kills : int
        Kills within 5s of a teammate dying.
    trade_rate : float
        trade_kills / rifler_rounds. Good: 25%+ (every 4th round a trade).
    spray_accuracy : float
        Kills with rifle / total shots fired with rifle (approx from weapon events).
        Top riflers: 30%+ accuracy.
    headshot_rate : float
        Headshot kills / total rifle kills. Top: 40%+.
    ct_site_anchor_rounds : int
        CT-side rounds playing site anchor (holding, not rotating).
    ct_anchor_survival_rate : float
        ct_survived_anchor / ct_site_anchor_rounds.
    t_execute_kills : int
        Kills during T-side executes (post-utility, site-clear phase).
    entry_kills : int
        First-in rounds with kills (can also entry).
    clutch_rounds : int
        Rounds where player survived to a 1vX situation.
    clutch_win_rate : float
        Clutch wins / clutch_rounds. Top riflers: 40%+.
    clutch_rounds_won : int
        Won clutches.
    """
    steam_id: int
    rifler_rounds: int = 0
    multi_kill_rounds: int = 0
    trade_kills: int = 0
    spray_accuracy: float = 0.0
    headshot_rate: float = 0.0
    ct_site_anchor_rounds: int = 0
    ct_survived_anchor: int = 0
    t_execute_kills: int = 0
    entry_kills: int = 0
    clutch_rounds: int = 0
    clutch_rounds_won: int = 0


@dataclass
class LurkerProfile:
    """Lurker-specific quality metrics — patience, solo impact, and rotation cuts.

    Quality signals
    ---------------
    lurk_attempts : int
        Rounds where player was in an isolated/flank position (away from team).
    solo_kills : int
        Kills while alone (no teammates nearby in same area).
    solo_kill_rate : float
        solo_kills / lurk_attempts. Top lurkers: 40%+.
    rotation_cut_kills : int
        Kills that intercepted enemies rotating between sites.
    rotation_cut_rate : float
        rotation_cut_kills / lurk_attempts. The signature lurker metric.
    flank_kills : int
        Kills from behind or side of enemies (clearly a flank, not a duel).
    flank_rate : float
        flank_kills / lurk_attempts.
    survived_lurk_rounds : int
        Lurk rounds where player survived (waited for right timing).
    survival_rate : float
        survived_lurk_rounds / lurk_attempts. Top lurkers: 55%+.
    clutch_rounds : int
        Solo rounds that became clutches.
    clutch_win_rate : float
        Clutch wins / clutch_rounds. Top lurkers: 45%+ (lurk = clutch art).
    clutch_rounds_won : int
        Won clutches.
    clutch_rounds_lost_early : int
        Clutches lost because player pushed too early and got traded.
    round_pressure_created : int
        Rounds where lurk position forced opponents to respect a flank
        (enemies heard/seen reacting to lurk side — no kill needed).
    lurk_timing_accuracy : float
        Kills where player pushed within 5s of team execute contact
        / total lurk kills. Top: 60%+.
    """
    steam_id: int
    lurk_attempts: int = 0
    solo_kills: int = 0
    rotation_cut_kills: int = 0
    flank_kills: int = 0
    survived_lurk_rounds: int = 0
    clutch_rounds: int = 0
    clutch_rounds_won: int = 0
    clutch_rounds_lost_early: int = 0
    round_pressure_created: int = 0


@dataclass
class PlayerRoleSignals:
    """All behavioral signals for one player."""
    steam_id: int
    kills: PlayerKillProfile
    weapons: PlayerWeaponProfile
    utility: PlayerUtilityProfile
    position: Optional[PlayerPositionProfile] = None
    economy: Optional[PlayerEconomyProfile] = None
    entry_frag: Optional[EntryFraggerProfile] = None
    awper: Optional[AwperProfile] = None
    support: Optional[SupportProfile] = None
    rifler: Optional[RiflerProfile] = None
    lurker: Optional[LurkerProfile] = None


# ── Core classification ────────────────────────────────────────────────────────

def classify_player_role(
    signals: PlayerRoleSignals,
    map_name: str,
    side: str,
    igl_steam_id: Optional[int] = None,
) -> RoleClassificationResult:
    """Classify a player's broad role and map position from behavioral signals.

    Parameters
    ----------
    signals : PlayerRoleSignals
        Aggregated behavioral signals for the player
    map_name : str
        e.g. "dust2", "mirage"
    side : str
        "t" or "ct"
    igl_steam_id : int, optional
        Steam ID of the designated IGL — IGL gets role_broad=igl
        regardless of kill/weapon signals

    Returns
    -------
    RoleClassificationResult
    """
    # IGL override — designated caller always gets igl role
    if igl_steam_id is not None and signals.steam_id == igl_steam_id:
        return RoleClassificationResult(
            steam_id=signals.steam_id,
            map_name=map_name,
            side=side,
            broad_role="igl",
            map_position=_most_common_position(signals.position),
            zone_role=_infer_zone_role(signals.position, side),
            confidence=0.95,
            metadata={"source": "igl_override"},
        )

    # Score each broad role
    role_scores = _score_broad_roles(signals, map_name, side)

    # Pick highest scoring role
    best_role = max(role_scores, key=lambda r: role_scores[r])
    best_score = role_scores[best_role]

    # Confidence: ratio of best vs second-best, modulated by evidence strength
    second_best = sorted(role_scores.values(), reverse=True)[1]
    rank_ratio = best_score / (best_score + second_best + 1e-6)
    evidence_factor = _evidence_strength(signals)
    confidence = round(min(0.95, rank_ratio * (0.5 + evidence_factor)), 3)

    # Secondary role
    secondary = _infer_secondary_role(signals, best_role)

    # Map position
    map_pos = _most_common_position(signals.position) if signals.position else "unknown"
    zone = _infer_zone_role(signals.position, side)

    return RoleClassificationResult(
        steam_id=signals.steam_id,
        map_name=map_name,
        side=side,
        broad_role=best_role,
        map_position=map_pos,
        zone_role=zone,
        secondary_role=secondary,
        confidence=confidence,
        metadata={
            "role_scores": {r: round(s, 3) for r, s in role_scores.items()},
            "evidence_rounds": signals.kills.total_kills + (signals.utility.total_utility_score > 0),
        },
    )


def _score_broad_roles(
    signals: PlayerRoleSignals,
    map_name: str,
    side: str,
) -> dict[str, float]:
    """Score every broad role and return a dict of role → score."""
    k = signals.kills
    w = signals.weapons
    u = signals.utility
    pos = signals.position

    scores: dict[str, float] = {role: 0.0 for role in BROAD_ROLES}

    # ── Entry fragger ─────────────────────────────────────────────────────────
    # Core: first blood rate (HLTV-tracked core entry metric)
    if k.first_bloods >= MIN_ENTRY_KILLS:
        scores["entry"] += ENTRY_KILL_BONUS * min(1.0, k.first_bloods / 5)
    # First blood ratio: first_bloods / total_kills (high ratio = dedicated entry)
    if k.total_kills > 0:
        fb_ratio = k.first_bloods / k.total_kills
        scores["entry"] += 0.15 * min(1.0, fb_ratio / 0.30)  # 30%+ first blood ratio
    # Multi-entry: first kill of the round that results in site entry
    if k.entry_kills > 0:
        scores["entry"] += 0.15 * min(1.0, k.entry_kills / 3)
    # Trade opportunity: entry died quickly after getting kill → set up teammate trade
    # Real-world signal: entry who dies 5-8s after getting a kill creates trade opportunity
    if k.trade_opportunities > 0 and k.first_bloods > 0:
        trade_ratio = k.trade_opportunities / k.first_bloods
        scores["entry"] += 0.10 * min(1.0, trade_ratio / 0.4)  # 40%+ trade opp ratio
    # Entry positions (map-specific: short_a, apartments, banana, etc.)
    if pos:
        entry_prefs = ROLE_POSITION_PREFERENCES.get("entry", {}).get(map_name, [])
        scores["entry"] += _position_match_score(pos.position_counts, entry_prefs) * POSITION_WEIGHT

    # ── AWPPer ───────────────────────────────────────────────────────────────
    if k.awp_kills >= MIN_AWP_KILLS:
        scores["awper"] += AWP_KILL_BONUS * min(1.0, k.awp_kills / 5)
    if w.awp_picks > 0:
        scores["awper"] += AWP_WEIGHT * min(1.0, w.awp_picks / max(1, w.total_rounds * 0.3))

    # ── Rifler ───────────────────────────────────────────────────────────────
    if w.rifle_picks > w.awp_picks and w.rifle_picks >= 3:
        scores["rifler"] += RIFLE_WEIGHT
    if k.total_kills > 0 and k.awp_kills < MIN_AWP_KILLS and k.first_bloods < MIN_ENTRY_KILLS:
        scores["rifler"] += 0.20
    if w.rifle_picks > w.smg_picks + w.pistol_picks:
        scores["rifler"] += 0.10

    # ── IGL ──────────────────────────────────────────────────────────────────
    # IGL has no in-game mechanical signal — handled by igl_steam_id override above.
    # Without override, IGL can be tentatively identified by:
    # - Lower kill count but round-winning impact (assists + utility)
    # - This is weak signal, set low score
    if k.total_kills < 5 and k.assists > k.total_kills * 0.5:
        scores["igl"] += 0.10

    # ── Lurker ────────────────────────────────────────────────────────────────
    if k.lurk_kills >= MIN_LURK_KILLS:
        scores["lurker"] += LURK_KILL_BONUS * min(1.0, k.lurk_kills / 4)
    if pos:
        lurk_prefs = ROLE_POSITION_PREFERENCES.get("lurker", {}).get(map_name, [])
        scores["lurker"] += _position_match_score(pos.position_counts, lurk_prefs) * POSITION_WEIGHT

    # ── Support ────────────────────────────────────────────────────────────────
    utility_events = u.flashes_thrown + u.he_detonations + u.smokes_thrown + u.mollies_thrown
    if utility_events >= MIN_SUPPORT_EVENTS:
        scores["support"] += UTILITY_WEIGHT * min(1.0, utility_events / 15)
    if u.flashes_enemy_hit > 0:
        scores["support"] += FLASH_ASSIST_BONUS * min(1.0, u.flashes_enemy_hit / 5)
    if w.smg_picks > w.rifle_picks:
        scores["support"] += SUPPORT_WEAPON
    if u.he_damage_dealt > 0:
        scores["support"] += HE_DAMAGE_BONUS * min(1.0, u.he_damage_dealt / 500)

    # ── Anchor (CT only) ─────────────────────────────────────────────────────
    if side == "ct" and pos:
        if pos.anchor_rounds >= 3:
            scores["anchor"] += ANCHOR_BONUS * min(1.0, pos.anchor_rounds / 8)
        anchor_prefs = ROLE_POSITION_PREFERENCES.get("anchor", {}).get(map_name, [])
        scores["anchor"] += _position_match_score(pos.position_counts, anchor_prefs) * POSITION_WEIGHT

    # ── Rotator (CT only) ────────────────────────────────────────────────────
    if side == "ct" and pos:
        if pos.rotator_rounds >= 2:
            scores["rotator"] += ROTATOR_BONUS * min(1.0, pos.rotator_rounds / 5)
        rot_prefs = ROLE_POSITION_PREFERENCES.get("rotator", {}).get(map_name, [])
        scores["rotator"] += _position_match_score(pos.position_counts, rot_prefs) * POSITION_WEIGHT

    # ── Second AWPer ──────────────────────────────────────────────────────────
    if w.awp_picks > 0 and w.awp_picks < MIN_AWP_KILLS:
        scores["second_awper"] += 0.30

    # ── Trade fragger ─────────────────────────────────────────────────────────
    if k.trade_kills >= MIN_LURK_KILLS:
        scores["trade_fragger"] += TRADE_KILL_BONUS * min(1.0, k.trade_kills / 4)

    # ── Second caller ─────────────────────────────────────────────────────────
    if k.assists > k.total_kills * 0.3 and k.assists < k.total_kills * 0.8:
        scores["second_caller"] += 0.20

    # ── Second support ────────────────────────────────────────────────────────
    if utility_events >= 3 and utility_events < MIN_SUPPORT_EVENTS:
        scores["second_support"] += 0.20

    return scores


def _position_match_score(
    position_counts: dict[str, int],
    preferred: list[str],
) -> float:
    """Return a 0-1 score for how well position counts match role preferences."""
    if not position_counts or not preferred:
        return 0.0
    total = sum(position_counts.values())
    if total == 0:
        return 0.0
    preferred_set = set(preferred)
    matched = sum(cnt for pos, cnt in position_counts.items() if pos in preferred_set)
    return matched / total


def _most_common_position(pos_profile: Optional[PlayerPositionProfile]) -> str:
    """Return the most common position code."""
    if pos_profile is None or not pos_profile.position_counts:
        return "unknown"
    return max(pos_profile.position_counts, key=pos_profile.position_counts.get)


def _infer_zone_role(
    pos_profile: Optional[PlayerPositionProfile],
    side: str,
) -> str:
    """Infer the zone role from position profile."""
    if pos_profile is None or not pos_profile.zone_counts:
        return "unknown"

    top_zone = max(pos_profile.zone_counts, key=pos_profile.zone_counts.get)

    # Zone → tactical role mapping
    zone_to_role = {
        "long_a": "sniper_lane" if side == "ct" else "entry",
        "short_a": "entry",
        "mid": "mid_control",
        "b_tunnels": "sniper_lane" if side == "ct" else "entry",
        "lower_tunnels": "flanker",
        "a_site": "a_anchor",
        "b_site": "b_anchor",
        "banana": "sniper_lane" if side == "ct" else "entry",
        "apartments": "flanker",
        "palace": "entry",
        "connector": "mid_control",
        "a_site_upper": "a_anchor",
        "b_site_lower": "b_anchor",
        "outside": "rotator",
        "squeaky": "entry",
        "ramp": "rotator",
        "bathrooms": "flanker",
        "monster": "flanker",
        "water": "flanker",
        "donut": "mid_control",
        "cave": "flanker",
        "b_ramp": "entry",
    }

    return zone_to_role.get(top_zone, "unknown")


def _infer_secondary_role(
    signals: PlayerRoleSignals,
    primary_role: str,
) -> Optional[str]:
    """Infer a secondary role modifier if evidence is strong enough."""
    k = signals.kills
    w = signals.weapons
    u = signals.utility

    # Second AWPer
    if primary_role != "awper" and w.awp_picks >= 2 and k.awp_kills < MIN_AWP_KILLS:
        return "second_awper"

    # Trade fragger
    if primary_role != "entry" and k.trade_kills >= 2:
        return "trade_fragger"

    # Second support
    if primary_role != "support":
        utility_events = u.flashes_thrown + u.he_detonations + u.smokes_thrown
        if utility_events >= 3:
            return "second_support"

    return None


def _evidence_strength(signals: PlayerRoleSignals) -> float:
    """Return a 0-1 score for how much evidence we have for classification."""
    k = signals.kills
    u = signals.utility

    kill_evidence = min(1.0, k.total_kills / 10)
    utility_evidence = min(1.0, (u.total_utility_score > 0))

    return (kill_evidence + utility_evidence) / 2


# ── Aggregate helper ─────────────────────────────────────────────────────────

def build_player_role_signals(
    kills_data: list[dict],
    weapon_events: list[dict],
    utility_events: list[dict],
    position_classifications: list[dict],
    steam_id: int,
) -> PlayerRoleSignals:
    """Build a PlayerRoleSignals object from raw event lists.

    Parameters
    ----------
    kills_data : list of dict
        Kill events with keys: killer_steam_id, victim_steam_id, tick, round_number,
        weapon_name, headshot, is_first_blood
    weapon_events : list of dict
        Weapon fire events with keys: steam_id, weapon_name, tick
    utility_events : list of dict
        Grenade detonation events with keys: player_steam_id, grenade_type,
        x, y, z, tick, damage (for HE)
    position_classifications : list of dict
        Output from position_classifier with keys: steam_id, position_code,
        zone, tick, round_number
    steam_id : int
        Target player
    """
    # Filter to this player
    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]
    weapons = [w for w in weapon_events if int(w.get("steam_id", 0)) == steam_id]
    utilities = [u for u in utility_events if int(u.get("player_steam_id", 0)) == steam_id]
    positions = [p for p in position_classifications if int(p.get("steam_id", 0)) == steam_id]

    # Kill profile
    kp = PlayerKillProfile(steam_id=steam_id)
    kp.total_kills = len(kills)
    kp.deaths = len(deaths)
    kp.awp_kills = sum(1 for k in kills if "awp" in str(k.get("weapon_name", "")).lower())
    kp.first_bloods = sum(1 for k in kills if k.get("is_first_blood", False))

    # Simple lurk detection: kill after round has been going for > 30s
    round_kills: dict[int, list[dict]] = {}
    for k in kills:
        rn = int(k.get("round_number", 0))
        if rn not in round_kills:
            round_kills[rn] = []
        round_kills[rn].append(k)
    kp.lurk_kills = sum(
        1 for rn, rk in round_kills.items()
        if rk and int(rk[0].get("tick", 0)) > 10000  # After early round
    )

    # Trade opportunities: player got a kill then died within ~8s (1024 ticks)
    # This signals the player created a trade opportunity for their teammate
    # Key entry fragger signal from HLTV/real-world analysis
    TRADE_WINDOW_TICKS = 1024  # ~8 seconds at 128 tick
    round_deaths: dict[int, list[dict]] = {}
    for d in deaths:
        rn = int(d.get("round_number", 0))
        if rn not in round_deaths:
            round_deaths[rn] = []
        round_deaths[rn].append(d)
    trade_opportunities = 0
    for rn, rk in round_kills.items():
        if not rk:
            continue
        kill_tick = int(rk[0].get("tick", 0))
        # Player died in this round after getting a kill within trade window
        if rn in round_deaths:
            for d in round_deaths[rn]:
                death_tick = int(d.get("tick", 0))
                if death_tick > kill_tick and death_tick - kill_tick <= TRADE_WINDOW_TICKS:
                    trade_opportunities += 1
                    break  # Only count once per kill, even if multiple deaths
    kp.trade_opportunities = trade_opportunities

    # Weapon profile
    wp = PlayerWeaponProfile(steam_id=steam_id)
    wp.total_rounds = len(set(int(w.get("round_number", 0)) for w in weapons)) if weapons else 0
    for w in weapons:
        wn = str(w.get("weapon_name", "")).lower()
        if "awp" in wn:
            wp.awp_picks += 1
        elif any(r in wn for r in ["ak", "m4", "scar", "galil", "famas"]):
            wp.rifle_picks += 1
        elif any(s in wn for s in ["mp5", "mp7", "mp9", "ump", "p90", "mac10"]):
            wp.smg_picks += 1
        elif "pistol" in wn or any(p in wn for p in ["glock", "usp", "deagle", "p250", "five"]):
            wp.pistol_picks += 1
        elif "shotgun" in wn:
            wp.shotgun_picks += 1

    # Utility profile
    up = PlayerUtilityProfile(steam_id=steam_id)
    for u in utilities:
        gt = str(u.get("grenade_type", "")).lower()
        if gt == "flashbang":
            up.flashes_thrown += 1
        elif gt == "hegrenade":
            up.he_detonations += 1
            up.he_damage_dealt += float(u.get("damage", 0) or 0)
        elif gt == "smokegrenade":
            up.smokes_thrown += 1
        elif gt in ("molotov", "incendiary"):
            up.mollies_thrown += 1

    # Rough utility score
    up.total_utility_score = (
        up.flashes_thrown * 0.5
        + up.flashes_enemy_hit * 1.0
        + up.he_detonations * 0.3
        + up.smokes_thrown * 0.5
        + up.mollies_thrown * 0.7
    )

    # Position profile (aggregated from position_classifier output)
    pos_profile: Optional[PlayerPositionProfile] = None
    if positions:
        pos_profile = PlayerPositionProfile(
            steam_id=steam_id,
            map_name=positions[0].get("map_name", "unknown") if positions else "unknown",
            side=str(positions[0].get("side", "ct")).lower(),
            position_counts={},
            zone_counts={},
        )
        for p in positions:
            pos_code = str(p.get("position_code", "unknown"))
            zone = str(p.get("zone", "unknown"))
            pos_profile.position_counts[pos_code] = pos_profile.position_counts.get(pos_code, 0) + 1
            pos_profile.zone_counts[zone] = pos_profile.zone_counts.get(zone, 0) + 1
        pos_profile.rounds_played = len(set(int(p.get("tick", 0)) // 50000 for p in positions))

    # Entry frag quality profile
    entry_frag = _build_entry_frag_profile(kills_data, utility_events, steam_id)

    # Role-specific quality profiles
    awper = _build_awper_profile(kills_data, weapon_events, utility_events, steam_id)
    support = _build_support_profile(kills_data, utility_events, steam_id)
    rifler = _build_rifler_profile(kills_data, weapon_events, utility_events, steam_id)
    lurker = _build_lurker_profile(kills_data, position_classifications, steam_id)

    return PlayerRoleSignals(
        steam_id=steam_id,
        kills=kp,
        weapons=wp,
        utility=up,
        position=pos_profile,
        entry_frag=entry_frag,
        awper=awper,
        support=support,
        rifler=rifler,
        lurker=lurker,
    )


def _build_entry_frag_profile(
    kills_data: list[dict],
    utility_events: list[dict],
    steam_id: int,
) -> EntryFraggerProfile:
    """Compute entry fragger quality metrics from kill and utility events.

    Entry attempt detection
    -----------------------
    A round is an "entry attempt" for a player if they are EITHER:
      (a) the first killer in that round  — strong entry signal (got first blood)
      (b) the first victim in that round — likely died while attempting entry

    Flash-pop detection
    -------------------
    A kill is flash-assisted if a teammate threw a flashbang within 3 seconds
    before the kill tick. We check the same round, ignoring the victim's flashes
    (you can't flash-pop yourself).

    Parameters
    ----------
    kills_data : list of dict
        Kill events with keys: killer_steam_id, victim_steam_id, tick,
        round_number, is_first_blood
    utility_events : list of dict
        Grenade events with keys: player_steam_id, grenade_type, tick, round_number
    steam_id : int
        Target player

    Returns
    -------
    EntryFraggerProfile
    """
    FLASH_POP_WINDOW_TICKS = 384   # ~3 seconds at 128 tick

    # Filter to this player
    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]

    # Group by round
    round_kills: dict[int, list[dict]] = {}
    round_deaths: dict[int, list[dict]] = {}
    all_rounds: set[int] = set()

    for k in kills:
        rn = int(k.get("round_number", 0))
        all_rounds.add(rn)
        round_kills.setdefault(rn, []).append(k)

    for d in deaths:
        rn = int(d.get("round_number", 0))
        all_rounds.add(rn)
        round_deaths.setdefault(rn, []).append(d)

    # Build flash lookup: round -> list of (tick, thrower) for teammate flashes
    round_flashes: dict[int, list[tuple[int, int]]] = {}
    for u in utility_events:
        if str(u.get("grenade_type", "")).lower() != "flashbang":
            continue
        rn = int(u.get("round_number", 0))
        thrower = int(u.get("player_steam_id", 0))
        tick = int(u.get("tick", 0))
        round_flashes.setdefault(rn, []).append((tick, thrower))

    ep = EntryFraggerProfile(steam_id=steam_id)

    for rn in sorted(all_rounds):
        rk = round_kills.get(rn, [])
        rd = round_deaths.get(rn, [])

        # Determine if this round was an entry attempt for this player
        is_entry_attempt = False
        got_first_kill = False
        died_first = False

        # First kill of round globally?
        all_round_kills = [k for k in kills_data if int(k.get("round_number", 0)) == rn]
        all_round_kills_sorted = sorted(all_round_kills, key=lambda k: int(k.get("tick", 0)))
        if all_round_kills_sorted:
            first_kill = all_round_kills_sorted[0]
            got_first_kill = int(first_kill.get("killer_steam_id") or 0) == steam_id

        if all_round_deaths := [d for d in kills_data if int(d.get("round_number", 0)) == rn]:
            all_round_deaths_sorted = sorted(all_round_deaths, key=lambda d: int(d.get("tick", 0)))
            died_first = int(all_round_deaths_sorted[0].get("victim_steam_id", 0)) == steam_id

        is_entry_attempt = got_first_kill or died_first

        if not is_entry_attempt:
            continue

        ep.entry_attempts += 1
        ep.rounds_with_entry_attempt += 1

        # Successful entry: player got at least one kill this round
        if rk:
            ep.successful_entries += 1
            ep.total_kills_in_entry_rounds += len(rk)
        else:
            # Entry attempt but died without getting a kill
            ep.entry_deaths_no_kill += 1

        # Opening duel win: player got first kill of the round
        if got_first_kill:
            ep.opening_duel_wins += 1

        # Flash-pop kills: teammate flash within 3s before each entry kill
        flashes_in_round = round_flashes.get(rn, [])
        for kill in rk:
            kill_tick = int(kill.get("tick", 0))
            for flash_tick, thrower in flashes_in_round:
                if thrower == steam_id:
                    continue  # Skip self-flashes
                # Flash must be before kill, within 3s window
                if flash_tick < kill_tick and kill_tick - flash_tick <= FLASH_POP_WINDOW_TICKS:
                    ep.flash_pop_kills += 1
                    break  # One flash-pop credit per kill

        # Survived post-entry: had kills this round AND no death this round
        if rk and not rd:
            ep.rounds_survived_post_entry += 1

    return ep


def score_entry_quality(entry_frag: EntryFraggerProfile) -> float:
    """Return a 0-1 entry fragger quality score from an EntryFraggerProfile.

    This measures how well a player *performs* the entry fragger role,
    complementing the role *detection* done by classify_player_role.

    Score components
    ---------------
    entry_kill_rate (40%):
        Proportional to successful_entries / entry_attempts.
        Top entries: 40%+ (every 2.5 attempts = 1 kill).
    flash_pop_ratio (20%):
        flash_pop_kills / successful_entries.
        High flash-pop rate = support coordination.
    survival_post_entry (20%):
        rounds_survived_post_entry / successful_entries.
        Top entries survive often — they don't just die.
    opening_duel_rate (20%):
        opening_duel_wins / rounds_with_entry_attempt.
        Top entries win 50%+ of opening duels.

    Returns
    -------
    float
        0.0 to 1.0 overall entry quality score.
        0.75+ = elite entry.  0.5-0.75 = solid.  0.3-0.5 = average.  <0.3 = liability.
    """
    if entry_frag.entry_attempts == 0:
        return 0.0

    ea = entry_frag.entry_attempts

    # Entry kill rate: 40% weight
    entry_kill_rate = entry_frag.successful_entries / ea
    entry_kill_score = min(1.0, entry_kill_rate / 0.40)  # 40% = perfect

    # Flash-pop ratio: 20% weight
    flash_pop_score = 0.0
    if entry_frag.successful_entries > 0:
        flash_pop_ratio = entry_frag.flash_pop_kills / entry_frag.successful_entries
        flash_pop_score = min(1.0, flash_pop_ratio / 0.50)  # 50% = perfect

    # Survival rate post-entry: 20% weight
    survival_score = 0.0
    if entry_frag.successful_entries > 0:
        survival_rate = entry_frag.rounds_survived_post_entry / entry_frag.successful_entries
        survival_score = min(1.0, survival_rate / 0.60)  # 60% survival = perfect

    # Opening duel win rate: 20% weight
    opening_duel_rate = entry_frag.opening_duel_wins / ea
    opening_duel_score = min(1.0, opening_duel_rate / 0.50)  # 50% = perfect

    quality = (
        0.40 * entry_kill_score
        + 0.20 * flash_pop_score
        + 0.20 * survival_score
        + 0.20 * opening_duel_score
    )
    return round(quality, 3)


# ── AWP Per ───────────────────────────────────────────────────────────────────


def _build_awper_profile(
    kills_data: list[dict],
    weapon_events: list[dict],
    utility_events: list[dict],
    steam_id: int,
) -> AwperProfile:
    """Build AWP quality profile from kill, weapon, and utility events.

    AWP round: player equipped AWP as primary weapon (from weapon_events).
    First pick: player's AWP kill was the first kill of the round globally.
    CT vs T split: determined by which side the player was on based on kills_data.
    """
    FLASH_WINDOW_TICKS = 384  # 3s

    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]
    weapons = [w for w in weapon_events if int(w.get("steam_id", 0)) == steam_id]

    # AWP rounds: rounds where player fired/equipped AWP
    awp_rounds: set[int] = set()
    for w in weapons:
        wn = str(w.get("weapon_name", "")).lower()
        if "awp" in wn:
            awp_rounds.add(int(w.get("round_number", 0)))

    # Build round-level data
    round_kills: dict[int, list[dict]] = {}
    round_deaths: dict[int, list[dict]] = {}
    all_rounds: set[int] = set()

    for k in kills:
        rn = int(k.get("round_number", 0))
        all_rounds.add(rn)
        round_kills.setdefault(rn, []).append(k)
    for d in deaths:
        rn = int(d.get("round_number", 0))
        all_rounds.add(rn)
        round_deaths.setdefault(rn, []).append(d)

    # Flash lookup for utility synergy
    round_flashes: dict[int, list[tuple[int, int]]] = {}
    for u in utility_events:
        if str(u.get("grenade_type", "")).lower() != "flashbang":
            continue
        rn = int(u.get("round_number", 0))
        thrower = int(u.get("player_steam_id", 0))
        round_flashes.setdefault(rn, []).append((int(u.get("tick", 0)), thrower))

    ap = AwperProfile(steam_id=steam_id)
    ap.awp_rounds = len(awp_rounds)

    for rn in sorted(all_rounds):
        if rn not in awp_rounds:
            continue
        rk = round_kills.get(rn, [])
        rd = round_deaths.get(rn, [])

        # Determine side from global round kill order
        all_round_kills = [k for k in kills_data if int(k.get("round_number", 0)) == rn]
        all_round_kills_sorted = sorted(all_round_kills, key=lambda k: int(k.get("tick", 0)))

        if not all_round_kills_sorted:
            continue

        # First pick of round
        first_kill = all_round_kills_sorted[0]
        is_first_pick = int(first_kill.get("killer_steam_id") or 0) == steam_id
        if is_first_pick:
            ap.first_pick_rounds += 1

        # CT vs T: if player's kill victim was on opposite team, estimate side
        # Simple heuristic: if player has more kills early tick = likely CT (holding)
        # This is approximate — position data would be more accurate
        # For now, use tick of first kill: early tick = CT side (aggressive hold)
        first_kill_tick = int(first_kill.get("tick", 0))
        is_ct_side = first_kill_tick < 10000  # Rough heuristic

        # Utility synergy: teammate flash within 3s before any AWP kill
        flashes_in_round = round_flashes.get(rn, [])
        for kill in rk:
            kill_tick = int(kill.get("tick", 0))
            if "awp" in str(kill.get("weapon_name", "")).lower():
                for flash_tick, thrower in flashes_in_round:
                    if thrower == steam_id:
                        continue
                    if flash_tick < kill_tick and kill_tick - flash_tick <= FLASH_WINDOW_TICKS:
                        ap.utility_synergy += 1
                        break

        if is_ct_side:
            if rk:
                ap.ct_hold_picks += 1
                if not rd:
                    ap.ct_survived_after_pick += 1
        else:
            if is_first_pick:
                ap.t_first_pick_rounds += 1
                if not rd:
                    ap.t_survived_after_pick += 1

    return ap


def score_awper_quality(ap: AwperProfile) -> float:
    """Score 0-1 AWP quality from an AwperProfile.

    Components (equal 25% each):
    - Opening pick rate: first_pick_rounds / awp_rounds. 35% = perfect.
    - CT survival rate: ct_survived_after_pick / ct_hold_picks. 60% = perfect.
    - T-side first pick rate: t_first_pick_rounds / (T-side rounds). 25% = perfect.
    - Save rate: awp_saves / (lost eco rounds with AWP alive). 70% = perfect.
    """
    if ap.awp_rounds == 0:
        return 0.0

    # Opening pick rate
    pick_score = min(1.0, (ap.first_pick_rounds / ap.awp_rounds) / 0.35)

    # CT survival rate
    ct_score = 0.0
    if ap.ct_hold_picks > 0:
        ct_score = min(1.0, (ap.ct_survived_after_pick / ap.ct_hold_picks) / 0.60)

    # T-side first pick rate (estimate T rounds as ~half of awp_rounds)
    t_rounds = ap.awp_rounds // 2
    t_score = min(1.0, (ap.t_first_pick_rounds / max(1, t_rounds)) / 0.25)

    # Save rate
    total_economically_meaningful = ap.awp_saves + ap.awp_deaths_on_eco
    save_score = 0.0
    if total_economically_meaningful > 0:
        save_score = min(1.0, (ap.awp_saves / total_economically_meaningful) / 0.70)

    return round((pick_score + ct_score + t_score + save_score) / 4, 3)


# ── Support ───────────────────────────────────────────────────────────────────


def _build_support_profile(
    kills_data: list[dict],
    utility_events: list[dict],
    steam_id: int,
) -> SupportProfile:
    """Build support quality profile from kill and utility events.

    Support rounds: rounds with high utility usage but few/no first kills.
    Trade opportunity: teammate died first in round, player was positioned to trade.
    """
    TRADE_WINDOW_TICKS = 640  # 5s

    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]

    round_kills: dict[int, list[dict]] = {}
    round_deaths: dict[int, list[dict]] = {}
    all_rounds: set[int] = set()

    for k in kills:
        rn = int(k.get("round_number", 0))
        all_rounds.add(rn)
        round_kills.setdefault(rn, []).append(k)
    for d in deaths:
        rn = int(d.get("round_number", 0))
        all_rounds.add(rn)
        round_deaths.setdefault(rn, []).append(d)

    # Flash lookup
    round_flashes: dict[int, list[tuple[int, int]]] = {}
    for u in utility_events:
        if str(u.get("grenade_type", "")).lower() != "flashbang":
            continue
        rn = int(u.get("round_number", 0))
        thrower = int(u.get("player_steam_id", 0))
        round_flashes.setdefault(rn, []).append((int(u.get("tick", 0)), thrower))

    # Utility rounds
    utility_rounds_set: set[int] = set()
    smoke_rounds: set[int] = set()
    flash_rounds: set[int] = set()
    he_rounds: set[int] = set()
    for u in utility_events:
        if int(u.get("player_steam_id", 0)) != steam_id:
            continue
        rn = int(u.get("round_number", 0))
        utility_rounds_set.add(rn)
        gt = str(u.get("grenade_type", "")).lower()
        if gt == "smokegrenade":
            smoke_rounds.add(rn)
        elif gt == "flashbang":
            flash_rounds.add(rn)
        elif gt in ("hegrenade", "frag"):
            he_rounds.add(rn)

    sp = SupportProfile(steam_id=steam_id)
    sp.support_rounds = len(utility_rounds_set)
    sp.utility_rounds = len(utility_rounds_set)
    sp.smoke_rounds = len(smoke_rounds)
    sp.flash_rounds = len(flash_rounds)
    sp.he_rounds = len(he_rounds)

    total_assists = sum(1 for k in kills_data if int(k.get("assist", 0)) == steam_id)
    if all_rounds:
        sp.assist_rate = round(total_assists / len(all_rounds), 3)

    for rn in sorted(all_rounds):
        rk = round_kills.get(rn, [])
        rd = round_deaths.get(rn, [])
        flashes_in_round = round_flashes.get(rn, [])

        # Flash-assisted kills: teammate flash before player's kill
        for kill in rk:
            kill_tick = int(kill.get("tick", 0))
            for flash_tick, thrower in flashes_in_round:
                if thrower == steam_id:
                    continue
                if flash_tick < kill_tick and kill_tick - flash_tick <= 384:
                    sp.flash_assisted_kills += 1
                    break

        # Trade: ANY teammate death in the round, followed by player's kill within window.
        # Player must NOT have been the first casualty (trade = positioned to respond).
        all_round_kills = [k for k in kills_data if int(k.get("round_number", 0)) == rn]
        all_round_deaths = [d for d in kills_data if int(d.get("round_number", 0)) == rn]

        # Find the earliest death tick where victim != player (teammate death)
        teammate_deaths = [d for d in all_round_deaths
                          if int(d.get("victim_steam_id", 0)) != steam_id]
        if not teammate_deaths:
            continue
        teammate_deaths_sorted = sorted(teammate_deaths, key=lambda d: int(d.get("tick", 0)))
        first_teammate_death = teammate_deaths_sorted[0]
        first_teammate_death_tick = int(first_teammate_death.get("tick", 0))

        # Was player already dead when this teammate died? If so, they couldn't trade.
        player_deaths = [d for d in all_round_deaths
                        if int(d.get("victim_steam_id", 0)) == steam_id]
        player_deaths_sorted = sorted(player_deaths, key=lambda d: int(d.get("tick", 0))) if player_deaths else []
        player_dead_before_teammate = (
            bool(player_deaths_sorted) and
            int(player_deaths_sorted[0].get("tick", 0)) <= first_teammate_death_tick
        )
        if player_dead_before_teammate:
            continue  # Player died before teammate — no trade possible

        # Player survived past the teammate death — trade opportunity
        sp.trade_opportunities += 1

        # Did player get a kill within the trade window after teammate died?
        for kill in rk:
            kill_tick = int(kill.get("tick", 0))
            if first_teammate_death_tick < kill_tick <= first_teammate_death_tick + TRADE_WINDOW_TICKS:
                sp.successful_trades += 1
                sp.entry_kills_when_needed += 1
                break

    return sp


def score_support_quality(sp: SupportProfile) -> float:
    """Score 0-1 support quality from a SupportProfile.

    Components:
    - Trade success rate (35%): successful_trades / trade_opportunities. 70% = perfect.
    - Flash assist rate (25%): flash_assisted_kills / kills. 30% = perfect.
    - Utility engagement (20%): utility_rounds / total_rounds. 80% = perfect.
    - Economy sacrifice (20%): economy_sacrifice_rounds / total_rounds. 20% = perfect.
    """
    if sp.support_rounds == 0:
        return 0.0

    # Trade success rate
    trade_score = 0.0
    if sp.trade_opportunities > 0:
        trade_score = min(1.0, (sp.successful_trades / sp.trade_opportunities) / 0.70)

    # Flash assist rate (estimate total kills as proxy)
    total_kills = sp.successful_trades + sp.entry_kills_when_needed + 1
    flash_score = min(1.0, (sp.flash_assisted_kills / max(1, total_kills)) / 0.30)

    # Utility engagement
    util_score = min(1.0, sp.utility_rounds / max(1, sp.support_rounds) / 0.80)

    # Economy sacrifice (as fraction of support rounds)
    eco_score = min(1.0, sp.economy_sacrifice_rounds / max(1, sp.support_rounds) / 0.20)

    return round(0.35 * trade_score + 0.25 * flash_score + 0.20 * util_score + 0.20 * eco_score, 3)


# ── Rifler ────────────────────────────────────────────────────────────────────


def _build_rifler_profile(
    kills_data: list[dict],
    weapon_events: list[dict],
    utility_events: list[dict],
    steam_id: int,
) -> RiflerProfile:
    """Build rifler quality profile from kill, weapon, and utility events.

    Rifler rounds: rounds with rifle as primary weapon.
    Multi-kill: 2+ kills in same round.
    Trade: kill within 5s of teammate dying.
    CT anchor: CT-side round with kills, played site-anchor position.
    Clutch: last player alive in a round.
    """
    TRADE_WINDOW_TICKS = 640  # 5s

    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]
    weapons = [w for w in weapon_events if int(w.get("steam_id", 0)) == steam_id]

    rifle_rounds: set[int] = set()
    for w in weapons:
        wn = str(w.get("weapon_name", "")).lower()
        if any(r in wn for r in ["ak", "m4", "sg", "galil", "famas", "scar"]):
            rifle_rounds.add(int(w.get("round_number", 0)))

    round_kills: dict[int, list[dict]] = {}
    round_deaths: dict[int, list[dict]] = {}
    all_rounds: set[int] = set()

    for k in kills:
        rn = int(k.get("round_number", 0))
        all_rounds.add(rn)
        round_kills.setdefault(rn, []).append(k)
    for d in deaths:
        rn = int(d.get("round_number", 0))
        all_rounds.add(rn)
        round_deaths.setdefault(rn, []).append(d)

    rp = RiflerProfile(steam_id=steam_id)
    rp.rifler_rounds = len(rifle_rounds)

    total_kills = 0
    headshot_kills = 0

    for rn in sorted(all_rounds):
        rk = round_kills.get(rn, [])
        rd = round_deaths.get(rn, [])

        if rn not in rifle_rounds:
            continue

        round_kill_count = len(rk)
        total_kills += round_kill_count
        rp.multi_kill_rounds += 1 if round_kill_count >= 2 else 0

        for kill in rk:
            if kill.get("headshot", False):
                headshot_kills += 1
            fb = kill.get("is_first_blood")
            if fb is True or fb == 1:
                rp.entry_kills += 1

        # Trade: ANY teammate death in the round, followed by player's kill within window.
        all_round_deaths = [d for d in kills_data if int(d.get("round_number", 0)) == rn]
        teammate_deaths = [d for d in all_round_deaths
                          if int(d.get("victim_steam_id", 0)) != steam_id]
        if not teammate_deaths:
            continue
        teammate_deaths_sorted = sorted(teammate_deaths, key=lambda d: int(d.get("tick", 0)))
        first_teammate_death_tick = int(teammate_deaths_sorted[0].get("tick", 0))

        # Player must have survived past the teammate death
        player_deaths = [d for d in all_round_deaths
                         if int(d.get("victim_steam_id", 0)) == steam_id]
        player_deaths_sorted = sorted(player_deaths, key=lambda d: int(d.get("tick", 0))) if player_deaths else []
        player_dead_before_teammate = (
            bool(player_deaths_sorted) and
            int(player_deaths_sorted[0].get("tick", 0)) <= first_teammate_death_tick
        )
        if not player_dead_before_teammate:
            for kill in rk:
                kill_tick = int(kill.get("tick", 0))
                if first_teammate_death_tick < kill_tick <= first_teammate_death_tick + TRADE_WINDOW_TICKS:
                    rp.trade_kills += 1
                    break

        # CT anchor: CT side, kills, survived round (stayed on site)
        if rd:
            continue  # Died, not anchor
        if rk:
            # Approximate CT side from tick: early tick = CT (holding)
            first_kill_tick = int(rk[0].get("tick", 0))
            if first_kill_tick < 10000:
                rp.ct_site_anchor_rounds += 1
                rp.ct_survived_anchor += 1
            else:
                rp.t_execute_kills += len(rk)

        # Clutch: last alive (no teammates left in round)
        team_alive = [d for d in kills_data
                      if int(d.get("round_number", 0)) == rn
                      and int(d.get("victim_steam_id", 0)) != steam_id
                      and int(d.get("victim_steam_id", 0)) not in
                      {int(k.get("killer_steam_id") or 0) for k in kills}]
        # Rough clutch detection: round with kills and no deaths for player
        if rk and not rd:
            rp.clutch_rounds += 1
            # Assume clutch won if enemy died too (simplified)
            # Real clutch detection needs team alive data
            rp.clutch_rounds_won += 1

    rp.headshot_rate = round(headshot_kills / max(1, total_kills), 3)
    rp.spray_accuracy = 0.25  # Placeholder: requires shot event data

    return rp


def score_rifler_quality(rp: RiflerProfile) -> float:
    """Score 0-1 rifler quality from a RiflerProfile.

    Components:
    - Multi-kill rate (25%): multi_kill_rounds / rifler_rounds. 30% = perfect.
    - Trade rate (25%): trade_kills / rifler_rounds. 25% = perfect.
    - Headshot rate (25%): headshot_rate. 40% = perfect.
    - CT anchor survival (25%): ct_survived_anchor / ct_site_anchor_rounds. 70% = perfect.
    """
    if rp.rifler_rounds == 0:
        return 0.0

    multi_kill_score = min(1.0, (rp.multi_kill_rounds / rp.rifler_rounds) / 0.30)
    trade_score = min(1.0, (rp.trade_kills / rp.rifler_rounds) / 0.25)
    hs_score = min(1.0, rp.headshot_rate / 0.40)
    anchor_score = 0.0
    if rp.ct_site_anchor_rounds > 0:
        anchor_score = min(1.0, (rp.ct_survived_anchor / rp.ct_site_anchor_rounds) / 0.70)

    return round((multi_kill_score + trade_score + hs_score + anchor_score) / 4, 3)


# ── Lurker ───────────────────────────────────────────────────────────────────


def _build_lurker_profile(
    kills_data: list[dict],
    position_classifications: list[dict],
    steam_id: int,
) -> LurkerProfile:
    """Build lurker quality profile from kill and position events.

    Lurk attempt: round where player was in isolated/flank position
    (based on position_classifications zone data).
    Solo kill: kill in a lurk attempt round.
    Rotation cut: kill of an enemy who died far from their team.
    Flank kill: kill from behind/side of enemy (position data).
    Clutch: lurk attempt round that became a 1vX.
    """
    kills = [k for k in kills_data if int(k.get("killer_steam_id") or 0) == steam_id]
    deaths = [d for d in kills_data if int(d.get("victim_steam_id", 0)) == steam_id]
    positions = [p for p in position_classifications if int(p.get("steam_id", 0)) == steam_id]

    round_kills: dict[int, list[dict]] = {}
    round_deaths: dict[int, list[dict]] = {}
    all_rounds: set[int] = set()

    for k in kills:
        rn = int(k.get("round_number", 0))
        all_rounds.add(rn)
        round_kills.setdefault(rn, []).append(k)
    for d in deaths:
        rn = int(d.get("round_number", 0))
        all_rounds.add(rn)
        round_deaths.setdefault(rn, []).append(d)

    # Lurk positions: flank, mid_control, isolated zones from position data
    lurk_zones = {"flanker", "mid_control", "b_anchor", "a_anchor"}
    lurk_positions_by_round: dict[int, bool] = {}
    if positions:
        for p in positions:
            rn = int(p.get("round_number", 0))
            zone = str(p.get("zone", "")).lower()
            if zone in lurk_zones:
                lurk_positions_by_round[rn] = True

    lp = LurkerProfile(steam_id=steam_id)

    for rn in sorted(all_rounds):
        rk = round_kills.get(rn, [])
        rd = round_deaths.get(rn, [])

        # Lurk attempt: position in lurk zone OR kill tick > 15000 (late-round solo play)
        is_lurk = lurk_positions_by_round.get(rn, False)
        if not is_lurk and rk:
            # Fallback: late-round isolated kill (no teammates died before)
            first_kill_tick = int(rk[0].get("tick", 0)) if rk else 0
            all_rd = [d for d in kills_data if int(d.get("round_number", 0)) == rn]
            if all_rd:
                all_rd_sorted = sorted(all_rd, key=lambda d: int(d.get("tick", 0)))
                first_death_tick = int(all_rd_sorted[0].get("tick", 0))
                is_lurk = first_kill_tick > 15000 and first_death_tick > 10000

        if not is_lurk:
            continue

        lp.lurk_attempts += 1

        if rk:
            lp.solo_kills += len(rk)
            lp.rotation_cut_kills += len(rk)  # Assume lurk kills are rotation cuts
            lp.flank_kills += len(rk)  # Lurk kills are flank by nature

        if not rd:
            lp.survived_lurk_rounds += 1

        # Clutch: lurk round with kills but all teammates dead
        team_deaths = [d for d in kills_data
                       if int(d.get("round_number", 0)) == rn
                       and int(d.get("victim_steam_id", 0)) != steam_id]
        if rk and team_deaths:
            # All teammates died, lurker still alive = clutch situation
            lp.clutch_rounds += 1
            if not rd:
                lp.clutch_rounds_won += 1

    return lp


def score_lurker_quality(lp: LurkerProfile) -> float:
    """Score 0-1 lurker quality from a LurkerProfile.

    Components:
    - Solo kill rate (30%): solo_kills / lurk_attempts. 40% = perfect.
    - Survival rate (25%): survived_lurk_rounds / lurk_attempts. 55% = perfect.
    - Rotation cut rate (20%): rotation_cut_kills / lurk_attempts. 30% = perfect.
    - Clutch win rate (25%): clutch_rounds_won / clutch_rounds. 45% = perfect.
    """
    if lp.lurk_attempts == 0:
        return 0.0

    solo_score = min(1.0, (lp.solo_kills / lp.lurk_attempts) / 0.40)
    survival_score = min(1.0, (lp.survived_lurk_rounds / lp.lurk_attempts) / 0.55)
    rotation_score = min(1.0, (lp.rotation_cut_kills / lp.lurk_attempts) / 0.30)

    clutch_score = 0.0
    if lp.clutch_rounds > 0:
        clutch_score = min(1.0, (lp.clutch_rounds_won / lp.clutch_rounds) / 0.45)

    return round(0.30 * solo_score + 0.25 * survival_score + 0.20 * rotation_score + 0.25 * clutch_score, 3)
