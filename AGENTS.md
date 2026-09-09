# Istruzioni per agenti AI (Hermes / OpenCode)

1. Leggi `SPEC.md` prima di scrivere codice. Non modificare mai l'hardware: solo proposte.
2. Stile: type hints obbligatori, docstring Google-style, `except` specifici (mai `except Exception:` nudo).
3. Parametri regolabili solo in `src/utils/config.py`, mai hardcoded.
4. Ogni feature: almeno un test in `src/tests/`. Esegui `pytest src/tests -q` prima di dichiarare finito.
5. Logging strutturato via `src/utils/logger.py` (formato JSON §9.1 SPEC).
6. Calibrazione camere manuale, documentata in `docs/calibration.md`. Niente auto-calibrazione.
7. Review con `skills/robocop-code-quality` prima di proporre merge.
