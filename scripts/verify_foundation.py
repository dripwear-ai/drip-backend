#!/usr/bin/env python3
"""Static structure checks only. This is not a Gate B acceptance runner."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        "apps/api/pyproject.toml",
        "apps/api/uv.lock",
        "apps/api/src/drip/main.py",
        "apps/web/package.json",
        "apps/mobile/package.json",
        "packages/shared-types/package.json",
        "infra/docker-compose.yml",
        ".env.example",
        ".gitignore",
        "docs/setup.md",
        "pnpm-lock.yaml",
        ".node-version",
        ".python-version",
    ]
    failures = [f"Missing {name}" for name in required if not (ROOT / name).is_file()]
    shared = json.loads((ROOT / "packages/shared-types/package.json").read_text())
    if any("react" in name for name in shared.get("dependencies", {})):
        failures.append("shared-types must not depend on React")
    mobile = json.loads((ROOT / "apps/mobile/app.json").read_text())["expo"]
    if mobile.get("icon") and not (ROOT / "apps/mobile" / mobile["icon"]).is_file():
        failures.append("Mobile icon reference does not exist")
    for failure in failures:
        print(f"FAIL: {failure}")
    print("FAIL: static structure checks" if failures else "PASS: static structure checks only")
    print(
        "NOT RUN by this script: installs, dependency compatibility, tests, security audits, "
        "migrations, services, type checks, lint, builds, mobile exports or device tests."
    )
    print("Gate B acceptance requires the documented verification suite and owner approval.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
