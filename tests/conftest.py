import hashlib
import json
from pathlib import Path

import pytest
from agent.research.models import Evidence, Finding, ResearchState, ResearchStep, StepReport

from frontier.assessment import Assessment
from frontier.manifest import prepare_assessment
from frontier.validators import CRITERIA, frontier_validators


def evidence(obj, snapshot_root):
    text = json.dumps(obj, sort_keys=True)
    digest = hashlib.sha256(text.encode()).hexdigest()
    snapshot = f"evidence/{digest}.txt"
    snapshot_file = Path(snapshot_root) / snapshot
    snapshot_file.parent.mkdir(parents=True, exist_ok=True)
    snapshot_file.write_text(text, encoding="utf-8")
    return Evidence(
        id=f"e-{digest}",
        source_path=f"evidence/{obj['phase']}-{digest}.json",
        snapshot_path=snapshot,
        sha256=digest,
        text=text,
    )


def make_chain(
    manifest,
    *,
    finding="finding-1",
    patch="patch-1",
    revision="after-1",
    regression_outcome="passed",
):
    snapshot_root = Path(manifest.target) / ".mcts-research" / "test-run"
    common = dict(
        schema_version=2,
        assessment_id=manifest.assessment_id,
        finding_id=finding,
        reproduction_id="security-test-1",
        prohibited_state=manifest.prohibited_states[0],
        protocol="pytest_assertion",
        reproduction_sha256="a" * 64,
    )
    baseline = evidence(
        dict(
            common,
            phase="baseline",
            command="pytest tests/security.py",
            exit_code=1,
            outcome="reproduced",
            workspace_revision="before",
        ),
        snapshot_root,
    )
    links = dict(baseline_sha256=baseline.sha256, baseline_revision="before", patch_id=patch)
    post = evidence(
        dict(
            common,
            **links,
            phase="post_patch",
            command="pytest tests/security.py",
            exit_code=0,
            outcome="not_reproduced",
            workspace_revision=revision,
        ),
        snapshot_root,
    )
    regression = evidence(
        dict(
            common,
            **links,
            phase="regression",
            command="pytest tests/existing",
            exit_code=0 if regression_outcome == "passed" else 1,
            outcome=regression_outcome,
            workspace_revision=revision,
            post_patch_sha256=post.sha256,
        ),
        snapshot_root,
    )
    return [baseline, post, regression]


def make_step(manifest, brief, chain, *, answer=True, number=1):
    obj = json.loads(chain[1].text)
    summary = (
        json.dumps(
            {
                k: obj[k]
                for k in (
                    "assessment_id",
                    "finding_id",
                    "reproduction_id",
                    "patch_id",
                    "workspace_revision",
                )
            }
        )
        if answer
        else None
    )
    findings, validations = [], []
    adapters = frontier_validators(manifest)
    for index, (key, (name, _)) in enumerate(CRITERIA.items()):
        supplied = chain[: index + 1]
        finding = Finding(
            criterion_id=key,
            claim="synthetic declared observation",
            evidence_ids=[e.id for e in supplied],
        )
        criterion = next(c for c in brief.criteria if c.id == key)
        findings.append(finding)
        validations.append(adapters[name].validate(criterion, finding, supplied, answer=summary))
    return ResearchStep(
        number=number,
        action="Synthetic integration fixture",
        execution_success=True,
        report=StepReport(summary="fixture", findings=findings, answer=summary),
        validations=validations,
    )


@pytest.fixture
def case(tmp_path):
    manifest, brief = prepare_assessment(Assessment(str(tmp_path), ["source"], ["cross-user read"]))
    chain = make_chain(manifest)
    step = make_step(manifest, brief, chain)
    state = ResearchState(
        run_id="test-run",
        query="security assessment",
        workspace=str(tmp_path),
        brief=brief,
        run_directory=str(Path(tmp_path) / ".mcts-research" / "test-run"),
        evidence=chain,
        steps=[step],
        status="candidate_ready",
        answer=step.report.answer,
    )
    return manifest, state, chain
