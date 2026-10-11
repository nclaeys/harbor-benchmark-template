#!/usr/bin/env python3
"""Summarize a Harbor job: binary pass rate AND mean fraction of tests passed.

Binary pass rate (reward 1 = every hidden test passed) is the headline, but on
20-30 tasks it is noisy: one flaky task moves it by 3-5 points. The fraction of
pytest tests passed per task (parsed from the pytest summary line in
verifier/test-stdout.txt) gives partial credit and moves less between runs.

Usage:
    python scripts/results.py jobs/<job-name>
    python scripts/results.py jobs/<job-name> --by category      # or difficulty, language, ...
    python scripts/results.py jobs/job-a jobs/job-b --by difficulty
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARY_RE = re.compile(r"^=+ (.+) in [\d.]+s.*=+$")
SUMMARY_LINE_Q = re.compile(r"^\d+ (passed|failed|errors?|skipped)\b.* in [\d.]+s")
COUNT_RE =re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


@dataclass
class Trial:
    task: str                 # task dir name
    reward: float | None      # None = no reward (infra/agent crash before grading)
    passed: int = 0
    failed: int = 0           # failed + errors
    skipped: int = 0
    exception: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def test_fraction(self) -> float:
        total = self.passed + self.failed
        return self.passed / total if total else 0.0

    @property
    def solved(self) -> bool:
        return (self.reward or 0.0) >= 1.0


def parse_pytest_summary(text: str) -> tuple[int, int, int] | None:
    """Return (passed, failed+errors, skipped) from the LAST pytest summary line.

    Matches both "===== 3 failed, 11 passed in 0.40s =====" (default/-rA) and
    the bare "3 failed, 11 passed in 0.40s" that `pytest -q` prints.
    """
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not (SUMMARY_RE.match(line) or SUMMARY_LINE_Q.match(line)):
            continue
        counts = defaultdict(int)
        for n, kind in COUNT_RE.findall(line):
            counts["error" if kind.startswith("error") else kind] += int(n)
        return counts["passed"], counts["failed"] + counts["error"], counts["skipped"]
    return None


def task_metadata(task_path: str | None, task_dir_name: str, tasks_dir: Path) -> dict:
    candidates = []
    if task_path:
        candidates += [Path(task_path), ROOT / task_path]
    candidates.append(tasks_dir / task_dir_name)
    for c in candidates:
        if (c / "task.toml").exists():
            return tomllib.loads((c / "task.toml").read_text()).get("metadata", {})
    return {}


def load_trials(job_dir: Path, tasks_dir: Path = ROOT / "tasks") -> list[Trial]:
    trials = []
    for result_file in sorted(job_dir.glob("*/result.json")):
        trial_dir = result_file.parent
        result = json.loads(result_file.read_text())
        task_path = (result.get("task_id") or {}).get("path")
        task = Path(task_path).name if task_path else result.get("task_name", trial_dir.name)

        reward = None
        reward_txt = trial_dir / "verifier" / "reward.txt"
        if reward_txt.exists() and reward_txt.read_text().strip():
            reward = float(reward_txt.read_text().strip())
        elif (result.get("verifier_result") or {}).get("rewards"):
            reward = float(result["verifier_result"]["rewards"].get("reward", 0.0))

        t = Trial(task=task, reward=reward,
                  exception=(result.get("exception_info") or {}).get("exception_type"),
                  metadata=task_metadata(task_path, task, tasks_dir))
        stdout = trial_dir / "verifier" / "test-stdout.txt"
        if stdout.exists():
            counts = parse_pytest_summary(stdout.read_text(errors="replace"))
            if counts:
                t.passed, t.failed, t.skipped = counts
        trials.append(t)
    return trials


def summarize(trials: list[Trial]) -> tuple[int, float, float]:
    n = len(trials)
    if not n:
        return 0, 0.0, 0.0
    return n, 100 * sum(t.solved for t in trials) / n, 100 * sum(t.test_fraction for t in trials) / n


def print_job(job_dir: Path, by: str | None, tasks_dir: Path) -> None:
    trials = load_trials(job_dir, tasks_dir)
    print(f"\n== {job_dir.name}")
    if not trials:
        print("   no trials found (expected <job>/<trial>/result.json)")
        return

    print(f"   {'task':<40} {'reward':>6} {'tests':>9} {'note'}")
    for t in sorted(trials, key=lambda t: t.task):
        tests = f"{t.passed}/{t.passed + t.failed}" if (t.passed + t.failed) else "-"
        note = t.exception or ("no reward" if t.reward is None else "")
        if t.skipped:
            note = (note + f" {t.skipped} skipped").strip()
        reward = "-" if t.reward is None else f"{t.reward:g}"
        print(f"   {t.task:<40} {reward:>6} {tests:>9} {note}")

    n, pass_rate, frac = summarize(trials)
    errors = sum(1 for t in trials if t.reward is None)
    print(f"\n   trials: {n}   pass rate: {pass_rate:.1f}%   mean tests passed: {frac:.1f}%"
          + (f"   ({errors} without a reward, counted as 0)" if errors else ""))

    if by:
        groups = defaultdict(list)
        for t in trials:
            groups[str(t.metadata.get(by, "(unset)"))].append(t)
        print(f"\n   by {by}:")
        print(f"   {'':<24} {'n':>3} {'pass rate':>10} {'tests passed':>13}")
        for key in sorted(groups):
            n, pass_rate, frac = summarize(groups[key])
            print(f"   {key:<24} {n:>3} {pass_rate:>9.1f}% {frac:>12.1f}%")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job_dirs", nargs="+", type=Path)
    ap.add_argument("--by", help="group by this key from task.toml [metadata] (e.g. category, difficulty)")
    ap.add_argument("--tasks-dir", type=Path, default=ROOT / "tasks",
                    help="where to look up task.toml for metadata (default: tasks/)")
    args = ap.parse_args()
    for job_dir in args.job_dirs:
        print_job(job_dir, args.by, args.tasks_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
