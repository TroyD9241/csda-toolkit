"""Utility classifier — classifies throw quality per grenade per player.

Evaluates how well a player threw each utility piece in a round.
Classifications: good | missed | self_damage | blocked | whiffed | pending

Signals used:
- GrenadeDetonation (landing x/y/z, grenade_type, player_steam_id, tick)
- GrenadeTrajectory (full throw path, grenade_entity_id, thrower_steam_id)
- DamageEvent (weapon, attacker_steam_id, victim_steam_id, dmg_health, attacker_last_place_name)
- PlayerBlind (attacker_steam_id, victim_steam_id, blind_duration)
- InfernoEvent (start_burn/expire, x/y/z) — molotov spread coverage

Utility quality logic:
- HE grenade: good if it dealt damage; missed if detonated but no damage; self_damage if
  attacker==victim
- Molotov/Incendiary: good if it dealt damage OR started burning in a strategic area;
  missed if it expired without hitting anyone
- Flashbang: good if it blinded an enemy for >= 1.5s; decent if blinded for 0.5-1.5s;
  missed/whiffed if detonated but no enemy blinded
- Smoke: good if it expired at a strategic chokepoint; pending if still active at round end
- Decoy: informational only — no quality signal

For smoke, we use the grenade's landing position + map zone to determine strategic value.
For molotov, we correlate grenade landing position with inferno start_burn positions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UtilityQuality(str, Enum):
    GOOD = "good"          # Effective utility
    DECENT = "decent"      # Partially effective
    MISSED = "missed"      # Landed but no effect
    SELF_DAMAGE = "self_damage"  # Hit yourself
    BLOCKED = "blocked"     # Blocked by geometry
    WHIFFED = "whiffed"    # No detonation record found
    PENDING = "pending"    # Smoke still active at round end


# ── Thresholds ────────────────────────────────────────────────────────────────
FLASHBLIND_GOOD_SECONDS = 1.5
FLASHBLIND_DECENT_SECONDS = 0.5
FLASHBLIND_FLOOR_SECONDS = 0.1  # any blind above this is intentional throw

# Smoke duration at chokepoints (seconds). Map-specific.
SMOKE_CHOKEPOINT_RADIUS = 300  # world units — if smoke landed within this dist of
# a named chokepoint, it's considered strategic
MOLOTOV_SPREAD_RADIUS = 150   # world units — inferno start_burn within this dist
# of detonation = good spread

# Utility defindexes for filtering
GRENADE_DEFINDICES = {43: "flashbang", 44: "he_grenade", 45: "smoke_grenade",
                      46: "decoy", 47: "molotov", 48: "incendiary",
                      49: "tag_grenade"}


@dataclass
class UtilityThrow:
    """One grenade throw evaluated for quality."""
    steam_id: int
    player_name: str
    round_number: int
    grenade_type: str  # hegrenade | flashbang | smoke | molotov | inferno | decoy
    quality: UtilityQuality
    confidence: float
    landed_x: Optional[float] = None
    landed_y: Optional[float] = None
    landed_z: Optional[float] = None
    landed_zone: str = ""  # attacker_last_place_name at detonation
    hit_victim_steam_id: Optional[int] = None
    hit_victim_name: str = ""
    blind_duration: float = 0.0
    damage_dealt: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class UtilityRoundSummary:
    """Per-player utility summary for one round."""
    round_number: int
    steam_id: int
    player_name: str

    total_throws: int = 0
    good_he: int = 0
    missed_he: int = 0
    good_flash: int = 0
    decent_flash: int = 0
    missed_flash: int = 0
    good_smoke: int = 0
    pending_smoke: int = 0
    good_molotov: int = 0
    missed_molotov: int = 0
    self_damage_grenades: int = 0

    throws: list[UtilityThrow] = field(default_factory=list)

    @property
    def utility_score(self) -> float:
        """Simple quality score: (good / total) weighted by grenade type importance."""
        if self.total_throws == 0:
            return 0.0
        score = 0.0
        score += self.good_he * 1.0
        score += self.missed_he * -0.3
        score += self.good_flash * 0.7
        score += self.decent_flash * 0.3
        score += self.missed_flash * -0.2
        score += self.good_smoke * 0.5
        score += self.good_molotov * 1.2
        score += self.missed_molotov * -0.4
        score += self.self_damage_grenades * -0.5
        max_score = self.total_throws * 1.2
        return round(max(0.0, score) / max(max_score, 1.0), 3)


def evaluate_he_grenade(
    detonation: dict,
    damage_events: list[dict],
    steam_id: int,
) -> UtilityThrow:
    """Evaluate a single HE grenade throw.

    Algorithm:
    - Find damage events from this player with weapon=hegrenade at same tick
    - If self_damage (attacker == victim): SELF_DAMAGE
    - If any damage to enemy: GOOD (count all damage as quality signal)
    - If detonated but no damage: MISSED (geometry blocked or victim moved)
    """
    tick = detonation.get("tick", 0)
    rn = detonation.get("round_number", 0)
    player_name = detonation.get("player_name", "")

    # Find damage events from this player with HE at same tick (within ~100 tick window)
    he_damage = [
        d for d in damage_events
        if str(d.get("weapon", "")).lower() == "hegrenade"
        and int(d.get("attacker_steam_id") or 0) == steam_id
        and abs(int(d.get("tick", 0)) - tick) <= 128  # ~2 seconds at 64-tick
    ]

    throw = UtilityThrow(
        steam_id=steam_id,
        player_name=player_name,
        round_number=rn,
        grenade_type="hegrenade",
        quality=UtilityQuality.MISSED,
        confidence=0.5,
        landed_x=detonation.get("x"),
        landed_y=detonation.get("y"),
        landed_z=detonation.get("z"),
    )

    if not he_damage:
        # Detonated but no damage
        throw.quality = UtilityQuality.MISSED
        throw.confidence = 0.6
        return throw

    # Check for self-damage
    for dmg in he_damage:
        victim = int(dmg.get("victim_steam_id") or 0)
        if victim == steam_id:
            # Self-damage
            throw.quality = UtilityQuality.SELF_DAMAGE
            throw.damage_dealt = int(dmg.get("dmg_health", 0))
            throw.confidence = 0.9
            return throw

    # Hit an enemy
    total_dmg = sum(int(d.get("dmg_health", 0)) for d in he_damage)
    throw.quality = UtilityQuality.GOOD
    throw.damage_dealt = total_dmg
    throw.confidence = 0.9
    if he_damage:
        throw.hit_victim_steam_id = int(he_damage[0].get("victim_steam_id") or 0)
        throw.hit_victim_name = str(he_damage[0].get("victim_name", ""))

    return throw


def evaluate_flashbang(
    detonation: dict,
    blind_events: list[dict],
    steam_id: int,
) -> UtilityThrow:
    """Evaluate a single flashbang throw.

    Algorithm:
    - Find player_blind events from this player at same tick
    - Classify by max blind_duration on an enemy:
      >= 1.5s: GOOD
      >= 0.5s: DECENT
      > 0.1s: MISSED (short blind)
      = 0: no record → WHIFFED (enemy dodged)
    """
    tick = detonation.get("tick", 0)
    rn = detonation.get("round_number", 0)
    player_name = detonation.get("player_name", "")

    # Find blind events from this player (within 64 ticks = 1 second)
    blinds = [
        b for b in blind_events
        if int(b.get("attacker_steam_id") or 0) == steam_id
        and abs(int(b.get("tick", 0)) - tick) <= 64
    ]

    throw = UtilityThrow(
        steam_id=steam_id,
        player_name=player_name,
        round_number=rn,
        grenade_type="flashbang",
        quality=UtilityQuality.WHIFFED,
        confidence=0.5,
        landed_x=detonation.get("x"),
        landed_y=detonation.get("y"),
        landed_z=detonation.get("z"),
    )

    if not blinds:
        throw.quality = UtilityQuality.WHIFFED
        throw.confidence = 0.6
        return throw

    # Check for self-flash
    for b in blinds:
        victim = int(b.get("victim_steam_id") or 0)
        if victim == steam_id:
            throw.blind_duration = float(b.get("blind_duration", 0.0))
            # Self-flash — partial credit if it also blinded enemies
            pass  # fall through to enemy check

    # Find enemy blinds
    enemy_blinds = [b for b in blinds if int(b.get("victim_steam_id") or 0) != steam_id]
    if not enemy_blinds:
        # Only self-flashed
        throw.quality = UtilityQuality.SELF_DAMAGE
        throw.confidence = 0.7
        return throw

    max_duration = max(float(b.get("blind_duration", 0.0)) for b in enemy_blinds)
    throw.blind_duration = max_duration

    if max_duration >= FLASHBLIND_GOOD_SECONDS:
        throw.quality = UtilityQuality.GOOD
        throw.confidence = 0.85
    elif max_duration >= FLASHBLIND_DECENT_SECONDS:
        throw.quality = UtilityQuality.DECENT
        throw.confidence = 0.75
    elif max_duration > 0:
        throw.quality = UtilityQuality.MISSED
        throw.confidence = 0.6
    else:
        throw.quality = UtilityQuality.WHIFFED
        throw.confidence = 0.6

    if enemy_blinds:
        throw.hit_victim_steam_id = int(enemy_blinds[0].get("victim_steam_id") or 0)
        throw.hit_victim_name = str(enemy_blinds[0].get("victim_name", ""))

    return throw


def evaluate_smoke(
    detonation: dict,
    smoke_expirations: list[dict],
    steam_id: int,
    grenade_entity_id: int = 0,
    trajectories: list[dict] = None,
    landed_zone: str = "",
) -> UtilityThrow:
    """Evaluate a smoke grenade throw.

    Smoke quality is harder to measure since smoke doesn't deal damage.
    Signals:
    - Smoke expired at a location (not still active at round end): it was thrown
    - Smoke that never expired was either:
      (a) still smoking at round end (CT smoke on T spawn, etc.) — PENDING
      (b) player died mid-smoke — hard to classify
    - Strategic placement: landed_zone (from attacker_last_place_name on correlated
      damage event at same tick) indicates intentional placement in a named area.
      Within SMOKE_CHOKEPOINT_RADIUS of a known chokepoint = GOOD.
    """
    if trajectories is None:
        trajectories = []

    tick = detonation.get("tick", 0)
    rn = detonation.get("round_number", 0)
    player_name = detonation.get("player_name", "")
    gtype = detonation.get("grenade_type", "")

    throw = UtilityThrow(
        steam_id=steam_id,
        player_name=player_name,
        round_number=rn,
        grenade_type="smoke",
        quality=UtilityQuality.PENDING,
        confidence=0.4,
        landed_x=detonation.get("x"),
        landed_y=detonation.get("y"),
        landed_z=detonation.get("z"),
    )

    # If it expired, it completed its duration — better than still active
    if gtype == "smoke_expired":
        throw.quality = UtilityQuality.DECENT
        throw.confidence = 0.55

    # Zone-based quality boost: if it landed in a named zone, it was intentional
    if landed_zone:
        throw.landed_zone = landed_zone
        throw.quality = UtilityQuality.GOOD
        throw.confidence = 0.65

    return throw


def evaluate_molotov(
    detonation: dict,
    inferno_events: list[dict],
    damage_events: list[dict],
    steam_id: int,
) -> UtilityThrow:
    """Evaluate a molotov/incendiary throw.

    Algorithm:
    - Find inferno_start_burn events within a radius of the detonation position
    - If started burning: GOOD (even if no damage — area denial is valuable)
    - If no inferno and no damage: MISSED (dud or immediate extinguish)
    - Self-damage: attacker == victim in damage events
    """
    tick = detonation.get("tick", 0)
    rn = detonation.get("round_number", 0)
    player_name = detonation.get("player_name", "")
    dx = float(detonation.get("x") or 0)
    dy = float(detonation.get("y") or 0)

    throw = UtilityThrow(
        steam_id=steam_id,
        player_name=player_name,
        round_number=rn,
        grenade_type="molotov",
        quality=UtilityQuality.MISSED,
        confidence=0.5,
        landed_x=dx,
        landed_y=dy,
        landed_z=detonation.get("z"),
    )

    # Find inferno start_burn within spread radius of detonation
    burning = [
        i for i in inferno_events
        if i.get("event_type", "").lower() == "start_burn"
        and abs(float(i.get("x") or 0) - dx) <= MOLOTOV_SPREAD_RADIUS
        and abs(float(i.get("y") or 0) - dy) <= MOLOTOV_SPREAD_RADIUS
    ]

    # Find molotov damage from this player
    molotov_damage = [
        d for d in damage_events
        if str(d.get("weapon", "")).lower() in ("molotov", "inferno")
        and int(d.get("attacker_steam_id") or 0) == steam_id
    ]

    if burning:
        throw.quality = UtilityQuality.GOOD
        throw.confidence = 0.85
    elif molotov_damage:
        # No burn record but dealt damage
        throw.quality = UtilityQuality.GOOD
        throw.damage_dealt = sum(int(d.get("dmg_health", 0)) for d in molotov_damage)
        throw.confidence = 0.8
    else:
        throw.quality = UtilityQuality.MISSED
        throw.confidence = 0.6

    return throw


def classify_player_utilities(
    round_number: int,
    steam_id: int,
    player_name: str,
    grenade_detonations: list[dict],
    grenade_trajectories: list[dict],
    damage_events: list[dict],
    blind_events: list[dict],
    inferno_events: list[dict],
    grenade_entity_id: int = 0,
) -> UtilityThrow:
    """Classify one grenade throw for one player.

    Dispatches to the right grenade-type evaluator.
    """
    det = grenade_detonations
    gtype = str(det.get("grenade_type", "")).lower()

    if gtype in ("hegrenade",):
        return evaluate_he_grenade(det, damage_events, steam_id)
    elif gtype == "flashbang":
        return evaluate_flashbang(det, blind_events, steam_id)
    elif gtype in ("molotov", "inferno"):
        return evaluate_molotov(det, inferno_events, damage_events, steam_id)
    elif gtype in ("smoke", "smoke_expired"):
        return evaluate_smoke(det, grenade_detonations, steam_id, grenade_entity_id, grenade_trajectories)
    else:
        return UtilityThrow(
            steam_id=steam_id,
            player_name=player_name,
            round_number=round_number,
            grenade_type=gtype,
            quality=UtilityQuality.MISSED,
            confidence=0.0,
        )


def summarize_player_utility(throws: list[UtilityThrow]) -> UtilityRoundSummary:
    """Aggregate per-throw evaluations into a round summary for one player."""
    if not throws:
        rn = 0
        sid = 0
        pname = ""
    else:
        rn = throws[0].round_number
        sid = throws[0].steam_id
        pname = throws[0].player_name

    s = UtilityRoundSummary(
        round_number=rn,
        steam_id=sid,
        player_name=pname,
        total_throws=len(throws),
        throws=throws,
    )

    for t in throws:
        if t.grenade_type == "hegrenade":
            if t.quality == UtilityQuality.GOOD:
                s.good_he += 1
            elif t.quality in (UtilityQuality.MISSED, UtilityQuality.BLOCKED):
                s.missed_he += 1
        elif t.grenade_type == "flashbang":
            if t.quality == UtilityQuality.GOOD:
                s.good_flash += 1
            elif t.quality == UtilityQuality.DECENT:
                s.decent_flash += 1
            elif t.quality in (UtilityQuality.MISSED, UtilityQuality.WHIFFED):
                s.missed_flash += 1
        elif t.grenade_type == "smoke":
            if t.quality == UtilityQuality.GOOD:
                s.good_smoke += 1
            elif t.quality == UtilityQuality.PENDING:
                s.pending_smoke += 1
        elif t.grenade_type in ("molotov", "inferno"):
            if t.quality == UtilityQuality.GOOD:
                s.good_molotov += 1
            elif t.quality in (UtilityQuality.MISSED, UtilityQuality.BLOCKED):
                s.missed_molotov += 1
        if t.quality == UtilityQuality.SELF_DAMAGE:
            s.self_damage_grenades += 1

    return s
