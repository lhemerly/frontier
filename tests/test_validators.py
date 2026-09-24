import json

from agent.research.models import Criterion, Evidence, Finding

from frontier.validators import frontier_validators


def _evidence(phase: str, outcome: str) -> Evidence:
    artifact = {"schema_version": 1, "phase": phase, "reproduction_id": "repro-1",
                "outcome": outcome,
                "command": "pytest -q", "exit_code": 1}
    return Evidence(id="ev-1", source_path="evidence/result.json", snapshot_path="snapshots/ev-1",
                    sha256="0" * 64, text=json.dumps(artifact))


def test_validators_accept_matching_captured_artifact_contract() -> None:
    validator = frontier_validators()["frontier_reproduction"]
    result = validator.validate(
        Criterion(id="vulnerability_reproduced", description="baseline reproduces",
                  validator=validator.name),
        Finding(criterion_id="vulnerability_reproduced", claim="IDOR reproduced",
                evidence_paths=["evidence/result.json"]),
        [_evidence("baseline", "reproduced")],
    )
    assert result.status == "supported"
    assert result.evidence_ids == ["ev-1"]


def test_wrong_phase_or_outcome_cannot_support_claim() -> None:
    validator = frontier_validators()["frontier_reproduction"]
    result = validator.validate(
        Criterion(id="vulnerability_reproduced", description="baseline reproduces",
                  validator=validator.name),
        Finding(criterion_id="vulnerability_reproduced", claim="IDOR reproduced"),
        [_evidence("post_patch", "not_reproduced")],
    )
    assert result.status == "inconclusive"
    assert not result.evidence_ids


def test_post_patch_requires_same_baseline_reproduction_and_command() -> None:
    validator = frontier_validators()["frontier_remediation"]
    baseline = _evidence("baseline", "reproduced")
    post_patch = _evidence("post_patch", "not_reproduced")
    result = validator.validate(
        Criterion(id="remediation_revalidated", description="same issue no longer reproduces",
                  validator=validator.name),
        Finding(criterion_id="remediation_revalidated", claim="original path no longer reproduces"),
        [baseline, post_patch],
    )
    assert result.status == "supported"
    assert result.evidence_ids == [post_patch.id]
