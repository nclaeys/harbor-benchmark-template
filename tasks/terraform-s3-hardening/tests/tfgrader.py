"""Offline Terraform grading helpers: parse HCL with python-hcl2, run `tofu validate`.

Structural checks (does the module contain the right resources and arguments?)
use python-hcl2. Validity (is it HCL the provider schema accepts?) uses
`tofu validate` / `terraform validate` against an offline provider mirror.
Neither needs cloud credentials, so grading runs unattended.

Copy this file into every Terraform task's tests/ dir: tasks stay self-contained.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import hcl2

# python-hcl2 >= 5 keeps the quotes on string values and labels and adds
# "__is_block__" markers; older versions don't. normalize() makes both look the same.
_MARKERS = {"__is_block__", "__start_line__", "__end_line__", "__comments__"}


def _unquote(value):
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def normalize(obj):
    if isinstance(obj, dict):
        return {_unquote(k): normalize(v) for k, v in obj.items() if k not in _MARKERS}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    return _unquote(obj)


def ref(value) -> str:
    """'${aws_s3_bucket.this.id}' -> 'aws_s3_bucket.this.id'."""
    value = str(value)
    if value.startswith("${") and value.endswith("}"):
        return value[2:-1]
    return value


def parse_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return normalize(hcl2.load(f))


def parse_module(module_dir: Path) -> list[dict]:
    """Parse the *.tf files of ONE module (non-recursive, like Terraform)."""
    return [parse_file(p) for p in sorted(Path(module_dir).glob("*.tf"))]


def blocks(parsed_files: list[dict], kind: str) -> dict[str, dict]:
    """Single-label blocks (variable, output, module) -> {name: body}."""
    found = {}
    for parsed in parsed_files:
        for entry in parsed.get(kind, []):
            found.update(entry)
    return found


def resources(parsed_files: list[dict], rtype: str) -> dict[str, dict]:
    """All resources of a type -> {name: body}."""
    found = {}
    for parsed in parsed_files:
        for entry in parsed.get("resource", []):
            found.update(entry.get(rtype, {}))
    return found


def first_block(body: dict, name: str) -> dict:
    """Nested blocks parse as a list of dicts; return the first one (or {})."""
    value = body.get(name)
    if isinstance(value, list) and value:
        return value[0]
    return value if isinstance(value, dict) else {}


# --- tofu validate -----------------------------------------------------------

_PROVIDER_INSTALL_ERRORS = (
    "Failed to install provider",
    "Failed to query available provider packages",
    "could not query provider",
    "Could not retrieve the list of available versions",
)


def tf_binary() -> str | None:
    return shutil.which(os.environ.get("TF_BIN", "")) or shutil.which("tofu") or shutil.which("terraform")


def validate(target_dir: Path, timeout: int = 300) -> tuple[bool, str]:
    """Copy the workspace to a scratch dir, `init -backend=false`, `validate`."""
    tf = tf_binary()
    if tf is None:
        raise RuntimeError("no tofu/terraform binary on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(target_dir, work,
                        ignore=shutil.ignore_patterns(".terraform", ".terraform.lock.hcl", "*.tfstate*"))

        def run(*args):
            return subprocess.run([tf, *args], cwd=work, capture_output=True, text=True, timeout=timeout)

        init = run("init", "-backend=false", "-input=false", "-no-color")
        if init.returncode != 0:
            return False, init.stdout + init.stderr
        val = run("validate", "-no-color")
        return val.returncode == 0, val.stdout + val.stderr


def is_provider_install_failure(output: str) -> bool:
    return any(s in output for s in _PROVIDER_INSTALL_ERRORS)
