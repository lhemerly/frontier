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
            self.stage = (AssessmentStage.REJECTED if reproduction_supported is False
                          else AssessmentStage.INCONCLUSIVE)
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

    def close(self, *, original_path_absent: bool, regression_tests_passed: bool) -> None:
        if self.stage != AssessmentStage.REVALIDATE:
            raise ValueError("closure requires revalidation")
        self.post_patch_reproduction_absent = original_path_absent
        self.regression_tests_passed = regression_tests_passed
        if not regression_tests_passed:
            self.stage = AssessmentStage.REGRESSION
        elif not original_path_absent:
            self.stage = AssessmentStage.INCONCLUSIVE
        else:
            self.stage = AssessmentStage.CLOSED
        self.history.append(self.stage)

    def reject(self) -> None:
        if self.stage not in (AssessmentStage.DISCOVER, AssessmentStage.VALIDATE):
            raise ValueError("a finding can only be rejected before confirmation")
        self.stage = AssessmentStage.REJECTED
        self.history.append(self.stage)
