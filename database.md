# Database Iterations

This document summarises the schema evolution across the three current migrations.

For the full project context, see `docs/project-state.md`.
For the visual ERD, see `docs/schema-visualizer.md`.

---

## Migration 0001 — initial schema

File: `crates/csda-storage/migrations/0001_initial.sql`

Tables created:
- `csda.demo_files` — ingestion provenance (checksum, parser name/version, source)
- `csda.matches` — canonical match record with `canonical_match_json` snapshot
- `csda.players` — global player identity keyed by `steam_id`
- `csda.match_players` — per-match player participation
- `csda.rounds` — round facts (ticks, sides, score snapshot)
- `csda.kills` — kill events with raw names and optional player links
- `csda.external_match_links` — external provider match IDs (FACEIT, HLTV, etc.)
- `csda.analyst_notes` — analyst annotations scoped to match / round / tick / player

Design decisions:
- `canonical_match_json` is stored on `matches` so the raw canonical parse is preserved for safe reprocessing.
- `kills` stores raw names as a fallback so ingestion works even when player identity is incomplete.

---

## Migration 0002 — teams and match context

File: `crates/csda-storage/migrations/0002_team_context.sql`

Tables created:
- `csda.teams` — canonical team identity with `slug` and optional `country_code`
- `csda.external_team_links` — external provider team IDs per team
- `csda.team_aliases` — alternate team names with source and confidence
- `csda.match_teams` — per-match team slots (slot 1 = CT start, slot 2 = T start)
- `csda.match_contexts` — analytical context per match (pool, environment, tier, provider)

Alters:
- `match_players` gains `match_team_id`

Design decisions:
- `match_contexts` uses orthogonal fields (`context_provider`, `play_environment`, `is_structured_team_play`, `tier_estimate`, `analysis_pool`) rather than a single `competition_type` enum.
- `match_teams.team_id` is nullable — a provisional slot can exist before canonical team identity is resolved.
- Analysis pools: `pro_structured`, `team_structured`, `individual_competitive`, `low_signal`.

---

## Migration 0003 — match time, lineups, and roster history

File: `crates/csda-storage/migrations/0003_lineups_roster_history.sql`

Tables created:
- `csda.lineups` — reusable player-set identity; `lineup_hash` = sorted canonical `player_id`s
- `csda.lineup_players` — maps players to a lineup
- `csda.team_memberships` — historical roster archive with join/leave dates, type, source, confidence

Alters:
- `matches` gains `played_at`, `played_at_source`, `played_at_confidence`
- `match_teams` gains `lineup_id`

Backfill:
- Derives lineups from existing `match_players` for all rows where player identity is fully resolved.

Design decisions:
- `lineup_hash` is player-set based only. Team / coach / era context belongs in a future `competitive_units` model.
- `team_memberships` is the archive/historical layer. It is **not** a replacement for factual match participation via `match_teams` + `match_players`.
- `played_at` is nullable and carries a `played_at_source` and `played_at_confidence` because timestamps may come from the demo, HLTV, FACEIT, file metadata, or manual correction.

---

## Migration 0004 — team type hierarchy

File: `crates/csda-storage/migrations/0004_team_type_hierarchy.sql`

Alters:
- `teams` gains `team_type` (`main` / `academy` / `mixed`) and `parent_team_id` (self-referential FK)

Design decisions:
- `team_type` categorizes the team's roster type within the org hierarchy
- `parent_team_id` enables academy/sister team links to parent orgs (e.g., Navi Junior → Navi)
- Self-reference constraint prevents circular hierarchy

---

## Migration 0005 — classification pipeline + team hierarchy cleanup + match event qualifiers

File: `crates/csda-storage/migrations/0005_classification_team_hierarchy_event_qualifiers.sql`

