# Build your own coding benchmark (Harbor template)

This is a template for building a private coding benchmark out of tickets your team
has already solved. It runs unattended with [Harbor](https://github.com/laude-institute/harbor)
against any model, either a self-hosted one behind an OpenAI-compatible endpoint (vLLM,
SGLang, a gateway) or a frontier API.

It goes with my talk *"Are Frontier Models Overkill for Coding?"*.

You get the scaffolding, the scripts and two small example tasks. You don't get our own
benchmark tasks. Those stay private on purpose (see [Keep it private](#tips)).

## Why build your own benchmark

Public coding benchmarks (LiveCodeBench, Aider polyglot, SWE-bench) tell you how good a
model is at *those* problems. The question you actually have is whether a model is good
enough for *your* work.

Your own tickets also differ from public tasks in ways that matter:

- there is almost always existing code or input data to understand next to the
  instruction.
- the model needs to know your external dependencies (Terraform providers, Helm
  charts, internal libraries), not just the language.
- they were never on the internet, so they cannot be in anyone's training data.

## How to start your own benchmark

1. Pick 20-30 tickets you solved in the last 2-3 months. They should be recent, so they
   reflect the work you do today, and already solved, so the reference solution exists
   (the merged PR). Spread them across your task categories in roughly the proportion
   you do them, e.g. "10x messy data in Python, 8x Terraform, 5x troubleshooting, ...".
   Skip tickets whose outcome you can only judge by eye.
2. Per ticket, write four things. Once you have the rhythm, each ticket takes about
   30-60 minutes:
   - `instruction.md`: the ticket rewritten so it is self-contained. Everything the
     grader checks must be stated here. Grade what you asked for and nothing hidden.
   - `environment/app/`: the starter workspace, i.e. the relevant code and data as they
     were before the fix. Trim it to what's needed and replace client data with made-up data.
   - `tests/`: a hidden pytest grader with one test per requirement. The agent never sees it.
   - `solution/app/`: the files as they were after the fix.
3. Make grading fully automatic and offline. That means no human judgement, no cloud
   credentials and no network at grading time. For Terraform I use a structural check
   with a Python HCL parser plus `tofu validate` against an offline provider mirror (see
   the example). It won't prove the code applies, but it catches the vast majority of
   mistakes and it runs anywhere.
4. Validate every task. The reference solution must pass and the untouched starter
   must fail (`scripts/validate_tasks.py`).
5. Run it against the models you care about, run it again, and read the results
   with both metrics (see [Read the results](docs/running-and-results.md#read-the-results)).

If you can't run a benchmark unattended, you won't run it repeatedly. And a benchmark
you don't re-run is a one-time test.

## Repo layout

The repo looks like this:

```
README.md
docs/
  writing-tasks.md            # task anatomy, adding and validating tasks
  running-and-results.md      # harbor runs, tweaking the harness, reading results
  improving-the-harness.md    # reading trajectories, attributing failures, iterating per model
  images/                     # screenshots of harbor view
requirements-dev.txt          # host-side deps for local validation (pytest, python-hcl2)
.env.example                  # endpoint + keys; copy to .env (gitignored)
tasks/                        # the benchmark: one Harbor task per directory
  python-clean-customers/     # example: normalize a messy CSV
  terraform-s3-hardening/     # example: harden an existing S3 module (AWS provider)
template/                     # skeleton that scripts/new_task.py copies
scripts/
  new_task.py                 # scaffold a task from template/ (or clone an existing one)
  validate_tasks.py           # reference must pass, starter must fail (local or via harbor)
  run_opencode.sh             # run all tasks with opencode against your OpenAI-compatible endpoint
  results.py                  # pass rate + % tests passed per job, grouped or compared across runs
  trajectory.py               # one-line-per-step timeline of a trial
.claude/skills/
  analyze-trajectories/       # Claude Code skill: diagnose a run and suggest harness changes
jobs/                         # harbor output (gitignored)
```

## Where to go next

- [Writing tasks](docs/writing-tasks.md): what a task looks like, how to scaffold one
  with `scripts/new_task.py` and how to validate it.
- [Running and reading results](docs/running-and-results.md): running the benchmark with
  Harbor against self-hosted and frontier models, tweaking the harness and context
  (agent loop, `AGENTS.md`, MCP, skills), and reading the scores.
- [Improving the harness for a model](docs/improving-the-harness.md): finding failures,
  reading trajectories in `harbor view`, telling model failures from harness failures,
  and iterating, with a worked example.

## Tips

- Keep it private. Don't push your tasks to a public repo and don't paste them into
  a hosted chat. Once a task is on the internet it can end up in training data, and
  from then on it measures memory instead of skill. Use made-up data in the workspaces,
  never client data, credentials or internal hostnames.
- Refresh it. Every few months, add tickets from the most recent period and retire
  tasks that every model now solves.

## License

MIT, see [LICENSE](LICENSE).