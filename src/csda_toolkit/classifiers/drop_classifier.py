"""Weapon drop classifier — tracks who gives up weapons to whom on a team.

Drop insight: the value of what a player gives to teammates vs what they receive.
This reveals selflessness (gives up good guns to team), selfishness (takes drops),
and team economics (who enables the team's best players).

Signals used:
- WeaponDrop DB model: dropped_by / picked_up_by per round (from item_drops)
- PlayerRoundWeapon: is_purchased, is_dropped flags per weapon
- RoundEquipment weapons JSON: what each player held at freezetime end
- Purchase records: what was bought

Two detection modes:
1. DIRECT: Use WeaponDrop model (dropped_by / picked_up_by fields)
2. INFERRED: Player bought weapon W but their active_weapon at freezetime is not W
   → they bought it, then dropped it to someone else before freezetime end

Per-player metrics per match:
- drops_given: count of weapons dropped to teammates
- drops_received: count of weapons received from teammates
- total_value_given: sum of weapon costs dropped
- total_value_received: sum of weapon costs received
- net_transfer: value_received - value_given (positive = net receiver)
- drop_ratio: drops_given / (drops_given + drops_received) — high = selfless
"""

from dataclasses import dataclass, field
from typing import Optional

from csda_toolkit.parsing.constants import weapon_category


# Weapon cost lookup (approximate USD values from CS2 buy menu)
WEAPON_COSTS: dict[str, int] = {
    "ak_47": 2700,
    "m4a4": 3100,
    "m4a1_s": 2900,
    "galil_ar": 2000,
    "famas": 2050,
    "sg_553": 3000,
    "ssg_08": 1700,
    "awp": 4750,
    "g3sg1": 5000,
    "scar_20": 5000,
    "aug": 3300,
    "ak_47": 2700,
    # SMGs
    "mp5_sd": 1500,
    "mp7": 1700,
    "mp9": 1250,
    "pp_bizon": 1400,
    "ump_45": 1200,
    "mac_10": 1050,
    # Pistols
    "glock_18": 200,
    "p250": 300,
    "hkp2000": 200,
    "usp_s": 200,
    "five_seven": 500,
    "tec_9": 500,
    "desert_eagle": 700,
    "dual_berettas": 500,
    "revolver": 600,
    "cz75_auto": 500,
    # Shotguns
    "mag_7": 1200,
    "sawed_off": 1100,
    "nova": 1200,
    "xm1014": 2000,
    # Rifles / misc
    "fiveseven": 500,
    "cz75": 500,
    "deagle": 700,
    "elite": 500,
    "p228": 200,
    "scout": 1700,
    "tmp": 200,
    "m249": 5200,
    "negev": 1700,
    "scar20": 5000,
    "g3sg1": 5000,
    "ak47": 2700,
    "m4a1": 2900,
}


def weapon_cost(weapon_key: str) -> int:
    """Return approximate buy-menu cost for a weapon key."""
    return WEAPON_COSTS.get(weapon_key.lower(), 0)


@dataclass
class PlayerDropProfile:
    """Per-player drop statistics for one match."""
    steam_id: int
    player_name: str

    drops_given_count: int = 0
    drops_received_count: int = 0
    inferred_drops_given_count: int = 0
    inferred_drops_received_count: int = 0

    drops_given_cost: int = 0
    drops_received_cost: int = 0

    # Players who received drops from this player
    given_to: dict[int, int] = field(default_factory=dict)  # steam_id -> count
    # Players who gave drops to this player
    received_from: dict[int, int] = field(default_factory=dict)  # steam_id -> count

    # Drop quality: avg cost of weapons given away
    avg_drop_cost: float = 0.0
    avg_receive_cost: float = 0.0

    @property
    def total_drops_given(self) -> int:
        return self.drops_given_count + self.inferred_drops_given_count

    @property
    def total_drops_received(self) -> int:
        return self.drops_received_count + self.inferred_drops_received_count

    @property
    def net_transfer(self) -> int:
        """Positive = net receiver, Negative = net giver."""
        return self.drops_received_cost - self.drops_given_cost

    @property
    def drop_role(self) -> str:
        """Classify player as giver, receiver, or balanced."""
        given = self.total_drops_given
        received = self.total_drops_received
        total = given + received
        if total == 0:
            return "neutral"

        ratio = given / total
        if ratio >= 0.6:
            return "giver"       # gives more than receives
        elif ratio <= 0.3 and received > 0:
            return "receiver"   # receives more than gives
        else:
            return "balanced"

    def finalize(self):
        """Compute averages after all drops are accumulated."""
        if self.drops_given_count > 0:
            self.avg_drop_cost = round(self.drops_given_cost / self.drops_given_count, 1)
        if self.drops_received_count > 0:
            self.avg_receive_cost = round(self.drops_received_cost / self.drops_received_count, 1)


