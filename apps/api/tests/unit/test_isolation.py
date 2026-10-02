"""Ground-truth isolation (architecture §10) and module boundaries (architecture §5)."""

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "episight"
GROUND_TRUTH_PATTERN = re.compile(r"ground[-_ ]?truth", re.IGNORECASE)

# These files name ground truth only in order to refuse it: the ingest path guard and the
# forbidden-field list of the data contract.
GROUND_TRUTH_ALLOWLIST = {SRC / "ingest" / "loader.py", SRC / "contracts" / "data.py"}


def _python_files():
    return sorted(SRC.rglob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_runtime_code_never_references_ground_truth(path):
    if path in GROUND_TRUTH_ALLOWLIST:
        return
    assert not GROUND_TRUTH_PATTERN.search(path.read_text(encoding="utf-8")), f"{path} mentions ground truth"


def test_ingest_guard_only_refuses_ground_truth():
    text = (SRC / "ingest" / "loader.py").read_text(encoding="utf-8")
    assert "_BLOCKED_DIR_NAMES" in text and "refusing to ingest" in text


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_runtime_code_never_imports_evaluation(path):
    assert not any(n == "evaluation" or n.startswith("evaluation.") for n in _imports(path))


# Domain modules stay independent of the web and persistence layers.
_DOMAIN_PACKAGES = ["screening", "episodes", "agent", "retrieval", "brief", "evidence"]
_FORBIDDEN_FOR_DOMAIN = ("episight.api", "episight.db", "fastapi", "sqlalchemy")


@pytest.mark.parametrize("package", _DOMAIN_PACKAGES)
def test_domain_packages_do_not_import_api_or_db(package):
    root = SRC / package
    if not root.exists():
        pytest.skip(f"{package} not implemented yet")
    for path in root.rglob("*.py"):
        bad = [n for n in _imports(path) if n.startswith(_FORBIDDEN_FOR_DOMAIN)]
        assert not bad, f"{path.relative_to(SRC)} imports {bad}"


def test_safety_envelope_does_not_import_llm():
    root = SRC / "agent" / "envelope"
    if not root.exists():
        pytest.skip("safety envelope not implemented yet (M6)")
    for path in root.rglob("*.py"):
        bad = [n for n in _imports(path) if n.startswith(("episight.llm", "anthropic"))]
        assert not bad, f"{path.relative_to(SRC)} imports {bad}"
