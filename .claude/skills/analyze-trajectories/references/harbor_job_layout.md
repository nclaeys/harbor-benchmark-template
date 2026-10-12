# Harbor job layout, trajectory schema and failure signatures

## Contents
- Job directory layout
- Trial outcome detection
- Trajectory schema (ATIF)
- Extracting from large trajectories
- Known failure signatures

## Job directory layout

```
jobs/<job>/
├── config.json                     full run config: agents[].name / import_path / model_name / kwargs
│                                   (e.g. opencode_config), timeouts. May contain API keys.
├── result.json                     aggregate stats: n_total/n_errored trials, stats.evals.*
├── job.log
└── <task>__<id>/                   one trial per task (and per attempt with -k N)
    ├── result.json                 task_name, task_id.path, agent_info, agent_result
    │                               (n_input_tokens, n_output_tokens), exception_info
    ├── config.json                 per-trial copy of the config
    ├── trial.log                   harness-side log (setup, agent exec, verifier)
    ├── exception.txt               ONLY present when the trial crashed or timed out
    ├── agent/
    │   ├── trajectory.json         the transcript (schema below)
    │   └── <agent>.txt             raw agent stdout (e.g. opencode.txt)
    ├── verifier/
    │   ├── reward.txt              "1" solved, "0" failed; missing => never graded
    │   └── test-stdout.txt         hidden pytest output: the "why it failed" evidence
    └── artifacts/                  the graded workspace as the agent left it
```

Task metadata (`category`, `difficulty`, `source_ticket`) is in `tasks/<task>/task.toml [metadata]`.

## Trial outcome detection

- `verifier/reward.txt` is `1` → **PASS**
- `reward.txt` missing or empty → **ERROR** (check `exception_info.exception_type` in `result.json`)
- otherwise → **FAIL** (`test-stdout.txt` has the pytest summary, e.g. `3 failed, 11 passed`)

Exception types: `AgentTimeoutError` (agent loop hit `[agent] timeout_sec`; counts against the model/harness), `VerifierTimeoutError`, environment build/start errors, endpoint errors in a `RuntimeError` message (infra). `scripts/results.py` treats agent-side exceptions as model failures and everything else as infra.

## Trajectory schema (ATIF)

`agent/trajectory.json` = `{schema_version: "ATIF-v1.x", session_id, agent: {name, version, model_name}, steps: [...], final_metrics: {total_prompt_tokens, total_completion_tokens, total_steps}}`.

- `steps[0]`: `{step_id: 1, source: "user", message: <the instruction>}`
- later steps: `source: "agent"` with `message` (`"(tool use)"` when the turn is a tool call), `reasoning_content` (model thinking), `tool_calls: [{tool_call_id, function_name, arguments}]`, `observation: {results: [{source_call_id, content}]}`, `metrics: {prompt_tokens, completion_tokens}`.

opencode tool names: `read`, `write`, `edit`, `patch`, `glob`, `grep`, `list`, `bash`, `todowrite`, `todoread`. Claude Code: `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `TodoWrite`, ...

## Extracting from large trajectories

Use `python3 scripts/trajectory.py <trial_dir>` first. For anything it doesn't show, extract with a snippet instead of reading the file:

```bash
# the observations of steps that mention an error
python3 -c "
import json,sys
t=json.load(open(sys.argv[1]))
for s in t['steps']:
    for r in (s.get('observation') or {}).get('results') or []:
        c=str(r.get('content'))
        if any(k in c for k in ('Error','Traceback','FAILED','not found')):
            print(s['step_id'], c[:400].replace(chr(10),' | '))
" <trial_dir>/agent/trajectory.json
```

The last agent step and the observations containing `Error`, `Traceback` or `FAILED` are usually the decisive evidence.

## Known failure signatures

- **Never tested (harness, often)**: solution written, no `bash` step that runs it, wrong logic. If a rules file telling it to verify by execution fixes it on re-run, it was harness. If it ran its own checks and was still wrong, it's the model.
- **Hunting the hidden tests (harness)**: repeated `find / -name '*test*'`, `ls -R`, pytest discovery that collects 0 items. The grader is only uploaded after the agent finishes. Tell the agent there is no test suite and to write its own checks.
- **Unparsed tool calls (harness/serving)**: the model emits its native tool-call syntax as plain text (e.g. `<|tool_call>call:bash{...}`); the harness records it as a final message and the run ends while trying to act. Usually a wrong or missing tool-call parser / chat template in the serving stack.
- **Agent timeout loops (harness)**: `AgentTimeoutError` after many repeated, near-identical calls or edits. Bound the loop in the rules ("at most 3 test iterations") or raise the timeout if the model is just slow.
- **Empty stop / truncation (harness)**: final turn with ~0 completion tokens right after writing code. Often `max_tokens` too low.
- **Interface drift (model or task)**: renamed functions, changed signatures, different error messages. Model if the instruction specified them; task if it didn't.
- **Setup crashes, verifier timeouts (infra)**: leave out of the model score; report the infra-adjusted pass rate.
