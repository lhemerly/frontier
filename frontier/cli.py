"""Run a repository assessment or resume its saved, bound manifest."""

import json
from dataclasses import replace
from pathlib import Path

import typer
from agent.config import load_config
from agent.research.models import ResearchState
from agent.research.runner import run_research

from .assessment import Assessment
from .manifest import AssessmentManifest, manifest_from_state, prepare_assessment
from .report import assessment_result
from .validators import frontier_validators

app = typer.Typer(help="Run a Frontier repository security assurance assessment.")
SUPPORTED_CONNECTORS = {"codex", "opencode"}


def manifest_path(manifest: AssessmentManifest) -> Path:
    return Path(manifest.target) / ".frontier" / manifest.assessment_id / "manifest.json"


def read_saved_manifest(manifest: AssessmentManifest) -> None:
    saved = AssessmentManifest.model_validate_json(manifest_path(manifest).read_text())
    if saved != manifest:
        raise ValueError("Saved manifest was changed; refusing to relabel the assessment")


def run_assessment(
    *,
    target: Path | None = None,
    resume: Path | None = None,
    scope: list[str] | None = None,
    prohibited_states: list[str] | None = None,
    max_steps: int = 12,
    connector: str | None = None,
    model: str | None = None,
):
    if resume is not None:
        if target is not None or scope is not None or prohibited_states is not None:
            raise ValueError(
                "Resume uses saved metadata; omit target, --scope and --prohibited-state"
            )
        if connector is not None or model is not None:
            raise ValueError("Resume uses the saved connector and model; omit --connector and --model")
        checkpoint = resume / "checkpoint.json" if resume.is_dir() else resume
        before = ResearchState.model_validate_json(checkpoint.read_text())
        manifest = manifest_from_state(before)
        read_saved_manifest(manifest)
        kwargs = {"resume": str(checkpoint.resolve())}
    else:
        if target is None or not target.is_dir():
            raise ValueError("A new assessment requires an existing target directory")
        selected_connector = (connector or "codex").strip().lower()
        if selected_connector not in SUPPORTED_CONNECTORS:
            raise ValueError(
                f"Unknown connector '{selected_connector}'. Choose one of: "
                f"{', '.join(sorted(SUPPORTED_CONNECTORS))}"
            )
        assessment = Assessment(
            str(target.resolve()),
            scope if scope is not None else ["application source", "local test environment"],
            prohibited_states
            if prohibited_states is not None
            else ["unauthorized access", "unsafe data access"],
        )
        manifest, brief = prepare_assessment(assessment)
        path = manifest_path(manifest)
        path.parent.mkdir(parents=True, exist_ok=False)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(manifest.model_dump_json(indent=2))
        config = replace(load_config(), executor_provider=selected_connector)
        if model is not None:
            config = replace(config, executor_model=model)
        kwargs = {
            "query": "Determine whether defined prohibited states are reachable within scope. "
            "Reproduce a verified path, remediate it, and re-evaluate it. Report uncertainty "
            "when evidence is absent; do not invent a vulnerability to satisfy criteria.",
            "workspace": manifest.target,
            "config": config,
            "brief": brief,
        }
    state, run_dir = run_research(
        **kwargs, validators=frontier_validators(manifest), max_steps=max_steps
    )
    if manifest_from_state(state) != manifest:
        raise ValueError("Research returned a different assessment manifest")
    read_saved_manifest(manifest)
    payload = assessment_result(state)
    output = run_dir / "assessment.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output)
    return state, run_dir, output


@app.command()
def assess(
    target: Path | None = typer.Argument(None, exists=True, file_okay=False, dir_okay=True),
    max_steps: int = typer.Option(12, min=1),
    resume: Path | None = typer.Option(None, exists=True),
    scope: list[str] | None = typer.Option(None),
    prohibited_state: list[str] | None = typer.Option(None),
    connector: str | None = typer.Option(
        None, help="Executor connector for new assessments: codex (default) or opencode."
    ),
    model: str | None = typer.Option(
        None, help="Optional model override in the connector's native format."
    ),
) -> None:
    """Run with TARGET, or resume using --resume CHECKPOINT without new metadata."""
    try:
        state, run_dir, output = run_assessment(
            target=target,
            resume=resume,
            scope=scope,
            prohibited_states=prohibited_state,
            max_steps=max_steps,
            connector=connector,
            model=model,
        )
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps({"status": state.status, "run_directory": str(run_dir), "report": str(output)})
    )


if __name__ == "__main__":
    app()
