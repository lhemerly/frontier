"""Frontier's reviewed scope and evidence criteria for repository AppSec."""

import json
from dataclasses import dataclass, field

from agent.research.models import Criterion, ResearchBrief

from .evidence import Observation


@dataclass(frozen=True)
class Assessment:
    """A bounded assessment target, its permitted scope, and prohibited outcomes."""

    target: str
    scope: list[str]
    prohibited_states: list[str]
    assumptions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise ValueError("target must not be blank")
        if not self.scope or any(not item.strip() for item in self.scope):
            raise ValueError("scope must contain nonblank entries")
        if not self.prohibited_states or any(not item.strip() for item in self.prohibited_states):
            raise ValueError("at least one prohibited state is required")


def assessment_brief(assessment: Assessment) -> ResearchBrief:
    """Create a fixed Frontier brief; Codex does not author the acceptance criteria."""
    states = "; ".join(assessment.prohibited_states)
    scope = "; ".join(assessment.scope)
    return ResearchBrief(
        scope=f"Target: {assessment.target}. Permitted scope: {scope}.",
        assumptions=[
            *assessment.assumptions,
            "Evidence contract: " + json.dumps(Observation.model_json_schema(), sort_keys=True),
            "Use the assessment_id in FRONTIER_MANIFEST_V1. All phases must identify the same finding, "
            "prohibited state, reproduction_id and reproduction_sha256 (hash of the unchanged test). "
            "The pytest_assertion protocol requires a security assertion failure (exit 1) at baseline, "
            "then success (exit 0) post-patch. Other pytest exit codes are inconclusive. Regression "
            "success requires exit 0; exit 1 means failed tests. Record workspace content revisions. "
            "Post-patch references baseline_sha256 (hash of the baseline JSON bytes), baseline_revision "
            "and patch_id; regression references these plus post_patch_sha256 and the same patched "
            "workspace_revision. Save compact UTF-8 JSON artifacts. Cite baseline for reproduction, "
            "baseline+post_patch for remediation, and all three for regression. Hashes bind declarations, "
            "not execution provenance. Never edit the saved Frontier manifest.",
            "For a final synthesis, supply all three findings in ONE StepReport and reuse evidence IDs. "
            "The answer must be a JSON object with assessment_id, finding_id, reproduction_id, patch_id "
            "and workspace_revision matching that chain. Do not report success from unrelated attempts.",
        ],
        questions=[f"Can the application reach any prohibited state: {states}?"],
        criteria=[
            Criterion(
                id="vulnerability_reproduced",
                description="A baseline reproduction artifact records the prohibited behavior occurring.",
                validator="frontier_reproduction",
            ),
            Criterion(
                id="remediation_revalidated",
                description="The same reproduction after the patch records that the prohibited behavior no longer occurs.",
                validator="frontier_remediation",
            ),
            Criterion(
                id="regression_tests_pass",
                description="The relevant existing application test suite completes successfully after the patch.",
                validator="frontier_regression",
            ),
        ],
    )
