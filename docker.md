# Docker Development Setup

This project includes a local Docker Compose setup for the first Postgres-backed database iteration.

## Files

- `compose.yml`
- `.env.example`

## What it provides

### `postgres`
A local Postgres database for development and testing.

### `adminer`
An optional database UI for inspection.
It is behind the `tools` profile so it does not start unless you ask for it.

## Quick start

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Start Postgres:

```bash
docker compose up -d postgres
```

3. Apply migrations:

```bash
cargo run -p csda-cli -- db migrate
```

4. Ingest sample data:

```bash
cargo run -p csda-cli -- db sample-ingest
```

## Optional: start Adminer

```bash
docker compose --profile tools up -d adminer
```

Then open:

- `http://localhost:8080`

Suggested login values:

- system: `PostgreSQL`
- server: `postgres` when connecting from inside Docker tooling, or `host.docker.internal` / `localhost` depending on your setup
- username: value from `POSTGRES_USER`
- password: value from `POSTGRES_PASSWORD`
- database: value from `POSTGRES_DB`

## Notes

- The Compose setup creates the database server only.
- Migrations are applied by `csda-cli` through `db migrate`.
- This keeps the migration flow aligned with the Rust storage layer instead of splitting schema ownership between Docker init scripts and application code.
- The CLI auto-loads `.env` via `dotenvy`, so `DATABASE_URL` can live in that file for local development.

## Resetting the local database

To remove the database and start fresh:

```bash
docker compose down -v
```

Then repeat the quick start steps.
