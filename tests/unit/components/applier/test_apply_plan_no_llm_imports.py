"""Static guarantee that apply_plan does not import LLM-related modules."""
import ast
from pathlib import Path


_BANNED = ("app.services.agents", "app.services.llm_provider", "anthropic", "openai")


def test_apply_plan_no_llm_imports():
    path = Path("app/components/applier.py").resolve()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
    for imp in imports:
        for banned in _BANNED:
            assert not imp.startswith(banned), (
                f"apply_plan.py imports {imp}, which is banned (LLM/agent)"
            )
