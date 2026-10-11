#!/usr/bin/env python3
"""Scaffold a new task in tasks/ from template/ (or by cloning an existing task).

Usage:
    python scripts/new_task.py fix-date-parsing
    python scripts/new_task.py fix-date-parsing --category python-messy-data --difficulty medium
    python scripts/new_task.py gcs-bucket-iam --from terraform-s3-hardening   # reuse the Terraform image + grader helpers

Then fill in, in this order:
    instruction.md          the ticket, rewritten to be self-contained
    environment/app/        the starter workspace (code/data as it was BEFORE the fix)
    solution/app/           the files as they were AFTER the fix (overlaid onto /app)
    tests/                  the hidden pytest grader (one test per requirement)
    task.toml [metadata]    category, difficulty, source_ticket
and run: python scripts/validate_tasks.py <name>
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
TEMPLATE = ROOT / "template"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def set_toml_value(text: str, key: str, value: str) -> str:
    """Replace the first `key = "..."` line (keeps comments and layout intact)."""
    pattern = re.compile(rf'^({re.escape(key)}\s*=\s*)"[^"]*"', re.MULTILINE)
    return pattern.sub(lambda m: f'{m.group(1)}"{value}"', text, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="task dir name, e.g. fix-date-parsing (lowercase, dashes)")
    ap.add_argument("--from", dest="source", help="existing task in tasks/ to clone instead of template/")
    ap.add_argument("--category")
    ap.add_argument("--difficulty")
    args = ap.parse_args()

    if not NAME_RE.match(args.name):
        ap.error("name must be lowercase letters, digits, '.', '_' or '-'")
    dest = TASKS / args.name
    if dest.exists():
        ap.error(f"{dest} already exists")
    source = TASKS / args.source if args.source else TEMPLATE
    if not (source / "task.toml").exists():
        ap.error(f"{source} is not a task dir")

    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", ".terraform", ".terraform.lock.hcl"))

    toml_path = dest / "task.toml"
    text = toml_path.read_text()
    org = re.search(r'^name\s*=\s*"([^/"]+)/', text, re.MULTILINE)
    text = set_toml_value(text, "name", f"{org.group(1) if org else 'mybench'}/{args.name}")
    if args.category:
        text = set_toml_value(text, "category", args.category)
    if args.difficulty:
        text = set_toml_value(text, "difficulty", args.difficulty)
    toml_path.write_text(text)

    print(f"created {dest.relative_to(ROOT)} (from {source.relative_to(ROOT)})")
    print("next: edit instruction.md, environment/app/, solution/app/, tests/, then")
    print(f"      python scripts/validate_tasks.py {args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
