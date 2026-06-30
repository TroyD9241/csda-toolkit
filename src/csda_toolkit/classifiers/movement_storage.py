"""Movement storage — keyframes, zone transitions, and per-round movement summaries.

Three storage layers:
1. KEYFRAMES: Sampled player positions at tick intervals (every 1000 ticks ≈ 15s).
   Use case: reconstruct movement paths, heatmaps, average positions.
2. ZONE TRANSITIONS: When a player's CS2-internal zone (last_place_name) changes
   within a round. Use case: T/CT positioning patterns, rotation timing, stack detection.
3. MOVEMENT SUMMARY: Aggregated stats per player per round. Use case: distance
   traveled, time in zones, average speed, velocity.

For zone transitions, we use CS2's internal `last_place_name` from damage events —
the game already labels zones like 'Long A', 'BombsiteA', 'Mid', etc.
For players with no damage events in a round, zone transitions are unknown.
"""

from dataclasses import dataclass
from typing import Optional

from csda_toolkit.parsing.constants import weapon_category


# ── Domain models ──────────────────────────────────────────────────────────────


@dataclass
class PlayerRoundKeyframe:
    """One sampled position for one player at one tick."""
    match_id: int
    round_number: int
    steam_id: int
    player_name: str
    tick: int
    x: float
    y: float
    z: float
    eye_angle_x: float = 0.0
    eye_angle_y: float = 0.0
    eye_angle_z: float = 0.0
    velocity_modifier: float = 1.0
    is_alive: bool = True
    health: int = 100
    side: str = ""  # "t" or "ct"


@dataclass
class PlayerRoundZoneTransition:
    """A player's zone change within a round.

    Produced by tracking changes in attacker_last_place_name from damage events.
    Also includes the player's zone at round start and end.
    """
    match_id: int
    round_number: int
    steam_id: int
    player_name: str
    side: str

    tick: int                # tick when this zone was entered
    zone: str                # CS2 zone name (e.g. 'Long A', 'BombsiteA')
    zone_category: str       # "site" | "mid" | "spawn" | "connector" | "unknown"


@dataclass
class PlayerRoundMovementSummary:
    """Aggregated movement statistics per player per round."""
    match_id: int
    round_number: int
    steam_id: int
    player_name: str
    side: str

    # Distance and speed
    total_distance: float = 0.0    # world units traveled (from keyframes)
    avg_speed: float = 0.0         # distance / time alive
    max_speed: float = 0.0         # peak velocity

    # Zone occupancy (seconds in each zone category)
    time_in_site: float = 0.0     # seconds on/near bombsite
    time_in_mid: float = 0.0      # seconds in mid
    time_in_spawn: float = 0.0    # seconds in T/CT spawn
    time_in_connector: float = 0.0

    # Zone transitions
    zone_transition_count: int = 0
    unique_zones_visited: int = 0

    # Combat activity
    damage_dealt: int = 0
    kills: int = 0
    deaths: int = 0

    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def movement_score(self) -> float:
        """High movement = active player, low = passive/anchor."""
        if self.avg_speed == 0:
            return 0.0
        # Normalize: avg speed of ~200 units/sec is very active, ~50 is passive
        return round(min(1.0, self.avg_speed / 200.0), 3)


# ── Zone categorization ────────────────────────────────────────────────────────


ZONE_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "site": ["bombsite", "site", "a site", "b site", "long a", "short a",
             "b_short", "a_main", "b_main", "a_plant", "b_plant"],
    "mid": ["mid", "middle", "center", "middoors", "midDoor"],
    "spawn": ["spawn", "t_spawn", "ct_spawn", "terrorist spawn", "ct spawn",
              "outside", "backyard"],
    "connector": ["connector", "link", "access", "cross"],
}


def categorize_zone(zone_name: str) -> str:
    """Infer the category of a CS2 zone name.

    Uses keyword matching since CS2 zone names are not perfectly structured.
    Falls back to 'unknown' if no keyword matches.
    """
    if not zone_name:
        return "unknown"
    zone_lower = zone_name.lower()
    for category, keywords in ZONE_CATEGORY_KEYWORDS.items():
        if any(kw in zone_lower for kw in keywords):
            return category
    return "unknown"


# ── Keyframe sampling ─────────────────────────────────────────────────────────
#
# Keyframes are sampled every N ticks from the raw player_frames.


