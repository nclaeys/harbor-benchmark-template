#!/usr/bin/env python3
"""Print a compact, one-line-per-step timeline of a Harbor trial.

agent/trajectory.json embeds whole files in its observations, which makes it
hard to skim. This prints what the agent did per step (tool calls, or its
message), the first line of its reasoning, and the outcome of the trial, so
you can see at a glance whether it explored, tested, looped or gave up.

Usage:
    python scripts/trajectory.py jobs/<job>/<trial>
    python scripts/trajectory.py jobs/<job> --task affine     # every trial whose name contains "affine"
    python scripts/trajectory.py jobs/<job>/<trial> --full    # don't truncate arguments and reasoning
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def one_line(text: str, limit: int | None) -> str:
    text = " ".join(str(text).split())
    return text if limit is None or len(text) <= limit else text[: limit - 1] + "…"


def outcome(trial: Path) -> str:
    reward = trial / "verifier" / "reward.txt"
    result = json.loads((trial / "result.json").read_text()) if (trial / "result.json").exists() else {}
    exception = (result.get("exception_info") or {}).get("exception_type")
    parts = []
    if reward.exists() and reward.read_text().strip():
        parts.append(f"reward {reward.read_text().strip()}")
    else:
        parts.append("no reward")
    if exception:
        parts.append(exception)
    return ", ".join(parts)


def print_trial(trial: Path, full: bool) -> None:
    limit = None if full else 90
    print(f"\n== {trial.name}   ({outcome(trial)})")
    path = trial / "agent" / "trajectory.json"
    if not path.exists():
        print("   no agent/trajectory.json (agent crashed early, or this agent doesn't write one)")
        return
    trajectory = json.loads(path.read_text())
    for step in trajectory.get("steps", []):
        if step.get("source") != "agent":
            print(f"   {step.get('step_id', '?'):>3} {step.get('source', '?')}: {one_line(step.get('message') or '', limit)}")
            continue
        calls = step.get("tool_calls") or []
        if calls:
            action = "; ".join(
                f"{c.get('function_name')}({one_line(json.dumps(c.get('arguments', {})), None if full else 60)})"
                for c in calls
            )
        else:
            action = f"says: {one_line(step.get('message') or '', limit)}"
        print(f"   {step.get('step_id', '?'):>3} {action}")
        reasoning = (step.get("reasoning_content") or "").strip()
        if reasoning:
            print(f"       thinks: {one_line(reasoning.splitlines()[0], limit)}")
    metrics = trajectory.get("final_metrics") or {}
    if metrics:
        print(f"   -- {metrics.get('total_steps')} steps, {metrics.get('total_prompt_tokens') or 0:,} prompt tokens, "
              f"{metrics.get('total_completion_tokens') or 0:,} completion tokens")
    stdout = trial / "verifier" / "test-stdout.txt"
    if stdout.exists():
        last = [l for l in stdout.read_text(errors="replace").splitlines() if l.strip()]
        if last:
            print(f"   -- verifier: {one_line(last[-1], 120)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, help="a trial dir, or a job dir together with --task")
    ap.add_argument("--task", help="substring of the trial names to print (when path is a job dir)")
    ap.add_argument("--full", action="store_true", help="don't truncate arguments and reasoning")
    args = ap.parse_args()

    if (args.path / "result.json").exists() and (args.path / "agent").exists():
        trials = [args.path]
    else:
        trials = sorted(d for d in args.path.iterdir() if d.is_dir() and (d / "result.json").exists())
        if args.task:
            trials = [d for d in trials if args.task in d.name]
        elif len(trials) > 1:
            print(f"{args.path} is a job dir with {len(trials)} trials; pass --task <substring>", file=sys.stderr)
            return 1
    for trial in trials:
        print_trial(trial, args.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
