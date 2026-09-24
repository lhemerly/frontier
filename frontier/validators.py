"""Validate one declared chain without running tools or repository code."""

import json

from agent.research.models import Criterion, Evidence, Finding, ValidationResult

from .evidence import baseline_for, chain_for, records, unique_object
from .manifest import AssessmentManifest

CRITERIA = {
    "vulnerability_reproduced": ("frontier_reproduction", "baseline"),
    "remediation_revalidated": ("frontier_remediation", "post_patch"),
    "regression_tests_pass": ("frontier_regression", "regression"),
}


class ArtifactValidator:
    kind = "deterministic"

    def __init__(self, manifest: AssessmentManifest, criterion_id: str):
        self.manifest = manifest
        self.criterion_id = criterion_id
        self.name, self.phase = CRITERIA[criterion_id]

    def validate(
        self,
        criterion: Criterion,
        finding: Finding,
        evidence: list[Evidence],
        *,
        answer: str | None = None,
    ) -> ValidationResult:
        status, ids = "inconclusive", []
        try:
            if criterion.id != self.criterion_id or finding.criterion_id != criterion.id:
                raise ValueError("Criterion does not match the installed adapter")
            items = records(evidence, self.manifest.assessment_id, self.manifest.prohibited_states)
            candidates = [r for r in items if r.observation.phase == self.phase]
            if len(candidates) != 1:
                raise ValueError("Supply exactly one observation for this phase")
            selected = candidates[0]
            obj = selected.observation
            chain = [selected]
            if self.phase == "post_patch":
                chain = [baseline_for(selected, items), selected]
            elif self.phase == "regression":
                chain = list(chain_for(selected, items))
            expected = {
                "baseline": {("reproduced", 1): "supported", ("not_reproduced", 0): "contradicted"},
                "post_patch": {
                    ("not_reproduced", 0): "supported",
                    ("reproduced", 1): "contradicted",
                },
                "regression": {("passed", 0): "supported", ("failed", 1): "contradicted"},
            }
            verdict = expected[self.phase].get((obj.outcome, obj.exit_code))
            if verdict is None:
                raise ValueError(
                    "Outcome and exit code disagree with the pytest_assertion protocol"
                )
            if answer is not None:
                summary = json.loads(answer, object_pairs_hook=unique_object)
                keys = ("assessment_id", "finding_id", "reproduction_id")
                if self.phase != "baseline":
                    keys += ("patch_id", "workspace_revision")
                if not isinstance(summary, dict) or any(
                    summary.get(k) != getattr(obj, k) for k in keys
                ):
                    raise ValueError("Candidate answer describes a different evidence chain")
            status = verdict
            ids = [r.evidence.id for r in chain]
            reason = "Consistent declared artifact chain under pytest_assertion; execution is not attested"
        except (ValueError, TypeError) as exc:
            reason = str(exc)
        return ValidationResult(
            criterion_id=criterion.id,
            claim=finding.claim,
            status=status,
            validator=self.name,
            kind=self.kind,
            evidence_ids=ids,
            reason=reason,
        )


def frontier_validators(manifest: AssessmentManifest) -> dict[str, ArtifactValidator]:
    return {name: ArtifactValidator(manifest, key) for key, (name, _) in CRITERIA.items()}