def _frame_to_keyframe(frame: dict, match_id: int, tick: int, round_number: int) -> PlayerRoundKeyframe:
    """Convert a raw frame dict to a PlayerRoundKeyframe."""
    return PlayerRoundKeyframe(
        match_id=match_id,
        round_number=round_number,
        steam_id=int(frame.get("steam_id", 0)),
        player_name=str(frame.get("name", "")),
        tick=tick,
        x=float(frame.get("x", 0.0)),
        y=float(frame.get("y", 0.0)),
        z=float(frame.get("z", 0.0)),
        eye_angle_x=float(frame.get("eye_angle_x", 0.0)),
        eye_angle_y=float(frame.get("eye_angle_y", 0.0)),
        eye_angle_z=float(frame.get("eye_angle_z", 0.0)),
        velocity_modifier=float(frame.get("velocity_modifier", 1.0)),
        is_alive=bool(frame.get("is_alive", True)),
        health=int(frame.get("health", 100)),
        side=str(frame.get("side", "")),
    )
# At 64-tick:
#   500 ticks = 7.8s  (fine grain, ~24 per 2-min round)
#   1000 ticks = 15.6s (coarse grain, ~12 per 2-min round)
#   2000 ticks = 31s   (very coarse, ~4 per round)

KEYFRAME_TICK_INTERVAL = 1000  # world units per keyframe sample


def sample_keyframes(
    player_frames: list[dict],
    match_id: int,
    round_number: int,
    KEYFRAME_INTERVAL: int = KEYFRAME_TICK_INTERVAL,
) -> list[PlayerRoundKeyframe]:
    """Sample keyframes from raw player frame data.

    Takes all player frames and samples every KEYFRAME_INTERVAL ticks.
    This reduces storage from ~7680 frames/player/round to ~8.
    """
    if not player_frames:
        return []

    # Group frames by tick
    frames_by_tick: dict[int, list[dict]] = {}
    for frame in player_frames:
        tick = int(frame.get("tick", 0))
        if tick not in frames_by_tick:
            frames_by_tick[tick] = []
        frames_by_tick[tick].append(frame)

    if not frames_by_tick:
        return []

    sorted_ticks = sorted(frames_by_tick.keys())
    if len(sorted_ticks) < 2:
        # Only one unique tick — still record the position(s), no distance to compute
        all_frames: list[PlayerRoundKeyframe] = []
        for frame in frames_by_tick.get(sorted_ticks[0], []):
            all_frames.append(_frame_to_keyframe(frame, match_id, sorted_ticks[0], round_number))
        return all_frames

    keyframe_ticks: list[int] = []
    first_tick = sorted_ticks[0]
    last_tick = sorted_ticks[-1]

    tick = first_tick
    while tick <= last_tick:
        keyframe_ticks.append(tick)
        tick += KEYFRAME_INTERVAL

    # Always include the last tick
    if keyframe_ticks[-1] != last_tick:
        keyframe_ticks.append(last_tick)

    # For each keyframe tick, find the nearest actual tick with data
    keyframes: list[PlayerRoundKeyframe] = []

    for kt in keyframe_ticks:
        # Find closest tick ≤ kt
        closest_tick = max(t for t in sorted_ticks if t <= kt)
        frames = frames_by_tick.get(closest_tick, [])

        for frame in frames:
            keyframes.append(_frame_to_keyframe(frame, match_id, closest_tick, round_number))

    return keyframes


# ── Zone transitions ────────────────────────────────────────────────────────────


def extract_zone_transitions(
    damage_events: list[dict],
    match_id: int,
    side_map: Optional[dict[int, str]] = None,
) -> list[PlayerRoundZoneTransition]:
    """Extract zone transitions from damage events.

    For each player, track changes in their attacker_last_place_name within
    a round. Each change = a new zone entry.

    Note: this only captures zones where damage occurred. Players who dealt
    no damage in a round will have no zone transition records.
    """
    transitions: list[PlayerRoundZoneTransition] = []
    side_map = side_map or {}

    # Group damage events by (steam_id, round_number) in tick order
    events_by_player: dict[tuple[int, int], list[dict]] = {}
    for ev in damage_events:
        sid = int(ev.get("attacker_steam_id") or 0)
        if sid == 0:
            continue
        rn = int(ev.get("round_number", 0))
        if rn == 0:
            continue
        key = (sid, rn)
        if key not in events_by_player:
            events_by_player[key] = []
        events_by_player[key].append(ev)

    for (sid, rn), events in events_by_player.items():
        # Sort by tick
        events = sorted(events, key=lambda e: int(e.get("tick", 0)))

        last_zone = None
        for ev in events:
            zone = str(ev.get("attacker_last_place_name", "")).strip()
            if not zone:
                continue
            if zone != last_zone:
                player_side = side_map.get(sid, "")
                transitions.append(PlayerRoundZoneTransition(
                    match_id=match_id,
                    round_number=rn,
                    steam_id=sid,
                    player_name=str(ev.get("attacker_name", "")),
                    side=player_side,
                    tick=int(ev.get("tick", 0)),
                    zone=zone,
                    zone_category=categorize_zone(zone),
                ))
                last_zone = zone

    return transitions


# ── Movement summaries ──────────────────────────────────────────────────────────


