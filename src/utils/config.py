"""Parametri regolabili del robot.

Tutti i threshold/guadagni stanno qui (SPEC §4.2). Niente costanti magiche nei moduli.
"""

# --- Visione linea nera M1 (threshold su V) ---
LINE_BLACK_MAX_V: int = 60  # pixel con V <= 60 = nero (linea V~8, pavimento min ~83)
LINE_ROI_TOP_FRAC: float = 0.35  # preview lungo + KP basso = reazione precoce ma dolce in curva

# --- Marker verdi M2 (HSV, solo svolte/incroci) ---
LINE_HSV_LOWER: tuple[int, int, int] = (40, 50, 50)
LINE_HSV_UPPER: tuple[int, int, int] = (70, 255, 255)
LINE_MIN_CONTOUR_AREA: int = 500

# --- Vittime (YOLO) ---
VICTIM_MODEL_PATH: str = "models/yolo_victims.pt"
VICTIM_CONF_THRESHOLD: float = 0.5

# --- Controllo motori ---
MOTOR_MAX_PWM: int = 204  # 80% di 255 (vincolo hardware SPEC §3.1)
BASE_PWM: int = 90  # ~7cm/s sul dritto: margine per sterzare senza rollio (M1 robusto > veloce)
MAX_WHEEL_RAD_S: float = 6.0  # velocita angolare ruota a MOTOR_MAX_PWM
WHEEL_DIRECTION: float = 1.0  # +omega su asse +X = marcia +Z (verificato con probe)
LINE_KP: float = 75.0  # P puro sul plant sano: eq. arco a dev~70px, centrato, senza bias
LINE_KA: float = 0.0  # OFF: su arco costante crea bias verso l'interno (taglia la curva)
CURVE_SLOW_GAIN: float = 0.65  # in curva base al 35%: piu' tempo per yaw dolci, raggio stretto
CURVE_SLOW_DEV_REF: float = 0.6  # dev normalizzato (±1) a cui il rallentamento e' pieno
PID_KP: float = 1.2
PID_KI: float = 6.0  # toglie offset statico (es. 26mm su rettilineo dopo curva)
PID_KD: float = 1.0  # smorzo leggero: oltre scatta il derivative-kick all'ingresso curva
SLEW_MAX_DPWM: int = 8  # rampa dolce (~0.5s fondo scala): niente snap di rollio in skid
STEER_MAX_CORR: int = 40  # plant sano: yaw deciso senza snap (skid + ballast rispondono)

# --- State machine ---
OBSTACLE_DISTANCE_CM: float = 15.0
STATE_DEBOUNCE_MS: int = 200
LOST_LINE_TIMEOUT_MS: int = 2000

# --- Seriale Arduino ---
ARDUINO_PORT: str = "/dev/ttyACM0"
ARDUINO_BAUDRATE: int = 115200
