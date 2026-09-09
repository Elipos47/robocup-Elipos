# Skill: robocop-vision-test — test visione con campioni Webots

1. Genera/estrai frame campione da Webots (rettilineo, curva, controluce, linea persa).
2. Salva in `src/tests/data/` come PNG + JSON con atteso (deviazione px / n° vittime).
3. Test: `detect_line` ±5px su retti/curve, None su linea persa; `detect_victims` recall 100% su set campione.
4. Mai committare pesi .pt: solo path in config + istruzioni training.
