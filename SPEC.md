# SPEC.md — RoboCup Rescue Line 2027
## Piano di Automazione Iterativa per Simulazione Webots

**Versione:** 1.0  
**Data:** 6 Settembre 2026  
**Competizione:** RoboCupJunior Rescue Line 2027 (Incheon, Corea del Sud — Luglio 2027)  
**Obiettivo primario:** Affidabilità±¹ e consistenza delle run, poi ottimizzazione di velocità e punteggio

---

## 1. Panoramica del Progetto

### 1.1 Contesto
Sviluppo del software di controllo per un robot **Rescue Line** con architettura ibrida Raspberry Pi 5 + Arduino Mega 2560, simulato in **Webots** per test iterativi assistiti da AI. Il codice Python sarà scritto principalmente da agenti AI (Hermes Agent, OpenCode) con supervisione umana sulle scelte architetturali e di gara.

### 1.2 Hardware Target
| Componente | Modello | Ruolo |
|------------|---------|-------|
| Computer di bordo | Raspberry Pi 5 (4GB RAM) | Elaborazione immagini, logica principale, machine learning |
| Microcontrollore | Arduino Mega 2560 | Controllo motori, lettura sensori IR (se presenti), PWM |
| Telecamere | 2x camera module | Camera nera → rilevamento palline (vittime), Camera verde → seguilinea |
| Attuatori | 2 motori DC con trasmissione | Tank turn (differenziale) |
| Sensori opzionali | IR, encoder, IMU | Stabilizzazione, rilevamento linea argentata |

### 1.3 Stack Software
| Layer | Tecnologia | Note |
|-------|------------|------|
| Simulazione | Webots R2025a stable | Ambiente di test primario |
| Linguaggio | Python 3.10+ | Codice principale su Raspberry Pi |
| Firmware | Arduino C++ | Solo per controllo motori a bassa latenza |
| Comunicazione | Serial (USB) / MQTT | Pi ↔ Arduino |
| Visione | OpenCV + YOLOv8/v10 | Rilevamento linea e vittime |
| Versionamento | Git + GitHub | Repository esistente con gare passate |
| Agenti AI | Hermes Agent, OpenCode | Scrittura codice assistita |
| Skills | skills.sh (custom + esistenti) | Prompt riutilizzabili per agenti |

---

## 2. Architettura del Sistema

