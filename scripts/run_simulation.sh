#!/bin/bash
# Avvia simulazione Webots headless su uno scenario (SPEC §6).
# Uso: ./scripts/run_simulation.sh simulation/scenarios/basic_straight.json [run_id]
set -euo pipefail
SCENARIO="${1:?Uso: $0 <scenario.json> [run_id]}"
RUN_ID="${2:-run_$(date +%Y%m%d_%H%M%S)}"
WORLD=$(python -c "import json;print(json.load(open('$SCENARIO'))['world'])")
webots --mode=fast --no-rendering --minimize "$WORLD" 2>&1 | tee "docs/logs/${RUN_ID}.stdout.log"
