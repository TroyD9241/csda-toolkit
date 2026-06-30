"""Economy classifier — buy type per side per round.

Uses equipment_value from round_equipment and purchase data to classify
each team's buy type as full/half/eco/force.

Reference thresholds (HLTV/Liquipedia/esport.is) are used ONLY as
classification boundaries — all actual metrics are computed from
parsed demo data.
"""

from dataclasses import dataclass
from typing import Optional

from csda_toolkit.domain.models import BuyType, EconomyClassification
from csda_toolkit.parsing.constants import weapon_category


# Equipment value thresholds per player (USD)
# These are calibrated boundaries, not assumed values.
FULL_BUY_THRESHOLD = 5000
HALF_BUY_THRESHOLD = 2500
FORCE_BUY_THRESHOLD = 2000  # player has money but buys anyway

# Team-level thresholds: sum of all 5 players' equipment values
TEAM_FULL_BUY_THRESHOLD = FULL_BUY_THRESHOLD * 5        # ~25000
TEAM_HALF_BUY_THRESHOLD = HALF_BUY_THRESHOLD * 5        # ~12500


@dataclass
class PlayerBuyProfile:
    """Per-player buy summary for one round."""
    steam_id: int
    equipment_value: int
    weapon_names: list[str]  # weapons purchased or carried


@dataclass
class SideBuyProfile:
    """Per-side (T or CT) buy summary for one round."""
    team_side: str
    round_number: int
    total_equipment_value: int
    avg_equipment_value: float
    num_rifles: int
    num_smgs: int
    num_pistols: int
    num_awps: int
    num_kevlar: int       # players with armor
    num_helmets: int      # players with helmets
    num_defuse_kits: int
    players: list[PlayerBuyProfile]

    def buy_type(self) -> BuyType:
        """Classify the buy type for this side based on equipment values."""
        avg = self.avg_equipment_value
        if avg >= FULL_BUY_THRESHOLD:
            return BuyType.FULL
        elif avg >= HALF_BUY_THRESHOLD:
            return BuyType.HALF
        else:
            return BuyType.ECO


def classify_side_economy(
    equipment_records: list[dict],
    purchase_records: Optional[list[dict]] = None,
    round_number: int = 0,
    team_side: str = "",
) -> EconomyClassification:
    """Classify buy type for one side in one round.

    Parameters
    ----------
    equipment_records : list of dict
        Dicts from RoundEquipment model (or serialized JSON).
        Expected keys: steam_id, equipment_value, weapons, armor, helmet, defuse_kit
    purchase_records : list of dict, optional
        Dicts from RoundPurchase model.
        Expected keys: steam_id, weapon_name
    round_number : int
    team_side : str
        "t" or "ct"

    Returns
    -------
    EconomyClassification
    """
    purchase_records = purchase_records or []

    # Build per-player profiles
    players: list[PlayerBuyProfile] = []
    steam_ids_seen: set[int] = set()

    for rec in equipment_records:
        sid = int(rec.get("steam_id", 0))
        if sid in steam_ids_seen:
            continue
        steam_ids_seen.add(sid)

        # weapons from equipment JSON dict
        weapons_raw = rec.get("weapons") or {}
        if isinstance(weapons_raw, dict):
            weapon_names = list(weapons_raw.keys())
        elif isinstance(weapons_raw, list):
            weapon_names = weapons_raw
        else:
            weapon_names = []

        players.append(PlayerBuyProfile(
            steam_id=sid,
            equipment_value=int(rec.get("equipment_value", 0)),
            weapon_names=weapon_names,
        ))

    # Add weapons from purchase records for players not in equipment
    purchases_by_steam: dict[int, list[str]] = {}
    for pr in purchase_records:
        sid = int(pr.get("steam_id", 0))
        if sid not in purchases_by_steam:
            purchases_by_steam[sid] = []
        purchases_by_steam[sid].append(str(pr.get("weapon_name", "")))

    for sid, names in purchases_by_steam.items():
        if sid not in steam_ids_seen:
            steam_ids_seen.add(sid)
            players.append(PlayerBuyProfile(
                steam_id=sid,
                equipment_value=0,
                weapon_names=names,
            ))
        else:
            # Merge purchase weapons into existing profile
            for p in players:
                if p.steam_id == sid:
                    p.weapon_names.extend(names)

    if not players:
        return EconomyClassification(
            round_number=round_number,
            team_side=team_side,
            buy_type=BuyType.UNKNOWN,
            total_equipment_value=0,
            num_rifles=0,
            num_smgs=0,
            num_pistols=0,
            num_awps=0,
            confidence=0.0,
        )

    total_value = sum(p.equipment_value for p in players)
    avg_value = total_value / len(players)

    num_rifles = sum(
        1 for p in players
        if weapon_category(" ".join(p.weapon_names)) == "rifle"
    )
    num_smgs = sum(
        1 for p in players
        if weapon_category(" ".join(p.weapon_names)) == "smg"
    )
    num_pistols = sum(
        1 for p in players
        if weapon_category(" ".join(p.weapon_names)) == "pistol"
    )
    num_awps = sum(
        1 for p in players
        if any("awp" in w.lower() for w in p.weapon_names)
    )
    num_kevlar = sum(1 for p in players if p.equipment_value >= 650)
    num_helmets = sum(1 for p in players if p.equipment_value >= 1000)

    # Classify buy type
    buy_type = _classify_buy_type(avg_value, total_value, num_awps)

    # Confidence: higher when equipment values are clearly in one category
    # and lower when near thresholds
    confidence = _buy_confidence(avg_value)

    return EconomyClassification(
        round_number=round_number,
        team_side=team_side,
        buy_type=buy_type,
        total_equipment_value=total_value,
        num_rifles=num_rifles,
        num_smgs=num_smgs,
        num_pistols=num_pistols,
        num_awps=num_awps,
        confidence=confidence,
    )


