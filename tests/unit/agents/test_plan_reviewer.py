from app.services.agents.plan_reviewer import SPEC


def test_plan_reviewer_spec_loaded():
    assert SPEC.name == "plan_reviewer"
    assert SPEC.output_schema.__name__ == "PlanVerdict"
