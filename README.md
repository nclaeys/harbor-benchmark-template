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

## The two-day recipe

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
   with both metrics below.

If you can't run a benchmark unattended, you won't run it repeatedly. And a benchmark
you don't re-run is a one-time test.

## Repo layout

The repo looks like this:

```
README.md
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
  results.py                  # pass rate + % tests passed for a job dir, optionally grouped
jobs/                         # harbor output (gitignored)
```

### Anatomy of a task

Every task follows Harbor's task format:

```
tasks/<name>/
  task.toml                 # Harbor config: timeouts, build timeout, [metadata] category/difficulty
  instruction.md            # the prompt the agent gets
  environment/
    Dockerfile              # image the agent works in (and the grader later runs in)
    app/                    # starter workspace, COPY'd to /app (the agent's working dir)
  tests/                    # uploaded to /tests only AFTER the agent finishes
    test.sh                 # Harbor's entry point: runs pytest, writes /logs/verifier/reward.txt
    conftest.py, test_*.py  # the hidden grader, reads the workspace from $BENCH_TARGET (default /app)
  solution/                 # uploaded to /solution only for the oracle agent
    solve.sh                # copies solution/app/ over /app
    app/                    # reference files (the "after" state of the ticket)
```

Harbor builds `environment/Dockerfile`, starts a container and runs the agent with
`instruction.md` in `/app`. When the agent is done, Harbor uploads `tests/` and runs
`tests/test.sh`. The reward is whatever `test.sh` writes to `/logs/verifier/reward.txt`.
In this template that is `1` if every test passed and `0` otherwise. The script's stdout,
including pytest's summary line, ends up in `jobs/<job>/<trial>/verifier/test-stdout.txt`,
and `results.py` reads it from there for partial credit.

## Add a task

Set up a venv and scaffold the task:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

# Python-flavoured skeleton
.venv/bin/python scripts/new_task.py fix-invoice-rounding --category python-messy-data --difficulty medium

# or clone an existing task to reuse its image and grader helpers (e.g. Terraform)
.venv/bin/python scripts/new_task.py gcs-bucket-iam --from terraform-s3-hardening
```

Then fill in `instruction.md`, `environment/app/`, `solution/app/`, `tests/` and the
`[metadata]` in `task.toml`. This is what I think makes a grader good:

- One test per requirement. The pytest summary then gives you partial credit.
- At least one easy-to-miss edge case that the instruction states but a sloppy
  implementation gets wrong. The examples use day-first dates, `1.234,50` and
  where `bucket_key_enabled` goes.
- Run the solution on input the agent never saw (`tests/fixtures/`), so hard-coding
  the expected output doesn't pass.
- Check behaviour, not wording. Parse the HCL instead of grepping strings, and run the
  script instead of reading it.
- Put grader dependencies in the Dockerfile. The grader runs in the same container
  the agent used, so the agent can use anything you install there too (pytest,
  `python-hcl2`, OpenTofu). I think that's realistic, because a developer would have them.

For Terraform tasks, copy `tests/tfgrader.py` (python-hcl2 parsing + `tofu validate`)
and the Dockerfile from `terraform-s3-hardening`. Then change the mirrored providers in
the Dockerfile to the ones your task needs.

## Validate a task

Every task needs two properties: the reference solution passes and the untouched
starter workspace fails. If the reference fails, the task can't be solved. If the
starter passes, the task measures nothing.

You can validate on the host or in Docker:

```bash
# fast, on the host, no Docker (tofu validate is skipped if tofu isn't installed)
.venv/bin/python scripts/validate_tasks.py
.venv/bin/python scripts/validate_tasks.py python-clean-customers

# the real thing: builds the images and runs Harbor's oracle agent (solution/solve.sh,
# must score 1) and nop agent (does nothing, must score 0) in Docker
.venv/bin/python scripts/validate_tasks.py --harbor
```

The output looks like this:

```
OK   python-clean-customers
     starter   (must FAIL): 0/14 tests                   ok
     reference (must PASS): 14/14 tests                  ok
OK   terraform-s3-hardening
     starter   (must FAIL): 6/16 tests                   ok
     reference (must PASS): 16/16 tests                  ok
```

Run `--harbor` at least once per task. It is the only check that the Dockerfile builds,
that `test.sh` works inside the image and that `tofu validate` works offline there.

## Run it

You need Harbor (`uv tool install harbor`) and a running Docker daemon. Each task runs in
its own container. Harbor installs the agent (opencode, Claude Code, Codex, ...) into that
container, and the agent calls the model from there.

### Against a self-hosted model (OpenAI-compatible endpoint)

Put your endpoint in `.env` and run the script:

```bash
cp .env.example .env    # set OPENAI_BASE_URL, OPENAI_API_KEY, MODEL
set -a && source .env && set +a

