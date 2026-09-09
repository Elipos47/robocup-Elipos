"""Loop automatico tuning parametri — SOLO simulazione (SPEC §3.2).

Pseudo-implementazione da completare in Fase 4: griglia parametri x scenari,
salva best params se success_rate > soglia.
"""

SCENARIOS = ["simulation/scenarios/basic_straight.json", "simulation/scenarios/curve_90.json"]
PARAM_GRID = [{"PID_KP": 1.0}, {"PID_KP": 1.2}, {"PID_KP": 1.5}]


def run_simulation(scenario: str, params: dict) -> dict:  # pragma: no cover
    """Esegue una run simulata (stub Fase 4)."""
    raise NotImplementedError("Fase 4: collegare a Webots batch")


def main() -> None:  # pragma: no cover
    """Grid search stub."""
    for scenario in SCENARIOS:
        for params in PARAM_GRID:
            print(scenario, params)


if __name__ == "__main__":
    main()
