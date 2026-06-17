"""Demo header/metadata parsing."""

from __future__ import annotations

from typing import Optional

from demoparser2 import DemoParser

from csda_toolkit.domain.models import DemoFile


def parse_demo_header(parser: DemoParser) -> dict:
    """Return the raw demo header dict (same as demoparser2's parse_header)."""
    return parser.parse_header()


def parse_demo_file_info(parser: DemoParser, demo_path: str) -> DemoFile:
    """Build a DemoFile domain object from the demo header."""
    header = parser.parse_header()
    demo_filename = demo_path.split("/")[-1].split("\\")[-1]
    return DemoFile(
        demo_filename=demo_filename,
        demo_checksum="",
        parser_name="demoparser2",
        parser_version="0.41.3",
        source=header.get("game_directory", "unknown"),
        raw_metadata=dict(header),
    )


def parse_map_name(parser: DemoParser) -> str:
    """Return the map name from the demo header."""
    return parser.parse_header().get("map_name", "")


def parse_server_name(parser: DemoParser) -> str:
    """Return the server name."""
    return parser.parse_header().get("server_name", "")


def parse_game_directory(parser: DemoParser) -> str:
    """Return the game directory (e.g. 'csgo', 'cs2')."""
    return parser.parse_header().get("game_directory", "")


def parse_client_name(parser: DemoParser) -> str:
    """Return the client name from the header."""
    return parser.parse_header().get("client_name", "")


def parse_network_protocol(parser: DemoParser) -> int:
    """Return the network protocol version."""
    try:
        return int(parser.parse_header().get("network_protocol", 0))
    except (ValueError, TypeError):
        return 0