def _classify_buy_type(avg_value: float, total_value: float, num_awps: int) -> BuyType:
    """Classify buy type from equipment values."""
    # AWP changes the threshold — snipers push avg up significantly
    adjusted_avg = avg_value
    if num_awps > 0:
        # Even with one AWP (~4700), a full buy team can still be
        # in the 3500-5000 avg range. Adjust threshold down slightly.
        adjusted_avg = avg_value - (num_awps * 1500)

    if adjusted_avg >= FULL_BUY_THRESHOLD:
        return BuyType.FULL
    elif adjusted_avg >= HALF_BUY_THRESHOLD:
        return BuyType.HALF
    else:
        return BuyType.ECO


def _buy_confidence(avg_value: float) -> float:
    """Compute confidence based on how clearly the buy type is defined.

    Values deep within a threshold band = high confidence.
    Values near boundary = lower confidence.
    """
    import math
    if avg_value >= FULL_BUY_THRESHOLD:
        # Distance above full threshold
        distance = avg_value - FULL_BUY_THRESHOLD
        confidence = min(0.95, 0.7 + distance / 5000)
    elif avg_value >= HALF_BUY_THRESHOLD:
        # Distance above half threshold
        distance = avg_value - HALF_BUY_THRESHOLD
        band = FULL_BUY_THRESHOLD - HALF_BUY_THRESHOLD
        confidence = min(0.9, 0.6 + distance / band * 0.3)
    else:
        # Eco band
        band = HALF_BUY_THRESHOLD
        distance = HALF_BUY_THRESHOLD - avg_value
        confidence = min(0.9, 0.6 + distance / band * 0.3)
    return round(confidence, 3)


def classify_round_economy(
    ct_equipment: list[dict],
    t_equipment: list[dict],
    ct_purchases: Optional[list[dict]] = None,
    t_purchases: Optional[list[dict]] = None,
    round_number: int = 0,
) -> tuple[EconomyClassification, EconomyClassification]:
    """Classify buy type for both sides in a round.

    Returns
    -------
    (ct_economy, t_economy)
    """
    ct = classify_side_economy(
        equipment_records=ct_equipment,
        purchase_records=ct_purchases or [],
        round_number=round_number,
        team_side="ct",
    )
    t = classify_side_economy(
        equipment_records=t_equipment,
        purchase_records=t_purchases or [],
        round_number=round_number,
        team_side="t",
    )
    return ct, t
