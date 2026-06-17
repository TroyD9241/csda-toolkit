# `0005` Schema Proposal: Classification Pipeline + Team Hierarchy + Match Event Qualifiers

This document proposes the **next schema iteration** after `0004_team_type_hierarchy.sql`.

Three goals:

1. **Build the classification pipeline foundation** — versioned, rerunnable derived labels for rounds and player situational roles. This is the infrastructure that makes tactical analytics possible without hardcoding labels into the schema.
2. **Fix team hierarchy** — currently teams like "Navi Junior" (academy) are aliased to "Navi" (parent) rather than being properly linked as a child org. `parent_team_id` from `0004` enables this, but a clean alias table for human-readable aliases is also needed.
3. **Add match event qualifiers** — LAN vs online, crowd presence and intensity. These are enrichable facts from HLTV/external sources that meaningfully affect player/team behavior analysis.

---

## Goal 1: Classification Pipeline

### Why this should come before damage/utility events

Raw events (kills, damage, utility) are cheap to add later — they're observations.
**Classification is the expensive part to redesign once you've built on top of it.**

Currently you have no place to store:
- "this round was a full-buy eco-round"
- "player X was used as a CT B-anchor on Mirage"
- "this match was a low-intensity scrim"

Adding those as columns to `rounds` or `matches` creates a mess.
A proper classification pipeline solves this: every label is versioned, sourced, and rerunnable.

### Core design principle

**Classifier outputs are not ground truth — they are derived artifacts.**

Each classifier has:
- A name (e.g., `economy_classifier`, `round_archetype_classifier`)
- A semantic version (e.g., `v1.0.0`)
- A match it ran against
- A timestamp

Every classification label references a `classifier_run_id`. When you improve the classifier, you run it again with a new version and get new labels. Old classifications remain queryable for historical comparison.

---

## Proposed schema changes

### 1. `csda.classifier_runs`

Tracks every classifier execution. Every classification label in the system references one of these.

```sql
create table csda.classifier_runs (
    id bigserial primary key,
    classifier_name text not null,
    classifier_version text not null,
    match_id bigint not null references csda.matches(id) on delete cascade,
    ran_at timestamptz not null default now(),
    metadata jsonb,
    constraint classifier_runs_name_version_unique unique (classifier_name, classifier_version)
);
```

Notes:
- `(classifier_name, classifier_version)` is unique — prevents duplicate runs of the same classifier version
- `metadata` can carry inputs used, confidence thresholds, or diagnostic info
- `match_id` scope — classifiers run per match (not per round)

---

### 2. `csda.round_classifications`

Per-round labels from a classifier run.

```sql
create table csda.round_classifications (
    id bigserial primary key,
    classifier_run_id bigint not null references csda.classifier_runs(id) on delete cascade,
    round_id bigint not null references csda.rounds(id) on delete cascade,
    label_name text not null,
    label_value text not null,
    confidence numeric(4,3),
    notes text,
    metadata jsonb,
    constraint round_classifications_run_round_label_unique
        unique (classifier_run_id, round_id, label_name)
);
```

Notes:
- `(classifier_run_id, round_id, label_name)` is unique — a classifier run can only assign one value per label per round
- `label_name` is the classifier's output key (e.g., `buy_type`, `archetype`)
- `label_value` is the value (e.g., `full`, `eco`, `exec_a`)
- Examples of label names this table can hold:
  - `buy_type` → `full` / `force` / `half` / `eco`
  - `archetype` → `default` / `exec` / `contact` / `split` / `fake` / `late_hit` / `retake` / `save`
  - `ct_strategy` → `aggressive` / `passive` / `rotator` / `anchor`
  - `t_strategy` → `rush` / `default` / `delayed` / `lurk_heavy`

---

### 3. `csda.player_situation_roles`

This is the key table for your insight: **role is a function of (player, lineup, map, side), not a static player property**.

```sql
create table csda.player_situation_roles (
    id bigserial primary key,
    classifier_run_id bigint not null references csda.classifier_runs(id) on delete cascade,
    player_id bigint not null references csda.players(id) on delete cascade,
    lineup_id bigint references csda.lineups(id) on delete set null,
    map_name text not null,
    side text not null,
    role_code text not null,
    confidence numeric(4,3),
    notes text,
    metadata jsonb,
    constraint player_situation_roles_run_player_map_side_label_unique
        unique (classifier_run_id, player_id, map_name, side, role_code),
    constraint player_situation_roles_side_check check (side in ('t', 'ct'))
);
```

