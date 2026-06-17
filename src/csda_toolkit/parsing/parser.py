"""High-level DemoParser wrapper for csda-toolkit.

Wraps demoparser2.DemoParser to provide clean access to all CS2 demo data
as typed Python domain objects.
"""

from datetime import datetime
from typing import Optional

import pandas as pd
from demoparser2 import DemoParser as Parser2

from csda_toolkit.domain.models import (
    BombEvent,
    DamageEvent,
    DemoFile,
    GrenadeEvent,
    Kill,
    Match,
    MatchContext,
    MatchTeam,
    Player,
    PlayerEquipment,
    PurchaseEvent,
    Round,
    WeaponDropEvent,
)


class DemoParser:
    """High-level parser wrapping demoparser2.

    Usage:
        parser = DemoParser("path/to/demo.dem")
        match = parser.parse_match()
        kills = parser.parse_kills()
    """

    def __init__(self, demo_path: str):
        self._path = demo_path
        self._parser = Parser2(demo_path)

    # ── Header / metadata ────────────────────────────────────────────────

    def parse_header(self) -> dict:
        """Return raw demo header data."""
        return self._parser.parse_header()

    def map_name(self) -> str:
        """Return the map name from the demo header."""
        return self._parser.parse_header().get("map_name", "")

    def server_name(self) -> str:
        """Return the server name from the demo header."""
        return self._parser.parse_header().get("server_name", "")

    def tick_rate(self) -> int:
        """Return the tick rate."""
        try:
            return int(self._parser.parse_header().get("network_protocol", 0))
        except (ValueError, TypeError):
            return 64  # default CS2 tick rate

    def demo_file_info(self) -> DemoFile:
        """Return a DemoFile with ingestion provenance."""
        header = self._parser.parse_header()
        return DemoFile(
            demo_filename=self._path.split("/")[-1].split("\\")[-1],
            demo_checksum="",  # computed externally
            source=header.get("game_directory", "unknown"),
        )

    # ── Player info ──────────────────────────────────────────────────────

    def parse_players(self) -> list[Player]:
        """Return all players in the demo."""
        df = self._parser.parse_player_info()
        players: list[Player] = []
        for _, row in df.iterrows():
            sid = row.get("steamid")
            if sid and sid > 0:
                players.append(
                    Player(steam_id=int(sid), name=str(row.get("name", "")))
                )
        return players

    # ── Rounds ───────────────────────────────────────────────────────────

    def _get_freeze_end_ticks(self) -> list[int]:
        """Get ticks where round_freeze_end fires (CS2 round starts)."""
        try:
            df = self._parser.parse_event("round_freeze_end")
            return df["tick"].tolist()
        except Exception:
            return []

    def parse_rounds(self) -> list[Round]:
        """Derive rounds from round_freeze_end events + game state."""
        freeze_end_ticks = self._get_freeze_end_ticks()
        if not freeze_end_ticks:
            return []

        # Get round counts from ticks
        df_ticks = self._parser.parse_ticks(
            ["total_rounds_played"],
            ticks=freeze_end_ticks,
        )

        rounds: list[Round] = []
        for i, tick in enumerate(freeze_end_ticks):
            mask = df_ticks["tick"] == tick
            round_data = df_ticks[mask]
            round_num = int(round_data["total_rounds_played"].iloc[0]) if not round_data.empty else i

            # Get score info from game state
            rounds.append(
                Round(
                    round_number=round_num,
                    start_tick=tick,
                    end_tick=freeze_end_ticks[i + 1] if i + 1 < len(freeze_end_ticks) else None,
                )
            )

        return rounds

    # ── Kills ────────────────────────────────────────────────────────────

    def parse_kills(self) -> list[Kill]:
        """Parse all kill events."""
        df = self._parser.parse_event(
            "player_death",
            player=["steamid", "team_name", "last_place_name"],
            other=["total_rounds_played"],
        )
        kills: list[Kill] = []
        for _, row in df.iterrows():
            kills.append(
                Kill(
                    round_number=int(row.get("total_rounds_played", 0)),
                    tick=int(row.get("tick", 0)),
                    killer_steam_id=_int_or_none(row.get("attacker_steamid")),
                    killer_name=str(row.get("attacker_name", "")),
                    victim_steam_id=_int_or_none(row.get("user_steamid")),
                    victim_name=str(row.get("user_name", "")),
                    assister_steam_id=_int_or_none(row.get("assister_steamid")),
                    assister_name=str(row.get("assister_name", "")),
                    weapon_name=str(row.get("weapon", "")),
                    is_headshot=bool(row.get("headshot", False)),
                    is_wallbang=False,
                )
            )
        return kills

    # ── Damage ───────────────────────────────────────────────────────────

    def parse_damage(self) -> list[DamageEvent]:
        """Parse all damage events."""
        df = self._parser.parse_event(
            "player_hurt",
            player=["steamid"],
            other=["total_rounds_played"],
        )
        damage_events: list[DamageEvent] = []
        for _, row in df.iterrows():
            damage_events.append(
                DamageEvent(
                    round_number=int(row.get("total_rounds_played", 0)),
                    tick=int(row.get("tick", 0)),
                    attacker_steam_id=_int_or_none(row.get("attacker_steamid")),
                    attacker_name=str(row.get("attacker_name", "")),
                    victim_steam_id=_int_or_none(row.get("user_steamid")),
                    victim_name=str(row.get("user_name", "")),
                    weapon_name=str(row.get("weapon", "")),
                    damage=int(row.get("dmg_health", 0)),
                    hit_group=str(row.get("hitgroup", "")),
                    is_headshot=str(row.get("hitgroup", "")) == "head",
                )
            )
        return damage_events

    # ── Bomb events ──────────────────────────────────────────────────────

    def parse_bomb_events(self) -> list[BombEvent]:
        """Parse bomb plant, defuse, and explode events."""
        events: list[BombEvent] = []

        for event_name, event_type in [
            ("bomb_planted", "plant"),
            ("bomb_defused", "defuse"),
            ("bomb_exploded", "explode"),
        ]:
            try:
                df = self._parser.parse_event(
                    event_name,
                    player=["steamid"],
                    other=["total_rounds_played"],
                )
                for _, row in df.iterrows():
                    events.append(
                        BombEvent(
                            round_number=int(row.get("total_rounds_played", 0)),
                            tick=int(row.get("tick", 0)),
                            event_type=event_type,
                            player_steam_id=_int_or_none(row.get("user_steamid")),
                            player_name=str(row.get("user_name", "")),
                            site=str(row.get("site", "")),
                        )
                    )
            except Exception:
                continue

        return events

    # ── Grenades ─────────────────────────────────────────────────────────

    def parse_grenades(self) -> list[GrenadeEvent]:
        """Parse grenade trajectory detonation endpoints."""
        try:
            df = self._parser.parse_grenades(grenades=True)
        except Exception:
            return []

        events: list[GrenadeEvent] = []
        for _, row in df.iterrows():
            events.append(
                GrenadeEvent(
                    round_number=0,  # Determined externally
                    tick=int(row.get("tick", 0)),
                    thrower_steam_id=_int_or_none(row.get("thrower_steamid")),
                    grenade_type=str(row.get("grenade_type", "")),
                    position_x=row.get("X"),
                    position_y=row.get("Y"),
                    position_z=row.get("Z"),
                )
            )
        return events

    # ── Economy snapshots ────────────────────────────────────────────────

    def parse_equipment_at_freeze_end(self) -> list[PlayerEquipment]:
        """Parse player equipment at round_freeze_end ticks."""
        try:
            freeze_ticks = self._get_freeze_end_ticks()
        except Exception:
            return []

        if not freeze_ticks:
            return []

        df = self._parser.parse_ticks(
            ["current_equip_value", "total_rounds_played", "has_defuser", "has_helmet"],
            ticks=freeze_ticks,
        )

        equipment: list[PlayerEquipment] = []
        for _, row in df.iterrows():
            sid = row.get("steamid")
            if not sid or sid == 0:
                continue
            equipment.append(
                PlayerEquipment(
                    round_number=int(row.get("total_rounds_played", 0)),
                    steam_id=int(sid),
                    player_name=str(row.get("name", "")),
                    equipment_value=int(row.get("current_equip_value", 0)),
                    armor=bool(row.get("has_defuser", False)),
                    helmet=bool(row.get("has_helmet", False)),
                    defuse_kit=bool(row.get("has_defuser", False)),
                )
            )
        return equipment

    # ── Weapon purchases ─────────────────────────────────────────────────

    def parse_purchases(self) -> list[PurchaseEvent]:
        """Synthesize purchase events from item_purchase game events."""
        try:
            df = self._parser.parse_event(
                "item_purchase",
                player=["steamid", "team_name"],
                other=["total_rounds_played"],
            )
        except Exception:
            return []

        purchases: list[PurchaseEvent] = []
        for _, row in df.iterrows():
            purchases.append(
                PurchaseEvent(
                    round_number=int(row.get("total_rounds_played", 0)),
                    tick=int(row.get("tick", 0)),
                    steam_id=int(row.get("user_steamid", 0)),
                    player_name=str(row.get("user_name", "")),
                    weapon_name=str(row.get("weapon", "")),
                    weapon_category=_weapon_category(str(row.get("weapon", ""))),
                    cost=0,  # Not available in game event
                )
            )
        return purchases

    # ── Weapon drops ─────────────────────────────────────────────────────

    def parse_item_drops(self) -> list[WeaponDropEvent]:
        """Parse item drop events."""
        try:
            df = self._parser.parse_item_drops()
        except Exception:
            return []

        drops: list[WeaponDropEvent] = []
        for _, row in df.iterrows():
            drops.append(
                WeaponDropEvent(
                    round_number=0,
                    tick=0,
                    weapon_name=_defindex_to_weapon(int(row.get("def_index", 0))),
                )
            )
        return drops

    # ── Composite: full match ────────────────────────────────────────────

    def parse_match(self, match_context: Optional[MatchContext] = None) -> Match:
        """Parse an entire match from the demo."""
        header = self._parser.parse_header()
        players = self.parse_players()
        rounds = self.parse_rounds()
        kills = self.parse_kills()
        demo_file = self.demo_file_info()

        match = Match(
            map_name=header.get("map_name", ""),
            tick_rate=64,
            server_name=header.get("server_name", ""),
            source=header.get("game_directory", "unknown"),
            demo_file=demo_file,
            players=players,
            rounds=rounds,
            kills=kills,
            context=match_context,
        )

        return match

    # ── Raw access ───────────────────────────────────────────────────────

    def raw(self) -> Parser2:
        """Access the underlying demoparser2 instance."""
        return self._parser

    def list_game_events(self) -> list[str]:
        """List all available game events in this demo."""
        return self._parser.list_game_events()

    def list_updated_fields(self) -> list[str]:
        """List all tracked entity fields in this demo."""
        return self._parser.list_updated_fields()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _int_or_none(val) -> Optional[int]:
    """Convert a value to int, returning None if invalid."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _weapon_category(weapon: str) -> Optional[str]:
    """Rough weapon categorization."""
    rifles = {"ak-47", "m4a4", "m4a1-s", "aug", "sg 553", "galil ar", "famas"}
    smgs = {"mp9", "mp7", "mp5-sd", "mac-10", "p90", "bizon", "ump-45"}
    pistols = {"usp-s", "glock-18", "p2000", "p250", "five-seven", "tec-9", "cz75-auto", "desert eagle", "revolver"}
    heavy = {"nova", "xm1014", "mag-7", "m249", "negev"}
    equipment = {"flashbang", "smoke grenade", "he grenade", "molotov", "incendiary", "decoy", "zeus x27"}
    awp_set = {"awp"}
    if weapon.lower() in rifles:
        return "rifle"
    if weapon.lower() in awp_set:
        return "awp"
    if weapon.lower() in smgs:
        return "smg"
    if weapon.lower() in pistols:
        return "pistol"
    if weapon.lower() in heavy:
        return "heavy"
    if weapon.lower() in equipment:
        return "equipment"
    return None


def _defindex_to_weapon(defindex: int) -> str:
    """Map item definition index to weapon name."""
    mapping = {
        1: "desert eagle",
        2: "dual berettas",
        3: "five-seven",
        4: "glock-18",
        7: "ak-47",
        8: "aug",
        9: "awp",
        10: "famas",
        11: "g3sg1",
        13: "galil ar",
        14: "m249",
        16: "m4a4",
        17: "mac-10",
        19: "p90",
        23: "mp5-sd",
        24: "ump-45",
        25: "xm1014",
        26: "pp-bizon",
        27: "mag-7",
        28: "negev",
        29: "sawed-off",
        30: "tec-9",
        31: "zeus x27",
        32: "p2000",
        33: "mp7",
        34: "mp9",
        35: "nova",
        36: "p250",
        37: "scar-20",
        38: "sg 553",
        39: "ssg 08",
        40: "m4a1-s",
        41: "usp-s",
        42: "cz75-auto",
        43: "revolver",
    }
    return mapping.get(defindex, f"unknown_{defindex}")
