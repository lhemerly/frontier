"""Declared evidence contract. Hashes bind records; they do not attest execution."""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from agent.research.models import Evidence
from pydantic import BaseModel, ConfigDict, Field


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[2]
    assessment_id: str = Field(min_length=1)
    finding_id: str = Field(min_length=1)
    reproduction_id: str = Field(min_length=1)
    prohibited_state: str = Field(min_length=1)
    phase: Literal["baseline", "post_patch", "regression"]
    protocol: Literal["pytest_assertion"]
    command: str = Field(min_length=1)
    exit_code: int
    outcome: Literal["reproduced", "not_reproduced", "passed", "failed"]
    workspace_revision: str = Field(min_length=1)
    reproduction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    baseline_revision: str | None = None
    patch_id: str | None = None
    post_patch_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def identity(self) -> tuple[str, ...]:
        return (
            self.assessment_id,
            self.finding_id,
            self.reproduction_id,
            self.prohibited_state,
            self.reproduction_sha256,
        )


@dataclass(frozen=True)
class Record:
    evidence: Evidence
    observation: Observation


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def records(evidence: list[Evidence], assessment_id: str, prohibited_states: tuple[str, ...]):
    result = []
    seen = set()
    for item in evidence:
        if item.id in seen:
            raise ValueError("Duplicate evidence ID")
        seen.add(item.id)
        if item.truncated or hashlib.sha256(item.text.encode()).hexdigest() != item.sha256:
            raise ValueError("Evidence is truncated or its content hash differs")
        if not item.source_path.endswith(".json"):
            continue
        value = json.loads(item.text, object_pairs_hook=unique_object)
        obj = Observation.model_validate(value)
        if obj.assessment_id != assessment_id or obj.prohibited_state not in prohibited_states:
            raise ValueError("Evidence belongs to a different assessment or prohibited state")
        if any(
            not v.strip()
            for v in (obj.finding_id, obj.reproduction_id, obj.command, obj.workspace_revision)
        ):
            raise ValueError("Evidence identity, command and revision must not be blank")
        result.append(Record(item, obj))
    return result


def baseline_for(post: Record, items: list[Record]) -> Record:
    p = post.observation
    candidates = [
        b
        for b in items
        if b.observation.phase == "baseline"
        and b.evidence.sha256 == p.baseline_sha256
        and b.observation.workspace_revision == p.baseline_revision
        and b.observation.identity() == p.identity()
        and b.observation.command == p.command
        and b.observation.protocol == p.protocol
        and b.observation.outcome == "reproduced"
        and b.observation.exit_code == 1
    ]
    if (
        len(candidates) != 1
        or not p.patch_id
        or not p.patch_id.strip()
        or p.workspace_revision == p.baseline_revision
    ):
        raise ValueError("Post-patch evidence needs one matching baseline and a changed revision")
    return candidates[0]


def chain_for(regression: Record, items: list[Record]) -> tuple[Record, Record, Record]:
    r = regression.observation
    candidates = [
        p
        for p in items
        if p.observation.phase == "post_patch"
        and p.evidence.sha256 == r.post_patch_sha256
        and p.observation.identity() == r.identity()
        and p.observation.patch_id == r.patch_id
        and p.observation.workspace_revision == r.workspace_revision
        and p.observation.baseline_sha256 == r.baseline_sha256
        and p.observation.baseline_revision == r.baseline_revision
        and p.observation.outcome == "not_reproduced"
        and p.observation.exit_code == 0
    ]
    if len(candidates) != 1:
        raise ValueError("Regression evidence needs one matching successful post-patch record")
    post = candidates[0]
    return baseline_for(post, items), post, regression
