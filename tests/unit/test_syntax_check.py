"""
Syntax check: AST-parse every Python file to catch syntax errors early.

This runs in CI alongside other unit tests. It dynamically discovers all
.py files under service/, tests/local/, tests/integration/, and tests/browser/
so it never needs to be kept in sync with the file list.

Catches: syntax errors, invalid Python, broken f-strings, etc.
Does NOT catch: import resolution errors (those require runtime).

Run:  python -m pytest tests/unit/test_syntax_check.py -v
Cost: zero — no network, no side effects, just AST parsing.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SCAN_DIRS = [
    REPO_ROOT / "service",
    REPO_ROOT / "tests" / "local",
    REPO_ROOT / "tests" / "integration",
    REPO_ROOT / "tests" / "browser",
]


def _collect_py_files():
    """Yield (relative_path_str, absolute_path) for every .py file."""
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for py_file in sorted(scan_dir.rglob("*.py")):
            label = str(py_file.relative_to(REPO_ROOT))
            yield pytest.param(py_file, id=label)


@pytest.mark.parametrize("py_file", list(_collect_py_files()))
def test_syntax_valid(py_file: Path):
    """Every Python file must parse without syntax errors."""
    source = py_file.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(py_file))
    except SyntaxError as exc:
        pytest.fail(f"Syntax error in {py_file.relative_to(REPO_ROOT)}: {exc}")
