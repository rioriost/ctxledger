#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path

LOCAL_PLACEHOLDERS: dict[str, str] = {
    "CTXLEDGER_SMALL_AUTH_TOKEN": "replace-with-a-generated-strong-secret",
    "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD": "replace-with-a-generated-strong-password",
    "CTXLEDGER_GRAFANA_ADMIN_PASSWORD": "replace-with-a-generated-strong-password",
}

PRODUCTION_PLACEHOLDERS: dict[str, str] = {
    "CTXLEDGER_AUTH_BEARER_TOKEN": "replace-with-a-generated-strong-secret",
    "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD": "replace-with-a-generated-strong-password",
    "CTXLEDGER_GRAFANA_ADMIN_PASSWORD": "replace-with-a-generated-strong-password",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Populate known ctxledger env placeholder values with generated secrets.")
    )
    parser.add_argument(
        "env_file",
        nargs="?",
        default=".env",
        help="Path to the env file to update in place (default: .env).",
    )
    parser.add_argument(
        "--mode",
        choices=("local", "production", "auto"),
        default="auto",
        help=(
            "Placeholder set to target. "
            "'local' updates .env.example-style values, "
            "'production' updates .env.production.example-style values, "
            "'auto' updates any known placeholders it finds."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the updated content to stdout instead of writing the file.",
    )
    return parser.parse_args()


def generate_base64ish_secret(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_grafana_admin_password() -> str:
    return f"Admin-{secrets.token_hex(16)}A1!"


def placeholders_for_mode(mode: str) -> dict[str, str]:
    if mode == "local":
        return dict(LOCAL_PLACEHOLDERS)
    if mode == "production":
        return dict(PRODUCTION_PLACEHOLDERS)

    merged = dict(LOCAL_PLACEHOLDERS)
    merged.update(PRODUCTION_PLACEHOLDERS)
    return merged


def generated_values_for_mode(mode: str) -> dict[str, str]:
    if mode == "local":
        return {
            "CTXLEDGER_SMALL_AUTH_TOKEN": generate_base64ish_secret(),
            "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD": generate_base64ish_secret(),
            "CTXLEDGER_GRAFANA_ADMIN_PASSWORD": generate_grafana_admin_password(),
        }
    if mode == "production":
        return {
            "CTXLEDGER_AUTH_BEARER_TOKEN": generate_base64ish_secret(),
            "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD": generate_base64ish_secret(),
            "CTXLEDGER_GRAFANA_ADMIN_PASSWORD": generate_grafana_admin_password(),
        }
    return {
        "CTXLEDGER_SMALL_AUTH_TOKEN": generate_base64ish_secret(),
        "CTXLEDGER_AUTH_BEARER_TOKEN": generate_base64ish_secret(),
        "CTXLEDGER_GRAFANA_POSTGRES_PASSWORD": generate_base64ish_secret(),
        "CTXLEDGER_GRAFANA_ADMIN_PASSWORD": generate_grafana_admin_password(),
    }


def replace_placeholders(
    content: str,
    *,
    placeholders: dict[str, str],
    generated_values: dict[str, str],
) -> tuple[str, list[str]]:
    updated = content
    replaced_keys: list[str] = []

    for key, placeholder_value in placeholders.items():
        needle = f"{key}={placeholder_value}"
        if needle not in updated:
            continue
        updated = updated.replace(needle, f"{key}={generated_values[key]}")
        replaced_keys.append(key)

    return updated, replaced_keys


def main() -> int:
    args = parse_args()
    env_path = Path(args.env_file)

    if not env_path.exists():
        print(f"error: env file not found: {env_path}", file=sys.stderr)
        return 1
    if not env_path.is_file():
        print(f"error: path is not a file: {env_path}", file=sys.stderr)
        return 1

    original = env_path.read_text(encoding="utf-8")
    placeholders = placeholders_for_mode(args.mode)
    generated_values = generated_values_for_mode(args.mode)
    updated, replaced_keys = replace_placeholders(
        original,
        placeholders=placeholders,
        generated_values=generated_values,
    )

    if not replaced_keys:
        print(
            "error: no known placeholder values were found to replace. "
            "Check the target file and --mode.",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        sys.stdout.write(updated)
    else:
        env_path.write_text(updated, encoding="utf-8")
        print(f"Updated {env_path}")
        for key in replaced_keys:
            print(f"- populated {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
