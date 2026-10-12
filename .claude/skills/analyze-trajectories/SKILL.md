---
name: analyze-trajectories
description: Analyzes Harbor benchmark runs in this repo (jobs/) by reading per-task agent trajectories and grader output. Produces a report of what went right, what went wrong (model vs harness vs task vs infra), and ranked, evidence-backed suggestions to improve the harness for that model. Use when asked to analyze a benchmark run, inspect trajectories, explain why tasks failed, compare two runs, or decide what to change in the harness next.
---

# Analyze benchmark trajectories

Turn one or more Harbor job directories into a diagnostic report: per-task outcomes, failure attribution, and concrete harness changes with evidence. The human-facing version of this workflow is `docs/improving-the-harness.md`.

For directory layout, the trajectory schema and known failure signatures, see [references/harbor_job_layout.md](references/harbor_job_layout.md).

## Workflow

Copy this checklist and track progress:

```
- [ ] 1. Locate job dir(s)
- [ ] 2. Quantitative sweep
- [ ] 3. Qualitative deep-dive on non-passing trials
- [ ] 4. Attribute every non-pass: model / harness / task / infra
- [ ] 5. Write the report
```

### 1. Locate job dirs

Jobs live in `jobs/<job-name>/`. A job dir has a top-level `config.json` and `result.json` plus one trial dir per task named `<task>__<id>`. If the user names a run loosely, glob `jobs/` for it.

A trial dir without files means the trial never ran or was never synced from the machine that ran it. Report it as unavailable; do not guess.

### 2. Quantitative sweep

From the repo root:

```bash
python3 scripts/results.py jobs/<job>                       # per task: reward, tests passed, exception
python3 scripts/results.py jobs/<job> --by category         # per category / difficulty
python3 scripts/results.py jobs/<job-a> jobs/<job-b> --compare   # task x run table, flips marked
```

`results.py` prints the pass rate, the mean % of tests passed, an infra-adjusted pass rate and average steps/tokens per trial. Also read the job's `config.json` (agent, `import_path`, model, kwargs such as `opencode_config`, timeouts): every harness suggestion has to point back at something there or in the run script.

When comparing runs, check that they differ in one thing only. If two things changed, say so: the delta can't be attributed.

### 3. Qualitative deep-dive

The numbers say *where* to look, not *why*. Read actual trajectories:

- **Every trial without a reward**: `exception.txt` and the tail of `trial.log`.
- **Every failing trial** (sample ~10 if there are many, spread across tasks and categories): `verifier/test-stdout.txt` for *what was wrong*, then the timeline for *what the agent did*.
- **2–3 passing trials** for contrast: what did they do that the failing ones didn't?
- **Every task that flipped between runs** (from `--compare`): read both trajectories side by side. This is the most direct evidence of what a harness change did.

Print a compact timeline per trial:

```bash
python3 scripts/trajectory.py jobs/<job> --task <task-name-substring>
python3 scripts/trajectory.py jobs/<job>/<trial> --full     # untruncated arguments and reasoning
```

Never `Read` `agent/trajectory.json` raw: observations embed whole files. Use `trajectory.py` or a short snippet that extracts only the steps you need (see the reference file).

### 4. Attribute every non-pass

Put each non-passing trial in exactly one bucket:

- **Model capability**: the agent explored, wrote, tested, and still produced wrong logic.
- **Harness**: the agent tried to act but the harness got in the way or didn't steer it: tool calls emitted as plain text and dropped, no test run because nothing told it to, searching for a hidden test suite, agent timeout too short for the model's speed, output truncated by `max_tokens`, a missing tool or MCP server, a rules file that misled it.
- **Task**: the instruction left out something the grader checks, or the grader checks wording instead of behaviour. Fix the task (see `docs/writing-tasks.md`), not the harness. Flag these prominently; they bias every model.
- **Infra**: container build or start failure, verifier timeout, endpoint/gateway errors. Not the model's fault; report the infra-adjusted pass rate alongside the raw one.

When a signature repeats (e.g. many trials ending without a test run), count how many non-passing trials it plausibly blocks. That count is the expected impact of fixing it.

### 5. Write the report

```markdown
# <job name(s)>: trajectory analysis

## Summary
Raw and infra-adjusted pass rate, mean % tests passed, trial counts, agent/model/harness config.
For comparisons: what differs between the runs, which tasks flipped in each direction.

## What went right
Behaviours common to passing trials, with 1–2 example trial names.

## What went wrong
One subsection per bucket and signature, ordered by count:
count, root cause, evidence (trial names + the decisive timeline step or verifier line).

## Task issues
Tasks whose instruction or grader looks wrong, with evidence. Omit if none.

## Harness improvements
Ranked list. Each item: the change, where to make it, evidence (trial names), expected impact
(how many non-passing trials it plausibly unblocks), and how to verify it (which job to re-run).
```

Harness knobs in this repo: `scripts/run_opencode.sh` (opencode provider config, `REASONING`, model options), `--ak` agent kwargs, a custom agent class passed to `--agent`, an `AGENTS.md`/rules file, `--mcp-config`, `--skill`, and timeouts in `task.toml`. See "Tweak the harness and context" in `docs/running-and-results.md`. Point every suggestion at one of these.

Keep suggestions task-agnostic. A rule that only helps because it encodes a specific task's answer or a grader detail is leaking the benchmark, not improving the harness.
