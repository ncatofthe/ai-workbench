"""CLI interface for AI Workbench using Typer."""

from __future__ import annotations

import typer
import uvicorn

app = typer.Typer(name="workbench", help="AI Workbench CLI")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(True, help="Auto-reload on changes"),
):
    """Start the AI Workbench backend server."""
    typer.echo(f"Starting AI Workbench on {host}:{port}")
    uvicorn.run("src.main:app", host=host, port=port, reload=reload)


@app.command()
def init():
    """Initialize the database and default config."""
    from src.storage.database import init_db
    from src.utils.config import load_config
    load_config()
    init_db()
    typer.echo("Database initialized. Config loaded.")


@app.command()
def check():
    """Check environment status."""
    import shutil
    import subprocess

    checks = {
        "Python": shutil.which("python3"),
        "Node": shutil.which("node"),
        "npm": shutil.which("npm"),
        "Ollama": shutil.which("ollama"),
        "Codex": shutil.which("codex"),
        "Claude": shutil.which("claude"),
    }

    for name, path in checks.items():
        status = f"found at {path}" if path else "NOT FOUND"
        typer.echo(f"  {name}: {status}")


if __name__ == "__main__":
    app()
