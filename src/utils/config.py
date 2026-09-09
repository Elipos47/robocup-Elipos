"""Parametri regolabili del robot.

Tutti i threshold/guadagni stanno qui (SPEC §4.2). Niente costanti magiche nei moduli.
"""

# --- Visione linea nera M1 (threshold su V) ---
LINE_BLACK_MAX_V: int = 80  # pixel con V <= 80 = nero (SPEC §7.1)

# --- Marker verdi M2 (HSV, solo svolte/incroci) ---
LINE_HSV_LOWER: tuple[int, int, int] = (40, 50, 50)
LINE_HSV_UPPER: tuple[int, int, int] = (70, 255, 255)
LINE_MIN_CONTOUR_AREA: int = 500

# --- Vittime (YOLO) ---
VICTIM_MODEL_PATH: str = "models/yolo_victims.pt"
VICTIM_CONF_THRESHOLD: float = 0.5

# --- Controllo motori ---
MOTOR_MAX_PWM: int = 204  # 80% di 255 (vincolo hardware SPEC §3.1)
BASE_PWM: int = 120  # avanzamento base seguilinea in sim (scenario curve_90)
MAX_WHEEL_RAD_S: float = 6.0  # velocita angolare ruota a MOTOR_MAX_PWM
WHEEL_DIRECTION: float = -1.0  # segno marcia avanti (assi ruote lungo +X)
LINE_KP: float = 80.0  # PWM per errore normalizzato ±1 (SPEC §7.1)
PID_KP: float = 1.2
PID_KI: float = 0.0
PID_KD: float = 0.3

# --- State machine ---
OBSTACLE_DISTANCE_CM: float = 15.0
STATE_DEBOUNCE_MS: int = 200
LOST_LINE_TIMEOUT_MS: int = 2000

# --- Seriale Arduino ---
ARDUINO_PORT: str = "/dev/ttyACM0"
ARDUINO_BAUDRATE: int = 115200
