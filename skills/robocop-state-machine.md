# Skill: robocop-state-machine — verifica FSM

1. Ogni stato in TRANSITIONS deve avere almeno una transizione d'uscita (nessuno stato morto).
2. Ogni transizione deve avere test dedicato con debounce simulato.
3. Timeout anti-stallo: nessuno stato foglia trattiene il robot oltre il suo timeout.
4. `finish_action()` deve riportare a SEGUILINEA; loggare ogni cambio stato.
