"""Explicit, guarded state transitions for a single assurance finding."""

from dataclasses import dataclass, field
from enum import Enum


class AssessmentStage(str, Enum):
    DISCOVER = "discover"
    VALIDATE = "validate"
    CONFIRMED = "confirmed"
    REMEDIATE = "remediate"
    REVALIDATE = "revalidate"
    CLOSED = "closed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    NOT_TESTED = "not_tested"
    REGRESSION = "regression"


@dataclass
class AssuranceState:
    """State ledger; only validator-backed observations permit forward movement."""

    stage: AssessmentStage = AssessmentStage.DISCOVER
    baseline_reproduced: bool = False
    remediation_applied: bool = False
    post_patch_reproduction_absent: bool = False
    regression_tests_passed: bool = False
    history: list[AssessmentStage] = field(default_factory=lambda: [AssessmentStage.DISCOVER])

    def confirm(self, *, reproduction_supported: bool | None) -> None:
        if self.stage != AssessmentStage.DISCOVER:
            raise ValueError("confirmation is only allowed after discovery")
        self.stage = AssessmentStage.VALIDATE
        self.history.append(self.stage)
        if reproduction_supported is not True:
            self.stage = (
                AssessmentStage.REJECTED
                if reproduction_supported is False
                else AssessmentStage.INCONCLUSIVE
            )
            self.history.append(self.stage)
            return
        self.baseline_reproduced = True
        self.stage = AssessmentStage.CONFIRMED
        self.history.append(self.stage)

    def begin_remediation(self) -> None:
        if self.stage != AssessmentStage.CONFIRMED:
            raise ValueError("remediation requires a confirmed reproduction")
        self.stage = AssessmentStage.REMEDIATE
        self.history.append(self.stage)

    def record_remediation(self, *, applied: bool) -> None:
        if self.stage != AssessmentStage.REMEDIATE:
            raise ValueError("remediation result requires the remediation stage")
        self.remediation_applied = applied
        self.stage = AssessmentStage.REVALIDATE if applied else AssessmentStage.INCONCLUSIVE
        self.history.append(self.stage)

    def close(self, *, original_path_absent: bool, regression_tests_passed: bool | None) -> None:
        if self.stage != AssessmentStage.REVALIDATE:
            raise ValueError("closure requires revalidation")
        self.post_patch_reproduction_absent = original_path_absent
        self.regression_tests_passed = regression_tests_passed is True
        if regression_tests_passed is False:
            self.stage = AssessmentStage.REGRESSION
        elif not original_path_absent or regression_tests_passed is None:
            self.stage = AssessmentStage.INCONCLUSIVE
        else:
            self.stage = AssessmentStage.CLOSED
        self.history.append(self.stage)

    def reject(self) -> None:
        if self.stage not in (AssessmentStage.DISCOVER, AssessmentStage.VALIDATE):
            raise ValueError("a finding can only be rejected before confirmation")
        self.stage = AssessmentStage.REJECTED
        self.history.append(self.stage)


def derive_assurance_state(state, manifest):
    """Replay only the current step's checked chain through the methodology.

    Earlier validations cannot certify a later synthesis. Rechecking snapshots
    makes standalone report generation obey the same contract as the runner.
    """
    from .evidence import records
    from .validators import CRITERIA, frontier_validators

    assurance = AssuranceState(
        stage=AssessmentStage.NOT_TESTED, history=[AssessmentStage.NOT_TESTED]
    )
    if not state.steps:
        return assurance, {}
    assurance.stage = AssessmentStage.INCONCLUSIVE
    assurance.history = [AssessmentStage.DISCOVER, AssessmentStage.INCONCLUSIVE]
    step = state.steps[-1]
    if not step.execution_success or state.mock or state.status in ("failed", "blocked"):
        return assurance, {}
    findings = {f.criterion_id: f for f in step.report.findings}
    validations = {v.criterion_id: v for v in step.validations}
    evidence = {e.id: e for e in state.evidence}
    if len(evidence) != len(state.evidence) or len(validations) != len(step.validations):
        return assurance, {}
    checked = {}
    adapters = frontier_validators(manifest)
    criteria = {c.id: c for c in state.brief.criteria}
    for key, (name, _) in CRITERIA.items():
        result, finding = validations.get(key), findings.get(key)
        if (
            result is None
            or finding is None
            or result.validator != name
            or result.kind != "deterministic"
            or result.claim != finding.claim
        ):
            continue
        if any(i not in evidence for i in result.evidence_ids):
            continue
        supplied = [evidence[i] for i in result.evidence_ids]
        fresh = adapters[name].validate(criteria[key], finding, supplied, answer=step.report.answer)
        if (
            fresh.status == result.status
            and fresh.evidence_ids == result.evidence_ids
            and fresh.status in ("supported", "contradicted")
        ):
            checked[key] = (
                fresh,
                records(supplied, manifest.assessment_id, manifest.prohibited_states),
            )
    baseline = checked.get("vulnerability_reproduced")
    if baseline is None:
        return assurance, {}
    assurance = AssuranceState()
    assurance.confirm(reproduction_supported=baseline[0].status == "supported")
    chain = {"baseline": baseline[1][0]}
    if not assurance.baseline_reproduced:
        return assurance, chain
    remediation = checked.get("remediation_revalidated")
    if remediation is None or remediation[1][0].evidence.id != chain["baseline"].evidence.id:
        return assurance, chain
    chain["post_patch"] = remediation[1][1]
    assurance.begin_remediation()
    assurance.record_remediation(applied=True)
    if remediation[0].status != "supported":
        assurance.close(original_path_absent=False, regression_tests_passed=None)
        return assurance, chain
    assurance.post_patch_reproduction_absent = True
    regression = checked.get("regression_tests_pass")
    if (
        regression is None
        or regression[1][0].evidence.id != chain["baseline"].evidence.id
        or regression[1][1].evidence.id != chain["post_patch"].evidence.id
    ):
        return assurance, chain
    chain["regression"] = regression[1][2]
    if regression[0].status == "contradicted":
        assurance.close(original_path_absent=True, regression_tests_passed=False)
    elif (
        state.status == "candidate_ready"
        and step.report.answer
        and state.answer == step.report.answer
    ):
        assurance.close(original_path_absent=True, regression_tests_passed=True)
    return assurance, chain
