"""Round archetype classifier — classifies the tactical type of each round.

Round archetypes: default, exec, contact, split, fake, late_hit, retakesave, save, unknown.

Signals used:
- bomb_events (plant site: A/B, or no plant = anti-eco/force)
- grenade_detonations (count + types per side → exec vs rush vs default)
- inferno_events (molotov placement → site commitment)
- damage_events with attacker_last_place_name (CS2 zone labels: 'Long A', 'BombsiteA', etc.)
- economy (eco round → save/contact, full buy → exec/split)
- round_end_reason (clutch, retake, etc.)

The last_place_name approach uses CS2's internal map zone labels directly —
no bounding-box inference needed. Values like 'Long A', 'BombsiteA', 'Mid',
'T Spawn', 'CT Spawn' come from the game engine.
"""

from dataclasses import dataclass
from typing import Optional

from csda_toolkit.domain.models import RoundArchetype


# ── Grenade type constants ──────────────────────────────────────────────────────

HE_GRENADE = "hegrenade"
FLASHBANG = "flashbang"
SMOKE = "smoke"
SMOKE_EXPIRED = "smoke_expired"
MOLOTOV = "molotov"
INFERNO = "inferno"


# ── Signal thresholds ─────────────────────────────────────────────────────────
#
# Thresholds are calibrated from actual demo data, not arbitrary values.
# Adjust based on observed distributions across maps.

GRENADE_RUSH_THRESHOLD = 2    # T side with <= this many grenades total = rush
GRENADE_EXEC_THRESHOLD = 6    # > this many grenades = exec (deliberate setup)
MOLOTOV_COMMIT_THRESHOLD = 2  # > this many molotovs = committed site take
FLASH_PER_ATTACKER_THRESHOLD = 2  # avg flashes per attacker = coordinated exec


@dataclass
class RoundArchetypeSignals:
    """Raw signals extracted from a round's events."""
    round_number: int
    was_planted: bool
    plant_site: str = ""  # "A" | "B" | ""
    bomb_defused: bool = False
    bomb_exploded: bool = False

    # T-side grenade counts
    t_he_count: int = 0
    t_flash_count: int = 0
    t_smoke_count: int = 0
    t_molotov_count: int = 0
    t_total_nades: int = 0

    # CT-side grenade counts
    ct_he_count: int = 0
    ct_flash_count: int = 0
    ct_smoke_count: int = 0
    ct_molotov_count: int = 0
    ct_total_nades: int = 0

    # Damage activity
    total_damage_events: int = 0
    damage_events_in_plant_zone: int = 0  # damage in bomb site's zone

    # Inferno (molotov) coverage
    inferno_count: int = 0

    # Last-place zones from CS2 (attacker_last_place_name from damage events)
    unique_attacker_zones: list[str] = None

    # Economy signals
    t_buy_type: str = "unknown"  # eco | half | full
    ct_buy_type: str = "unknown"

    def __post_init__(self):
        if self.unique_attacker_zones is None:
            self.unique_attacker_zones = []

    @property
    def t_avg_grenades_per_player(self) -> float:
        """Approximate avg grenades per alive T. 5 is max attackers."""
        return self.t_total_nades / 5.0

    @property
    def was_rush(self) -> bool:
        return self.t_total_nades <= GRENADE_RUSH_THRESHOLD

    @property
    def was_exec(self) -> bool:
        return self.t_total_nades >= GRENADE_EXEC_THRESHOLD

    @property
    def was_ct_aggressive(self) -> bool:
        """CTs used lots of utility = they were pushing, not holding."""
        return self.ct_total_nades >= GRENADE_EXEC_THRESHOLD

    @property
    def site_matches_plant(self) -> bool:
        """Attackers dealt damage in the planted site's zone."""
        if not self.plant_site:
            return False
        zones_lower = [z.lower() for z in self.unique_attacker_zones]
        site_zone = f"bombsite{self.plant_site.lower()}"
        return any(site_zone in z for z in zones_lower)


