from app.services.agents.layout_hinter import SPEC


def test_layout_hinter_spec_loaded():
    assert SPEC.name == "layout_hinter"
    assert SPEC.output_schema.__name__ == "LayoutHints"
