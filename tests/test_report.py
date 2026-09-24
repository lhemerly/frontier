import pytest
from conftest import make_chain, make_step

from frontier.report import assessment_result


def test_current_complete_chain_closes_through_methodology(case):
    _, state, _ = case
    report = assessment_result(state)
    assert report["stage"] == "closed"
    assert report["history"] == [
        "discover",
        "validate",
        "confirmed",
        "remediate",
        "revalidate",
        "closed",
    ]
    assert report["result"] == "declared_remediated"
    assert report["verification"] == "declared_artifacts"


def test_unrelated_latest_verdicts_cannot_be_combined(case):
    manifest, state, _ = case
    steps, evidence = [], []
    for index in range(3):
        chain = make_chain(manifest, finding=f"finding-{index}")
        step = make_step(manifest, state.brief, chain, answer=False, number=index + 1)
        step.report.findings = [step.report.findings[index]]
        step.validations = [step.validations[index]]
        steps.append(step)
        evidence.extend(chain)
    state.steps, state.evidence = steps, evidence
    assert all(v.status == "supported" for v in state.latest_validations().values())
    assert assessment_result(state)["stage"] != "closed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "budget_exhausted"),
        ("status", "failed"),
        ("status", "blocked"),
        ("answer", "unrelated answer"),
        ("mock", True),
    ],
)
def test_nonfinal_or_mock_state_cannot_close(case, field, value):
    _, state, _ = case
    setattr(state, field, value)
    assert assessment_result(state)["stage"] != "closed"


def test_failed_execution_and_later_empty_step_revoke_previous_closure(case):
    _, state, _ = case
    state.steps[0].execution_success = False
    assert assessment_result(state)["stage"] != "closed"
    state.steps[0].execution_success = True
    newer = state.steps[0].model_copy(deep=True)
    newer.number = 2
    newer.validations, newer.report.findings = [], []
    state.steps.append(newer)
    assert assessment_result(state)["stage"] != "closed"


def test_regression_failure_has_regression_state(case):
    manifest, state, _ = case
    state.evidence = make_chain(manifest, regression_outcome="failed")
    state.steps = [make_step(manifest, state.brief, state.evidence)]
    assert assessment_result(state)["stage"] == "regression"


def test_same_step_mixed_patch_support_does_not_close(case):
    manifest, state, chain = case
    other = make_chain(manifest, patch="patch-other", revision="revision-other")
    other_step = make_step(manifest, state.brief, other, answer=False)
    state.steps[0].report.answer = None
    state.steps[0].report.findings[2] = other_step.report.findings[2]
    state.steps[0].validations[2] = other_step.validations[2]
    state.evidence = chain + other[1:]
    assert assessment_result(state)["stage"] != "closed"


def test_same_final_answer_cannot_hide_different_baseline_snapshot(case):
    import json
    from pathlib import Path

    from conftest import evidence

    manifest, state, chain = case
    b = json.loads(chain[0].text)
    b["workspace_revision"] = "another-baseline-revision"
    snapshot_root = Path(manifest.target) / ".mcts-research" / "test-run"
    baseline = evidence(b, snapshot_root)
    p = json.loads(chain[1].text)
    p.update(baseline_sha256=baseline.sha256, baseline_revision=b["workspace_revision"])
    post = evidence(p, snapshot_root)
    r = json.loads(chain[2].text)
    r.update(
        baseline_sha256=baseline.sha256,
        baseline_revision=b["workspace_revision"],
        post_patch_sha256=post.sha256,
    )
    other = [baseline, post, evidence(r, snapshot_root)]
    step = make_step(manifest, state.brief, other)
    # Every adapter supports its supplied evidence and the final answer is identical.
    assert step.report.answer == state.answer
    assert all(v.status == "supported" for v in step.validations)
    step.report.findings[0] = state.steps[0].report.findings[0]
    step.validations[0] = state.steps[0].validations[0]
    state.steps = [step]
    state.evidence = [*chain, *other]
    assert assessment_result(state)["stage"] != "closed"


def test_snapshot_mutated_after_runner_returns_cannot_support_closure(case):
    from pathlib import Path

    _, state, chain = case
    snapshot = Path(state.run_directory) / chain[0].snapshot_path
    snapshot.write_text("changed after capture", encoding="utf-8")
    report = assessment_result(state)
    assert report["stage"] == "inconclusive"
    assert report["evidence_chain"] == {}


def test_missing_snapshot_cannot_be_replaced_by_stored_supported_verdict(case):
    _, state, _ = case
    state.evidence = state.evidence[:1]
    assert assessment_result(state)["stage"] != "closed"
