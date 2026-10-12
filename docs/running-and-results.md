# Running the benchmark and reading the results

How to run your tasks with Harbor against self-hosted and frontier models, how to tweak
the harness and the agent's context, and how to read the scores. To write tasks first,
see [Writing tasks](writing-tasks.md).

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

## Tweak the harness and context

A score belongs to *model x harness*, and the context you give the agent is part of the
harness. Below are the four knobs I use most. Change one at a time, give every variant
its own `--job-name`, and compare the runs with `results.py`.

There are two places to put context, and the choice matters:

- In the task (`environment/`, `task.toml`): only that task gets it. Use this for context
  the real repo would have had anyway, such as the repo's own `AGENTS.md`.
- On the command line (`--ak`, `--mcp-config`, `--skill`, `--agent`): every task in the
  run gets it, and the tasks stay untouched. Use this for the harness experiments you
  want to compare.

Whatever you add, don't leak the grader into it. A rule like "dates are day-first" in a
shared rules file turns a test of understanding into a test of reading.

### Change the agent loop

The cheapest change is a different agent. Harbor ships many of them (`claude-code`,
`codex`, `opencode`, `openhands`, `mini-swe-agent`, `aider`, ...; see `harbor run --help`),
and running the same model in two of them shows how much the harness itself matters.

Most agents also take kwargs. You can find them in the agent's `__init__` and `CLI_FLAGS`
in Harbor's source (`harbor/agents/installed/<agent>.py`). For example:

```bash
# Claude Code: limit turns, set the effort, add to the system prompt
harbor run -p tasks -a claude-code -m anthropic/<model-id> \
  --ak max_turns=50 --ak reasoning_effort=high \
  --ak append_system_prompt="$(cat prompts/rules.md)" \
  --job-name claude-code-rules-run1 -o jobs

# opencode: anything in opencode.json, merged into the config Harbor writes
--ak opencode_config='{"agent":{"build":{"temperature":0.2}}}'
```

To change the loop itself, write your own agent class and pass its import path to
`--agent`. The easiest route is to subclass an existing agent and override one method,
e.g. to wrap the instruction:

```python
# agents/opencode_plan.py
from harbor.agents.installed.opencode import OpenCode

class OpenCodePlan(OpenCode):
    async def run(self, instruction, environment, context):
        instruction += (
            "\n\nBefore you edit anything, write a short plan. "
            "When you are done, run whatever tests you can find."
        )
        await super().run(instruction, environment, context)
```

```bash
PYTHONPATH=. harbor run -p tasks --agent agents.opencode_plan:OpenCodePlan \
  --model "selfhosted/$MODEL" --ak opencode_config="$OPENCODE_CFG" \
  --job-name opencode-plan-run1 -o jobs
```

For a loop of your own from scratch, subclass `harbor.agents.base.BaseAgent` and
implement `setup()` (install your tools in the container) and `run()` (call the model,
execute its commands with `environment.exec(...)` until it is done).

### Add an AGENTS.md

Agents read a rules file from the working directory (`/app`): opencode and Codex read
`AGENTS.md`.

To give every task the same rules without editing each workspace, pass them on the
command line instead (`append_system_prompt` for Claude Code, a subclassed agent as
above for the others), or `COPY` a shared file in each Dockerfile.

The file ends up in the graded workspace too. That is fine for the grader in this
template, which only looks at the files it checks.

### Add MCP servers

Pass a Claude-style `.mcp.json` (or a Harbor TOML/YAML file) to `--mcp-config`. Harbor
registers the servers with the agent, for every agent that supports MCP (Claude Code,
opencode, Codex, OpenHands, Gemini CLI, ...):

```json
{
  "mcpServers": {
    "docs":   { "type": "http",  "url": "http://my-docs-mcp:8080/mcp" },
    "tofu-docs": { "command": "tofu-docs-mcp", "args": ["--offline"] }
  }
}
```

```bash
harbor run -p tasks -a claude-code -m anthropic/<model-id> \
  --mcp-config mcp/docs.json --job-name claude-code-mcp-run1 -o jobs
```

### Add skills

A skill is a directory with a `SKILL.md`. Pass it with `--skill`, as a local path or a
git source (`org/repo[@ref]` or a GitHub URL). Harbor uploads it into the container and
copies it to the agent's skills directory. Claude Code, Codex, opencode, Gemini CLI and
most other CLI agents support this. If you're unsure, look for `skills_dir` in the agent's
source.

```bash
harbor run -p tasks -a claude-code -m anthropic/<model-id> \
  --skill skills/terraform-conventions --skill my-org/agent-skills@v1 \
  --job-name claude-code-skills-run1 -o jobs
```

## Read the results

Point `results.py` at one or more job directories:

```bash
python3 scripts/results.py jobs/my-model-run1
python3 scripts/results.py jobs/my-model-run1 jobs/my-model-run2 --by category
python3 scripts/results.py jobs/my-model-run1 --by difficulty
python3 scripts/results.py jobs/my-model-run1 jobs/my-model-run2 --compare   # task x run, flips marked
```

The output looks like this (the numbers are illustrative):

```
== my-model-run1
   task                                     reward     tests note
   python-clean-customers                        0     13/14
   terraform-s3-hardening                        1     16/16

   trials: 2   pass rate: 50.0%   mean tests passed: 96.4%
   per trial: 9.5 steps, 61,204 input tokens, 3,870 output tokens

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
look at which tasks flipped, not only at the total. `--compare` lists them, and the
Compare page in `harbor view` shows the same matrix (see
[Improving the harness](improving-the-harness.md#find-the-failures)).

Trials that crashed before grading (agent timeout, container build failure) have no
reward and count as 0. `results.py` lists them with their exception type and, if any
of them weren't caused by the agent, also prints an infra-adjusted pass rate that leaves
those out. Check what the failures are before you blame the model.

## Tips

- Re-tune the harness per model. A score belongs to *model x harness*, not to the
  model. The agent, its system prompt or rules file, the reasoning effort, the sampling
  settings and the serving stack (tool-call parser, chat template) all move the score,
  and what works for one model can hurt another. Compare each model with a reasonable
  setup for *that* model, and read a few trajectories before you trust a number. See
  [Tweak the harness and context](#tweak-the-harness-and-context) for the knobs and
  [Improving the harness for a model](improving-the-harness.md) for how to find out
  which ones to turn.