Notes:
- `map_name` + `side` + `role_code` is the full role context
- `lineup_id` links to the specific lineup the player was in (nullable — classifier may not always have it)
- `role_code` is freeform but should follow a controlled vocabulary in practice (e.g., `ct_b_anchor`, `t_lurk`, `entry`, `igl`, `awp`)
- Examples of what this can express:
  - `player=Navi_s1mple, map=mirage, side=ct, role_code=ct_b_anchor`
  - `player=Navi_s1mple, map=ancient, side=t, role_code=t_lurk`
  - `player=Navi_b1t, map=mirage, side=ct, role_code=entry`
- Role can vary by map and side — same player, different contexts get different rows

---

### 4. `csda.match_classifications`

Broader match-level classification labels.

```sql
create table csda.match_classifications (
    id bigserial primary key,
    classifier_run_id bigint not null references csda.classifier_runs(id) on delete cascade,
    match_id bigint not null references csda.matches(id) on delete cascade,
    label_name text not null,
    label_value text not null,
    confidence numeric(4,3),
    notes text,
    metadata jsonb,
    constraint match_classifications_run_label_unique
        unique (classifier_run_id, match_id, label_name)
);
```

Examples:
- `archetype` → `clutch_heavy` / `A_site_heavy` / `economy_led` / `low_intensity`
- `dominant_side` → `ct` / `t` / `balanced`
- `pace` → `slow` / `fast` / `adaptive`

---

## Goal 3: Match Event Qualifiers

### Why these belong in the schema

LAN vs online meaningfully affects player behavior — timing consistency, communication pressure, clutch performance under crowd noise. Crowd intensity affects timeout strategy and player comfort. These are observable facts from HLTV/event data, not opinions.

Currently `match_contexts` has `event_name` but no way to store network type or crowd context.

### Proposed table: `csda.match_event_qualifiers`

```sql
create table csda.match_event_qualifiers (
    id bigserial primary key,
    match_id bigint not null unique references csda.matches(id) on delete cascade,
    network_type text not null default 'unknown',
    crowd_level text not null default 'unknown',
    crowd_consistency text not null default 'unknown',
    crowd_notes text,
    source text not null default 'unknown',
    confidence numeric(4,3),
    metadata jsonb,
    created_at timestamptz not null default now(),
    constraint match_event_qualifiers_network_type_check check (
        network_type in ('lan', 'online', 'unknown')
    ),
    constraint match_event_qualifiers_crowd_level_check check (
        crowd_level in ('none', 'quiet', 'normal', 'loud', 'extreme', 'unknown')
    ),
    constraint match_event_qualifiers_crowd_consistency_check check (
        crowd_consistency in ('none', 'constant', 'intermittent', 'late_round', 'unknown')
    ),
    constraint match_event_qualifiers_source_check check (
        source in ('hltv', 'faceit', 'parser', 'manual', 'heuristic', 'unknown')
    ),
    constraint match_event_qualifiers_confidence_range check (
        confidence is null or (confidence >= 0 and confidence <= 1)
    )
);
```

Notes:
- `network_type`: `lan` = on-site servers, `online` = remote, `unknown` = undetermined
- `crowd_level`: `none` (empty arena), `quiet` (sparse), `normal` (typical event noise), `loud` (major crowd), `extreme` (record-breaking noise levels)
- `crowd_consistency`: `none` (no crowd), `constant` (consistent throughout), `intermittent` (episodic cheers), `late_round` (mostly late-round clutch moments)
- `source`: where this qualifier came from — HLTV has `lan` flags for big events, some crowd data is manually noted
- `crowd_notes`: freeform notes for edge cases (e.g., "crowd died after pistol round", "technical issues caused silence")
- `1:1 with matches` — every match can have at most one qualifier row
- Enrichable from HLTV (`lan` flag), event metadata, or manual review

---

## Goal 2: Team Hierarchy Cleanup

### The problem

`0004` added `team_type` (`main` / `academy` / `mixed`) and `parent_team_id` on `teams`, which enables hierarchy. But in practice:

- Academy teams (e.g., "Navi Junior") are being aliased to the parent team (e.g., "Navi") via `team_aliases` instead of being properly linked as a child org
- There's no explicit way to say "Team X is the academy/reserve of Team Y"
- The alias table conflates two very different concepts: **display aliases** (how the same team is spelled across demos) and **org relationships** (academy, mixed roster, sister team)