### 2.1 Diagramma Architetturale
```
┌─────────────────────────────────────────────────────────────┐
│                     WEBOTS SIMULATION                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Robot     │  │   Campo     │  │   Sensori           │  │
│  │   Model     │  │   Rescue    │  │   Camera (2x)       │  │
│  │   (e-puck/  │  │   Line      │  │   Ground Sensors    │  │
│  │    custom)  │  │             │  │   Distance Sensors  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Webots Python API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    CONTROLLER PYTHON                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              MAIN LOOP (state_machine.py)             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │ Seguilinea   │  │ Ostacolo     │  │ Stanza      │ │  │
│  │  │ (green cam)  │  │ (distance)   │  │ (palline)   │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │ Verde DX     │  │ Verde SX     │  │ U-Turn      │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │ Vision Module   │  │ Communication Module            │   │
│  │ - OpenCV        │  │ - Serial (Arduino)              │   │
│  │ - YOLO (palline)│  │ - Logging (JSON/CSV)            │   │
│  │ - Blob (linea)  │  │ - Webots telemetry              │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Serial / MQTT
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    ARDUINO FIRMWARE                          │
│  - Controllo motori (PWM + direzioni)                       │
│  - Lettura sensori IR (opzionale)                           │
│  - Encoder feedback (opzionale)                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Struttura del Repository
```
robocup-rescue-line-2027/
├── docs/
│   ├── SPEC.md                  # Questo file
│   ├── rules/                   # Regolamento RCJ Rescue Line 2026/2027
│   └── logs/                    # Log delle run (simulazione e reali)
├── simulation/
│   ├── webots/
│   │   ├── worlds/              # File .wbt (campi Rescue Line)
│   │   ├── controllers/         # Controller Python per Webots
│   │   ├── protos/              # Modelli 3D custom (robot, ostacoli)
│   │   └── textures/            # Texture per linea, vittime, stanza
│   └── scenarios/               # Configurazioni di test (JSON)
├── src/
│   ├── main.py                  # Entry point
│   ├── state_machine.py         # Macchina a stati principale
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── line_detector.py     # Linea nera M1 + marker verdi M2
│   │   ├── victim_detector.py   # YOLO/blob per palline
│   │   └── camera_calibration.py# Calibrazione (manuale, no auto)
│   ├── control/
│   │   ├── __init__.py
│   │   ├── motor_control.py     # PID per motori
│   │   └── arduino_bridge.py    # Comunicazione seriale
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py            # Logging strutturato
│   │   ├── config.py            # Costanti e parametri
│   │   └── metrics.py           # Raccolta metriche di performance
│   └── tests/
│       ├── test_state_machine.py
│       ├── test_vision.py
│       └── test_control.py
├── skills/
│   ├── robocop-code-quality.skill.md    # Custom skill per code review
│   ├── robocop-vision-test.skill.md     # Test visione artificiale
│   └── robocop-state-machine.skill.md   # FSM best practices
├── scripts/
│   ├── run_simulation.sh        # Avvia simulazione Webots
│   ├── collect_metrics.py       # Estrae metriche dai log
│   └── generate_report.py       # Report automatico post-run
├── hardware/
│   ├── arduino/                 # Firmware Arduino (.ino)
│   ├── cad/                     # File STL/STEP per stampa 3D
│   └── wiring/                  # Schemi elettrici (Fritzing/KiCad)
├── .github/
│   └── workflows/
│       ├── ci.yml               # Test automatici su push
│       └── simulation.yml       # Run simulazione su PR
├── .gitignore
├── requirements.txt             # Dipendenze Python
└── README.md
```

---

## 3. Workflow di Sviluppo Iterativo

### 3.1 Ciclo di Sviluppo Base (Human-in-the-Loop)
```
┌──────────────────────────────────────────────────────────────┐
│                    FASE 1: DEFINIZIONE                        │
│  Tu definisci:                                                │
│  - Obiettivo della feature (es. "migliorare curva a destra") │
│  - Vincoli hardware (es. "non superare 80% PWM")             │
│  - Criteri di accettazione (es. "90% successo in 10 run")   │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FASE 2: AGENTE AI                          │
│  Hermes Agent / OpenCode:                                     │
│  - Legge SPEC.md e skill correlate                           │
│  - Propone implementazione (codice + test)                   │
│  - Esegue code review con skill Thermo-Nuclear               │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FASE 3: SIMULAZIONE                        │
│  Webots:                                                      │
│  - Esegue scenario di test (es. "curva_90_gradi.wbt")        │
│  - Raccoglie metriche (tempo, deviazione, successo)          │
│  - Genera log strutturato (JSON)                             │
└──────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    FASE 4: VALIDAZIONE                        │
│  Tu valuti:                                                   │
│  - Metriche rispetto ai criteri di accettazione              │
│  - Log e video della simulazione                             │
│  - Decisione: APPROVA / RICHIEDI MODIFICHE                   │
└──────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
         APPROVA                    RICHIEDI MODIFICHE
              │                           │
              ▼                           ▼
         MERGE SU MAIN            TORNA A FASE 2
```

### 3.2 Loop Automatico di Ottimizzazione (Opzionale)
Per parametri regolabili (es. guadagni PID, threshold visione), si può usare un loop automatico:

```python
# Pseudo-codice per scripts/optimize_loop.py
for scenario in test_scenarios:
    for param_set in parameter_grid:
        run_simulation(scenario, param_set)
        metrics = collect_metrics()
        if metrics.success_rate > 0.9:
            save_best_params(param_set)
