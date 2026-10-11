#!/usr/bin/env python3
"""Validate tasks: the reference solution must pass, the untouched starter must fail.

A task where the starter already passes measures nothing; a task where the
reference fails will score every model 0. Run this after every grader change.

Two modes:

  local (default)  Fast, no Docker. Runs each task's hidden pytest grader on the
                   host against (a) a temp copy of environment/app and (b) that
                   copy with solution/app overlaid. Needs the grader deps on the
                   host: pip install -r requirements-dev.txt. `tofu validate`
                   checks skip when tofu/terraform is not installed.

  --harbor         The real thing. Builds each task image and runs
                   `harbor run -a oracle` (executes solution/solve.sh, expect
                   reward 1) and `harbor run -a nop` (does nothing, expect
                   reward 0) through Docker, exactly as a benchmark run would.

Usage:
    python scripts/validate_tasks.py                      # all tasks, local
    python scripts/validate_tasks.py python-clean-customers
    python scripts/validate_tasks.py --harbor             # all tasks via harbor + docker
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from results import load_trials, parse_pytest_summary

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
REQUIRED = ["task.toml", "instruction.md", "environment/Dockerfile", "environment/app",
            "tests/test.sh", "solution/solve.sh", "solution/app"]


def check_structure(task: Path) -> list[str]:
    problems = [f"missing {p}" for p in REQUIRED if not (task / p).exists()]
    for script in ("tests/test.sh", "solution/solve.sh"):
        if (task / script).exists() and not os.access(task / script, os.X_OK):
            problems.append(f"{script} is not executable (chmod +x)")
    if (task / "task.toml").exists():
        cfg = tomllib.loads((task / "task.toml").read_text())
        meta = cfg.get("metadata", {})
        for key in ("category", "difficulty"):
            if meta.get(key, "TODO") == "TODO":
                problems.append(f"warning: [metadata] {key} not set")
        if "/" not in cfg.get("task", {}).get("name", ""):
            problems.append('[task] name must look like "org/name"')
    return problems


def run_grader(task: Path, workspace: Path) -> tuple[int, str]:
    env = dict(os.environ, BENCH_TARGET=str(workspace))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(task / "tests"), "-q", "-p", "no:cacheprovider"],
        cwd=task / "tests", env=env, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def describe(rc: int, output: str) -> str:
    counts = parse_pytest_summary(output)
    if rc not in (0, 1) or counts is None:
        return f"GRADER ERROR (pytest exit {rc})"
    passed, failed, skipped = counts
    text = f"{passed}/{passed + failed} tests"
    return text + (f", {skipped} skipped" if skipped else "")


def validate_local(task: Path) -> bool:
    problems = check_structure(task)
    errors = [p for p in problems if not p.startswith("warning")]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "app"
        shutil.copytree(task / "environment" / "app", work)
        rc_start, out_start = run_grader(task, work)
        shutil.copytree(task / "solution" / "app", work, dirs_exist_ok=True)
        rc_ref, out_ref = run_grader(task, work)

    start_ok = rc_start == 1          # tests ran and at least one failed
    ref_ok = rc_ref == 0
    ok = start_ok and ref_ok and not errors
    print(f"{'OK  ' if ok else 'BAD '} {task.name}")
    print(f"     starter   (must FAIL): {describe(rc_start, out_start):<28} {'ok' if start_ok else '<-- starter passes or grader crashed'}")
    print(f"     reference (must PASS): {describe(rc_ref, out_ref):<28} {'ok' if ref_ok else '<-- reference fails'}")
    for p in problems:
        print(f"     {p}")
    if not ref_ok:
        print("     --- reference grader output (tail) ---")
        print("\n".join("     " + l for l in out_ref.splitlines()[-25:]))
    if not start_ok and rc_start != 0:
        print("     --- starter grader output (tail) ---")
        print("\n".join("     " + l for l in out_start.splitlines()[-15:]))
    return ok


def harbor_job(agent: str, task_paths: list[Path], stamp: str) -> list:
    trials = []
    for path in task_paths:
        job = f"validate-{agent}-{path.name}-{stamp}"
        cmd = ["harbor", "run", "-p", str(path), "-a", agent, "-n", "4",
               "--job-name", job, "-o", str(ROOT / "jobs"), "-y"]
        print("$", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=ROOT, check=False)
        trials += load_trials(ROOT / "jobs" / job, TASKS)
    return trials


def validate_harbor(tasks: list[Path], everything: bool) -> bool:
    if shutil.which("harbor") is None:
        sys.exit("harbor not found on PATH (uv tool install harbor)")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    # One job over the whole tasks/ dir when validating everything, else per task.
    paths = [TASKS] if everything else tasks
    oracle = {t.task: t for t in harbor_job("oracle", paths, stamp)}
    nop = {t.task: t for t in harbor_job("nop", paths, stamp)}

    all_ok = True
    print()
    for task in tasks:
        o, n = oracle.get(task.name), nop.get(task.name)
        o_ok = bool(o and o.solved)
        n_ok = bool(n and n.reward is not None and not n.solved)
        all_ok &= o_ok and n_ok
        fmt = lambda t: "no trial" if t is None else (
            f"reward {t.reward}, {t.passed}/{t.passed + t.failed} tests" + (f" ({t.exception})" if t.exception else ""))
        print(f"{'OK  ' if o_ok and n_ok else 'BAD '} {task.name}")
        print(f"     oracle (must PASS): {fmt(o)}")
        print(f"     nop    (must FAIL): {fmt(n)}")
    print(f"\njob dirs: {ROOT / 'jobs'}/validate-*-{stamp}")
    return all_ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks", nargs="*", help="task dir names (default: all in tasks/)")
    ap.add_argument("--harbor", action="store_true", help="validate through harbor + docker")
    args = ap.parse_args()

    all_tasks = sorted(p for p in TASKS.iterdir() if (p / "task.toml").exists())
    tasks = [t for t in all_tasks if not args.tasks or t.name in args.tasks]
    unknown = set(args.tasks) - {t.name for t in tasks}
    if unknown:
        sys.exit(f"unknown task(s): {', '.join(sorted(unknown))}")

    if args.harbor:
        ok = validate_harbor(tasks, everything=not args.tasks)
    else:
        ok = all([validate_local(t) for t in tasks])
    print("\nALL TASKS VALID" if ok else "\nSOME TASKS NEED WORK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
