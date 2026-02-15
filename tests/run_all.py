#!/usr/bin/env python3
"""
Run all PEB tests by category.

Usage:
    python tests/run_all.py              # unit + local (default)
    python tests/run_all.py unit         # unit tests only
    python tests/run_all.py local        # local tests only (hits SM, Firestore, OpenAI)
    python tests/run_all.py integration  # integration tests only (requires deployed functions)
    python tests/run_all.py all          # everything
"""

import subprocess
import sys

SUITES = {
    "unit":        {"path": "tests/unit/",        "timeout": 30,  "desc": "Unit tests (fast, no network)"},
    "local":       {"path": "tests/local/",       "timeout": 60,  "desc": "Local tests (Secret Manager, Firestore, OpenAI)"},
    "integration": {"path": "tests/integration/", "timeout": 180, "desc": "Integration tests (deployed functions, real emails)"},
}

DEFAULT_SUITES = ["unit", "local"]


def run_suite(name: str) -> bool:
    suite = SUITES[name]
    print(f"\n{'='*60}")
    print(f"  {suite['desc']}")
    print(f"  pytest {suite['path']} --timeout={suite['timeout']}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", suite["path"],
         "-v", "--tb=short", f"--timeout={suite['timeout']}"],
    )
    return result.returncode == 0


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if arg == "all":
        suites = list(SUITES.keys())
    elif arg in SUITES:
        suites = [arg]
    elif arg is None:
        suites = DEFAULT_SUITES
    else:
        print(f"Unknown suite: {arg}")
        print(f"Available: {', '.join(SUITES.keys())}, all")
        return 1

    results = {}
    for name in suites:
        results[name] = run_suite(name)

    # Summary
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    for name, passed in results.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}: {'PASSED' if passed else 'FAILED'}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
