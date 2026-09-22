#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 fetch.py
python3 diff.py

if [[ "${1:-}" == "--regress" ]]; then
  bash hooks/trigger_regression.sh
fi
