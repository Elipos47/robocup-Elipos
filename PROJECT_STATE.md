# PROJECT_STATE.md — Stato Corrente del Progetto

> Ultimo aggiornamento: 2026-03-07

## 🎯 Prossimi Obiettivi

## ✅ Funzionalità Implementate

| Feature | Stato | File principali |
|---------|-------|----------------|
| Line following (angolo + centroide) | ✅ Funzionante | `logic_controller.py`, `line_detector.py` |
| Filtro anti-ombre | ✅ Funzionante | `line_detector.py` |
| Curve handling (entry delay + forward interleaving + isteresi) | ✅ Funzionante (~90%) | `logic_controller.py` |
| Seesaw/rampa detection | ✅ Implementato, da testare | `logic_controller.py`, `main.py` |
| Marker verdi (svolta sx/dx/U-turn) | ✅ Funzionante | `color_detector.py`, `logic_controller.py` |
| Marker rossi (stop) | ✅ Funzionante | `color_detector.py`, `logic_controller.py` |
| Gap detection + attraversamento | ✅ Funzionante | `gap_detector.py`, `logic_controller.py` |
| Rilevamento ostacoli (HC-SR04) | ✅ Funzionante | `obstacle_detector.py`, `serial_interface.py` |
| Smart Recovery (image similarity) | ✅ Implementato | `recovery_manager.py` |
| Giroscopio BNO085 | ✅ Integrato via Arduino | `gyroscope_interface.py`, `serial_interface.py` |
| GUI touchscreen 800×480 | ✅ Funzionante | `gui_main.py` |
| Logging strutturato | ✅ Funzionante | `logger.py` |
| Config esternalizzata | ✅ Tutti i parametri in `config.ini` | `config_manager.py`, `config.ini` |
| Telecamera USB (zona/evacuation) | ⚠️ Processo attivo, logica zona non implementata | `usb_camera_process.py` |
| Zigzag shortcut | ❌ Non implementato | — |
| Zona/Evacuation (palline) | ❌ Non implementato | — |

## 🔧 Parametri Attuali

```ini
[detection]
black_threshold_top = 65
black_threshold_bottom = 95
shadow_v_min = 100
line_loss_threshold = 5

[control]
curve_entry_delay = 1
curve_exit_threshold = 10
curve_exit_frames = 2
curve_forward_ratio = 4
seesaw_pitch_threshold = -8
seesaw_min_frames = 5
```

## 🐛 Problemi Noti

| Problema | Severità | Note |
|----------|----------|------|
| Curve strette (90°+) non sempre completate | Media | Forward ratio 4 migliora ma non risolve al 100% |
| Calcolo angolo non sempre affidabile | Bassa | Rumore nei frame, compensato da isteresi |
| Seesaw non ancora testata sul campo | — | Implementazione presente ma non validata |

## 📝 Storico Modifiche Recenti

- **2026-03-07**: Riformattato `AGENTS.md`, creato `PROJECT_STATE.md`, aggiunto hardware specs
- **2026-03-04**: Esternalizzato tutti i parametri in `config.ini`. Semplificato curve handling (rimossi persistenza e anti-oscillazione, tenuti entry delay + forward interleaving + isteresi uscita). Implementato seesaw detection via BNO085. Filtro anti-ombre per `line_detector.py`
