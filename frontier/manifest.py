"""Assessment metadata bound to the reviewed brief and saved in its checkpoint."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from agent.research.models import ResearchBrief, ResearchState
from pydantic import BaseModel, ConfigDict, Field

from .assessment import ASSESSMENT_MANIFEST_PREFIX, Assessment, assessment_brief

PREFIX = ASSESSMENT_MANIFEST_PREFIX


def brief_digest(brief: ResearchBrief) -> str:
    return hashlib.sha256(
        json.dumps(brief.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class AssessmentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    assessment_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    target: str
    scope: tuple[str, ...]
    prohibited_states: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    brief_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str


def prepare_assessment(assessment: Assessment) -> tuple[AssessmentManifest, ResearchBrief]:
    assessment = Assessment(
        str(Path(assessment.target).resolve()),
        assessment.scope,
        assessment.prohibited_states,
        assessment.assumptions,
    )
    base = assessment_brief(assessment)
    manifest = AssessmentManifest(
        assessment_id=uuid4().hex,
        target=str(Path(assessment.target).resolve()),
        scope=tuple(assessment.scope),
        prohibited_states=tuple(assessment.prohibited_states),
        assumptions=tuple(assessment.assumptions),
        brief_hash=brief_digest(base),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return manifest, base.model_copy(
        update={"assumptions": [*base.assumptions, PREFIX + manifest.model_dump_json()]}
    )


def manifest_from_state(state: ResearchState) -> AssessmentManifest:
    if state.brief is None:
        raise ValueError("Checkpoint has no reviewed Frontier brief")
    entries = [s for s in state.brief.assumptions if s.startswith(PREFIX)]
    if len(entries) != 1:
        raise ValueError(
            "Checkpoint needs exactly one saved Frontier manifest; legacy runs cannot resume"
        )
    manifest = AssessmentManifest.model_validate_json(entries[0][len(PREFIX) :])
    base = state.brief.model_copy(
        update={"assumptions": [s for s in state.brief.assumptions if not s.startswith(PREFIX)]}
    )
    expected = assessment_brief(
        Assessment(
            manifest.target,
            list(manifest.scope),
            list(manifest.prohibited_states),
            list(manifest.assumptions),
        )
    )
    if (
        brief_digest(base) != manifest.brief_hash
        or base != expected
        or str(Path(state.workspace).resolve()) != manifest.target
    ):
        raise ValueError(
            "Saved target, scope or reviewed brief does not match the Frontier manifest"
        )
    return manifest
