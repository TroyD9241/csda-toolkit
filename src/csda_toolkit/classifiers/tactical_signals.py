"""Tactical signal detection from player positions and round events.

Detects team-level tactical behaviors by clustering player positions at key
round moments and cross-referencing with grenade/kill events.

SIGNALS
=======
CT-Side:
  ct_stack_correct  — 4+ CT on one site at mid-round, T committed there, CT won
  ct_stack_wrong    — 4+ CT on one site at mid-round, T hit OTHER site
  ct_wrong_rotate   — CT cluster moved A→B between early and mid round
  ct_correct_adapt   — CT cluster shifted to match T commit site, CT won
  ct_gamble_correct  — 4+ on one site, T hit that site, CT won
  ct_gamble_wrong   — 4+ on one site, T hit other site

T-Side:
  t_fast_execute    — 3+ T at bombsite approach within first 20s with heavy utility
  t_split_correct   — Split from 2 directions, both sites reached
  t_fake_detected   — Utility at site A, T committed to site B
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ── Signal dataclasses ─────────────────────────────────────────────────────────

@dataclass
class TacticalSignal:
    """One detected tactical signal for a round."""
    signal_type: str          # e.g. "ct_stack_correct"
    side: str                 # "ct" or "t"
    description: str
    confidence: float         # 0.0–1.0
    metadata: dict = field(default_factory=dict)

    def to_classification_dict(self, match_id: int, round_number: int) -> dict:
        return {
            "entity_type": "round",
            "entity_id": round_number,
            "label_name": f"tactical_{self.side}_{self.signal_type}",
            "label_value": "true",
            "confidence": self.confidence,
            "metadata": {
                "description": self.description,
                **self.metadata,
            },
        }


@dataclass
class RoundClusterResult:
    """K-means clustering result for player positions at one tick."""
    tick: int
    site_a_centroid: tuple[float, float]
    site_b_centroid: tuple[float, float]
    ct_players_in_a: int
    ct_players_in_b: int
    t_players_in_a: int
    t_players_in_b: int
    dominant_ct_site: str     # "a", "b", or "split"
    dominant_t_site: str
    confidence: float


# ── Position clustering ────────────────────────────────────────────────────────

def cluster_round_positions(
    player_frames: list[dict],
    tick: int,
    map_name: str,
) -> Optional[RoundClusterResult]:
    """Run k-means (k=2) on player positions at a given tick to identify
    A-site vs B-site clustering.

    Parameters
    ----------
    player_frames : list of dict
        Serialized PlayerRoundKeyframe or raw frame dicts with keys:
        x, y, z, side, steam_id, tick
    tick : int
        The tick to analyze
    map_name : str
        Map identifier (e.g. "dust2")

    Returns
    -------
    RoundClusterResult or None if fewer than 4 players present
    """
    # Filter frames to the target tick (or nearest earlier tick)
    frames_at_tick = [f for f in player_frames if int(f.get("tick", 0)) == tick]
    if not frames_at_tick:
        return None

    ct_frames = [f for f in frames_at_tick if str(f.get("side", "")).lower() == "ct"]
    t_frames  = [f for f in frames_at_tick if str(f.get("side", "")).lower() == "t"]

    if len(ct_frames) < 2 and len(t_frames) < 2:
        return None

    # Rough site centroids per map (A is negative-X, B is positive-X on most maps)
    site_a, site_b = _map_site_centroids(map_name)

    # Count players per site based on proximity
    ct_a = sum(1 for f in ct_frames if _closer_to(f, site_a, site_b) == "a")
    ct_b = len(ct_frames) - ct_a
    t_a  = sum(1 for f in t_frames  if _closer_to(f, site_a, site_b) == "a")
    t_b  = len(t_frames) - t_a

    dominant_ct = "a" if ct_a > ct_b else "b" if ct_b > ct_a else "split"
    dominant_t = "a" if t_a > t_b else "b" if t_b > t_a else "split"

    # Confidence: how lopsided the distribution is
    total_ct = len(ct_frames)
    total_t  = len(t_frames)
    ct_conf  = (abs(ct_a - ct_b) / total_ct) if total_ct > 0 else 0.0
    t_conf   = (abs(t_a - t_b) / total_t) if total_t > 0 else 0.0
    confidence = round((ct_conf + t_conf) / 2, 3)

    return RoundClusterResult(
        tick=tick,
        site_a_centroid=site_a,
        site_b_centroid=site_b,
        ct_players_in_a=ct_a,
        ct_players_in_b=ct_b,
        t_players_in_a=t_a,
        t_players_in_b=t_b,
        dominant_ct_site=dominant_ct,
        dominant_t_site=dominant_t,
        confidence=confidence,
    )


def _map_site_centroids(map_name: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return (site_a_centroid, site_b_centroid) in (x, y) for each map."""
    # These are approximate world centroids — calibrated from demo data
    centroids = {
        "dust2":   ((-1400, -2400), (900, 1700)),
        "mirage":  ((-800, -300),  (900, 1100)),
        "inferno": ((-1700, 0),    (400, 1400)),
        "nuke":    ((0, -1800),    (900, 200)),
        "overpass":((-200, -2000), (200, 800)),
        "ancient": ((-1400, -1000), (1000, 400)),
    }
    return centroids.get(map_name, ((-1000, -1000), (1000, 1000)))


