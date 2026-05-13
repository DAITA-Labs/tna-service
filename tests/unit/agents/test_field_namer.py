from app.services.agents.field_namer import SPEC


def test_field_namer_spec_loaded():
    assert SPEC.name == "field_namer"
    assert SPEC.output_schema.__name__ == "CanonicalNameMap"
