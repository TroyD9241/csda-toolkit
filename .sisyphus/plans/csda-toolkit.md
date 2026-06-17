# CSDA Toolkit — Implementation Plan

## Status: ALL TASKS COMPLETE ✅

## TODOs
- [x] Create Alembic setup and initial migration
- [x] Build Python domain models (Match, Player, Round, Kill, Team, etc.)
- [x] Build DemoParser wrapper class with high-level API
- [x] Build IngestBundle pipeline: demoparser data → DB records
- [x] Build database session/connection management
- [x] Create CLI entry point for db migrate, ingest, etc.
- [x] Initialize Git repo and verify install

## Deliverables
- `src/csda_toolkit/db/models.py` — 25 SQLAlchemy 2.0 ORM models (csda schema)
- `src/csda_toolkit/db/database.py` — Database class, engine, session management
- `alembic.ini` + `alembic/env.py` + `alembic/script.py.mako` — Alembic migration env
- `alembic/versions/0001_initial_schema.py` — Combined migration from all 7 reference schemas
- `src/csda_toolkit/domain/models.py` — Domain dataclasses (Match, Player, Round, Kill, Team, economy models)
- `src/csda_toolkit/parsing/parser.py` — DemoParser wrapper wrapping demoparser2.DemoParser
- `src/csda_toolkit/ingest/bundle.py` — IngestBundle: parser → domain → DB pipeline
- `src/csda_toolkit/cli/main.py` — Click CLI (db init, db migrate, ingest)
- `pyproject.toml` — Editable install working
- `.env.example` — Database URL config template
- Git repo initialized with initial commit

## Files Changed/Verified
- All imports pass on Python 3.10.11
- `pip install -e .` succeeds
- 25 tables registered in Base.metadata under `csda` schema
