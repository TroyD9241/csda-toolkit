"""CsdaParser — high-level orchestrator wrapping demoparser2.

Usage::

    from csda_toolkit.parsing.parser import CsdaParser

    parser = CsdaParser("demo.dem")
    
    # Extract everything
    header = parser.header()
    players = parser.players()
    rounds = parser.rounds()
    kills = parser.kills()
    damage = parser.damage()
    grenades = parser.grenades()
    bomb_events = parser.bomb_events()
    weapon_fires = parser.weapon_fires()
    player_frames = parser.player_frames()  # tick-level state
    game_rules = parser.game_rules()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd
from demoparser2 import DemoParser as Parser2

from csda_toolkit.domain.models import (
    BombEvent,
    DamageEvent,
    DemoFile,
    FootstepEvent,
    GameRulesFrame,
    GrenadeDetonation,
    GrenadeTrajectory,
    HltvVersionInfo,
    InfernoEvent,
    ItemDrop,
    ItemEquip,
    ItemPickup,
    Kill,
    Match,
    MatchContext,
    MatchPanel,
    OtherDeath,
    Player,
    PlayerBlind,
    PlayerFrame,
    PlayerJump,
    PlayerMoney,
    PlayerRoundStats,
    PlayerSpawn,
    RankUpdate,
    Round,
    RoundEndReason,
    RoundMvp,
    RoundStartEvent,
    SkinData,
    TickEvent,
    WeaponFire,
    WeaponReload,
    WeaponZoom,
    WinPanelRound,
)
from csda_toolkit.parsing import events, header as hdr, ticks


class CsdaParser:
    """High-level parser for CS2 demo files.

    Wraps demoparser2.DemoParser and provides typed access to all 46 game
    events and 904 tick fields organised by category.

    Most methods are lazy — they parse on first call and cache the result.
    """

    def __init__(self, demo_path: str | Path):
        self._path = str(demo_path)
        self._parser = Parser2(self._path)

        # Internal caches
        self._header: dict | None = None
        self._players: list[Player] | None = None
        self._rounds: list[Round] | None = None
        self._kills: list[Kill] | None = None
        self._damage: list[DamageEvent] | None = None

    def _event_df(self, event_name: str, **kwargs: list[str]) -> pd.DataFrame:
        """Safely parse an event - our fork returns [] for events that don't fire.
        
        Supports demoparser2 parse_event kwargs: player=[...], other=[...].
        """
        result = self._parser.parse_event(event_name, **kwargs)
        if isinstance(result, list):
            return pd.DataFrame()
        return result

    # ── Property ─────────────────────────────────────────────────────────

    @property
    def raw(self) -> Parser2:
        """Access the underlying demoparser2 instance directly."""
        return self._parser

    # ═══════════════════════════════════════════════════════════════════════
    # HEADER / METADATA
    # ═══════════════════════════════════════════════════════════════════════

    def header_raw(self) -> dict:
        """Return raw header dict from demoparser2."""
        if self._header is None:
            self._header = hdr.parse_demo_header(self._parser)
        return self._header

    def demo_file(self) -> DemoFile:
        """Return a DemoFile provenance object."""
        return hdr.parse_demo_file_info(self._parser, self._path)

    def map_name(self) -> str:
        return hdr.parse_map_name(self._parser)

    def server_name(self) -> str:
        return hdr.parse_server_name(self._parser)

    def game_directory(self) -> str:
        return hdr.parse_game_directory(self._parser)

    def network_protocol(self) -> int:
        return hdr.parse_network_protocol(self._parser)

    def tick_rate(self) -> int:
        """Estimate tick rate from network protocol (usually 64)."""
        proto = self.network_protocol()
        return proto if proto > 0 else 64

    def list_game_events(self) -> list[str]:
        """List all available game events in this demo."""
        return self._parser.list_game_events()

    def list_tick_fields(self) -> list[str]:
        """List all available tick fields in this demo."""
        return self._parser.list_updated_fields()

    # ═══════════════════════════════════════════════════════════════════════
    # PLAYERS
    # ═══════════════════════════════════════════════════════════════════════

    def players(self) -> list[Player]:
        """Return all players from the demo."""
        if self._players is not None:
            return self._players

        df = self._parser.parse_player_info()
        players: list[Player] = []
        for _, row in df.iterrows():
            sid = row.get("steamid")
            if sid and sid > 0:
                players.append(Player(steam_id=int(sid), name=str(row.get("name", ""))))
        self._players = players
        return players

    # ═══════════════════════════════════════════════════════════════════════
    # ROUNDS
    # ═══════════════════════════════════════════════════════════════════════

    def _freeze_end_ticks(self) -> list[int]:
        """Get ticks where round_freeze_end fires (CS2 round starts)."""
        try:
            return events.parse_round_freeze_end(
                self._event_df("round_freeze_end")
            )
        except Exception:
            return []

    def _round_start_ticks(self) -> list[int]:
        """Get ticks where round_start fires."""
        try:
            df = self._event_df("round_start")
            return df["tick"].tolist()
        except Exception:
            return []

    def rounds(self) -> list[Round]:
        """Derive rounds from round_freeze_end and round_end events."""
        if self._rounds is not None:
            return self._rounds

        freeze_ticks = self._freeze_end_ticks()
        round_end_results = self.round_end_reasons()

        if not freeze_ticks:
            # Fall back to round_start ticks
            start_ticks = self._round_start_ticks()
            rounds_list: list[Round] = []
            for i, tick in enumerate(start_ticks):
                rounds_list.append(Round(round_number=i + 1, start_tick=tick))
            self._rounds = rounds_list
            return rounds_list

        rounds_list: list[Round] = []
        for i, freeze_tick in enumerate(freeze_ticks):
            round_num = i + 1
            end_tick = freeze_ticks[i + 1] if i + 1 < len(freeze_ticks) else None

            # Find matching round_end
            rer = None
            for re in round_end_results:
                if re.tick >= freeze_tick and (
                    end_tick is None or re.tick < end_tick
                ):
                    rer = re
                    break

            rounds_list.append(
                Round(
                    round_number=round_num,
                    start_tick=freeze_tick - 1,
                    freeze_end_tick=freeze_tick,
                    end_tick=rer.tick if rer else end_tick,
                    winner_side=rer.winner_side if rer else None,
                    end_reason=rer.reason_name if rer else None,
                )
            )

        self._rounds = rounds_list
        return rounds_list

    # ═══════════════════════════════════════════════════════════════════════
    # KILLS (player_death)
    # ═══════════════════════════════════════════════════════════════════════

    def kills(self) -> list[Kill]:
        """Parse all kills (player_death events) with full 34-field detail."""
        if self._kills is not None:
            return self._kills

        try:
            df = self._event_df(
                "player_death",
                player=["steamid", "team_name", "last_place_name"],
                other=["total_rounds_played"],
            )
            self._kills = events.parse_player_death(df)
        except Exception:
            df = self._event_df("player_death")
            self._kills = events.parse_player_death(df)

        return self._kills

    # ═══════════════════════════════════════════════════════════════════════
    # DAMAGE (player_hurt)
    # ═══════════════════════════════════════════════════════════════════════

    def damage(self) -> list[DamageEvent]:
        """Parse all damage events (player_hurt)."""
        if self._damage is not None:
            return self._damage

        try:
            df = self._event_df(
                "player_hurt",
                player=["steamid"],
                other=["total_rounds_played"],
            )
            self._damage = events.parse_player_hurt(df)
        except Exception:
            df = self._event_df("player_hurt")
            self._damage = events.parse_player_hurt(df)

        return self._damage

    # ═══════════════════════════════════════════════════════════════════════
    # ROUND EVENT PARSERS
    # ═══════════════════════════════════════════════════════════════════════

    def round_end_reasons(self) -> list[RoundEndReason]:
        """Parse round_end events."""
        try:
            df = self._event_df(
                "round_end",
                other=["total_rounds_played"],
            )
            return events.parse_round_end(df)
        except Exception:
            df = self._event_df("round_end")
            return events.parse_round_end(df)

    def round_mvps(self) -> list[RoundMvp]:
        """Parse round_mvp events."""
        df = self._event_df("round_mvp")
        return events.parse_round_mvp(df)

    def win_panel_rounds(self) -> list[WinPanelRound]:
        """Parse cs_win_panel_round events."""
        df = self._event_df("cs_win_panel_round")
        return events.parse_cs_win_panel_round(df)

    def win_panel_match(self) -> list[MatchPanel]:
        """Parse cs_win_panel_match events."""
        df = self._event_df("cs_win_panel_match")
        return events.parse_cs_win_panel_match(df)

    # ═══════════════════════════════════════════════════════════════════════
    # PLAYER EVENT PARSERS
    # ═══════════════════════════════════════════════════════════════════════

    def player_blinds(self) -> list[PlayerBlind]:
        """Parse player_blind (flashbang) events."""
        df = self._event_df("player_blind")
        return events.parse_player_blind(df)

    def player_spawns(self) -> list[PlayerSpawn]:
        """Parse player_spawn events."""
        df = self._event_df("player_spawn")
        return events.parse_player_spawn(df)

    def player_jumps(self) -> list[PlayerJump]:
        """Parse player_jump events."""
        df = self._event_df("player_jump")
        return events.parse_player_jump(df)

    def player_footsteps(self) -> list[FootstepEvent]:
        """Parse player_footstep events."""
        df = self._event_df("player_footstep")
        return events.parse_player_footstep(df)

    # ═══════════════════════════════════════════════════════════════════════
    # WEAPON EVENT PARSERS
    # ═══════════════════════════════════════════════════════════════════════

    def weapon_fires(self) -> list[WeaponFire]:
        """Parse weapon_fire events."""
        df = self._event_df("weapon_fire")
        return events.parse_weapon_fire(df)

    def weapon_reloads(self) -> list[WeaponReload]:
        """Parse weapon_reload events."""
        df = self._event_df("weapon_reload")
        return events.parse_weapon_reload(df)

    def weapon_zooms(self) -> list[WeaponZoom]:
        """Parse weapon_zoom events."""
        df = self._event_df("weapon_zoom")
        return events.parse_weapon_zoom(df)

    def item_equips(self) -> list[ItemEquip]:
        """Parse item_equip events."""
        df = self._event_df("item_equip")
        return events.parse_item_equip(df)

    def item_pickups(self) -> list[ItemPickup]:
        """Parse item_pickup events."""
        df = self._event_df("item_pickup")
        return events.parse_item_pickup(df)

    def bullet_details(self) -> list[dict]:
        """Return raw fire_bullets data (shot-level bullet detail)."""
        df = self._event_df("fire_bullets")
        return events.parse_fire_bullets(df)

    # ═══════════════════════════════════════════════════════════════════════
    # BOMB EVENT PARSERS
    # ═══════════════════════════════════════════════════════════════════════

    def bomb_events(self) -> list[BombEvent]:
        """Parse all bomb-related events (plant, defuse, explode, etc.)."""
        events_list: list[BombEvent] = []
        try:
            events_list.extend(events.parse_bomb_planted(self._event_df("bomb_planted")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_beginplant(self._event_df("bomb_beginplant")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_defused(self._event_df("bomb_defused")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_begindefuse(self._event_df("bomb_begindefuse")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_exploded(self._event_df("bomb_exploded")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_dropped(self._event_df("bomb_dropped")))
        except Exception: pass
        try:
            events_list.extend(events.parse_bomb_pickup(self._event_df("bomb_pickup")))
        except Exception: pass
        events_list.sort(key=lambda e: e.tick)
        return events_list

    # ═══════════════════════════════════════════════════════════════════════
    # GRENADE / INFERNO PARSERS
    # ═══════════════════════════════════════════════════════════════════════

    def grenades(self) -> list[GrenadeDetonation]:
        """Parse all grenade detonation events."""
        events_list: list[GrenadeDetonation] = []
        try:
            events_list.extend(events.parse_hegrenade_detonate(self._event_df("hegrenade_detonate")))
        except Exception: pass
        try:
            events_list.extend(events.parse_flashbang_detonate(self._event_df("flashbang_detonate")))
        except Exception: pass
        try:
            events_list.extend(events.parse_smokegrenade_detonate(self._event_df("smokegrenade_detonate")))
        except Exception: pass
        try:
            events_list.extend(events.parse_smokegrenade_expired(self._event_df("smokegrenade_expired")))
        except Exception: pass
        events_list.sort(key=lambda e: e.tick)
        return events_list

    def inferno_events(self) -> list[InfernoEvent]:
        """Parse molotov/incendiary start and expire events."""
        events_list: list[InfernoEvent] = []
        try:
            events_list.extend(events.parse_inferno_startburn(self._event_df("inferno_startburn")))
        except Exception: pass
        try:
            events_list.extend(events.parse_inferno_expire(self._event_df("inferno_expire")))
        except Exception: pass
        events_list.sort(key=lambda e: e.tick)
        return events_list

    def grenade_trajectories(self) -> list[GrenadeTrajectory]:
        """Return grenade trajectory data (from parse_grenades)."""
        try:
            df = self._parser.parse_grenades(grenades=True)
            return events.parse_grenade_trajectories(df)
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # RANK / PROGRESSION
    # ═══════════════════════════════════════════════════════════════════════

    def rank_updates(self) -> list[RankUpdate]:
        """Parse rank_update events."""
        df = self._event_df("rank_update")
        return events.parse_rank_update(df)

    # ═══════════════════════════════════════════════════════════════════════
    # TICK MARKER / MISC EVENTS
    # ═══════════════════════════════════════════════════════════════════════

    def begin_new_match(self) -> list[TickEvent]:
        """Parse begin_new_match events."""
        try:
            return events.parse_begin_new_match(self._event_df("begin_new_match"))
        except Exception: return []

    def buytime_ended(self) -> list[TickEvent]:
        """Parse buytime_ended events."""
        try:
            return events.parse_buytime_ended(self._event_df("buytime_ended"))
        except Exception: return []

    def cs_pre_restart(self) -> list[TickEvent]:
        """Parse cs_pre_restart events."""
        try:
            return events.parse_cs_pre_restart(self._event_df("cs_pre_restart"))
        except Exception: return []

    def cs_round_final_beep(self) -> list[TickEvent]:
        """Parse cs_round_final_beep events."""
        try:
            return events.parse_cs_round_final_beep(self._event_df("cs_round_final_beep"))
        except Exception: return []

    def cs_round_start_beep(self) -> list[TickEvent]:
        """Parse cs_round_start_beep events."""
        try:
            return events.parse_cs_round_start_beep(self._event_df("cs_round_start_beep"))
        except Exception: return []

    def round_announce_match_start(self) -> list[TickEvent]:
        """Parse round_announce_match_start events."""
        try:
            return events.parse_round_announce_match_start(self._event_df("round_announce_match_start"))
        except Exception: return []

    def round_officially_ended(self) -> list[TickEvent]:
        """Parse round_officially_ended events."""
        try:
            return events.parse_round_officially_ended(self._event_df("round_officially_ended"))
        except Exception: return []

    def round_poststart(self) -> list[TickEvent]:
        """Parse round_poststart events."""
        try:
            return events.parse_round_poststart(self._event_df("round_poststart"))
        except Exception: return []

    def round_prestart(self) -> list[TickEvent]:
        """Parse round_prestart events."""
        try:
            return events.parse_round_prestart(self._event_df("round_prestart"))
        except Exception: return []

    def round_time_warning(self) -> list[TickEvent]:
        """Parse round_time_warning events."""
        try:
            return events.parse_round_time_warning(self._event_df("round_time_warning"))
        except Exception: return []

    def round_start_events(self) -> list[RoundStartEvent]:
        """Parse round_start events (fraglimit, objective, timelimit)."""
        try:
            return events.parse_round_start(self._event_df("round_start"))
        except Exception: return []

    def hltv_version_info(self) -> list[HltvVersionInfo]:
        """Parse hltv_versioninfo events."""
        try:
            return events.parse_hltv_versioninfo(self._event_df("hltv_versioninfo"))
        except Exception: return []

    def other_deaths(self) -> list[OtherDeath]:
        """Parse other_death events (entity deaths, not players)."""
        try:
            return events.parse_other_death(self._event_df("other_death"))
        except Exception: return []

    # ═══════════════════════════════════════════════════════════════════════
    # TICK-LEVEL STATE
    # ═══════════════════════════════════════════════════════════════════════

    def player_frames(self, specific_ticks: Optional[Sequence[int]] = None) -> list[PlayerFrame]:
        """Extract per-player world state at given ticks (or all ticks)."""
        return ticks.extract_player_frames(self._parser, specific_ticks)

    def player_controller_frames(self, specific_ticks: Optional[Sequence[int]] = None) -> list[PlayerFrame]:
        """Extract controller-level data (team, identity, alive status)."""
        return ticks.extract_controller_frames(self._parser, specific_ticks)

    def player_round_stats(self, specific_ticks: Optional[Sequence[int]] = None) -> list[PlayerRoundStats]:
        """Extract per-round cumulative stats from ActionTrackingServices."""
        return ticks.extract_player_round_stats(self._parser, specific_ticks)

    def player_money(self, specific_ticks: Optional[Sequence[int]] = None) -> list[PlayerMoney]:
        """Extract per-player money state."""
        return ticks.extract_player_money(self._parser, specific_ticks)

    def game_rules(self, specific_ticks: Optional[Sequence[int]] = None) -> list[GameRulesFrame]:
        """Extract CS2 game rules state at given ticks."""
        return ticks.extract_game_rules(self._parser, specific_ticks)

    def combined_player_state(self, specific_ticks: Optional[Sequence[int]] = None) -> dict[int, PlayerFrame]:
        """Get combined player state (pawn + controller) keyed by steam_id."""
        return ticks.extract_all_player_state(self._parser, specific_ticks)

    # ═══════════════════════════════════════════════════════════════════════
    # EQUIPMENT / ECONOMY HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def player_equipment_at_freezetime(self) -> list[dict]:
        """Return equipment value snapshots at freeze-end ticks."""
        freeze_ticks = self._freeze_end_ticks()
        if not freeze_ticks:
            return []
        df = self._parser.parse_ticks(
            ["m_unCurrentEquipmentValue", "m_unFreezetimeEndEquipmentValue"],
            ticks=freeze_ticks,
        )
        records = df.to_dict(orient="records")
        round_map = {ft: i + 1 for i, ft in enumerate(freeze_ticks)}
        for r in records:
            r["round_number"] = round_map.get(r.get("tick", 0), 0)
        return records

    def item_drops(self) -> list[ItemDrop]:
        """Parse item drop events (weapon provenance)."""
        try:
            df = self._parser.parse_item_drops()
            return events.parse_item_drops(df)
        except Exception:
            return []

    def skins(self) -> list[SkinData]:
        """Parse weapon skin data."""
        try:
            df = self._parser.parse_skins()
            return events.parse_skins(df)
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # COMPOSITE — full match
    # ═══════════════════════════════════════════════════════════════════════

    def parse_match(self, match_context: Optional[MatchContext] = None) -> Match:
        """Parse an entire match — header + players + rounds + kills."""
        return Match(
            map_name=self.map_name(),
            tick_rate=self.tick_rate(),
            server_name=self.server_name(),
            source=self.game_directory(),
            demo_file=self.demo_file(),
            players=self.players(),
            rounds=self.rounds(),
            kills=self.kills(),
            context=match_context,
        )
