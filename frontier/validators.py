"""Deterministic checks over captured, immutable mcts-agent evidence snapshots."""

import json
from typing import Any

from agent.research.models import Criterion, Evidence, Finding, ValidationResult


class ArtifactValidator:
    """Validate the declared JSON evidence contract; never execute repository code."""

    kind = "deterministic"

    def __init__(self, name: str, expected_phase: str, expected_outcome: str,
                 expected_exit_code: int):
        self.name = name
        self.expected_phase = expected_phase
        self.expected_outcome = expected_outcome
        self.expected_exit_code = expected_exit_code

    def validate(
        self, criterion: Criterion, finding: Finding, evidence: list[Evidence], *, answer: str | None = None
    ) -> ValidationResult:
        del answer
        matching = [item for item in evidence if item.source_path.endswith(".json")]
        parsed: list[tuple[Evidence, dict[str, Any]]] = []
        for item in matching:
            try:
                value = json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(value, dict):
                parsed.append((item, value))

        candidates = [(item, obj) for item, obj in parsed if
                    obj.get("schema_version") == 1
                    and obj.get("phase") == self.expected_phase
                    and obj.get("outcome") == self.expected_outcome
                    and isinstance(obj.get("command"), str) and obj["command"].strip()
                    and type(obj.get("exit_code")) is int
                    and obj["exit_code"] == self.expected_exit_code]
        if self.expected_phase in ("baseline", "post_patch"):
            candidates = [(item, obj) for item, obj in candidates
                          if isinstance(obj.get("reproduction_id"), str)
                          and obj["reproduction_id"].strip()]
        accepted = candidates
        if self.expected_phase == "post_patch":
            baselines = [obj for _, obj in parsed if obj.get("schema_version") == 1
                         and isinstance(obj.get("reproduction_id"), str)
                         and obj["reproduction_id"].strip()
                         and isinstance(obj.get("command"), str) and obj["command"].strip()
                         and obj.get("phase") == "baseline"
                         and obj.get("outcome") == "reproduced"
                         and type(obj.get("exit_code")) is int and obj["exit_code"] == 1]
            accepted = [(item, obj) for item, obj in candidates if any(
                obj.get("reproduction_id") == baseline.get("reproduction_id")
                and obj.get("command") == baseline.get("command")
                for baseline in baselines
            )]
        status = "supported" if accepted else "inconclusive"
        reason = (
            f"Captured JSON records satisfy the {self.expected_phase!r}/{self.expected_outcome!r} "
            "artifact contract and command/exit-code rules. The post-patch record is tied to a baseline "
            "by reproduction_id and identical command. This checks recorded artifact contents, not the "
            "truth or provenance of the executed command."
            if accepted else
            f"No captured JSON evidence satisfies the required {self.expected_phase!r}/"
            f"{self.expected_outcome!r} artifact contract and command/exit-code rules."
        )
        return ValidationResult(
            criterion_id=criterion.id,
            claim=finding.claim,
            status=status,
            validator=self.name,
            kind=self.kind,
            evidence_ids=[item.id for item, _ in accepted],
            reason=reason,
        )


def frontier_validators() -> dict[str, ArtifactValidator]:
    """Return validator adapters referenced by :func:`assessment_brief`."""
    return {
        "frontier_reproduction": ArtifactValidator(
            "frontier_reproduction", "baseline", "reproduced", expected_exit_code=1
        ),
        "frontier_remediation": ArtifactValidator(
            "frontier_remediation", "post_patch", "not_reproduced", expected_exit_code=0
        ),
        "frontier_regression": ArtifactValidator(
            "frontier_regression", "regression", "passed", expected_exit_code=0
        ),
    }