def compute_movement_summary(
    keyframes: list[PlayerRoundKeyframe],
    zone_transitions: list[PlayerRoundZoneTransition],
    damage_events: list[dict],
    kill_events: list[dict],
    match_id: int,
) -> list[PlayerRoundMovementSummary]:
    """Compute per-player per-round movement summaries from keyframes + zones."""
    summaries: dict[tuple[int, int], PlayerRoundMovementSummary] = {}

    # Build keyframe map
    kf_by_player_round: dict[tuple[int, int], list[PlayerRoundKeyframe]] = {}
    for kf in keyframes:
        key = (kf.steam_id, kf.round_number)
        kf_by_player_round.setdefault(key, []).append(kf)

    # Build zone transition map
    zt_by_player_round: dict[tuple[int, int], list[PlayerRoundZoneTransition]] = {}
    for zt in zone_transitions:
        key = (zt.steam_id, zt.round_number)
        zt_by_player_round.setdefault(key, []).append(zt)

    # Build damage map
    dmg_by_player_round: dict[tuple[int, int], list[dict]] = {}
    for d in damage_events:
        sid = int(d.get("attacker_steam_id") or 0)
        rn = int(d.get("round_number", 0))
        if sid == 0 or rn == 0:
            continue
        dmg_by_player_round.setdefault((sid, rn), []).append(d)

    # Build kill map
    kill_by_player_round: dict[tuple[int, int], dict] = {}
    for k in kill_events:
        sid = int(k.get("killer_steam_id") or 0)
        rn = int(k.get("round_number", 0))
        if sid == 0 or rn == 0:
            continue
        kill_by_player_round[(sid, rn)] = k

    # Collect all (steam_id, round_number) pairs
    all_keys = set(kf_by_player_round.keys()) | set(zt_by_player_round.keys())

    for (sid, rn) in all_keys:
        kfs = sorted(kf_by_player_round.get((sid, rn), []), key=lambda k: k.tick)
        zts = sorted(zt_by_player_round.get((sid, rn), []), key=lambda z: z.tick)

        if not kfs:
            continue

        # Distance traveled
        total_dist = 0.0
        max_speed = 0.0
        prev_kf = None
        alive_kfs = [k for k in kfs if k.is_alive]

        for kf in alive_kfs:
            if prev_kf is not None:
                dt = abs(kf.tick - prev_kf.tick) / 64.0  # seconds
                dist = ((kf.x - prev_kf.x)**2 + (kf.y - prev_kf.y)**2 + (kf.z - prev_kf.z)**2)**0.5
                total_dist += dist
                if dt > 0:
                    speed = dist / dt
                    max_speed = max(max_speed, speed)
            prev_kf = kf

        alive_time = len(alive_kfs) * KEYFRAME_TICK_INTERVAL / 64.0  # seconds
        avg_speed = total_dist / alive_time if alive_time > 0 else 0.0

        # Zone time
        time_in_site = sum(1 for z in zts if z.zone_category == "site") * (KEYFRAME_TICK_INTERVAL / 64.0)
        time_in_mid = sum(1 for z in zts if z.zone_category == "mid") * (KEYFRAME_TICK_INTERVAL / 64.0)
        time_in_spawn = sum(1 for z in zts if z.zone_category == "spawn") * (KEYFRAME_TICK_INTERVAL / 64.0)
        time_in_connector = sum(1 for z in zts if z.zone_category == "connector") * (KEYFRAME_TICK_INTERVAL / 64.0)

        # Damage dealt
        player_dmg = dmg_by_player_round.get((sid, rn), [])
        total_dmg = sum(int(d.get("dmg_health", 0)) for d in player_dmg)

        # Kills / deaths
        kills = 1 if (sid, rn) in kill_by_player_round else 0
        deaths = 1 if any(int(d.get("victim_steam_id") or 0) == sid for d in damage_events) else 0

        pname = kfs[0].player_name if kfs else ""
        side = kfs[0].side if kfs else ""

        unique_zones = len(set(z.zone_category for z in zts if z.zone_category != "unknown"))

        summaries[(sid, rn)] = PlayerRoundMovementSummary(
            match_id=match_id,
            round_number=rn,
            steam_id=sid,
            player_name=pname,
            side=side,
            total_distance=round(total_dist, 1),
            avg_speed=round(avg_speed, 1),
            max_speed=round(max_speed, 1),
            time_in_site=round(time_in_site, 1),
            time_in_mid=round(time_in_mid, 1),
            time_in_spawn=round(time_in_spawn, 1),
            time_in_connector=round(time_in_connector, 1),
            zone_transition_count=len(zts),
            unique_zones_visited=unique_zones,
            damage_dealt=total_dmg,
            kills=kills,
            deaths=deaths,
        )

    return list(summaries.values())
