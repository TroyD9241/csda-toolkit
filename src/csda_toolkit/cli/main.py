"""CLI entry point for csda-toolkit.

Usage:
    csda db init
    csda db migrate
    csda ingest path/to/demo.dem
"""

import logging
import os
import sys

import click

from csda_toolkit.db.database import Database
from csda_toolkit.ingest.bundle import IngestBundle

logger = logging.getLogger(__name__)


@click.group()
@click.option("--db-url", envvar="DATABASE_URL", help="Postgres connection URL")
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Enable debug logging"
)
@click.pass_context
def cli(ctx: click.Context, db_url: str | None, verbose: bool) -> None:
    """CS2 Demo Analysis Toolkit."""
    ctx.ensure_object(dict)

    # Logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Resolve DB URL
    resolved_url = db_url or os.environ.get("DATABASE_URL")
    if not resolved_url:
        resolved_url = "postgresql://postgres:postgres@localhost:5432/csda"
    ctx.obj["DATABASE_URL"] = resolved_url


@cli.group()
def db() -> None:
    """Database management commands."""


@db.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Create the csda schema and all tables."""
    db_url = ctx.obj["DATABASE_URL"]
    database = Database(db_url)
    database.create_schema()
    from csda_toolkit.db.models import Base
    Base.metadata.create_all(database.engine)
    click.echo("✓ Schema 'csda' and all tables created.")


@db.command()
@click.pass_context
def migrate(ctx: click.Context) -> None:
    """Run Alembic migrations."""
    db_url = ctx.obj["DATABASE_URL"]
    os.environ["DATABASE_URL"] = db_url

    from alembic.config import CommandLine
    from alembic.config import Config as AlembicConfig

    alembic_cfg = AlembicConfig("alembic.ini")
    CommandLine().run_cmd(alembic_cfg, ["upgrade", "head"])
    click.echo("✓ Alembic migrations complete.")


@cli.command()
@click.argument("demo_path", type=click.Path(exists=True))
@click.pass_context
def ingest(ctx: click.Context, demo_path: str) -> None:
    """Ingest a .dem file into the database."""
    db_url = ctx.obj["DATABASE_URL"]
    database = Database(db_url)

    click.echo(f"⏳ Ingesting {demo_path}...")
    try:
        bundle = IngestBundle(database, demo_path)
        result = bundle.run()
        click.echo(
            f"✓ Ingest complete: match_id={result.match_id}, "
            f"{result.players_created} players, "
            f"{result.rounds_created} rounds, "
            f"{result.kills_created} kills, "
            f"{result.teams_created} teams"
        )
    except Exception as e:
        click.echo(f"✗ Ingest failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