def _closer_to(frame: dict, site_a: tuple[float, float], site_b: tuple[float, float]) -> str:
    """Return which site (a or b) the player frame is closer to."""
    x, y = float(frame.get("x", 0)), float(frame.get("y", 0))
    da = math.hypot(x - site_a[0], y - site_a[1])
    db = math.hypot(x - site_b[0], y - site_b[1])
    return "a" if da < db else "b"


# ── Signal detection ───────────────────────────────────────────────────────────

def detect_ct_stack(
    cluster_early: Optional[RoundClusterResult],
    cluster_mid: Optional[RoundClusterResult],
    t_committed_site: str,
    ct_won: bool,
    mid_round_tick: int,
) -> Optional[TacticalSignal]:
    """Detect CT stack signal.

    Triggers when 4+ CT players cluster on one site at mid_round_tick
    and the T committed to the same (correct) or opposite (wrong) site.
    """
    if cluster_mid is None or cluster_mid.dominant_ct_site == "split":
        return None

    ct_on_committed = (
        cluster_mid.ct_players_in_a if cluster_mid.dominant_ct_site == "a" else
        cluster_mid.ct_players_in_b if cluster_mid.dominant_ct_site == "b" else 0
    )

    if ct_on_committed < 4:
        return None

    stacked_site = cluster_mid.dominant_ct_site
    correct = stacked_site == t_committed_site

    if correct:
        desc = f"CT stacked {stacked_site.upper()} ({ct_on_committed} players), T committed there, CT won"
        conf = round(0.5 + (ct_on_committed - 4) * 0.1 + (0.2 if ct_won else 0.0), 3)
        return TacticalSignal(
            signal_type="ct_stack_correct",
            side="ct",
            description=desc,
            confidence=min(0.95, conf),
            metadata={"stacked_site": stacked_site, "ct_count": ct_on_committed, "t_commit_site": t_committed_site},
        )
    else:
        desc = f"CT stacked {stacked_site.upper()} ({ct_on_committed} players), T hit opposite site"
        conf = round(0.5 + (ct_on_committed - 4) * 0.1, 3)
        return TacticalSignal(
            signal_type="ct_stack_wrong",
            side="ct",
            description=desc,
            confidence=min(0.95, conf),
            metadata={"stacked_site": stacked_site, "ct_count": ct_on_committed, "t_commit_site": t_committed_site},
        )


