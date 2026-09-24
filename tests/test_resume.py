import json

import pytest
from agent.research.runner import run_research
from conftest import make_chain, make_step
from typer.testing import CliRunner

from frontier.cli import app, manifest_path, run_assessment
from frontier.manifest import manifest_from_state


class FixtureHarness:
    """Writes synthetic declarations to exercise real snapshot and resume machinery."""

    def perform(self, state, action, output, kind):
        manifest = manifest_from_state(state)
        chain = make_chain(manifest)
        step = make_step(manifest, state.brief, chain, answer=bool(state.steps))
        if not state.steps:
            step.report.findings = step.report.findings[:1]
        for item in chain:
            # Target always comes from the real research state.
            from pathlib import Path

            path = Path(state.workspace) / item.source_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item.text)
        for finding in step.report.findings:
            finding.evidence_paths = [e.source_path for e in chain if e.id in finding.evidence_ids]
            finding.evidence_ids = []
        output.write_text(step.report.model_dump_json())
        return {"success": True, "returncode": 0}


@pytest.fixture
def real_runner(monkeypatch):
    def injected(**kwargs):
        return run_research(
            **kwargs,
            harness=FixtureHarness(),
            selector=lambda state: ("Synthetic evidence fixture", None),
        )

    monkeypatch.setattr("frontier.cli.run_research", injected)


def test_real_runner_roundtrip_preserves_manifest_and_closes(real_runner, tmp_path):
    first, run_dir, report = run_assessment(
        target=tmp_path, scope=["only source"], prohibited_states=["cross-user read"], max_steps=1
    )
    saved = manifest_from_state(first)
    assert first.agent_config["executor_provider"] == "codex"
    assert first.status == "budget_exhausted"
    assert json.loads(report.read_text())["stage"] == "confirmed"
    second, _, report = run_assessment(resume=run_dir / "checkpoint.json", max_steps=1)
    assert manifest_from_state(second) == saved
    assert second.status == "candidate_ready"
    payload = json.loads(report.read_text())
    assert payload["target"] == str(tmp_path)
    assert payload["scope"] == ["only source"]
    assert payload["prohibited_states"] == ["cross-user read"]
    assert payload["stage"] == "closed"
    assert len(payload["evidence_chain"]) == 3


@pytest.mark.parametrize("override", ["target", "scope", "prohibited_states"])
def test_resume_rejects_new_metadata_before_execution(real_runner, tmp_path, monkeypatch, override):
    _, run_dir, _ = run_assessment(target=tmp_path, max_steps=1)
    monkeypatch.setattr(
        "frontier.cli.run_research", lambda **kwargs: pytest.fail("must not execute")
    )
    value = tmp_path if override == "target" else ["replacement"]
    with pytest.raises(ValueError, match="saved metadata"):
        run_assessment(resume=run_dir, **{override: value})


@pytest.mark.parametrize("mutation", ["manifest", "brief", "workspace", "legacy"])
def test_resume_rejects_tampering_before_execution(real_runner, tmp_path, monkeypatch, mutation):
    state, run_dir, _ = run_assessment(target=tmp_path, max_steps=1)
    checkpoint = run_dir / "checkpoint.json"
    manifest = manifest_from_state(state)
    if mutation == "manifest":
        saved = json.loads(manifest_path(manifest).read_text())
        saved["prohibited_states"] = ["replacement"]
        manifest_path(manifest).write_text(json.dumps(saved))
    else:
        saved = json.loads(checkpoint.read_text())
        if mutation == "brief":
            saved["brief"]["criteria"][0]["required"] = False
        elif mutation == "workspace":
            saved["workspace"] = str(tmp_path / "another")
        else:
            saved["brief"]["assumptions"] = []
        checkpoint.write_text(json.dumps(saved))
    monkeypatch.setattr(
        "frontier.cli.run_research", lambda **kwargs: pytest.fail("must not execute")
    )
    with pytest.raises(ValueError):
        run_assessment(resume=checkpoint)


def test_cli_resume_needs_no_target_and_reports_saved_scope(real_runner, tmp_path):
    _, run_dir, _ = run_assessment(target=tmp_path, max_steps=1)
    result = CliRunner().invoke(app, ["--resume", str(run_dir), "--max-steps", "1"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "candidate_ready"


def test_cli_resume_rejects_even_explicit_default_scope(real_runner, tmp_path):
    _, run_dir, _ = run_assessment(target=tmp_path, max_steps=1)
    result = CliRunner().invoke(app, ["--resume", str(run_dir), "--scope", "application source"])
    assert result.exit_code != 0
    assert "saved metadata" in result.output
