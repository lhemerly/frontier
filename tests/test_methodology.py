import pytest

from frontier.methodology import AssessmentStage, AssuranceState


def test_closure_requires_confirmed_issue_remediation_and_successful_revalidation() -> None:
    state = AssuranceState()
    with pytest.raises(ValueError):
        state.begin_remediation()
    state.confirm(reproduction_supported=True)
    state.begin_remediation()
    state.record_remediation(applied=True)
    state.close(original_path_absent=True, regression_tests_passed=True)
    assert state.stage is AssessmentStage.CLOSED


def test_regression_failure_prevents_closure() -> None:
    state = AssuranceState()
    state.confirm(reproduction_supported=True)
    state.begin_remediation()
    state.record_remediation(applied=True)
    state.close(original_path_absent=True, regression_tests_passed=False)
    assert state.stage is AssessmentStage.REGRESSION


def test_unreproduced_claim_is_rejected_but_unavailable_evidence_is_inconclusive() -> None:
    state = AssuranceState()
    state.confirm(reproduction_supported=False)
    assert state.stage is AssessmentStage.REJECTED
    assert not state.baseline_reproduced
    uncertain = AssuranceState()
    uncertain.confirm(reproduction_supported=None)
    assert uncertain.stage is AssessmentStage.INCONCLUSIVE
