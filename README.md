# RoboCup Rescue Line 2027 — Incheon

Software di controllo per robot **Rescue Line** (Raspberry Pi 5 + Arduino Mega 2560),
sviluppato con test iterativi in **Webots**. Obiettivo primario: **affidabilita e consistenza**, poi velocita/punteggio.

Spec completa: [`SPEC.md`](SPEC.md)

## Quickstart (simulazione)

```bash
pip install -r requirements.txt
python src/main.py --scenario simulation/scenarios/basic_straight.json
```

## Layout

```
src/            # codice robot (state machine, visione, controllo, utils)
simulation/     # mondi Webots, controller, scenari di test (JSON)
scripts/        # run simulazione, metriche, report, tuning parametri
skills/         # skill custom per agenti AI
hardware/       # firmware Arduino, CAD, wiring
docs/           # calibrazione, log run, regolamento
```

## Workflow

1. Definisci obiettivo + vincoli + criteri di accettazione
2. Agente AI implementa (legge SPEC.md + skill)
3. Simulazione Webots → log JSON strutturato
4. Validazione umana: APPROVA / RICHIEDI MODIFICHE → merge su `main` solo se stabile
