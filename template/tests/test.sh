#!/bin/bash
# Harbor verifier: grade the agent's /app with the hidden pytest tests.
#
# Contract: Harbor uploads this tests/ dir to /tests after the agent finishes,
# runs this script, captures stdout into verifier/test-stdout.txt and reads the
# grade from /logs/verifier/reward.txt. reward = 1 iff every test passes.
# The pytest summary line ("3 failed, 11 passed in 0.4s") stays in the log, so
# scripts/results.py can compute partial credit afterwards. Always exit 0:
# reward.txt is the grade, a non-zero exit would look like a verifier crash.
set -u
mkdir -p /logs/verifier /logs/artifacts

export BENCH_TARGET=/app
cd /tests

python -m pytest /tests -rA -p no:cacheprovider 2>&1 | tee /logs/verifier/pytest.log
status=${PIPESTATUS[0]}

# Keep the agent's answer for post-hoc inspection (lands in <trial>/artifacts/).
tar -C /app --exclude=.terraform -cf - . 2>/dev/null | tar -C /logs/artifacts -xf - 2>/dev/null || true

if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit 0