Tables created:
- `csda.classifier_runs` — versioned, rerunnable classifier execution log
- `csda.round_classifications` — per-round labels (buy_type, archetype, ct_strategy, etc.)
- `csda.player_situation_roles` — role = f(player, lineup, map, side), not a static player property
- `csda.match_classifications` — broader match-level labels
- `csda.match_event_qualifiers` — LAN/online, crowd level/consistency/intensity

Alters:
- `match_teams` gains `parent_team_id` (links academy/sister teams to parent org)
- `team_aliases` gains `team_type` and `is_org_relationship` (distinguishes display aliases from org hierarchy links)

Design decisions:
- Classification labels are freeform text (`label_name`/`label_value`) — controlled vocabularies enforced in classifier code, not schema
- Every classification references a `classifier_run_id` — rerunning a classifier produces new rows, old ones stay queryable
- `player_situation_roles` is the key table for map/side/role nuance: `player=s1mple, map=mirage, side=ct → role_code=ct_b_anchor`
- `match_event_qualifiers` is enrichable from HLTV `lan` flags and crowd notes

---

## Migration 0006 — player aliases

File: `crates/csda-storage/migrations/0006_player_aliases.sql`

Tables created:
- `csda.player_aliases` — maps steam_id to all known display names across data sources

Design decisions:
- `steam_id` is the canonical key (players table already has it)
- `source` column distinguishes HLTV/pro names (`hltv`), demo names (`demo`), FACEIT names (`faceit`), HLTV roster names (`hltv_roster`), manually entered (`manual`), and heuristically matched (`inferred`)
- Unique constraint on `(steam_id, alias, source)` prevents duplicate aliases
- `is_canonical` flag marks the preferred display name (usually HLTV name for pro players)
- `first_seen_at` / `last_seen_at` track alias lifecycle

Why:
- Players have different names across data sources: "ZywOo" (HLTV), "ZywOo." (demo), "zywOo_csgo" (FACEIT)
- Canonical steam_id key enables aggregating stats across tournaments even when names differ

---

## What is intentionally deferred

Not yet modelled:
- damage events
- utility events
- bomb events
- economy snapshots
- player positions / trajectory blobs

---

## Current migrations

```
crates/csda-storage/migrations/
├── 0001_initial.sql
├── 0002_team_context.sql
├── 0003_lineups_roster_history.sql
├── 0004_team_type_hierarchy.sql
├── 0005_classification_team_hierarchy_event_qualifiers.sql
└── 0006_player_aliases.sql
```

---

## Rust-side storage support

`csda-storage` currently provides:

- `IngestBundle` — converts `csda-core::Match` into DB-ready records
- `MatchIngestContext` — carries checksum, parser info, match context, and match time
- `PostgresStorage` — full ingest + manual curation methods
- Curation types: `CreateTeamInput`, `AddTeamAliasInput`, `AddExternalTeamLinkInput`, `AssignMatchTeamInput`, `SetMatchTimeInput`, `AddTeamMembershipInput`
- Classification record types: `ClassifierRunRecord`, `RoundClassificationRecord`, `PlayerSituationRoleRecord`, `MatchClassificationRecord`
- Match event qualifier types: `MatchEventQualifierRecord` with `NetworkType`, `CrowdLevel`, `CrowdConsistency`
- Player alias types: `PlayerAliasRecord` with `AliasSource` enum
- Helper functions: `upsert_match_event_qualifiers`, `insert_classifier_run`, `insert_round_classification`, `insert_player_situation_role`, `insert_match_classification`, `upsert_player_alias`

---

## CLI commands

```bash
cargo run -p csda-cli -- db migrate
cargo run -p csda-cli -- db sample-ingest
cargo run -p csda-cli -- db team create
cargo run -p csda-cli -- db team alias-add
cargo run -p csda-cli -- db team link-add
cargo run -p csda-cli -- db team membership-add
cargo run -p csda-cli -- db match-team assign
cargo run -p csda-cli -- db match set-time
cargo run -p csda-cli -- db match classify
```

All commands accept `--database-url` or read `DATABASE_URL` from the environment.
