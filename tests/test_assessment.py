from frontier.assessment import Assessment, assessment_brief


def test_assessment_becomes_reviewed_research_brief() -> None:
    brief = assessment_brief(Assessment(
        target="./target",
        scope=["source", "local tests"],
        prohibited_states=["cross-user private data access"],
    ))
    assert brief.scope.startswith("Target: ./target")
    assert [criterion.id for criterion in brief.criteria] == [
        "vulnerability_reproduced", "remediation_revalidated", "regression_tests_pass"
    ]
    assert {criterion.validator for criterion in brief.criteria} == {
        "frontier_reproduction", "frontier_remediation", "frontier_regression"
    }
