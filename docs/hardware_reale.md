# Hardware reale — inventario e collegamenti

Fonte: utente (meccatronico), 09/09/2026. Lo SPEC §1.2 è il riferimento ideale,
questo file è la realtà del banco. Aggiornare a ogni misura.

## Mappa collegamenti (reale)

```text
Camera NERA (Arducam fisheye USB) ──► Raspberry Pi 5 (4GB)
Camera VERDE (Pi Module 3) ─────────► Raspberry Pi 5
UPS ──► sotto Raspberry (alimentazione Pi)
Raspberry ◄──► UPS + Arduino Mega + Schermo
Arduino Mega ◄──► Raspberry (seriale USB)
Schermo ──► Raspberry
Servo ──► Arduino (segnale) + Stepdown (potenza)
Motori DC ──► L298N
Luci ──► Raspberry
Batterie ──► Stepdown + L298N
Giroscopio ──► Arduino
HC-SR04 (x1) ──► Arduino
Stepdown ──► Batterie + Servomotore
L298N ──► Arduino (PWM/DIR) + Batterie (potenza)
```

## Inventario

| Componente | Modello | Stato | Note |
|------------|---------|-------|------|
| Raspberry Pi 5 | 4GB | ✓ presente | Elaborazione + entrambe le camere |
| Arduino Mega 2560 | — | ✓ presente | Motori, SR04, gyro, servo |
| Driver motori | L298N | ✓ presente | Drop ~2V: tenerne conto nel PWM max reale |
| Motori DC | **IGNOTO** | da identificare | Leggere sigla a banco; misurare RPM a vuoto/carico |
| Batterie | 2.6Ah (?) | **da verificare** | Servono V nominale, chimica, connettori |
| HC-SR04 | x1 | ✓ presente | Montaggio previsto: frontale ~10cm, orizzontale |
| Camera VERDE (linea) | Pi Module 3 (DCI) | ✓ presente | Inclinata ~45° verso il basso sulla linea |
| Camera NERA (stanza) | Arducam fisheye USB | ✓ presente | Frontale orizzontale verso stanza/vittime |
| Giroscopio/IMU | BNO085 (da docs 2025, **da confermare** sia lo stesso pezzo) | da verificare a banco | 9 assi via I2C su Arduino; protocollo `G:`/`M:` in `2025/robo_arduino` |
| Servo | **IGNOTO** | da identificare | Quale meccanismo muove? (raccolta vittime?) |
| Stepdown | **IGNOTO** | da identificare | V out verso servo |
| UPS | — | ✓ presente | Sotto il Pi |
| Schermo | — | ✓ presente | Debug a bordo |
| Luci | — | ✓ presente | Pilotate da Pi; utili contro luce variabile |
| Cingoli | cinghie gomma (Amazon) | **mancano le ruote** | Modello 3D senza ruote/cingoli → sim con placeholder |

## Decisioni software congelate (09/09/2026)

- Risoluzione/FPS: **640x480 @ 30fps** su entrambe le camere.
- Fisheye: nessuna undistort finché YOLO/blob vittime non falliscono per distorsione.
- Trazione in sim: **differenziale a 2 ruote** (placeholder) + `TRACK_SLIP_FACTOR`
  in config per i tank-turn; fisica cingoli vera solo se mai servirà.

## TODO banco (prima della taratura)

- [ ] Sigla motori + diametro ruote dentate / larghezza cinghie
- [ ] Batterie: V, chimica, capacità reale
- [ ] Sigla giroscopio, servo, stepdown (V out)
- [ ] A cosa è collegato meccanicamente il servo
- [ ] Export Fusion 360: STEP + STL + screenshot quotato
  (interasse, larghezza cinghie, altezza camere da terra)
