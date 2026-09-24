import json

import pytest
from conftest import evidence, make_chain, make_step

from frontier.validators import frontier_validators


def test_valid_chain_retains_all_links(case):
    _, state, chain = case
    assert [v.status for v in state.steps[0].validations] == ["supported"] * 3
    assert state.steps[0].validations[2].evidence_ids == [e.id for e in chain]


@pytest.mark.parametrize(
    "field,value",
    [
        ("patch_id", "unrelated"),
        ("workspace_revision", "wrong-revision"),
        ("finding_id", "another-finding"),
        ("baseline_sha256", "b" * 64),
        ("post_patch_sha256", "b" * 64),
        ("reproduction_sha256", "b" * 64),
        ("assessment_id", "another-assessment"),
        ("prohibited_state", "out of scope"),
        ("exit_code", 2),
        ("exit_code", True),
        ("schema_version", 1),
    ],
)
def test_regression_rejects_mixed_or_malformed_chain(case, field, value):
    manifest, state, chain = case
    from pathlib import Path

    obj = json.loads(chain[2].text)
    obj[field] = value
    changed = [
        *chain[:2],
        evidence(obj, Path(manifest.target) / ".mcts-research" / "test-run"),
    ]
    step = make_step(manifest, state.brief, changed)
    assert step.validations[2].status == "inconclusive"


def test_post_patch_rejects_changed_reproduction_command(case):
    manifest, state, chain = case
    from pathlib import Path

    obj = json.loads(chain[1].text)
    obj["command"] = "pytest another-test.py"
    changed = [
        chain[0],
        evidence(obj, Path(manifest.target) / ".mcts-research" / "test-run"),
        chain[2],
    ]
    assert make_step(manifest, state.brief, changed).validations[1].status == "inconclusive"


@pytest.mark.parametrize("mutation", ["truncated", "tampered", "duplicate"])
def test_invalid_snapshot_cannot_support_claim(case, mutation):
    manifest, state, chain = case
    supplied = chain[:1]
    if mutation == "truncated":
        supplied = [chain[0].model_copy(update={"truncated": True})]
    elif mutation == "tampered":
        supplied = [chain[0].model_copy(update={"text": chain[0].text + " "})]
    else:
        supplied *= 2
    criterion = state.brief.criteria[0]
    result = frontier_validators(manifest)[criterion.validator].validate(
        criterion, state.steps[0].report.findings[0], supplied
    )
    assert result.status == "inconclusive"


def test_regression_failure_is_contradiction(case):
    manifest, state, _ = case
    step = make_step(manifest, state.brief, make_chain(manifest, regression_outcome="failed"))
    assert step.validations[2].status == "contradicted"
