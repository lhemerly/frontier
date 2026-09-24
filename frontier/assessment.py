"""Frontier's reviewed scope and evidence criteria for repository AppSec."""

from dataclasses import dataclass, field

from agent.research.models import Criterion, ResearchBrief


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
        assumptions=assessment.assumptions,
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
