# Writing tasks

How a task is put together, how to add one and how to check that it measures something.
For the why and the overall recipe, see the [README](../README.md).

## Anatomy of a task

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

## Tips

- Tag every task with `category` and `difficulty` in `task.toml [metadata]`. "Model
  X is fine for Python data wrangling but not for Terraform" is a far more useful
  conclusion than one overall score. Add `source_ticket` so you can find the original.
- Keep the instruction honest. If a model fails because the ticket left something
  out, fix the instruction, not the grader. The benchmark should measure the model, not
  your ticket-writing.
- Budget the image build. Terraform images download OpenTofu and the providers on the
  first build, and Harbor caches the image after that. Raise `build_timeout_sec` if needed.