def extract_round_signals(
    round_number: int,
    bomb_events: list[dict],
    grenade_detonations: list[dict],
    inferno_events: list[dict],
    damage_events: list[dict],
    t_steam_ids: set[int],
    t_buy_type: str = "unknown",
    ct_buy_type: str = "unknown",
) -> RoundArchetypeSignals:
    """Extract raw signals from a round's event data.

    Parameters
    ----------
    round_number : int
    bomb_events : list of dict — BombEvent model serialized
    grenade_detonations : list of dict — GrenadeDetonation model serialized
    inferno_events : list of dict — InfernoEvent model serialized
    damage_events : list of dict — DamageEvent model serialized
    t_steam_ids : set of int — steam IDs of T-side players this round
    t_buy_type, ct_buy_type : str — buy classification from economy classifier

    Returns
    -------
    RoundArchetypeSignals
    """
    signals = RoundArchetypeSignals(round_number=round_number, was_planted=False)
    signals.t_buy_type = t_buy_type
    signals.ct_buy_type = ct_buy_type

    # ── Bomb events ──────────────────────────────────────────────────────────
    for ev in bomb_events:
        ev_type = str(ev.get("event_type", "")).lower()
        if ev_type == "planted":
            signals.was_planted = True
            site = ev.get("site", "")
            if site:
                # Site comes as "A" or "B" from demoparser
                signals.plant_site = site.upper().replace("BOMBSITE", "")
        elif ev_type == "defused":
            signals.bomb_defused = True
        elif ev_type == "exploded":
            signals.bomb_exploded = True

    # ── Grenade detonations ─────────────────────────────────────────────────
    for ev in grenade_detonations:
        gtype = str(ev.get("grenade_type", "")).lower()
        steam_id = int(ev.get("player_steam_id") or 0)
        is_t = steam_id in t_steam_ids

        if gtype == HE_GRENADE:
            if is_t:
                signals.t_he_count += 1
            else:
                signals.ct_he_count += 1
        elif gtype == FLASHBANG:
            if is_t:
                signals.t_flash_count += 1
            else:
                signals.ct_flash_count += 1
        elif gtype in (SMOKE, SMOKE_EXPIRED):
            if is_t:
                signals.t_smoke_count += 1
            else:
                signals.ct_smoke_count += 1
        elif gtype in (MOLOTOV, INFERNO):
            if is_t:
                signals.t_molotov_count += 1
            else:
                signals.ct_molotov_count += 1

    signals.t_total_nades = (
        signals.t_he_count + signals.t_flash_count +
        signals.t_smoke_count + signals.t_molotov_count
    )
    signals.ct_total_nades = (
        signals.ct_he_count + signals.ct_flash_count +
        signals.ct_smoke_count + signals.ct_molotov_count
    )

    # ── Inferno events ──────────────────────────────────────────────────────
    signals.inferno_count = len(inferno_events)

    # ── Damage events ───────────────────────────────────────────────────────
    signals.total_damage_events = len(damage_events)
    attacker_zones: set[str] = set()
    for ev in damage_events:
        zone = str(ev.get("attacker_last_place_name", "")).strip()
        if zone:
            attacker_zones.add(zone)
        # Count damage in plant zone
        if signals.plant_site:
            zone_lower = zone.lower()
            site_str = f"bombsite{signals.plant_site.lower()}"
            if site_str in zone_lower:
                signals.damage_events_in_plant_zone += 1

    signals.unique_attacker_zones = list(attacker_zones)

    return signals