### Proposed changes

#### A. Add `parent_team_id` to `team_aliases`

When `alias_normalized` points to a different team entity, `team_aliases` can also express the parent-child org relationship.

```sql
alter table csda.team_aliases
    add column team_type text,
    add column is_org_relationship boolean not null default false;
```

- `is_org_relationship = true` when this alias represents an organizational hierarchy link (academy, sister team, etc.), not just a name variant
- `team_type` in this context records the child team's type in the relationship (e.g., `academy`)

This is a minimal change — existing aliases work unchanged, new ones can express hierarchy.

#### B. Add `parent_team_id` to `match_teams`

Currently `match_teams` links to `teams` for org identity, but doesn't express the lineup's parent org. When an academy team plays, you'd want to know both "who played" and "who they belong to org-wise."

```sql
alter table csda.match_teams
    add column parent_team_id bigint references csda.teams(id) on delete set null;
```

This lets you query: "show me Navi academy matches played against Navi main" without confusing them as the same team.

---

## Summary of changes

### New tables
- `csda.classifier_runs`
- `csda.round_classifications`
- `csda.player_situation_roles`
- `csda.match_classifications`
- `csda.match_event_qualifiers`

### New fields
- `team_aliases.team_type`
- `team_aliases.is_org_relationship`
- `match_teams.parent_team_id`

### Enums / check constraints

`side` in `player_situation_roles`: `t`, `ct`
`network_type` in `match_event_qualifiers`: `lan`, `online`, `unknown`
`crowd_level`: `none`, `quiet`, `normal`, `loud`, `extreme`, `unknown`
`crowd_consistency`: `none`, `constant`, `intermittent`, `late_round`, `unknown`
`source`: `hltv`, `faceit`, `parser`, `manual`, `heuristic`, `unknown`

---

## Rust-side changes needed

### `csda-core` model additions
- New structs for classifier run output records
- No new enums hardcoded — `label_name` / `label_value` are freeform text (controlled vocabularies enforced in classifier code, not schema)

### `csda-storage` additions
- `ClassifierRunRecord` and classification record types in `bundle.rs`
- `IngestBundle` gains optional `classifier_runs` and classification fields
- `PostgresStorage` gains `upsert_classifier_run` and classification ingest methods

### `csda-parser-source2` additions
- Observer gains economy/damage event handlers (for future `buy_type` classification)
- No new events needed for this migration — the classification pipeline is ingest-agnostic

---

## What this unlocks

### Immediately queryable after classifier v1 runs:
- "Which rounds were full-buy vs eco based on opening damage and money?"
- "Show me all rounds where Player X played CT B site on Mirage"
- "Which players had different role codes on Ancient vs Mirage in the same lineup?"
- "What's the dominant round archetype per map for Team X?"

### Match event qualifier queries:
- "Compare Player X's clutch win rate on LAN vs online"
- "How does Team Y's communication pressure differ in loud vs quiet crowd environments?"
- "Filter for LAN-only tournaments when assessing T-side execute timings"

### Team hierarchy queries:
- "Show me Navi academy matches played against Navi main"
- "Compare academy vs main roster performance on the same maps"
- "Track roster moves across main/academy lineups over time"

### Future work (not this migration):
- Damage events table
- Utility events table
- Position snapshots
- Classifier: `smoke_utility_classifier`, `clutch_classifier`

---

## Proposed migration order within 0005

1. Add `classifier_runs` table
2. Add `round_classifications` table
3. Add `player_situation_roles` table
4. Add `match_classifications` table
5. Add `match_event_qualifiers` table
6. Add `parent_team_id` to `match_teams`
7. Add `team_type` + `is_org_relationship` to `team_aliases`
8. Add indexes for common query patterns

No backfill needed for classification tables — they are populated by classifiers running over existing (or new) matches. `parent_team_id` on `match_teams` and `match_event_qualifiers` start null — enriched from HLTV or manual review.

---

## Classifier naming convention

Recommended classifier names for future implementations:

```
economy_classifier          — buy type per round
round_archetype_classifier  — tactical type per round
player_role_classifier      — situational role per player per (map, side)
match_archetype_classifier  — overall match character
smoke_utility_classifier    — utility execution quality
clutch_classifier           — clutch situation detection
```

Each classifier should version semantically (`v1.0.0`, `v1.1.0`, `v2.0.0`) so results can be compared across versions.
