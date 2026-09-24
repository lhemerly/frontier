"""Serialize the methodology's current assessment; never aggregate loose verdicts."""

from agent.research.models import ResearchState

from .manifest import manifest_from_state
from .methodology import AssessmentStage, derive_assurance_state


def assessment_result(state: ResearchState) -> dict:
    manifest = manifest_from_state(state)
    assurance, chain = derive_assurance_state(state, manifest)
    baseline = chain.get("baseline")
    return {
        "assessment": manifest.assessment_id,
        "research_run": state.run_id,
        "target": manifest.target,
        "scope": list(manifest.scope),
        "prohibited_states": list(manifest.prohibited_states),
        "brief_hash": manifest.brief_hash,
        "finding_id": baseline.observation.finding_id if baseline else None,
        "stage": assurance.stage.value,
        "history": [stage.value for stage in assurance.history],
        "result": (
            "declared_remediated"
            if assurance.stage == AssessmentStage.CLOSED
            else assurance.stage.value
        ),
        "evidence_chain": {
            phase: {
                "evidence_id": record.evidence.id,
                "sha256": record.evidence.sha256,
                **record.observation.model_dump(),
            }
            for phase, record in chain.items()
        },
        "research_status": state.status,
        "verification": "declared_artifacts",
        "limitations": [
            "Content hashes link captured declarations. They do not establish that commands "
            "ran, that revisions were measured correctly, or that execution was attested."
        ],
    }
