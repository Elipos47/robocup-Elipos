"""Entry point robot (reale e Webots via controller bridge)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_scenario(path: str) -> dict:
    """Carica configurazione scenario JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """Loop principale (stub Fase 1: verifica wiring moduli)."""
    parser = argparse.ArgumentParser(description="Rescue Line 2027 — main")
    parser.add_argument("--scenario", default="simulation/scenarios/basic_straight.json")
    parser.add_argument("--run-id", default="smoke_001")
    args = parser.parse_args()

    from src.state_machine import Perception, StateMachine
    from src.utils.logger import RunLogger

    scenario = load_scenario(args.scenario)
    fsm = StateMachine()
    logger = RunLogger(run_id=args.run_id)
    logger.log(
        state=fsm.state.value,
        sensors={"scenario": scenario.get("name", "?")},
        actuators={"motor_left_pwm": 0, "motor_right_pwm": 0},
    )
    # Tick dimostrativo
    fsm.update(Perception())
    print(f"run={args.run_id} state={fsm.state.value} scenario={scenario.get('name', '?')}")


if __name__ == "__main__":
    main()
