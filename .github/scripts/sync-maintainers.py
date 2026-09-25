#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ruamel.yaml"]
# ///
"""Sync team rosters in maintainers.yaml from an upstream members.yaml.

Rules:
- project-maintainers = governance-committee ∪ technical-committee ∪ maintainers
- servicedesk        = governance-committee ∪ technical-committee

Rosters are sorted case-insensitively. Only the matching team rosters are
rewritten; every other field (comments, unrelated teams, ordering of the
outer document) is preserved.

Use --dry-run to preview a unified diff without modifying the target file.
"""

from __future__ import annotations

import argparse
import difflib
import io
import sys
from pathlib import Path

from ruamel.yaml import YAML

TEAM_RULES = {
    "project-maintainers": (
        "governance-committee",
        "technical-committee",
        "maintainers",
    ),
    "servicedesk": ("governance-committee", "technical-committee"),
}


def _collect(source: dict, section: str) -> set[str]:
    return {entry["name"] for entry in source.get(section, []) or []}


def _render(source_path: Path, target_path: Path) -> tuple[str, str]:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096

    original = target_path.read_text()
    source = yaml.load(source_path.read_text())
    target = yaml.load(original)

    rosters = {
        team: sorted(
            set().union(*(_collect(source, s) for s in sections)),
            key=str.casefold,
        )
        for team, sections in TEAM_RULES.items()
    }

    for project in target.get("maintainers", []):
        for team in project.get("teams", []):
            if team.get("name") in rosters:
                team["members"] = rosters[team["name"]]

    buf = io.StringIO()
    yaml.dump(target, buf)
    return original, buf.getvalue()


def sync(source_path: Path, target_path: Path, dry_run: bool = False) -> bool:
    original, updated = _render(source_path, target_path)
    if original == updated:
        return False

    if dry_run:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{target_path}",
            tofile=f"b/{target_path}",
        )
        sys.stdout.writelines(diff)
    else:
        target_path.write_text(updated)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="upstream members.yaml")
    parser.add_argument("target", type=Path, help="maintainers.yaml to update")
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print a unified diff of the proposed changes and exit",
    )
    args = parser.parse_args()
    changed = sync(args.source, args.target, dry_run=args.dry_run)
    if args.dry_run and not changed:
        print(f"{args.target}: already in sync", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
