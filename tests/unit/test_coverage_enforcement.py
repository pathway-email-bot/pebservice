"""
Meta-test: ensures every .py file in service/ has a corresponding test file.

This prevents new modules from being added without tests.
Skips __init__.py and __pycache__ files.
"""

from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parent.parent.parent / "service"
UNIT_TESTS_DIR = Path(__file__).resolve().parent

# Files that are intentionally skipped (with reasons)
SKIP_FILES = {
    "__init__.py",          # Package markers, no logic to test
}


def _service_py_files():
    """Recursively find all .py files in service/, excluding __init__.py."""
    files = []
    for py_file in sorted(SERVICE_DIR.rglob("*.py")):
        if py_file.name in SKIP_FILES:
            continue
        if "__pycache__" in str(py_file):
            continue
        files.append(py_file)
    return files


def _expected_test_path(source_file: Path) -> Path:
    """Map a service source file to its expected test file path."""
    relative = source_file.relative_to(SERVICE_DIR)
    test_name = f"test_{relative.name}"
    test_path = UNIT_TESTS_DIR / relative.parent / test_name
    return test_path


def test_all_service_files_have_tests():
    """Every .py file in service/ should have a corresponding test_*.py file."""
    missing = []
    for source_file in _service_py_files():
        expected = _expected_test_path(source_file)
        if not expected.exists():
            rel_source = source_file.relative_to(SERVICE_DIR)
            rel_test = expected.relative_to(UNIT_TESTS_DIR)
            missing.append(f"  {rel_source} → tests/unit/{rel_test}")

    if missing:
        msg = (
            f"\n{len(missing)} service file(s) missing unit tests:\n"
            + "\n".join(missing)
            + "\n\nCreate the test file or add to SKIP_FILES with a reason."
        )
        pytest.fail(msg)