def detect_ct_rotate(
    cluster_early: Optional[RoundClusterResult],
    cluster_mid: Optional[RoundClusterResult],
    t_commit_site: str,
    ct_won: bool,
) -> Optional[TacticalSignal]:
    """Detect CT rotation signal.

    Triggers when CT cluster shifts between early round and mid round,
    and the rotation was correct (matched T commit) or wrong.
    """
    if cluster_early is None or cluster_mid is None:
        return None
    if cluster_early.dominant_ct_site == "split" or cluster_mid.dominant_ct_site == "split":
        return None
    if cluster_early.dominant_ct_site == cluster_mid.dominant_ct_site:
        return None  # No rotation

    early_site = cluster_early.dominant_ct_site
    mid_site   = cluster_mid.dominant_ct_site

    # Rotation was A → B or B → A
    rotated = early_site != mid_site
    correct = mid_site == t_commit_site

    if rotated and not correct:
        return TacticalSignal(
            signal_type="ct_wrong_rotate",
            side="ct",
            description=f"CT rotated from {early_site.upper()} to {mid_site.upper()}, T hit opposite",
            confidence=0.75,
            metadata={"early_site": early_site, "mid_site": mid_site, "t_commit_site": t_commit_site},
        )
    elif rotated and correct and ct_won:
        return TacticalSignal(
            signal_type="ct_correct_adapt",
            side="ct",
            description=f"CT rotated from {early_site.upper()} to {mid_site.upper()}, matched T commit, CT won",
            confidence=0.8,
            metadata={"early_site": early_site, "mid_site": mid_site, "t_commit_site": t_commit_site},
        )
    return None


def detect_t_fast_execute(
    grenade_events: list[dict],
    cluster_mid: Optional[RoundClusterResult],
    round_start_tick: int,
    mid_round_tick: int,
) -> Optional[TacticalSignal]:
    """Detect T fast execute signal.

    Triggers when 3+ T players are at a bombsite within the first ~20 seconds
    (round_tick ~20,000 at 128-tick servers) with heavy utility usage.
    """
    if cluster_mid is None:
        return None

    t_at_site = (
        cluster_mid.t_players_in_a if cluster_mid.dominant_t_site == "a" else
        cluster_mid.t_players_in_b if cluster_mid.dominant_t_site == "b" else 0
    )

    if t_at_site < 3:
        return None

    # Count grenade events from T side in first 20 seconds
    early_window = [g for g in grenade_events
                   if int(g.get("tick", 0)) <= round_start_tick + 20000
                   and str(g.get("thrower_side", "")).lower() == "t"]

    grenade_count = len(early_window)
    site = cluster_mid.dominant_t_site

    if grenade_count >= 5:  # Heavy utility
        desc = f"T fast executed {site.upper()} ({t_at_site} players, {grenade_count} grenades in first 20s)"
        conf = min(0.95, round(0.6 + t_at_site * 0.05 + grenade_count * 0.01, 3))
        return TacticalSignal(
            signal_type="t_fast_execute",
            side="t",
            description=desc,
            confidence=conf,
            metadata={"site": site, "t_players": t_at_site, "grenade_count": grenade_count},
        )
    return None


def detect_t_split(
    cluster_mid: Optional[RoundClusterResult],
    grenade_events: list[dict],
    round_start_tick: int,
) -> Optional[TacticalSignal]:
    """Detect T split signal.

    Triggers when T players are split between A and B at mid-round
    and utility was used on both sites.
    """
    if cluster_mid is None:
        return None
    if cluster_mid.dominant_t_site != "split":
        return None  # Not a split

    # Check for utility on both sites in first 25 seconds
    early_grenades = [g for g in grenade_events
                      if int(g.get("tick", 0)) <= round_start_tick + 25000]
    nades_by_site: dict[str, int] = {"a": 0, "b": 0}
    for g in early_grenades:
        x, y = float(g.get("x", 0)), float(g.get("y", 0))
        # Simple A/B split based on x-coordinate sign
        site = "a" if x < 0 else "b"
        nades_by_site[site] += 1

    if nades_by_site["a"] >= 2 and nades_by_site["b"] >= 2:
        return TacticalSignal(
            signal_type="t_split_correct",
            side="t",
            description=f"T split with utility on both sites (A:{nades_by_site['a']} nades, B:{nades_by_site['b']} nades)",
            confidence=0.75,
            metadata={"a_nades": nades_by_site["a"], "b_nades": nades_by_site["b"]},
        )
    return None


