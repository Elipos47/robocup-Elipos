# Skill: robocop-metrics-analyzer — analisi log

1. Leggi `docs/logs/*.jsonl` con `scripts/collect_metrics.py`.
2. Confronta con target SPEC §9.2 (success >95%, deviazione <2cm, 0 falsi positivi).
3. Suggerisci UNA modifica parametrica alla volta (PID o threshold), mai due insieme.
4. Output: tabella prima/dopo + comando per replicare.
