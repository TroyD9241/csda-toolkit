"""Tests for the weapon drop classifier."""

import pytest

from csda_toolkit.classifiers.drop_classifier import (
    PlayerDropProfile,
    classify_match_drops,
    weapon_cost,
    WEAPON_COSTS,
)


class TestWeaponCost:
    def test_known_weapon(self):
        assert weapon_cost("ak_47") == 2700
        assert weapon_cost("awp") == 4750
        assert weapon_cost("glock_18") == 200

    def test_unknown_weapon(self):
        assert weapon_cost("unknown_weapon") == 0


class TestPlayerDropProfile:
    def test_net_transfer(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_cost = 1000
        p.drops_received_cost = 3000
        assert p.net_transfer == 2000

    def test_drop_role_giver(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_count = 3
        p.drops_received_count = 1
        p.inferred_drops_given_count = 0
        p.inferred_drops_received_count = 0
        assert p.drop_role == "giver"

    def test_drop_role_receiver(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_count = 1
        p.drops_received_count = 3
        p.inferred_drops_given_count = 0
        p.inferred_drops_received_count = 0
        assert p.drop_role == "receiver"

    def test_drop_role_balanced(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_count = 2
        p.drops_received_count = 2
        p.inferred_drops_given_count = 0
        p.inferred_drops_received_count = 0
        assert p.drop_role == "balanced"

    def test_drop_role_neutral(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        assert p.drop_role == "neutral"

    def test_total_drops_given(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_count = 2
        p.inferred_drops_given_count = 1
        assert p.total_drops_given == 3

    def test_finalize_avg(self):
        p = PlayerDropProfile(steam_id=1, player_name="player1")
        p.drops_given_count = 2
        p.drops_given_cost = 5000
        p.drops_received_count = 1
        p.drops_received_cost = 2000
        p.finalize()
        assert p.avg_drop_cost == 2500.0
        assert p.avg_receive_cost == 2000.0


class TestClassifyMatchDrops:
    def _prw(self, steam_id: int, round_number: int, weapon_key: str, is_equipped: bool = True) -> dict:
        return {
            "steam_id": steam_id, "round_number": round_number,
            "weapon_key": weapon_key, "is_equipped": is_equipped,
            "is_purchased": False, "is_dropped": False,
        }

    def _purchase(self, steam_id: int, round_number: int, weapon_name: str) -> dict:
        return {
            "steam_id": steam_id, "round_number": round_number,
            "weapon_name": weapon_name,
        }

    def _drop(self, dropped_by: int, picked_up_by: int, weapon_name: str) -> dict:
        return {
            "dropped_by_steam_id": dropped_by,
            "picked_up_by_steam_id": picked_up_by,
            "weapon_name": weapon_name,
        }

    def test_direct_drop(self):
        drops = [self._drop(dropped_by=1, picked_up_by=2, weapon_name="ak_47")]
        profiles = classify_match_drops(
            weapon_drops=drops,
            player_round_weapons=[],
            purchases=[],
            steam_id_to_name={1: "player1", 2: "player2"},
        )
        p1 = profiles[1]
        p2 = profiles[2]
        assert p1.drops_given_count == 1
        assert p1.drops_given_cost == 2700
        assert p2.drops_received_count == 1
        assert p2.drops_received_cost == 2700
        assert p2.received_from[1] == 1
        assert p1.given_to[2] == 1
        assert p1.drop_role == "giver"
        assert p2.drop_role == "receiver"

    def test_inferred_drop(self):
        # Player 1 bought AK but player 2 had it equipped at freezetime end → player 1 dropped to player 2
        prw = [
            self._prw(steam_id=2, round_number=1, weapon_key="ak_47"),
        ]
        purchases = [
            self._purchase(steam_id=1, round_number=1, weapon_name="ak_47"),
        ]
        profiles = classify_match_drops(
            weapon_drops=[],
            player_round_weapons=prw,
            purchases=purchases,
            steam_id_to_name={1: "player1", 2: "player2"},
        )
        p1 = profiles[1]
        p2 = profiles[2]
        assert p1.inferred_drops_given_count == 1
        assert p2.inferred_drops_received_count == 1
        assert p1.drops_given_cost == 2700
        assert p2.drops_received_cost == 2700

    def test_no_self_drop(self):
        # Dropped to self should be ignored — player profile still created (empty)
        drops = [self._drop(dropped_by=1, picked_up_by=1, weapon_name="ak_47")]
        profiles = classify_match_drops(
            weapon_drops=drops,
            player_round_weapons=[],
            purchases=[],
            steam_id_to_name={1: "player1"},
        )
        # Self-drop is skipped, so player has no drop activity
        assert 1 not in profiles  # no drops = no profile created

    def test_net_transfer_value(self):
        drops = [
            self._drop(dropped_by=1, picked_up_by=2, weapon_name="awp"),  # 4750
            self._drop(dropped_by=2, picked_up_by=1, weapon_name="ak_47"),  # 2700
        ]
        profiles = classify_match_drops(
            weapon_drops=drops,
            player_round_weapons=[],
            purchases=[],
            steam_id_to_name={1: "player1", 2: "player2"},
        )
        # player1: gave 4750, received 2700 → net = -2050 (net giver)
        assert profiles[1].net_transfer == -2050
        # player2: gave 2700, received 4750 → net = +2050 (net receiver)
        assert profiles[2].net_transfer == 2050

    def test_multi_drop_same_receiver(self):
        drops = [
            self._drop(dropped_by=1, picked_up_by=2, weapon_name="ak_47"),
            self._drop(dropped_by=1, picked_up_by=2, weapon_name="m4a4"),
        ]
        profiles = classify_match_drops(
            weapon_drops=drops,
            player_round_weapons=[],
            purchases=[],
            steam_id_to_name={1: "player1", 2: "player2"},
        )
        assert profiles[1].drops_given_count == 2
        assert profiles[1].given_to[2] == 2
        assert profiles[1].drops_given_cost == 2700 + 3100

    def test_purchased_but_held_by_self(self):
        # Player 1 bought AK and still has it at freezetime → not a drop (no profile)
        prw = [
            self._prw(steam_id=1, round_number=1, weapon_key="ak_47"),
        ]
        purchases = [
            self._purchase(steam_id=1, round_number=1, weapon_name="ak_47"),
        ]
        profiles = classify_match_drops(
            weapon_drops=[],
            player_round_weapons=prw,
            purchases=purchases,
            steam_id_to_name={1: "player1"},
        )
        # Player held their own purchase → no inferred drop → no profile created
        assert 1 not in profiles
