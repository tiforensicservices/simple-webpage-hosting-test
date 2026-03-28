"""src/cli.py — Gaitway CLI (Typer-based command-line interface).

Provides developer and operator commands for managing the Gaitway system.

Usage::

    python -m src.cli --help

    # Database management
    python -m src.cli init-db
    python -m src.cli db-status
    python -m src.cli db-downgrade

    # Scraper control
    python -m src.cli crawl-site zappos
    python -m src.cli crawl-all
    python -m src.cli list-sites

    # Crime scene search (CLI path)
    python -m src.cli crime-search ./path/to/impression.jpg --workspace-id 1

    # Infrastructure
    python -m src.cli check-health
    python -m src.cli setup-s3

Install as a script (after pip install -e .)::

    gaitway --help
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# Ensure project root is on sys.path when running as a script
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Rich console for colourful output
console = Console()

# ── Typer app ────────────────────────────────────────────────────────────────
app = typer.Typer(
    name="gaitway",
    help="Gaitway Footwear Intelligence Database — developer CLI",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

db_app = typer.Typer(help="Database management commands")
scraper_app = typer.Typer(help="Scraper control commands")

app.add_typer(db_app, name="db")
app.add_typer(scraper_app, name="scraper")


# ─────────────────────────────────────────────────────────────
# Database Commands
# ─────────────────────────────────────────────────────────────


@db_app.command("init")
def init_db(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Run Alembic migrations to bring the database to the latest revision.

    Equivalent to: ``alembic upgrade head``

    This command is safe to run multiple times — it only applies pending
    migrations.  Run this after pulling new code that includes new migration
    files.
    """
    if not yes:
        confirm = typer.confirm(
            "Apply all pending Alembic migrations? (alembic upgrade head)"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit()

    console.print("[cyan]🗄️  Running Alembic migrations...[/cyan]")
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        console.print("[green]✅ Migrations applied successfully.[/green]")
    except Exception as exc:
        console.print(f"[red]❌ Migration failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@db_app.command("status")
def db_status():
    """Show current Alembic revision and any pending migrations."""
    console.print("[cyan]📋 Checking database migration status...[/cyan]")
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from src.db.connection import get_engine

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        engine = get_engine()

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()

        head_rev = script.get_current_head()
        is_current = current_rev == head_rev

        table = Table(title="Alembic Migration Status")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Current revision", current_rev or "(none — not migrated)")
        table.add_row("Head revision", head_rev or "(no migrations found)")
        table.add_row(
            "Up to date",
            "[green]✅ Yes[/green]" if is_current else "[yellow]⚠️  No[/yellow]",
        )
        console.print(table)

        if not is_current:
            console.print(
                "[yellow]Run [bold]gaitway db init[/bold] to apply pending migrations.[/yellow]"
            )
    except Exception as exc:
        console.print(f"[red]❌ Could not check DB status: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@db_app.command("downgrade")
def db_downgrade(
    revision: str = typer.Argument("-1", help="Target revision (e.g. -1, base, abc123)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Roll back the database to a previous Alembic revision.

    Examples::

        gaitway db downgrade -1        # roll back one step
        gaitway db downgrade base      # roll back to empty DB
        gaitway db downgrade abc123    # roll back to specific revision
    """
    if not yes:
        confirm = typer.confirm(
            f"Roll back database to revision {revision!r}? This may destroy data."
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit()

    console.print(f"[yellow]⬇️  Rolling back to revision {revision!r}...[/yellow]")
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.downgrade(alembic_cfg, revision)
        console.print(f"[green]✅ Rolled back to {revision!r}.[/green]")
    except Exception as exc:
        console.print(f"[red]❌ Downgrade failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


# ─────────────────────────────────────────────────────────────
# Scraper Commands
# ─────────────────────────────────────────────────────────────


@scraper_app.command("crawl")
def crawl_site(
    site: str = typer.Argument(..., help="Site to crawl (e.g. zappos)"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", "-p", help="Max pages to crawl"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scrape but don't persist to DB"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed scraper output"),
):
    """Trigger a scrape job for a specific retailer site.

    Runs the scraper synchronously in the foreground.  For production,
    use the EventBridge scheduler or the API endpoint POST /api/v1/admin/scraper/trigger.

    Examples::

        gaitway scraper crawl zappos
        gaitway scraper crawl zappos --max-pages 5 --dry-run
    """
    supported = ["zappos"]
    if site.lower() not in supported:
        console.print(
            f"[red]❌ Site {site!r} not supported. Supported: {supported}[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[cyan]🕷️  Starting scrape: {site} (max_pages={max_pages}, dry_run={dry_run})[/cyan]")

    try:
        from src.scraper.zappos import ZapposScraper

        scraper = ZapposScraper()
        urls = scraper.get_catalog_urls(max_pages=max_pages or 1)
        console.print(f"   Found {len(urls)} product URLs")

        scraped = 0
        for url in urls[:5]:  # Preview first 5 in Phase 1
            result = scraper.scrape_product(url)
            if result:
                scraped += 1
                if verbose:
                    console.print(f"   ✓ {result.brand} {result.model_name}")

        console.print(
            f"[green]✅ Scraped {scraped} products from {site}. "
            f"(DB persist: {'disabled — dry run' if dry_run else 'Phase 6'})[/green]"
        )
    except Exception as exc:
        console.print(f"[red]❌ Scrape failed: {exc}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1) from exc


@scraper_app.command("crawl-all")
def crawl_all(
    dry_run: bool = typer.Option(False, "--dry-run", help="Scrape but don't persist to DB"),
):
    """Trigger scrape jobs for all enabled sites in config/scrapers.yaml.

    Runs each scraper sequentially.  Phase 3 will parallelize via EventBridge.
    """
    import yaml

    config_path = _project_root / "config" / "scrapers.yaml"
    if not config_path.exists():
        console.print(f"[red]❌ config/scrapers.yaml not found at {config_path}[/red]")
        raise typer.Exit(code=1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    enabled_sites = [
        name
        for name, cfg in raw.get("scrapers", {}).items()
        if cfg.get("enabled", False)
    ]

    if not enabled_sites:
        console.print("[yellow]⚠️  No enabled scraper sites found in config/scrapers.yaml[/yellow]")
        raise typer.Exit()

    console.print(f"[cyan]🕷️  Crawling {len(enabled_sites)} enabled site(s): {enabled_sites}[/cyan]")
    for site in enabled_sites:
        console.print(f"\n[bold]── {site} ──[/bold]")
        try:
            crawl_site(site=site, max_pages=None, dry_run=dry_run, verbose=False)
        except SystemExit:
            console.print(f"[red]  ❌ {site} failed — continuing with next site[/red]")


@scraper_app.command("list-sites")
def list_sites():
    """List all configured scraper sites from config/scrapers.yaml."""
    import yaml

    config_path = _project_root / "config" / "scrapers.yaml"
    if not config_path.exists():
        console.print(f"[red]❌ config/scrapers.yaml not found[/red]")
        raise typer.Exit(code=1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    table = Table(title="Configured Scraper Sites")
    table.add_column("Site", style="cyan")
    table.add_column("Enabled", style="white")
    table.add_column("Rate (req/s)", style="white")
    table.add_column("Max Pages", style="white")
    table.add_column("Categories", style="white")

    for name, cfg in raw.get("scrapers", {}).items():
        table.add_row(
            name,
            "[green]✅[/green]" if cfg.get("enabled") else "[red]❌[/red]",
            str(cfg.get("rate_limit_per_second", "?")),
            str(cfg.get("max_pages", "?")),
            ", ".join(cfg.get("categories", [])) or "(all)",
        )

    console.print(table)


# ─────────────────────────────────────────────────────────────
# Crime Scene Search Command
# ─────────────────────────────────────────────────────────────


@app.command("crime-search")
def crime_search(
    image_path: Path = typer.Argument(..., help="Path to the crime scene impression image"),
    workspace_id: int = typer.Option(1, "--workspace-id", "-w", help="Workspace ID for audit log"),
    top_k: int = typer.Option(20, "--top-k", "-k", help="Number of top matches to return"),
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON"),
):
    """Run a crime scene footwear similarity search from the command line.

    Preprocesses the image, generates embeddings, and runs a pgvector
    cosine similarity search against the shoe database.

    Example::

        gaitway crime-search ./evidence/impression.jpg --workspace-id 3 --top-k 10
    """
    if not image_path.exists():
        console.print(f"[red]❌ Image not found: {image_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]🔍 Searching for matches to: {image_path.name}[/cyan]")
    console.print(f"   Workspace: {workspace_id} | Top-K: {top_k}")
    console.print()

    # TODO (Phase 5): wire up full crime scene search pipeline
    console.print(
        "[yellow]⚠️  Crime scene search pipeline not yet implemented.[/yellow]\n"
        "   Full pipeline available in Phase 5 (image preprocessing + pgvector search)."
    )
    raise typer.Exit(code=0)


# ─────────────────────────────────────────────────────────────
# Infrastructure Commands
# ─────────────────────────────────────────────────────────────


@app.command("check-health")
def check_health():
    """Check health of all Gaitway infrastructure components.

    Verifies:
      - Database connectivity (PostgreSQL + pgvector)
      - S3 bucket accessibility
      - Environment variable configuration
    """
    console.print("[bold cyan]🏥 Gaitway Health Check[/bold cyan]\n")

    checks_passed = 0
    checks_total = 3

    # ── 1. Config ──────────────────────────────────────────────────────────
    from src.config import get_config
    cfg = get_config()

    if cfg.aws_region and cfg.s3_bucket:
        console.print(f"[green]✅ Config[/green] — region={cfg.aws_region} bucket={cfg.s3_bucket}")
        checks_passed += 1
    else:
        missing = []
        if not cfg.aws_region:
            missing.append("AWS_DEFAULT_REGION")
        if not cfg.s3_bucket:
            missing.append("S3_BUCKET_NAME")
        console.print(f"[yellow]⚠️  Config[/yellow] — missing: {', '.join(missing)}")

    # ── 2. Database ────────────────────────────────────────────────────────
    try:
        from src.db.connection import ping_db
        if ping_db():
            console.print("[green]✅ Database[/green] — PostgreSQL connection OK")
            checks_passed += 1
        else:
            console.print("[red]❌ Database[/red] — connection failed (is Docker running?)")
    except Exception as exc:
        console.print(f"[red]❌ Database[/red] — {exc}")

    # ── 3. S3 ─────────────────────────────────────────────────────────────
    if cfg.s3_bucket:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=cfg.aws_region)
            s3.head_bucket(Bucket=cfg.s3_bucket)
            console.print(f"[green]✅ S3[/green] — bucket {cfg.s3_bucket!r} accessible")
            checks_passed += 1
        except Exception as exc:
            console.print(f"[red]❌ S3[/red] — {exc}")
    else:
        console.print("[yellow]⚠️  S3[/yellow] — S3_BUCKET_NAME not set")

    # ── Summary ────────────────────────────────────────────────────────────
    console.print()
    colour = "green" if checks_passed == checks_total else "yellow" if checks_passed > 0 else "red"
    console.print(
        f"[{colour}]{'✅' if checks_passed == checks_total else '⚠️ '} "
        f"{checks_passed}/{checks_total} checks passed[/{colour}]"
    )

    if checks_passed < checks_total:
        raise typer.Exit(code=1)


@app.command("setup-s3")
def setup_s3(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Run the S3 bucket setup script (creates bucket + folders + policies).

    Delegates to ``src.aws.setup_s3`` which creates the Gaitway S3 bucket
    with versioning, encryption, lifecycle policy, and the 6 key prefixes.
    """
    from src.config import get_config
    cfg = get_config()

    if not cfg.s3_bucket:
        console.print("[red]❌ S3_BUCKET_NAME not set in .env[/red]")
        raise typer.Exit(code=1)

    if not yes:
        confirm = typer.confirm(
            f"Set up S3 bucket {cfg.s3_bucket!r} in {cfg.aws_region}?"
        )
        if not confirm:
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit()

    console.print(f"[cyan]🪣  Setting up S3 bucket: {cfg.s3_bucket}[/cyan]")
    try:
        from src.aws.setup_s3 import main as setup_main
        setup_main()
        console.print("[green]✅ S3 setup complete.[/green]")
    except Exception as exc:
        console.print(f"[red]❌ S3 setup failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────


def main():
    """CLI entry point (used by setup.py / pyproject.toml scripts)."""
    app()


if __name__ == "__main__":
    main()