def detect_t_fake(
    grenade_events: list[dict],
    cluster_mid: Optional[RoundClusterResult],
    round_start_tick: int,
) -> Optional[TacticalSignal]:
    """Detect T fake signal.

    Triggers when utility (smoke/flash) was deployed at one site but
    T players ended up at the other site at mid-round.
    """
    if cluster_mid is None or cluster_mid.dominant_t_site == "split":
        return None

    t_site = cluster_mid.dominant_t_site

    # Look for utility at the NON-committed site in first 15s
    fake_site = "b" if t_site == "a" else "a"
    fake_utility = [
        g for g in grenade_events
        if int(g.get("tick", 0)) <= round_start_tick + 15000
        and str(g.get("thrower_side", "")).lower() == "t"
        and g.get("grenade_type", "") in ("smoke", "flash")
    ]

    # Count utility on the fake site using x-coordinate (negative X = A side)
    def _on_fake_site(g: dict) -> bool:
        x = float(g.get("x", 0))
        return x < 0 if fake_site == "a" else x >= 0

    fake_nades = sum(1 for g in fake_utility if _on_fake_site(g))

    if fake_nades >= 2:
        return TacticalSignal(
            signal_type="t_fake_detected",
            side="t",
            description=f"T faked {fake_site.upper()} with {fake_nades} utility pieces, committed to {t_site.upper()}",
            confidence=0.7,
            metadata={"fake_site": fake_site, "commit_site": t_site, "fake_nade_count": fake_nades},
        )
    return None


# ── Main entry point ───────────────────────────────────────────────────────────

def classify_round_tactical_signals(
    player_frames: list[dict],
    grenade_events: list[dict],
    round_start_tick: int,
    mid_round_tick: int,
    round_end_tick: int,
    map_name: str,
    round_number: int,
    t_committed_site: str,    # "a", "b", or "split"
    ct_won: bool,
) -> list[TacticalSignal]:
    """Detect all tactical signals for a round.

    Parameters
    ----------
    player_frames : list of dict
        Serialized PlayerRoundKeyframe or raw frame dicts
    grenade_events : list of dict
        Dicts from grenade_detonations with keys: tick, grenade_type,
        thrower_side, x, y, z
    round_start_tick : int
    mid_round_tick : int
        Tick at ~15-20 seconds into the round (representative of mid-round)
    round_end_tick : int
    map_name : str
    round_number : int
    t_committed_site : str
        Which site T committed to: "a", "b", or "split"
    ct_won : bool

    Returns
    -------
    list of TacticalSignal
    """
    # Cluster positions at early and mid round
    cluster_early = cluster_round_positions(player_frames, round_start_tick, map_name)
    cluster_mid   = cluster_round_positions(player_frames, mid_round_tick,   map_name)

    signals: list[TacticalSignal] = []

    # CT signals
    ct_stack = detect_ct_stack(cluster_early, cluster_mid, t_committed_site, ct_won, mid_round_tick)
    if ct_stack:
        signals.append(ct_stack)

    ct_rotate = detect_ct_rotate(cluster_early, cluster_mid, t_committed_site, ct_won)
    if ct_rotate:
        signals.append(ct_rotate)

    # T signals
    t_fast = detect_t_fast_execute(grenade_events, cluster_mid, round_start_tick, mid_round_tick)
    if t_fast:
        signals.append(t_fast)

    t_split = detect_t_split(cluster_mid, grenade_events, round_start_tick)
    if t_split:
        signals.append(t_split)

    t_fake = detect_t_fake(grenade_events, cluster_mid, round_start_tick)
    if t_fake:
        signals.append(t_fake)

    return signals
