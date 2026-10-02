"""EPISIGHT command line: `uv run episight --help` (run from apps/api)."""

from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
db_app = typer.Typer(no_args_is_help=True, help="Database schema commands.")
app.add_typer(db_app, name="db")

API_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = API_DIR.parents[1]
DEFAULT_DATASET = API_DIR / "tests" / "fixtures" / "dataset" / "v0-interim"
DEFAULT_POLICIES = API_DIR / "tests" / "fixtures" / "policies" / "pc-0-interim"


def _alembic_config(url: str | None = None):
    from alembic.config import Config

    from episight.config import get_settings

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url or get_settings().database_url)
    return cfg


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Apply all migrations."""
    from alembic import command

    command.upgrade(_alembic_config(), "head")
    typer.echo("database at head")


@db_app.command("reset")
def db_reset(yes: bool = typer.Option(False, "--yes", help="Confirm dropping all EPISIGHT tables.")) -> None:
    """Drop every table and re-apply migrations (destroys local data)."""
    if not yes:
        typer.confirm("Drop all EPISIGHT tables in the configured database?", abort=True)
    from alembic import command

    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    typer.echo("database reset to head")


@app.command()
def seed(
    dataset: Path = typer.Option(DEFAULT_DATASET, help="Dataset directory (Data Contract v1 §2)."),
    policies: Path | None = typer.Option(DEFAULT_POLICIES, help="Policy corpus directory; omit with --no-policies."),
    no_policies: bool = typer.Option(False, "--no-policies"),
) -> None:
    """Validate a dataset, load it, and run screening. Replaces existing data."""
    from episight.db.session import make_session
    from episight.ingest.loader import IngestError, load_dataset, load_policies
    from episight.ingest.seed import seed as run_seed

    try:
        ds = load_dataset(dataset)
        corpus = None if no_policies or policies is None else load_policies(policies)
    except IngestError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc
    with make_session() as session:
        summary = run_seed(session, ds, corpus, str(dataset), str(policies) if corpus else None)
    typer.echo(f"dataset {summary.dataset_version} | corpus {summary.corpus_version or '-'}")
    typer.echo("  " + ", ".join(f"{k}={v}" for k, v in summary.counts.items()))
    typer.echo(f"  screening flagged {summary.cases} case(s)")
    for issue in summary.data_quality_issues:
        typer.echo(f"  data-quality: {issue}")


@app.command("export-contract")
def export_contract(
    out: Path = typer.Option(REPO_ROOT / "packages" / "shared-types", help="shared-types package directory."),
    dataset: Path = typer.Option(DEFAULT_DATASET),
    policies: Path = typer.Option(DEFAULT_POLICIES),
) -> None:
    """Write openapi.json, TS aliases and deterministic mock fixtures (real engine output) for the frontend."""
    from episight.devtools.contract_export import export

    written = export(out, dataset, policies)
    typer.echo(f"wrote {len(written)} files under {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    app()
