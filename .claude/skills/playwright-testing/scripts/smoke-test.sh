#!/bin/bash
# HTTP smoke check for a local UI stand.
# Usage: ./smoke-test.sh [base_url] [path ...]
#   base_url defaults to http://127.0.0.1:8000; paths default to "/"
#   Paths come from arguments (or the scenario's Preconditions) — never hardcoded.
# Reachability only: a 200 answer does NOT prove the stand's identity
# (which repo/worktree/revision is serving); prove identity separately.
# Windows note: curl over https may report 000 due to certificate revocation
# checks; retry with --ssl-no-revoke before declaring the stand down.

BASE_URL=${1:-http://127.0.0.1:8000}
[ $# -gt 0 ] && shift
[ $# -eq 0 ] && set -- "/"

FAILS=0
echo "Smoke checks against $BASE_URL"
echo "========================================"
for P in "$@"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$P")
  if [ "$STATUS" = "200" ]; then
    echo "PASS $P ($STATUS)"
  else
    echo "FAIL $P ($STATUS)"
    FAILS=$((FAILS + 1))
  fi
done
echo "========================================"
echo "Smoke checks complete. Failures: $FAILS"
[ "$FAILS" -eq 0 ]
