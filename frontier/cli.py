"""Small CLI entry point for preparing and running an AppSec research assessment."""

import json
from pathlib import Path

import typer

from agent.config import load_config
from agent.research.runner import run_research

from .assessment import Assessment, assessment_brief
from .report import assessment_result
from .validators import frontier_validators

app = typer.Typer(help="Run a Frontier repository security assurance assessment.")


@app.command()
def assess(
    target: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    max_steps: int = typer.Option(12, min=1),
    resume: Path | None = typer.Option(None, exists=True),
    scope: list[str] = typer.Option(["application source", "local test environment"]),
    prohibited_state: list[str] = typer.Option(["unauthorized access", "unsafe data access"]),
) -> None:
    """Investigate a local repository using mcts-agent; Codex performs execution."""
    assessment = Assessment(str(target.resolve()), scope, prohibited_state)
    state, run_dir = run_research(
        None if resume else (
            "Determine whether this application can reach any defined prohibited security state "
            "from the permitted starting state. Produce reproducible evidence for each claimed "
            "transition, remediate verified paths, and re-evaluate them."
        ),
        workspace=None if resume else str(target.resolve()),
        resume=str(resume) if resume else None,
        config=None if resume else load_config(),
        brief=None if resume else assessment_brief(assessment),
        validators=frontier_validators(),
        max_steps=max_steps,
    )
    payload = assessment_result(state, run_dir.name, str(target.resolve()))
    payload["prohibited_states"] = prohibited_state
    output = run_dir / "assessment.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(json.dumps({"status": state.status, "run_directory": str(run_dir), "report": str(output)}))


if __name__ == "__main__":
    app()
