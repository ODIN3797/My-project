#!/usr/bin/env bash
# Field-validation helper; never downloads/uploads customer data.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo 'Usage: bash scripts/validate_local_real_bag.sh /path/to/real.mcap [unknown|physical|simulation|synthetic] [output_dir]' >&2
  exit 2
fi
BAG="$1"
ORIGIN="${2:-unknown}"
OUT="${3:-field_results}"
if [[ ! -r "$BAG" ]]; then echo "Cannot read: $BAG" >&2; exit 2; fi
case "$BAG" in *.mcap|*.db3|*.sqlite3) ;; *) echo 'Expect .mcap/.db3/.sqlite3' >&2; exit 2;; esac
if ! command -v python3 >/dev/null; then echo 'python3 not found' >&2; exit 2; fi
set +e
python3 -m robot_incident_analyzer field-validate "$BAG" --origin "$ORIGIN" --output "$OUT"
STATUS=$?
set -e
if [[ $STATUS -eq 3 ]]; then
  echo 'REVIEW_REQUIRED: inspect warnings, mappings, missing coverage and engineering evidence in output.'
  echo "Report: $OUT/FIELD_RESULTS.md"
  exit 3
fi
if [[ $STATUS -ne 0 ]]; then
  echo "Analysis process failed (exit code $STATUS)." >&2
  exit "$STATUS"
fi
echo "Inspect $OUT/FIELD_RESULTS.md before treating results as valid."
