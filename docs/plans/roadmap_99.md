# Roadmap verso il 99% (09/09/2026 → maggio 2027)

Definizione di successo: **100 run nominali sulla matrice scenari completa,
0 bug di codice** (tassonomia in `verification_pipeline.md` §4).
I fallimenti solo esterni non rompono il conteggio ma generano contromisure.

## M0 — Setup (settembre 2026, questa settimana)

- [ ] Env dev su PC: venv + numpy/opencv/pyserial/pytest (`scripts/setup_dev.sh`)
- [ ] Webots **R2025a stable** installato (installer ufficiale, ~3GB).
  Upgrade a 2026a solo quando esce la stable: le nightly 2026 sono rumore
  esterno (bug del sim scambiati per bug nostri). API usata (Camera/
  DistanceSensor/Motor) stabile tra versioni; mondi .wbt compatibili in avanti.
- [ ] Mondo placeholder + robot tank-drive che si muove (controller minimo)
- [ ] `pytest src/tests -q` verde + prima run loggata in `docs/logs/`

## M1 — Linea nera robusta (entro marzo 2027)

- [ ] Blob detection camera verde tarata (calibrazione manuale → `docs/calibration.md`)
- [ ] PID differenziale stabile: retta, curve 90°, incroci, gap linea
- [ ] Recovery linea persa (timeout + ricerca, SPEC `LOST_LINE_TIMEOUT_MS`)
- [ ] Scenari sim `basic_straight, curve_90, incroci` a 10/10
- [ ] Stessi test su pista fisica: 30/30 nominali

## M2 — Full rules (aprile–maggio 2027)

- [ ] Marker verdi dx/sx (stati VERDE_DX/SX)
- [ ] Ostacolo con HC-SR04 (stato OSTACOLO, aggiramento + rientro)
- [ ] Stanza argentata + vittime con camera nera (YOLOv8n/ONNX su Pi 5)
- [ ] Servo raccolta (definire meccanismo da TODO hardware), U-turn, rampa
- [ ] Giroscopio per stabilizzazione (se utile dopo i test, non prima)
- [ ] Matrice completa 100 run sim + 50 fisico, classificate per tassonomia

## Regole del percorso

- Si anticipa quando possibile, mai saltando criteri di accettazione.
- Ogni milestone chiude solo con report metriche in `docs/logs/`.
- SPEC resta il riferimento; discrepanze SPEC↔realtà si registrano
  in `docs/hardware_reale.md`, non a voce.
