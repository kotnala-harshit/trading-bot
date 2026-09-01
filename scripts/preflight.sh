#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"
python -m compileall -q src app.py
pytest -q
python -m qts.runtime --once --config configs/production-paper.yaml
python - <<'PY'
from qts.config import load_config
from qts.safety import evaluate_live_gate
assert not evaluate_live_gate(load_config("configs/production-live.yaml"), {}).allowed
print("preflight PASS: live defaults are locked")
PY
