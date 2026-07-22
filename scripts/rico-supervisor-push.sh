#!/usr/bin/env bash
# Thin entry point for the deterministic supervisor push gate.
# See scripts/supervisor_push_gate.py for the checks and exit codes
# (0 pushed / --check-only ok; 2 refused, nothing pushed; 6 precondition).
set -euo pipefail
exec python3 "$(dirname "$0")/supervisor_push_gate.py" "$@"
