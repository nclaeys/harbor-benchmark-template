#!/usr/bin/env bash
# Run the benchmark with the opencode agent against a self-hosted model behind an
# OpenAI-compatible endpoint (vLLM, SGLang, LiteLLM/Bifrost gateway, ...).
#
#   set -a && source .env && set +a
#   scripts/run_opencode.sh                          # all tasks
#   TASKS=tasks/python-clean-customers scripts/run_opencode.sh
#   REASONING=high JOB_NAME=gemma-high-r2 scripts/run_opencode.sh
#
# Env:
#   OPENAI_BASE_URL  (required) e.g. http://my-vllm-host:8000/v1, reachable from the containers
#   OPENAI_API_KEY   (required, any string for an unauthenticated vLLM)
#   MODEL            (required) model name as served, e.g. google/gemma-4-31B-it
#   REASONING        none | low | medium | high   (default: none)
#   TASKS            task dir or a single task  (default: tasks)
#   N_CONCURRENT     parallel trials            (default: 4)
#   JOB_NAME         default: <model>-<reasoning>-<timestamp>
set -euo pipefail
cd "$(dirname "$0")/.."

: "${OPENAI_BASE_URL:?set OPENAI_BASE_URL}"
: "${OPENAI_API_KEY:?set OPENAI_API_KEY}"
: "${MODEL:?set MODEL}"
REASONING="${REASONING:-none}"
TASKS="${TASKS:-tasks}"
N_CONCURRENT="${N_CONCURRENT:-4}"
JOB_NAME="${JOB_NAME:-${MODEL//\//-}-${REASONING}-$(date +%Y%m%d-%H%M%S)}"

case "$REASONING" in
  none)   MODEL_OPTS='"reasoning":false' ;;
  low|medium|high) MODEL_OPTS="\"reasoning\":true,\"options\":{\"reasoningEffort\":\"${REASONING}\"}" ;;
  *) echo "REASONING must be none|low|medium|high" >&2; exit 1 ;;
esac

# A custom opencode provider pointing at your endpoint. Harbor's --model is
# "<provider>/<model id>", so "selfhosted/google/gemma-4-31B-it" resolves to the
# model "google/gemma-4-31B-it" of the provider "selfhosted" defined here.
# Note: harbor stores agent kwargs (including this apiKey) in jobs/<job>/config.json.
OPENCODE_CFG=$(cat <<JSON
{"provider":{"selfhosted":{"npm":"@ai-sdk/openai-compatible","name":"Self-hosted","options":{"baseURL":"${OPENAI_BASE_URL}","apiKey":"${OPENAI_API_KEY}"},"models":{"${MODEL}":{"tool_call":true,${MODEL_OPTS}}}}}}
JSON
)

echo "Running $TASKS with opencode -> selfhosted/${MODEL} (reasoning=$REASONING), job=$JOB_NAME"
harbor run \
  -p "$TASKS" \
  --agent opencode \
  --model "selfhosted/${MODEL}" \
  --ak opencode_config="$OPENCODE_CFG" \
  --n-concurrent "$N_CONCURRENT" \
  --max-retries 1 \
  --job-name "$JOB_NAME" \
  -o jobs

python3 scripts/results.py "jobs/$JOB_NAME" --by category
