from __future__ import annotations

from importlib import metadata
from pathlib import Path


def _get_installed_package_metadata_value(key: str) -> str | None:
    try:
        if key == "name":
            return metadata.metadata("ctxledger").get("Name")
        if key == "version":
            return metadata.version("ctxledger")
    except metadata.PackageNotFoundError:
        return None

    return None


def _get_pyproject_metadata_value(key: str) -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject_path.exists():
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

    installed_value = _get_installed_package_metadata_value(key)
    if installed_value:
        return installed_value

    raise RuntimeError(
        f"Could not determine ctxledger {key} from pyproject.toml or package metadata"
    )


def get_app_name() -> str:
    return _get_pyproject_metadata_value("name")


def get_app_version() -> str:
    return _get_pyproject_metadata_value("version")