def classify_round_archetype(
    signals: RoundArchetypeSignals,
) -> tuple[RoundArchetype, float]:
    """Classify the tactical archetype of a round from its signals.

    Archetype priority order (checked in sequence):
    1. RETAKESAVE — bomb was defused or exploded after retake situation
    2. SAVE — losing side dropped weapons mid-round
    3. FAKE — high utility use, multiple zones hit, but no plant
    4. SPLIT — utility on both A and B zones, then plant on one
    5. EXEC — high grenade count, plant on one site, coordinated
    6. CONTACT — low grenade count, fast plant, minimal setup
    7. LATE_HIT — damage events concentrated late in round (not yet detected — TODO)
    8. DEFAULT — fallthrough

    Returns
    -------
    (archetype, confidence)
    """
    rn = signals.round_number
    t = signals.t_buy_type
    ct = signals.ct_buy_type

    # ── 1. Retake ───────────────────────────────────────────────────────────
    # If CT defused after plant, it's a retake
    if signals.was_planted and signals.bomb_defused:
        return (RoundArchetype.RETAKESAVE, 0.85)

    # ── 2. Eco/force rounds — save or contact ───────────────────────────────
    # Eco side (T or CT) with very few nades and no plant = save
    # Contact: eco T side fast push, minimal utility, plant attempt
    if t == "eco":
        if not signals.was_planted:
            # Ts saved — didn't attempt anything
            return (RoundArchetype.SAVE, 0.75)
        else:
            # Eco rush — fast plant, minimal setup
            return (RoundArchetype.CONTACT, 0.70)

    # ── 3. Fake detection ──────────────────────────────────────────────────
    # Fake: high utility expenditure, damage across MULTIPLE zones but no plant
    # (they faked one site and went to the other)
    if not signals.was_planted:
        unique_zones = len(signals.unique_attacker_zones)
        if signals.t_total_nades >= GRENADE_EXEC_THRESHOLD and unique_zones >= 2:
            # Multiple zones hit but no plant = fake
            return (RoundArchetype.FAKE, 0.70)

    # ── 4. Split detection ─────────────────────────────────────────────────
    # Split: T side threw grenades on BOTH A and B zones before plant
    if signals.was_planted and signals.t_total_nades >= GRENADE_EXEC_THRESHOLD:
        zones_str = " ".join(signals.unique_attacker_zones).lower()
        hit_a = any(z in zones_str for z in ["bombsitea", "long a", "short a", "a site", "a_main"])
        hit_b = any(z in zones_str for z in ["bombsiteb", "b site", "b_main", "b_tunnels"])
        if hit_a and hit_b:
            return (RoundArchetype.SPLIT, 0.75)

    # ── 5. Exec ─────────────────────────────────────────────────────────────
    # Exec: high utility, planted on a site, coordinated
    if signals.was_planted and signals.was_exec:
        return (RoundArchetype.EXEC, 0.80)

    # ── 6. Contact ──────────────────────────────────────────────────────────
    # Contact: moderate utility, planted, not a full exec
    if signals.was_planted:
        return (RoundArchetype.CONTACT, 0.65)

    # ── 7. Late hit (TODO) ──────────────────────────────────────────────────
    # Late hit: damage spikes concentrated late-round after slow default
    # Requires round time analysis — not yet implemented

    # ── 8. Default ───────────────────────────────────────────────────────────
    return (RoundArchetype.DEFAULT, 0.50)


def classify_round_archetypes_for_match(
    rounds: list[dict],
    bomb_events_by_round: dict[int, list[dict]],
    grenade_detonations_by_round: dict[int, list[dict]],
    inferno_events_by_round: dict[int, list[dict]],
    damage_events_by_round: dict[int, list[dict]],
    t_steam_ids_by_round: dict[int, set[int]],
    economies_by_round: dict[int, tuple[str, str]],
) -> list[tuple[int, RoundArchetype, float]]:
    """Classify archetypes for all rounds in a match.

    Parameters
    ----------
    rounds : list of dict — Round model serialized (round_number, etc.)
    *_by_round : dict of round_number → list of event dicts
    t_steam_ids_by_round : dict of round_number → set of T steam IDs
    economies_by_round : dict of round_number → (t_buy_type, ct_buy_type)

    Returns
    -------
    list of (round_number, archetype, confidence)
    """
    results: list[tuple[int, RoundArchetype, float]] = []

    for rd in rounds:
        rn = rd.get("round_number", 0)
        t_buy, ct_buy = economies_by_round.get(rn, ("unknown", "unknown"))

        signals = extract_round_signals(
            round_number=rn,
            bomb_events=bomb_events_by_round.get(rn, []),
            grenade_detonations=grenade_detonations_by_round.get(rn, []),
            inferno_events=inferno_events_by_round.get(rn, []),
            damage_events=damage_events_by_round.get(rn, []),
            t_steam_ids=t_steam_ids_by_round.get(rn, set()),
            t_buy_type=t_buy,
            ct_buy_type=ct_buy,
        )

        archetype, confidence = classify_round_archetype(signals)
        results.append((rn, archetype, confidence))

    return results