```

**Nota:** Questo loop va eseguito **solo in simulazione**, mai su hardware reale senza supervisione.

---

## 4. Regole e Best Practices

### 4.1 Regole per Agenti AI
1. **Non modificare mai l'hardware** — Gli agenti possono solo suggerire modifiche al codice. Eventuali cambiamenti hardware (es. "aggiungi un sensore IR") devono essere approvati da te.
2. **Segui lo stile del repository** — Usa le skill `codebase-design` e `Thermo-Nuclear Code Quality Review` per mantenere coerenza.
3. **Scrivi test per ogni feature** — Ogni nuova funzione deve avere almeno un test in `src/tests/`.
4. **Logga tutto** — Ogni stato, decisione e errore deve essere registrato nel logger strutturato.
5. **Non usare auto-calibrazione** — La calibrazione delle camere deve essere manuale e documentata in `docs/calibration.md`.

### 4.2 Best Practices per Codice Python
- **Type hints** — Tutti i parametri e return type devono essere annotati.
- **Docstring** — Ogni funzione pubblica deve avere docstring in formato Google-style.
- **Error handling** — Usa try/except specifici, mai `except Exception:` generico.
- **Configurazione esterna** — Parametri regolabili (threshold, guadagni PID) vanno in `src/utils/config.py`.
- **Modularità±²** — Ogni modulo deve avere una singola responsabilità (Single Responsibility Principle).

### 4.3 Git Workflow
```bash
# Branch strategy
main              # Codice stabile, pronto per gara
develop           # Integrazione feature
feature/*         # Nuove feature (es. feature/vision-yolo)
hotfix/*          # Correzioni urgenti
experiment/*      # Sperimentazioni (non mergiate su main senza test)

# Commit convention (ispirata a Conventional Commits)
feat: aggiungi rilevamento palline con YOLO
fix: correggi overflow PID in curva stretta
docs: aggiungi diagramma state machine
test: aggiungi test per vision/line_detector.py
refactor: semplifica logica U-turn
```

### 4.4 Skill Consigliate (skills.sh)
| Skill | Scopo | Quando usarla |
|-------|-------|---------------|
| `Thermo-Nuclear Code Quality Review` | Code review approfondita | Prima di ogni merge su develop |
| `ponytail` | Refactoring e pulizia codice | Dopo implementazione feature |
| `codebase-design` | Architettura e struttura | Inizio progetto o grandi refactoring |
| `test-driven-development` | Scrivere test prima del codice | Feature critiche (visione, controllo motori) |
| `systematic-debugging` | Debug strutturato | Quando un test fallisce |
| `writing-great-skills` | Creare nuove skill custom | Per catturare pattern specifici del progetto |
| `subagent-driven-development` | Delegare sotto-task a sub-agent | Feature complesse (es. integrazione YOLO) |

### 4.5 Skill Custom da Creare
1. **`robocop-code-quality.skill.md`** — Adatta la Thermo-Nuclear al contesto robotica (controlla latenza, uso memoria, gestione errori hardware).
2. **`robocop-vision-test.skill.md`** — Genera test per visione artificiale con immagini campione da Webots.
3. **`robocop-state-machine.skill.md`** — Verifica correttezza FSM (nessuno stato morto, transizioni complete).
4. **`robocop-metrics-analyzer.skill.md`** — Analizza log e suggerisce ottimizzazioni basate su metriche.

---

## 5. Macchina a Stati (State Machine)

### 5.1 Stati Principali
```python
STATES = {
    "SEGUILINEA": {
        "description": "Segue la linea nera usando camera verde",
        "transitions": ["OSTACOLO", "VERDE_DX", "VERDE_SX", "STANZA", "UTURN"]
    },
    "OSTACOLO": {
        "description": "Rileva ostacolo con sensori di distanza",
        "transitions": ["SEGUILINEA"]  # Dopo aver aggirato
    },
    "VERDE_DX": {
        "description": "Curva a destra per seguire linea",
        "transitions": ["SEGUILINEA"]
    },
    "VERDE_SX": {
        "description": "Curva a sinistra per seguire linea",
        "transitions": ["SEGUILINEA"]
    },
    "STANZA": {
        "description": "Rileva linea argentata, cerca palline con YOLO",
        "transitions": ["SEGUILINEA"]  # Dopo aver raccolto vittime
    },
    "UTURN": {
        "description": "Inversione a U a fine percorso",
        "transitions": ["SEGUILINEA"]
    }
}
```

### 5.2 Diagramma di Transizione
```
                    ┌──────────────┐
                    │  SEGUILINEA  │
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  VERDE_DX   │ │  VERDE_SX   │ │   OSTACOLO  │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┴───────────────┘
                           │
                    ┌──────▼──────┐
                    │  SEGUILINEA  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌───▼────┐ ┌────▼────┐
       │   STANZA    │ │ UTURN  │ │  FINE   │
       └─────────────┘ └────────┘ └─────────┘
```

---

## 6. Setup di Webots

### 6.1 Installazione
```bash
# Linux (Ubuntu/Debian): .deb R2025a da
# https://github.com/cyberbotics/webots/releases (tag R2025a)

# Windows
# Installer R2025a stable da https://cyberbotics.com (niente nightly 2026:
# rumore esterno, API Camera/DistanceSensor/Motor stabili tra versioni)
# Scarica installer da https://cyberbotics.com e segui wizard

# Verifica installazione
webots --version
```

> NOTA (verificato 09/09/2026): l'installer R2025a NON include i file PROTO
> dei robot né le texture: al primo avvio di un sample Webots li scarica da
> `raw.githubusercontent.com` e il suo downloader interno spesso fallisce
> (`Cannot download ... error code: 2: Connection closed` / 399) lasciando
> robot grigi senza texture. La rete è a posto (curl scarica a 200 OK):
> è il downloader di Webots a troncare le connessioni verso il CDN di GitHub.
> Fix: alla prima apertura premi il pulsante `Auto` nel dialogo di download
> (scarica tutto in un colpo solo) oppure riapri il mondo finché la cache
> (`%LOCALAPPDATA%/Cyberbotics/Webots/cache/assets`) è completa.
> I nostri mondi useranno solo texture locali,
> quindi il problema non si ripresenta nel progetto.

### 6.2 Primo Test
1. Apri Webots → `File > Open Sample World > robots/vehicles/e-puck.wbt`
2. Clicca `Run` per avviare la simulazione
3. Il controller Python di default dovrebbe far muovere l'e-puck

### 6.3 Creazione Mondo Custom
```python
# simulation/webots/worlds/rescue_line_basic.wbt (stato verificato 09/09/2026)
WEBOTS
├── RESCUEBOT Robot (skid-steer, placeholder cingoli M1)
│   ├── body + ballast basso (COM ~0.035; angoli anti-rollio, vedi nota)
│   ├── CAM_GREEN_MOUNT (Solid) + Camera verde 640x480 ~45° basso (linea)
│   └── 4x HingeJoint asse X + RotationalMotor (fl/rl sx, fr/rr dx, maxTorque 5.0)
├── Floor bianco 3x3 (top y=+0.01) + linea nera 19mm: 2m dritto + arco 90°
│   r=0.3 in 6 segmenti tangenziali + rettilineo finale + marker verde
└── Viewpoint dietro il robot (vede pista, non muro)
```
> NOTA (verificato 09/09/2026, 3 run identici): niente rotelle folli — con
> 2 ruote + sfere il robot entra in risonanza rollio-sterzo ±10°. Lo skid
> a 4 ruote + zavorra bassa modella i cingoli veri. Camera nera rimossa in
> M1 (overlay nero confondeva); torna in M2 dentro un Solid. Vista spawn
> da dietro-alto, non radente.

### 6.4 Controller Python Base
```python
# simulation/webots/controllers/rescue_controller/rescue_controller.py
from controller import Robot, Camera, DistanceSensor, Motor

robot = Robot()
timestep = int(robot.getBasicTimeStep())

# Inizializza dispositivi (M1: solo camera verde; nera in M2)
camera_green = robot.getDevice("camera_green")
camera_green.enable(timestep)

# Skid-steer M1: coppie fl/rl = sinistra, fr/rr = destra (stessi comandi)
motors_left = [robot.getDevice(n) for n in ("motor_fl", "motor_rl")]
motors_right = [robot.getDevice(n) for n in ("motor_fr", "motor_rr")]
for m in motors_left + motors_right:
    m.setPosition(float('inf'))

# Loop principale
while robot.step(timestep) != -1:
    # Leggi sensori (M1: solo linea nera)
    image_green = camera_green.getImage()
    
    # Elabora (qui chiamerai la state machine)
    # state_machine.update(image_green)
    
    # Scrivi su motori (coppie skid: fl/rl=sx, fr/rr=dx)
    # vedi src/control/motor_control.py: tank_mix + PID + slew (M1 verificato:
    # dritto ±2mm, arco 90° r=0.3, stop a fine linea — 3/3 run 09/09/2026)
    ...
```

---

## 7. Visione Artificiale

### 7.1 Rilevamento Linea Nera (Camera Verde, M1)
- **Approccio:** Blob detection con OpenCV
- **Preprocessing:** Threshold sul canale V (V <= `LINE_BLACK_MAX_V` = nero)
- **Output:** Deviazione in pixel dal centro immagine (>0 = linea a destra)
- **Nota:** il verde in pista indica solo marker di svolta/incroci (M2,
  `detect_line` con filtro HSV) — la linea da seguire e' nera su bianco.

```python
# src/vision/line_detector.py
import cv2
import numpy as np

from src.utils.config import LINE_BLACK_MAX_V, LINE_MIN_CONTOUR_AREA

def detect_black_line(image_bgr):
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, 0]),
        np.array([180, 255, LINE_BLACK_MAX_V]),
    )

    # Trova contorni
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= LINE_MIN_CONTOUR_AREA]
    if not contours:
        return None  # Linea non trovata

    # Prendi contorno più grande
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    center_x = x + w / 2

    # Calcola deviazione dal centro immagine (>0 = linea a destra)
    image_center = image_bgr.shape[1] / 2
    deviation = center_x - image_center

    return deviation
```

### 7.2 Rilevamento Vittime (Camera Nera + YOLO)
- **Modello:** YOLOv8n (leggero, adatto a Raspberry Pi 5)
- **Training:** Dataset custom con immagini di palline da Webots
- **Inferenza:** ONNX runtime per velocità

```python
# src/vision/victim_detector.py
from ultralytics import YOLO

model = YOLO("models/yolo_victims.pt")

def detect_victims(image_bgr):
    results = model(image_bgr, conf=0.5)
    victims = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = box.conf[0].item()
        victims.append({
            "bbox": (x1, y1, x2, y2),
            "confidence": confidence
        })
    return victims
```

---

## 8. Comunicazione con Arduino

### 8.1 Protocollo Seriale
```
Formato: <CMD><VALUE>\n
Esempi:
  M100\n   → Motore 1 a 100% PWM
  M2-50\n  → Motore 2 a -50% PWM (indietro)
  S?\n     → Richiedi stato sensori
```

### 8.2 Codice Python (Bridge)
```python
# src/control/arduino_bridge.py
import serial
import time

class ArduinoBridge:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Attendi reset Arduino
    
    def set_motor(self, motor_id: int, speed: int):
        """Imposta motore (1 o 2) con speed da -255 a 255"""
        cmd = f"M{motor_id}{speed}\n".encode()
        self.serial.write(cmd)
    
    def read_sensors(self):
        self.serial.write(b"S?\n")
        response = self.serial.readline().decode().strip()
        return response.split(",")
```

### 8.3 Firmware Arduino (Semplificato)
```cpp
// hardware/arduino/main.ino
#include <Arduino.h>

const int MOTOR1_PIN = 9;
const int MOTOR2_PIN = 10;

void setup() {
  Serial.begin(115200);
  pinMode(MOTOR1_PIN, OUTPUT);
  pinMode(MOTOR2_PIN, OUTPUT);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    if (cmd.startsWith("M1")) {
      int speed = cmd.substring(2).toInt();
      analogWrite(MOTOR1_PIN, map(abs(speed), 0, 255, 0, 255));
      // Gestione direzione...
    }
  }
}
```

---

## 9. Logging e Metriche

### 9.1 Formato Log (JSON)
```json
{
  "timestamp": "2026-09-06T22:30:15.123Z",
  "state": "SEGUILINEA",
  "sensors": {
    "camera_green_deviation": 12.5,
    "camera_black_victims": [],
    "distance_front": 45.2
  },
  "actuators": {
    "motor_left_pwm": 180,
    "motor_right_pwm": 200
  },
  "metrics": {
    "run_id": "test_001",
    "elapsed_time_ms": 1523,
    "distance_traveled_cm": 125.6
  }
}
```

### 9.2 Metriche Chiave
| Metrica | Descrizione | Target |
|---------|-------------|--------|
| `success_rate` | % run completate senza errori | > 95% |
| `avg_time` | Tempo medio di percorrenza | Minimizzare |
| `deviation_avg` | Deviazione media dalla linea | < 2 cm |
| `victims_detected` | Vittime identificate correttamente | 100% |
| `false_positives` | Falsi positivi (ostacoli/vittime) | 0 |

### 9.3 Script di Analisi
```bash
# Esegue tutte le run di test e genera report
./scripts/collect_metrics.py --output docs/logs/report_2026-09-06.md
```

---

## 10. Roadmap di Sviluppo

### Fase 1: Setup (Settembre 2026)
- [ ] Installa Webots e crea mondo base Rescue Line
- [ ] Implementa controller Python minimale (muovi avanti/indietro)
- [ ] Configura repository Git e CI base
- [ ] Scrivi skill custom `robocop-code-quality`

### Fase 2: Visione (Ottobre-Novembre 2026)
- [ ] Integra camera verde + blob detection per linea
- [ ] Integra camera nera + YOLO per vittime
- [ ] Crea dataset di training da Webots (renderizza immagini)
- [ ] Testa accuratezza visione in scenari controllati

### Fase 3: State Machine (Dicembre 2026 - Gennaio 2027)
- [ ] Implementa tutti gli stati (SEGUILINEA, OSTACOLO, STANZA, ecc.)
- [ ] Aggiungi transizioni robuste (debounce, timeout)
- [ ] Testa ogni stato in isolamento
- [ ] Integra con hardware Arduino (motori)

### Fase 4: Ottimizzazione (Febbraio-Marzo 2027)
- [ ] Loop automatico di tuning parametri (solo simulazione)
- [ ] Riduci latenza visione (ottimizza YOLO, usa ONNX)
- [ ] Migliora affidabilità®¹ (gestione errori, fallback)
- [ ] Documenta calibrazione manuale camere

### Fase 5: Test Finali (Aprile 2027)
- [ ] Esegui 100+ run in simulazione con scenari vari
- [ ] Testa su hardware reale con pista ufficiale
- [ ] Raccogli metriche finali e confronta con target
- [ ] Prepara backup e piano di emergenza per gara

---

## 11. Rischi e Mitigazione

| Rischio | Probabilità®³ | Impatto | Mitigazione |
|---------|---------------|---------|-------------|
| YOLO troppo lento su Pi 5 | Media | Alto | Usa YOLOv8n, ONNX runtime, o passa a blob detection semplice |
| Webots non rispecchia realtà | Media | Medio | Testa presto su hardware, usa parametri conservativi |
| Agenti AI scrivono codice non ottimale | Alta | Medio | Review obbligatoria con skill Thermo-Nuclear, test automatizzati |
| Hardware in ritardo | Bassa | Alto | Inizia ordini componenti a Ottobre 2026 |
| Regolamento cambia | Bassa | Medio | Monitora forum RoboCupJunior mensilmente |

---

## 12. Glossario

- **Affidabilità±¹:** Capacità±² del robot di completare run senza errori, anche a velocità ridotta.
- **Modularità±²:** Principio di progettazione per cui ogni componente ha una singola responsabilità.
- **Probabilità±³:** Stima qualitativa (Bassa/Media/Alta) della probabilità che un rischio si verifichi.

---

## 13. Riferimenti

1. [Regolamento RCJ Rescue Line 2026](https://rescue.rcj.cloud/rules/2026/RCJRescueLine2026-final.pdf)
2. [Documentazione Webots](https://cyberbotics.com/doc/guide/introduction-to-webots)
3. [skills.sh — Agent Skills Directory](https://www.skills.sh/)
4. [GitHub — RoboCup Rescue progetti](https://github.com/topics/robocup-rescue)
5. [YOLOv8 Documentazione](https://docs.ultralytics.com/)

---

## 14. Approvazioni

| Ruolo | Nome | Data | Firma |
|-------|------|------|-------|
| Lead Developer | Elipos | 06/09/2026 | _ _ _ |
| AI Agent Supervisor | — | — | — |
| Hardware Lead | — | — | — |

---

**Nota finale:** Questo documento è vivo. Aggiornalo ogni volta che una feature significativa viene aggiunta o una regola cambia. Usa Git per tracciare le versioni.