"""IngestBundle — maps raw demoparser output → domain models → DB records.

Orchestrates the full pipeline:
  1. Parse demo via DemoParser → domain objects
  2. Batch-insert into Postgres via SQLAlchemy
  3. Returns ingest summary
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from csda_toolkit.db.database import Database
from csda_toolkit.db.models import (
    DemoFile as DemoFileModel,
    Match as MatchModel,
    Player as PlayerModel,
    MatchPlayer as MatchPlayerModel,
    Round as RoundModel,
    Kill as KillModel,
    RoundEquipment,
    RoundPurchase,
    Team as TeamModel,
    MatchTeam as MatchTeamModel,
    PlayerAlias,
)
from csda_toolkit.domain.models import (
    DemoFile as DemoFileDomain,
    Kill as KillDomain,
    Match as MatchDomain,
    MatchTeam as MatchTeamDomain,
    Player as PlayerDomain,
    Round as RoundDomain,
    PlayerEquipment,
    PurchaseEvent,
)
from csda_toolkit.parsing.parser import DemoParser

logger = logging.getLogger(__name__)


class IngestResult:
    """Summary of an ingest operation."""

    def __init__(self, match_id: Optional[int] = None) -> None:
        self.match_id = match_id
        self.players_created: int = 0
        self.rounds_created: int = 0
        self.kills_created: int = 0
        self.teams_created: int = 0
        self.errors: list[str] = []

    def __repr__(self) -> str:
        return (
            f"IngestResult(match_id={self.match_id}, "
            f"players={self.players_created}, rounds={self.rounds_created}, "
            f"kills={self.kills_created}, teams={self.teams_created})"
        )


class IngestBundle:
    """Pipeline: parse demo → domain models → DB persistence."""

    def __init__(self, db: Database, demo_path: str):
        self.db = db
        self.demo_path = demo_path
        self._parser = DemoParser(demo_path)

    def run(self) -> IngestResult:
        """Execute the full ingest pipeline."""
        result = IngestResult()
        session = self.db.session()

        try:
            # 1. Parse match from demo
            match_domain = self._parser.parse_match()

            # 2. Persist demo_file record
            demo_file_model = self._insert_demo_file(session, match_domain.demo_file)
            session.flush()

            # 3. Persist teams (create or resolve)
            team_map = {}  # team_slot -> TeamModel.id
            for team_domain in match_domain.teams:
                team_model = self._upsert_team(session, team_domain)
                session.flush()
                team_map[team_domain.team_slot] = team_model.id
                result.teams_created += 1

            # 4. Persist players (create or resolve by steam_id)
            player_map = {}  # steam_id -> PlayerModel.id
            for player_domain in match_domain.players:
                player_model = self._upsert_player(session, player_domain)
                session.flush()
                player_map[player_domain.steam_id] = player_model.id
                result.players_created += 1

            # 5. Persist match record
            match_model = MatchModel(
                demo_file_id=demo_file_model.id if demo_file_model else None,
                map_name=match_domain.map_name,
                tick_rate=match_domain.tick_rate,
                server_name=match_domain.server_name,
                source=match_domain.source,
                played_at=match_domain.played_at or datetime.utcnow(),
            )
            session.add(match_model)
            session.flush()
            result.match_id = match_model.id

            # 6. Link teams to match
            for team_slot, team_id in team_map.items():
                match_team = MatchTeamModel(
                    match_id=match_model.id,
                    team_id=team_id,
                    team_slot=team_slot,
                    display_name=_get_team_name_for_slot(match_domain, team_slot),
                )
                session.add(match_team)

            # 7. Link players to match
            for player_domain in match_domain.players:
                player_id = player_map.get(player_domain.steam_id)
                if player_id:
                    mp = MatchPlayerModel(
                        match_id=match_model.id,
                        player_id=player_id,
                        team_slot=_guess_player_team_slot(match_domain, player_domain.steam_id),
                    )
                    session.add(mp)

            # 8. Persist rounds
            for rd in match_domain.rounds:
                round_model = RoundModel(
                    match_id=match_model.id,
                    round_number=rd.round_number,
                    start_tick=rd.start_tick,
                    end_tick=rd.end_tick,
                    winner_side=rd.winner_side,
                    end_reason=rd.end_reason,
                    score_t=rd.score_t,
                    score_ct=rd.score_ct,
                )
                session.add(round_model)
                result.rounds_created += 1

            # 9. Persist kills
            for kd in match_domain.kills:
                killer_id = player_map.get(kd.killer_steam_id) if kd.killer_steam_id else None
                victim_id = player_map.get(kd.victim_steam_id) if kd.victim_steam_id else None
                assister_id = player_map.get(kd.assister_steam_id) if kd.assister_steam_id else None

                kill_model = KillModel(
                    match_id=match_model.id,
                    round_number=kd.round_number,
                    tick=kd.tick,
                    killer_steam_id=kd.killer_steam_id,
                    killer_player_id=killer_id,
                    killer_name=kd.killer_name,
                    victim_steam_id=kd.victim_steam_id,
                    victim_player_id=victim_id,
                    victim_name=kd.victim_name,
                    assister_steam_id=kd.assister_steam_id,
                    assister_player_id=assister_id,
                    assister_name=kd.assister_name,
                    weapon_name=kd.weapon_name,
                    is_headshot=kd.is_headshot,
                    is_wallbang=kd.is_wallbang,
                )
                session.add(kill_model)
                result.kills_created += 1

            # 10. Persist round equipment if available
            try:
                equipment_list = self._parser.parse_equipment_at_freeze_end()
                for eq in equipment_list:
                    eq_model = RoundEquipment(
                        match_id=match_model.id,
                        round_number=eq.round_number,
                        steam_id=eq.steam_id,
                        player_id=player_map.get(eq.steam_id),
                        player_name=eq.player_name,
                        equipment_value=eq.equipment_value,
                        armor=eq.armor,
                        helmet=eq.helmet,
                        defuse_kit=eq.defuse_kit or False,
                    )
                    session.add(eq_model)
            except Exception as e:
                logger.warning("Equipment parsing failed (non-fatal): %s", e)

            # 11. Persist purchases if available
            try:
                purchase_list = self._parser.parse_purchases()
                for pu in purchase_list:
                    pu_model = RoundPurchase(
                        match_id=match_model.id,
                        round_number=pu.round_number,
                        tick=pu.tick,
                        steam_id=pu.steam_id,
                        player_id=player_map.get(pu.steam_id),
                        player_name=pu.player_name,
                        weapon_name=pu.weapon_name,
                        weapon_category=pu.weapon_category,
                        cost=pu.cost,
                    )
                    session.add(pu_model)
            except Exception as e:
                logger.warning("Purchase parsing failed (non-fatal): %s", e)

            # Commit everything
            session.commit()
            logger.info("Ingest complete: %s", result)

        except Exception as e:
            session.rollback()
            result.errors.append(str(e))
            logger.error("Ingest failed: %s", e)
            raise

        finally:
            session.close()

        return result

    # ── Internal helpers ─────────────────────────────────────────────────

    def _insert_demo_file(
        self, session: Session, demo: Optional[DemoFileDomain]
    ) -> Optional[DemoFileModel]:
        if demo is None:
            return None
        model = DemoFileModel(
            demo_filename=demo.demo_filename,
            demo_checksum=demo.demo_checksum,
            parser_name=demo.parser_name,
            parser_version=demo.parser_version,
            source=demo.source,
        )
        session.add(model)
        return model

    def _upsert_player(self, session: Session, player: PlayerDomain) -> PlayerModel:
        """Find existing player by steam_id or create a new one."""
        existing = session.execute(
            select(PlayerModel).where(PlayerModel.steam_id == player.steam_id)
        ).scalar_one_or_none()

        if existing:
            # Update name if different
            if existing.name != player.name:
                existing.name = player.name
            return existing

        model = PlayerModel(
            steam_id=player.steam_id,
            name=player.name,
        )
        session.add(model)
        return model

    def _upsert_team(self, session: Session, team: MatchTeamDomain) -> TeamModel:
        """Find existing team by display name or create a new one."""
        existing = session.execute(
            select(TeamModel).where(TeamModel.display_name == team.display_name)
        ).scalar_one_or_none()

        if existing:
            return existing

        model = TeamModel(
            display_name=team.display_name,
        )
        session.add(model)
        return model


# ── Helpers ─────────────────────────────────────────────────────────────────


def _get_team_name_for_slot(match: MatchDomain, slot: int) -> str:
    for t in match.teams:
        if t.team_slot == slot:
            return t.display_name
    return f"Team {slot}"


def _guess_player_team_slot(match: MatchDomain, steam_id: int) -> Optional[int]:
    """Guess which team a player belongs to based on team player lists."""
    for t in match.teams:
        if steam_id in t.player_ids:
            return t.team_slot
    return None