def classify_match_drops(
    weapon_drops: list[dict],
    player_round_weapons: list[dict],
    purchases: list[dict],
    steam_id_to_name: dict[int, str],
) -> dict[int, PlayerDropProfile]:
    """Build drop profiles for all players in a match.

    Parameters
    ----------
    weapon_drops : list of dict — WeaponDrop model serialized
    player_round_weapons : list of dict — PlayerRoundWeapon model serialized
    purchases : list of dict — RoundPurchase model serialized
    steam_id_to_name : dict of steam_id → display name

    Returns
    -------
    dict of steam_id → PlayerDropProfile
    """
    profiles: dict[int, PlayerDropProfile] = {}

    def get_profile(sid: int) -> PlayerDropProfile:
        if sid not in profiles:
            profiles[sid] = PlayerDropProfile(
                steam_id=sid,
                player_name=steam_id_to_name.get(sid, ""),
            )
        return profiles[sid]

    # ── Direct drops from WeaponDrop model ──────────────────────────────────
    for drop in weapon_drops:
        dropped_by = int(drop.get("dropped_by_steam_id") or 0)
        picked_up_by = int(drop.get("picked_up_by_steam_id") or 0)
        weapon_key = str(drop.get("weapon_name", "")).lower()

        if dropped_by == 0 or picked_up_by == 0:
            continue
        if dropped_by == picked_up_by:
            continue  # self-drop, not a team drop

        cost = weapon_cost(weapon_key)

        giver = get_profile(dropped_by)
        giver.drops_given_count += 1
        giver.drops_given_cost += cost
        giver.given_to[picked_up_by] = giver.given_to.get(picked_up_by, 0) + 1

        receiver = get_profile(picked_up_by)
        receiver.drops_received_count += 1
        receiver.drops_received_cost += cost
        receiver.received_from[dropped_by] = receiver.received_from.get(dropped_by, 0) + 1

    # ── Inferred drops: round-to-round comparison ─────────────────────────────
    # A player bought weapon W in round R, but their active_weapon at freezetime end
    # of round R is NOT W → they dropped it to someone else during the round.
    #
    # Algorithm:
    # For each round, for each player:
    #   - Get weapons purchased (from purchases)
    #   - Get active_weapon at freezetime end (from player_round_weapons where is_equipped=True)
    #   - If purchased but not active at freezetime end → inferred drop
    #
    # We can infer the receiver by looking at who HELD that weapon at freezetime end.
    # Build a map: round → weapon_key → steam_id who held it

    # round_player_weapons: which weapons each player had equipped at freezetime end
    round_holders: dict[int, dict[str, int]] = {}  # round_number → {weapon_key → steam_id}

    for prw in player_round_weapons:
        if not prw.get("is_equipped", False):
            continue
        rn = int(prw.get("round_number", 0))
        sid = int(prw.get("steam_id", 0))
        wk = str(prw.get("weapon_key", "")).lower()
        if rn not in round_holders:
            round_holders[rn] = {}
        # If multiple players had same weapon, last one wins (shouldn't happen)
        round_holders[rn][wk] = sid

    # For each purchase, check if the purchased weapon is held by anyone at freezetime
    purchases_by_player_round: dict[tuple[int, int], list[str]] = {}  # (sid, rn) → [weapon_keys]
    for p in purchases:
        sid = int(p.get("steam_id", 0))
        rn = int(p.get("round_number", 0))
        wk = str(p.get("weapon_name", "")).lower()
        key = (sid, rn)
        if key not in purchases_by_player_round:
            purchases_by_player_round[key] = []
        purchases_by_player_round[key].append(wk)

    # Check for inferred drops
    for (sid, rn), purchased_weapons in purchases_by_player_round.items():
        holders = round_holders.get(rn, {})
        for wk in purchased_weapons:
            holder = holders.get(wk)
            if holder is not None and holder != sid:
                # sid bought wk, but holder has it at freezetime end → sid dropped to holder
                cost = weapon_cost(wk)
                giver = get_profile(sid)
                receiver = get_profile(holder)

                giver.inferred_drops_given_count += 1
                giver.drops_given_cost += cost
                giver.given_to[holder] = giver.given_to.get(holder, 0) + 1

                receiver.inferred_drops_received_count += 1
                receiver.drops_received_cost += cost
                receiver.received_from[sid] = receiver.received_from.get(sid, 0) + 1

    # Finalize averages
    for p in profiles.values():
        p.finalize()

    return profiles
