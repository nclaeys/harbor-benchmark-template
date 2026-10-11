#!/bin/bash
# Reference solution, run by Harbor's oracle agent (`harbor run -a oracle`).
# Harbor uploads this solution/ dir to /solution; we overlay the reference files
# onto the agent workspace. scripts/validate_tasks.py does the same overlay locally.
set -euo pipefail
cp -r /solution/app/. /app/
