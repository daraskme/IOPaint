"""Check that requirements.txt mirrors project.dependencies in pyproject.toml."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

HEADER = "# GENERATED from pyproject.toml — do not edit"
ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
REQUIREMENTS = ROOT / "requirements.txt"


def project_dependencies(pyproject: Path) -> list[str]:
    """Read the simple PEP 621 dependency array without third-party TOML code."""
    contents = pyproject.read_text(encoding="utf-8")
    project_match = re.search(
        r"(?ms)^\[project\]\s*$.*?(?=^\[)",
        contents,
    )
    if project_match is None:
        raise ValueError(f"Missing [project] table in {pyproject}")

    dependencies_match = re.search(
        r"(?ms)^dependencies\s*=\s*(\[.*?^\])\s*$",
        project_match.group(0),
    )
    if dependencies_match is None:
        raise ValueError(f"Missing project.dependencies array in {pyproject}")

    dependencies = ast.literal_eval(dependencies_match.group(1))
    if not isinstance(dependencies, list) or not all(
        isinstance(dependency, str) for dependency in dependencies
    ):
        raise ValueError("project.dependencies must be an array of strings")
    return dependencies


def rendered_requirements() -> str:
    return "\n".join([HEADER, *project_dependencies(PYPROJECT)]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="regenerate requirements.txt instead of checking it",
    )
    args = parser.parse_args()

    expected = rendered_requirements()
    if args.write:
        REQUIREMENTS.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {REQUIREMENTS.relative_to(ROOT)}")
        return 0

    actual = REQUIREMENTS.read_text(encoding="utf-8")
    if actual != expected:
        print(
            "requirements.txt is out of sync with project.dependencies; "
            "run scripts/check_requirements_sync.py --write"
        )
        return 1

    print("requirements.txt matches project.dependencies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
