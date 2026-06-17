"""Integration tests using the real BLAST demo file."""

from pathlib import Path

import pytest

DEMO_DIR = Path("demos")
DEMO_NAME = "blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks"
DEMO_PATH = DEMO_DIR / DEMO_NAME


def find_demo_dem():
    """Find the .dem file inside the extracted demo directory."""
    if not DEMO_PATH.exists():
        pytest.skip(f"Demo directory not found: {DEMO_PATH}")
    candidates = list(DEMO_PATH.glob("*.dem"))
    if not candidates:
        pytest.skip(f"No .dem file found in {DEMO_PATH}")
    return str(candidates[0])


class TestDemoFileAvailable:
    """Sanity check: demo file exists before running parser tests."""

    def test_demo_directory_exists(self):
        assert DEMO_PATH.exists(), f"Demo directory not found: {DEMO_PATH}"

    def test_demo_dem_file_exists(self):
        dem_file = find_demo_dem()
        assert Path(dem_file).exists()
        assert dem_file.endswith(".dem")


class TestCsdaParserImport:
    """CsdaParser can be imported from the parsing module."""

    def test_parser_imports_from_parsing_module(self):
        from csda_toolkit.parsing.parser import CsdaParser
        assert CsdaParser is not None

    def test_parser_instantiation(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        assert parser is not None


class TestParserHeader:
    """Parser header/metadata extraction."""

    def test_map_name_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        name = parser.map_name()
        assert name
        assert isinstance(name, str)

    def test_tick_rate_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        rate = parser.tick_rate()
        assert isinstance(rate, int)
        assert rate > 0

    def test_demo_file_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        df = parser.demo_file()
        assert df is not None
        assert hasattr(df, "demo_filename")

    def test_header_raw_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        header = parser.header_raw()
        assert isinstance(header, dict)


class TestParserRounds:
    """Round data is accessible from parser."""

    def test_rounds_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        rounds = parser.rounds()
        assert isinstance(rounds, list)
        assert len(rounds) > 0, "Demo should have at least one round"


class TestParserPlayers:
    """Player data is accessible."""

    def test_players_method(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        players = parser.players()
        assert isinstance(players, list)
        assert len(players) > 0, "Should have at least one player"

    def test_player_has_steam_id_and_name(self):
        from csda_toolkit.parsing.parser import CsdaParser
        dem_file = find_demo_dem()
        parser = CsdaParser(dem_file)
        players = parser.players()
        first = players[0]
        assert hasattr(first, "steam_id")
        assert hasattr(first, "name")
        assert first.steam_id > 0
