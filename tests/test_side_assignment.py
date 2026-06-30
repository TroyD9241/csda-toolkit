"""Tests for round side assignment logic."""

import pytest
from csda_toolkit.domain.models import MatchTeam, Round, SideAssignment
from csda_toolkit.ingest.bundle import _compute_side_assignments, _guess_player_team_slot
from csda_toolkit.domain.models import Match


class TestComputeSideAssignments:
    """Test BLAST format (12 rounds per half) side assignment logic.

    CS2 BLAST format:
      - Rounds 1-12: first half, team_slot 1 = CT, team_slot 2 = T
      - Rounds 13-24: second half, team_slot 1 = T, team_slot 2 = CT  (halftime swap)
      - OT (rn > 24): 3 rounds on one side, then 3 rounds on the other
        - OT1: rounds 25-27 = team1 T, rounds 28-30 = team1 CT
        - OT2: rounds 31-33 = team1 T, rounds 34-36 = team1 CT
    """

    def _make_match_domain(self, teams: list[MatchTeam], rounds: list[Round]) -> Match:
        return Match(
            map_name="de_mirage",
            tick_rate=128,
            teams=teams,
            rounds=rounds,
        )

    def _make_team(self, slot: int, player_ids: list[int]) -> MatchTeam:
        return MatchTeam(
            team_slot=slot,
            display_name=f"Team {slot}",
            player_ids=player_ids,
        )

    def _make_round(self, number: int, winner_side: str | None = None) -> Round:
        """Create a round (BLAST format: 12 rounds per half)."""
        return Round(
            round_number=number,
            start_tick=number * 1280,
            winner_side=winner_side,
        )

    def test_regulation_first_half_team1_is_ct(self):
        """Rounds 1-12: team slot 1 = CT, team slot 2 = T."""
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n) for n in range(1, 13)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        assert len(result) == 24  # 12 rounds x 2 team slots

        for rn in range(1, 13):
            t1 = next(s for s in result if s.team_slot == 1 and s.round_number == rn)
            t2 = next(s for s in result if s.team_slot == 2 and s.round_number == rn)
            assert t1.side == "ct", f"round {rn}: team1 should be CT"
            assert t2.side == "t", f"round {rn}: team2 should be T"
            assert t1.overtime_index == 0
            assert t2.overtime_index == 0

    def test_regulation_second_half_halftime_swap(self):
        """Rounds 13-24: team slot 1 = T, team slot 2 = CT (halftime swap)."""
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n) for n in range(13, 25)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        assert len(result) == 24  # 12 rounds x 2

        for rn in range(13, 25):
            t1 = next(s for s in result if s.team_slot == 1 and s.round_number == rn)
            t2 = next(s for s in result if s.team_slot == 2 and s.round_number == rn)
            assert t1.side == "t", f"round {rn}: team1 should be T"
            assert t2.side == "ct", f"round {rn}: team2 should be CT"
            assert t1.overtime_index == 0

    def test_regulation_12_rounds_first_half_only(self):
        """A 12-round first half: team1 only plays CT, team2 only plays T."""
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n) for n in range(1, 13)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        for s in result:
            if s.team_slot == 1:
                assert s.side == "ct"
            else:
                assert s.side == "t"

    def test_overtime_rounds_25_to_30_ot1(self):
        """BLAST OT: 3 rounds T side, 3 rounds CT side for team 1.

        OT1: rounds 25-27 = team1 T, rounds 28-30 = team1 CT.
        """
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n, "ct") for n in range(25, 31)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        # Rounds 25-27: team1 = T
        for rn in [25, 26, 27]:
            r = next(s for s in result if s.round_number == rn and s.team_slot == 1)
            assert r.side == "t", f"round {rn}: expected T, got {r.side}"
            assert r.overtime_index == 1, f"round {rn}: expected OT1"

        # Rounds 28-30: team1 = CT
        for rn in [28, 29, 30]:
            r = next(s for s in result if s.round_number == rn and s.team_slot == 1)
            assert r.side == "ct", f"round {rn}: expected CT, got {r.side}"
            assert r.overtime_index == 1, f"round {rn}: expected OT1"

        # Team2 is always opposite
        r25_t2 = next(s for s in result if s.round_number == 25 and s.team_slot == 2)
        assert r25_t2.side == "ct"

    def test_overtime_rounds_31_to_36_ot2(self):
        """BLAST OT2: rounds 31-33 = team1 T, rounds 34-36 = team1 CT."""
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n, "ct") for n in range(31, 37)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        # OT2: rounds 31-33 = team1 T, rounds 34-36 = team1 CT
        for rn in [31, 32, 33]:
            r = next(s for s in result if s.round_number == rn and s.team_slot == 1)
            assert r.side == "t", f"round {rn}: expected T, got {r.side}"
            assert r.overtime_index == 2, f"round {rn}: expected OT2"

        for rn in [34, 35, 36]:
            r = next(s for s in result if s.round_number == rn and s.team_slot == 1)
            assert r.side == "ct", f"round {rn}: expected CT, got {r.side}"
            assert r.overtime_index == 2, f"round {rn}: expected OT2"

    def test_each_round_has_both_team_slots(self):
        """Every round has exactly 2 entries (one per team slot)."""
        teams = [self._make_team(1, [1, 2, 3, 4, 5]), self._make_team(2, [6, 7, 8, 9, 10])]
        rounds = [self._make_round(n) for n in range(1, 25)]
        match = self._make_match_domain(teams, rounds)

        result = _compute_side_assignments(match)

        for rn in range(1, 25):
            round_sides = [s for s in result if s.round_number == rn]
            assert len(round_sides) == 2
            sides = {s.side for s in round_sides}
            assert sides == {"t", "ct"}

    def test_side_assignment_dataclass_fields(self):
        """SideAssignment has all required fields."""
        sa = SideAssignment(team_slot=1, round_number=5, overtime_index=0, side="ct")
        assert sa.team_slot == 1
        assert sa.round_number == 5
        assert sa.overtime_index == 0
        assert sa.side == "ct"

    def test_side_assignment_defaults(self):
        """SideAssignment overtime_index defaults to 0."""
        sa = SideAssignment(team_slot=2, round_number=10, side="t")
        assert sa.overtime_index == 0


class TestGuessPlayerTeamSlot:
    """Test _guess_player_team_slot helper."""

    def _make_match_with_teams(self, slot1_players: list[int], slot2_players: list[int]) -> Match:
        t1 = MatchTeam(team_slot=1, display_name="Team 1", player_ids=slot1_players)
        t2 = MatchTeam(team_slot=2, display_name="Team 2", player_ids=slot2_players)
        return Match(map_name="de_mirage", tick_rate=128, teams=[t1, t2])

    def test_player_in_slot1(self):
        match = self._make_match_with_teams([1, 2, 3], [4, 5, 6])
        assert _guess_player_team_slot(match, 1) == 1
        assert _guess_player_team_slot(match, 2) == 1

    def test_player_in_slot2(self):
        match = self._make_match_with_teams([1, 2, 3], [4, 5, 6])
        assert _guess_player_team_slot(match, 4) == 2
        assert _guess_player_team_slot(match, 6) == 2

    def test_unknown_player_returns_none(self):
        match = self._make_match_with_teams([1, 2, 3], [4, 5, 6])
        assert _guess_player_team_slot(match, 999) is None