scripts/run_opencode.sh                               # all tasks
REASONING=high scripts/run_opencode.sh                # with reasoning, if the model supports it
TASKS=tasks/terraform-s3-hardening scripts/run_opencode.sh   # a single task
```

Under the hood, the script runs this:

```bash
OPENCODE_CFG='{"provider":{"selfhosted":{"npm":"@ai-sdk/openai-compatible","name":"Self-hosted",
  "options":{"baseURL":"'$OPENAI_BASE_URL'","apiKey":"'$OPENAI_API_KEY'"},
  "models":{"'$MODEL'":{"tool_call":true}}}}}'

harbor run -p tasks \
  --agent opencode \
  --model "selfhosted/$MODEL" \
  --ak opencode_config="$OPENCODE_CFG" \
  --n-concurrent 4 --max-retries 1 \
  --job-name my-model-run1 -o jobs
```

The endpoint must be reachable from inside the task containers. `localhost` there is
the container, not your machine, so use the host's IP or DNS name (or
`host.docker.internal` on Docker Desktop). For vLLM, serve the model with tool calling
enabled (`--enable-auto-tool-choice --tool-call-parser <parser for your model>`). A wrong
or missing tool-call parser is the most common reason an open model "fails" every task.

### Against a frontier API

Each vendor has its own harness, and you can also run the frontier model in opencode:

```bash
# Claude Code (Anthropic's own harness)
export ANTHROPIC_API_KEY=...
harbor run -p tasks -a claude-code -m anthropic/<model-id> -n 4 --job-name claude-code-run1 -o jobs

# Codex CLI (OpenAI's own harness)
export OPENAI_API_KEY=...
harbor run -p tasks -a codex -m openai/<model-id> -n 4 --job-name codex-run1 -o jobs

# Same harness as your self-hosted run (opencode), for an apples-to-apples comparison
unset OPENAI_BASE_URL   # otherwise harbor points opencode's openai provider at your endpoint
harbor run -p tasks -a opencode -m openai/<model-id> -n 4 --job-name opencode-frontier-run1 -o jobs
harbor run -p tasks -a opencode -m anthropic/<model-id> -n 4 --job-name opencode-claude-run1 -o jobs
```

Use `harbor view jobs` to inspect runs. Each trial directory has the agent's trajectory
(`agent/`), the graded workspace (`artifacts/`) and the grader output (`verifier/`).

## Read the results

Point `results.py` at one or more job directories:

```bash
python3 scripts/results.py jobs/my-model-run1
python3 scripts/results.py jobs/my-model-run1 jobs/my-model-run2 --by category
python3 scripts/results.py jobs/my-model-run1 --by difficulty
```

The output looks like this (the numbers are illustrative):

```
== my-model-run1
   task                                     reward     tests note
   python-clean-customers                        0     13/14
   terraform-s3-hardening                        1     16/16

   trials: 2   pass rate: 50.0%   mean tests passed: 96.4%

   by category:
                              n  pass rate  tests passed
   python-messy-data          1       0.0%         92.9%
   terraform                  1     100.0%        100.0%
```

I look at two numbers:

- Pass rate (reward 1 means every hidden test passed). This is the number that
  matters in practice, because a ticket that is 90% done is not done.
- Mean % of tests passed (partial credit, parsed from the pytest summary line).
  On 20-30 tasks the pass rate is noisy, and one task flipping moves it 3-5 points.
  Partial credit moves less between runs and shows *how close* a model got.

Agents and LLM serving are not deterministic. On a 25-task benchmark, expect run-to-run
swings of up to ~10 points for the same model and harness. We once saw a +24 point
"improvement" from a harness change shrink to +4 on a re-run. Re-run before you trust
any delta smaller than ~10 points (`harbor run -k 3` runs every task three times), and
look at which tasks flipped, not only at the total.

Trials that crashed before grading (agent timeout, container build failure) have no
reward and count as 0. `results.py` lists them with their exception type. Check whether
they are infrastructure failures before you blame the model.

## Tips

- Tag every task with `category` and `difficulty` in `task.toml [metadata]`. "Model
  X is fine for Python data wrangling but not for Terraform" is a far more useful
  conclusion than one overall score. Add `source_ticket` so you can find the original.
- Keep it private. Don't push your tasks to a public repo and don't paste them into
  a hosted chat. Once a task is on the internet it can end up in training data, and
  from then on it measures memory instead of skill. Use made-up data in the workspaces,
  never client data, credentials or internal hostnames.
- Re-tune the harness per model. A score belongs to *model x harness*, not to the
  model. The agent, its system prompt or rules file, the reasoning effort, the sampling
  settings and the serving stack (tool-call parser, chat template) all move the score,
  and what works for one model can hurt another. Compare each model with a reasonable
  setup for *that* model, and read a few trajectories before you trust a number.
- Keep the instruction honest. If a model fails because the ticket left something
  out, fix the instruction, not the grader. The benchmark should measure the model, not
  your ticket-writing.
- Refresh it. Every few months, add tickets from the most recent period and retire
  tasks that every model now solves.
- Budget the image build. Terraform images download OpenTofu and the providers on the
  first build, and Harbor caches the image after that. Raise `build_timeout_sec` if needed.

## License

MIT, see [LICENSE](LICENSE).