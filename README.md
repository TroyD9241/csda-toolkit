# CSDA Toolkit

**Python toolkit for CS2 demo analysis** — built on top of our fork of [`LaihoE/demoparser`](https://github.com/LaihoE/demoparser).

## What this is

`csda-toolkit` is a Python-native toolkit that wraps the `demoparser` to provide:
- Direct access to every data point the parser extracts (kills, damage, economy, grenades, bomb events, player positions, etc.)
- Classifiers and analytics (economy, round archetypes, player roles, team tendencies, HLTV 3.0 rating)
- Persistent storage to Postgres via SQLAlchemy 2.0
- No parsing bottleneck — extract data straight from demos, then enrich and analyze

## Fork

The parser fork lives at the project's sibling `demoparser/` directory.
GitHub: `https://github.com/TroyD9241/demoparser`

**Future intent**: We will actively extend this fork to expose additional data points, improve event coverage, and add new parsing capabilities beyond what the upstream `LaihoE/demoparser` provides. The fork is the foundation — everything in this toolkit depends on it.

## Directory Layout

```
csda-toolkit/
├── src/csda_toolkit/     # Source code
│   ├── classifiers/      # Economy, archetype, role, position, utility, drop, tactical, HLTV rating
│   ├── db/               # SQLAlchemy models, database connection
│   ├── domain/           # Pydantic/dataclass domain models
│   ├── enrichment/       # HLTV adapter (scrapes HLTV match pages)
│   ├── ingest/           # Demo ingestion pipeline
│   ├── parsing/          # Tick/event extraction from demoparser
│   └── cli/              # CLI entry points
├── tests/                # Test files (pytest)
│   ├── test_hltv_rating.py            # Unit tests for hltv_rating functions
│   ├── test_hltv_match_integration.py # Match-level integration test (vs HLTV reference)
│   └── ... (17 other test files)
├── scripts/              # Utility scripts
│   ├── ingest_one.py     # Ingest a single demo file
│   └── run_classifiers.py # Run full classifier pipeline on all matches
├── docs/                 # Documentation
│   ├── hltv_rating_formula.md
│   └── role-quality-formulas.md
├── alembic/              # DB migrations
├── demos/                # Demo files (gitignored)
└── weaponData/           # Weapon damage stats (from cs2damage.com)
```

## HLTV 3.0 Rating

The toolkit implements a baseline HLTV 3.0 rating for CS2 matches. The formula:

```
rating = 0.1358
       + 0.4941 × eKPR
       + 0.3795 × (1 − eDPR)
       + 0.4280 × (eADR / 100)
       + 0.2602 × eKAST         # eKAST is a 0-1 ratio (no /100)
       + 0.03748 × Swing%
       + 0.0241 × MK_per_r
```

### Key design decisions

- **Match-level computation** (not per-round averaging). HLTV computes the rating once per match using aggregate inputs.
- **eKAST is a 0-1 ratio** (e.g., 0.789 for 78.9%). The formula uses `0.2602 × eKAST` directly — no `/100` in the coefficient.
- **K-D from the Kill table** (not PRS cumulative, which has systematic timing bugs).
- **KAST traded detection**: victim-first revenge kill by a teammate within a 320-tick (~5s) window.
- **ADR from PRS `m_iDamage`** (weapon damage from `CCSPlayerController_ActionTrackingServices`). Most reliable cross-match baseline.

### Known limitations

- **Swing% not computed.** HLTV's exact formula is undocumented. The rating is a baseline without swing contribution.
- **ADR ~10-20% low** for some players. PRS `m_iDamage` undercounts damage from utility/grenades and inconsistent snapshot timing.
- **PRS snapshot timing**: PRS snapshots are taken at round START, not END. A `round_end_ticks` parameter has been added to `extract_player_round_stats` in `src/csda_toolkit/parsing/ticks.py` for future re-ingestion to fix this.

### Validation results (Map 1: Mirage, vs HLTV)

| Player | Ours | HLTV | Diff |
|--------|------|------|------|
| mezii | 1.36 | 1.81 | -0.45 (high swing) |
| dem0n | 1.30 | 1.70 | -0.40 (high swing + ADR gap) |
| apEX | 1.33 | 1.26 | +0.07 |
| ropz | 1.27 | 1.22 | +0.05 |
| flameZ | 1.15 | 1.06 | +0.09 |
| ZywOo | 1.15 | 0.92 | +0.23 |
| dziugss | 0.97 | 0.86 | +0.11 |
| Krabeni | 0.92 | 0.80 | +0.12 |
| cmtry | 0.84 | 0.74 | +0.10 |
| coolio | 0.71 | 0.65 | +0.06 |

**Mean abs diff: 0.169 (swing=0 baseline), 0.103 (with HLTV swing as sanity check).**
8/10 players within 0.12 of HLTV baseline. The 2 outliers (mezii, dem0n) have large positive swing which we're not computing.

## Quick Start

### Ingest a demo

```bash
py scripts/ingest_one.py path/to/demo.dem
```

### Run classifiers on all matches

```bash
py scripts/run_classifiers.py
```

### Run the HLTV rating test

```bash
py tests/test_hltv_match_integration.py
```

### Run all tests

```bash
pytest tests/ -v
```

## Reference Docs

- `docs/hltv_rating_formula.md` — Detailed HLTV 3.0 formula derivation and validation
- `docs/role-quality-formulas.md` — Role quality scoring formulas
- `project-state.md` — Full current project state — **start here**
- `architecture.md` — Long-term platform vision
- `database.md` — DB schema iteration notes
- `schema-visualizer.md` — ERD of current schema
- `docker.md` — Local dev setup

## Recent Work

- **Ingest 3 demos** (mirage, dust2, nuke) via IngestBundle
- **SHA256 idempotency** (prevents duplicate ingestion)
- **PlayerBlind proximity heuristic fallback** (with `is_heuristic` flag to distinguish real vs estimated)
- **Compact grenade trajectory summary** (12 points/throw vs raw, 99.95% size reduction)
- **Batch event tables** (weapon_fire, player_spawn, etc.)
- **PRS column types widened** (SMALLINT → INTEGER)

### Bug Fixes

- **Fix `match_players` NULL `team_side`**: Players inactive in round 0 (no kill/death) previously got NULL. Now checks assists, falls back to round 1, then assigns majority side.
- **Fix `match_teams.score` / `is_winner` NULL**: Computed from round wins (`COUNT(winner_side='ct'/'t')`) since demoparser's `round.score_t/score_ct` are 0 in our demos.
- **Fix `player_blinds.victim_name` empty**: Now looked up from `players.last_known_name` via raw SQL (avoids session caching). Applied in both real ingest and proximity heuristic.
- **SHA256 idempotency** (prevents duplicate ingestion)
- **PlayerBlind proximity heuristic fallback** (with `is_heuristic` flag to distinguish real vs estimated)
- **Compact grenade trajectory summary** (12 points/throw vs raw, 99.95% size reduction)
- **Batch event tables** (weapon_fire, player_spawn, etc.)
- **PRS column types widened** (SMALLINT → INTEGER)
- **Fix match_players NULL team_side** for players inactive in round 0 (also checks assists, falls back to round 1, then majority)
- **Populate match_teams.score and match_teams.is_winner** from round wins
- **Populate player_blinds.victim_name** from players table
- **HLTV 3.0 rating baseline**: Implemented match-level rating with eKAST fix, K-D from Kill table, traded detection, and PRS-based ADR
- **PRS snapshot timing fix**: Added `round_end_ticks` parameter to `extract_player_round_stats` for future re-ingestion
- **Self-damage filter utility**: Added `is_utility_weapon()` and `compute_utility_dmg_to_opponents()` helpers in `hltv_rating.py` for filtered utility damage
- **Test cleanup**: Removed 32 debug/one-off scripts. Tests organized in `tests/`, scripts in `scripts/`
