"""Machine-readable assessment summaries derived from the research ledger."""

from typing import Any

from agent.research.models import ResearchState


def assessment_result(state: ResearchState, assessment_id: str, target: str) -> dict[str, Any]:
    """Build an honest JSON-ready result; candidate readiness is not certification."""
    latest = state.latest_validations()
    finding = latest.get("vulnerability_reproduced")
    remediation = latest.get("remediation_revalidated")
    regression = latest.get("regression_tests_pass")
    all_supported = all(
        result is not None and result.status == "supported"
        for result in (finding, remediation, regression)
    )
    result = "verified_remediated" if all_supported else (
        "inconclusive" if state.status in ("failed", "blocked") else state.status
    )
    return {
        "assessment": assessment_id,
        "target": target,
        "prohibited_states": [],
        "finding": _validation(finding),
        "remediation": _validation(remediation),
        "revalidation": {
            "security_test": _status(remediation),
            "regression_tests": _status(regression),
            "original_path_reproduced": (
                False if remediation is not None and remediation.status == "supported" else None
            ),
        },
        "result": result,
        "research_status": state.status,
        "limitations": [
            "Frontier validators check captured artifact contents. They do not independently establish "
            "that the recorded command ran or that the evidence is untampered before capture."
        ],
    }


def _validation(value: Any) -> dict[str, Any]:
    if value is None:
        return {"status": "not_tested", "evidence": []}
    return {"status": value.status, "claim": value.claim, "evidence": value.evidence_ids,
            "validator": value.validator, "reason": value.reason}


def _status(value: Any) -> str:
    return "not_tested" if value is None else value.status
