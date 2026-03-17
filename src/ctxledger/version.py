from __future__ import annotations

from pathlib import Path


def _get_pyproject_metadata_value(key: str) -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    in_project_section = False

    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped == "[project]":
            in_project_section = True
            continue

        if in_project_section and stripped.startswith("[") and stripped != "[project]":
            break

        if in_project_section and stripped.startswith(f"{key} = "):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")

    raise RuntimeError(f"Could not determine ctxledger {key} from pyproject.toml")


def get_app_name() -> str:
    return _get_pyproject_metadata_value("name")


def get_app_version() -> str:
    return _get_pyproject_metadata_value("version")
