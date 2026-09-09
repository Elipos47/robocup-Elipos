# Skill: robocop-code-quality — code review per robotica

Usa prima di ogni merge su develop. Oltre al solito (tipi, SRP, test),
verifica vincoli robotici:

1. **Latenza**: niente inferenze bloccanti nel tick; YOLO solo in STANZA o throttled.
2. **Memoria Pi 5 4GB**: niente buffer frame illimitati; riusa array numpy.
3. **Sicurezza motori**: ogni set_velocity/set_motor saturato a MOTOR_MAX_PWM; mai PWM 100% senza motivo.
4. **Error handling hardware**: try/except specifici su seriale/camere con fallback (stop motori), mai `except Exception: pass`.
5. **Config esterna**: threshold/PID solo da config.py, mai literal.
