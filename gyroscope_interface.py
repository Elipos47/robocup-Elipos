# ===========================================================================
# gyroscope_interface.py – Interfaccia giroscopio BNO085 via Arduino Seriale
# ===========================================================================
# FASE 5: Gestione orientamento assoluto, turn precisi e stuck detection
# Il BNO085 è collegato all'Arduino Mega via I2C.
# I dati arrivano al Raspberry Pi tramite la SerialInterface già esistente.
# ===========================================================================
# FASE 5: Gestione orientamento assoluto, turn precisi e stuck detection
# Il BNO055 è collegato all'Arduino Mega via I2C.
# I dati arrivano al Raspberry Pi tramite la seriale già esistente.
# ===========================================================================

import time
import threading
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from collections import deque
import math

from logger import get_logger


@dataclass
class Orientation:
    """Orientamento 3D del robot."""
    yaw: float = 0.0      # Rotazione orizzontale (0-360°)
    pitch: float = 0.0    # Inclinazione avanti/indietro
    roll: float = 0.0     # Inclinazione laterale
    
    def normalized_yaw(self) -> float:
        """Restituisce yaw normalizzato 0-360°."""
        yaw = self.yaw % 360.0
        return yaw if yaw >= 0 else yaw + 360.0
    
    def angular_difference(self, other: 'Orientation') -> float:
        """Calcola differenza angolare con un altro orientamento."""
        diff = abs(self.yaw - other.yaw)
        return min(diff, 360.0 - diff)


@dataclass
class MotionData:
    """Dati di movimento dal giroscopio."""
    linear_accel: Tuple[float, float, float]  # x, y, z in m/s²
    gyro: Tuple[float, float, float]          # velocità angolare °/s
    gravity: Tuple[float, float, float]       # vettore gravità
    
    def is_moving(self, threshold: float = 0.1) -> bool:
        """Verifica se il robot si sta muovendo."""
        accel_magnitude = math.sqrt(sum(a**2 for a in self.linear_accel))
        return accel_magnitude > threshold


class StuckDetector:
    """Rileva se il robot è bloccato usando i dati del giroscopio."""
    
    def __init__(self, history_size: int = 30):
        """
        Parameters
        ----------
        history_size : int
            Numero di campioni per la storia (default 30 = 1s a 30Hz)
        """
        self._logger = get_logger("STUCK_DET")
        self._history_size = history_size
        self._motion_history = deque(maxlen=history_size)
        self._orientation_history = deque(maxlen=history_size)
        self._last_position = Orientation()
        self._stuck_counter = 0
        self._is_stuck = False
        self._warmup_frames = 0  # Conta frame dall'inizio, evita falsi positivi
        self._WARMUP_THRESHOLD = history_size  # Aspetta buffer pieno
        
        # Soglie
        self.ANGULAR_VELOCITY_THRESHOLD = 5.0   # °/s
        self.ACCEL_THRESHOLD = 0.2              # m/s²
        self.STUCK_FRAME_THRESHOLD = 20         # frame consecutivi
        self.POSITION_DRIFT_THRESHOLD = 3.0     # gradi
        
        self._logger.info("StuckDetector inizializzato")
    
    def update(self, orientation: Orientation, motion: MotionData):
        """Aggiorna il detector con nuovi dati."""
        # Warmup: non rilevare stuck finché non abbiamo abbastanza dati
        self._warmup_frames += 1
        if self._warmup_frames < self._WARMUP_THRESHOLD:
            return
        # Salva storia
        self._motion_history.append(motion)
        self._orientation_history.append(orientation)
        
        # Calcola movimento angolare
        if len(self._orientation_history) >= 2:
            prev = self._orientation_history[-2]
            curr = self._orientation_history[-1]
            
            # Differenza angolare
            angular_diff = abs(curr.yaw - prev.yaw)
            if angular_diff > 180:  # Gestisci wrap-around
                angular_diff = 360 - angular_diff
            
            # Verifica se dovrebbe muoversi ma non si muove
            if motion.is_moving(self.ACCEL_THRESHOLD):
                # C'è accelerazione ma piccolo cambio orientamento
                if angular_diff < self.POSITION_DRIFT_THRESHOLD:
                    self._stuck_counter += 1
                else:
                    self._stuck_counter = max(0, self._stuck_counter - 2)
            else:
                # Nessuna accelerazione, resetta
                self._stuck_counter = max(0, self._stuck_counter - 1)
            
            # Verifica soglia stuck
            if self._stuck_counter >= self.STUCK_FRAME_THRESHOLD:
                if not self._is_stuck:
                    self._is_stuck = True
                    self._logger.warning("STUCK DETECTED!", 
                                       counter=self._stuck_counter,
                                       angular_diff=angular_diff)
            else:
                if self._is_stuck:
                    self._is_stuck = False
                    self._logger.info("No longer stuck")
        
        self._last_position = orientation
    
    @property
    def is_stuck(self) -> bool:
        """True se il robot è rilevato come bloccato."""
        return self._is_stuck
    
    @property
    def stuck_frames(self) -> int:
        """Numero di frame consecutivi in cui sembra bloccato."""
        return self._stuck_counter
    
    def reset(self):
        """Resetta lo stato del detector."""
        self._stuck_counter = 0
        self._is_stuck = False
        self._warmup_frames = 0
        self._motion_history.clear()
        self._orientation_history.clear()
        self._logger.info("StuckDetector resettato")


class GyroscopeInterface:
    """Interfaccia per giroscopio BNO085 via Arduino seriale.
    
    Invece di comunicare direttamente via I2C con il BNO085,
    legge i dati dalla SerialInterface che li riceve dall'Arduino Mega.
    """
    
    def __init__(self, serial_interface=None):
        """
        Parameters
        ----------
        serial_interface : SerialInterface, optional
            Istanza di SerialInterface da cui leggere i dati.
            Se None, usa modalità simulazione.
        """
        self._logger = get_logger("GYRO")
        self._serial = serial_interface
        self._is_connected = False
        self._use_simulation = serial_interface is None
        
        # Dati attuali
        self._current_orientation = Orientation()
        self._current_motion = MotionData((0, 0, 0), (0, 0, 0), (0, 0, 0))
        self._calibration_status = (0, 0, 0, 0)  # sys, gyro, accel, mag
        
        # Threading
        self._lock = threading.Lock()
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        
        # Callback
        self._on_orientation_change: Optional[Callable] = None
        self._orientation_change_threshold = 5.0  # gradi
        
        # Stuck detector
        self.stuck_detector = StuckDetector()
        
        # Simulazione
        self._sim_yaw = 0.0
        self._sim_pitch = 0.0
        self._sim_roll = 0.0
        
        if self._use_simulation:
            self._logger.warning("Modalità SIMULAZIONE attiva (nessuna SerialInterface)")
            self._is_connected = True
        else:
            self._logger.info("GyroscopeInterface inizializzato (via Arduino seriale)")
    
    def set_serial(self, serial_interface):
        """Imposta/aggiorna l'istanza SerialInterface.
        
        Parameters
        ----------
        serial_interface : SerialInterface
            Istanza seriale da usare come sorgente dati
        """
        self._serial = serial_interface
        self._use_simulation = False
        self._is_connected = False  # Diventerà True quando arriva G:BNO085_OK
        self.stuck_detector.reset()
        self._logger.info("SerialInterface configurata per giroscopio")
    
    def start(self):
        """Avvia il thread di aggiornamento."""
        if self._running:
            return
        
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        self._logger.info("GyroscopeInterface avviato")
    
    def stop(self):
        """Ferma il thread di aggiornamento."""
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=1.0)
        self._logger.info("GyroscopeInterface fermato")
    
    def _update_loop(self):
        """Loop di aggiornamento dati (20Hz, sincronizzato con Arduino)."""
        update_interval = 1.0 / 20.0  # 20 Hz (Arduino invia a 20Hz)
        
        while self._running:
            start_time = time.perf_counter()
            
            try:
                self._read_sensor_data()
                
                # Aggiorna stuck detector
                self.stuck_detector.update(self._current_orientation, self._current_motion)
                
                # Verifica callback orientamento
                if self._on_orientation_change:
                    self._on_orientation_change(self._current_orientation)
                
            except Exception as e:
                self._logger.error(f"Errore lettura sensore: {e}")
            
            # Mantieni frequenza costante
            elapsed = time.perf_counter() - start_time
            sleep_time = update_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _read_sensor_data(self):
        """Legge dati dal SerialInterface o simula."""
        with self._lock:
            if self._use_simulation:
                self._simulate_data()
            elif self._serial is not None:
                # Leggi dati dalla seriale (già parsati da serial_interface)
                self._is_connected = self._serial.gyro_connected
                
                if self._is_connected:
                    # Orientamento
                    yaw, pitch, roll, calibration = self._serial.gyro_data
                    self._current_orientation = Orientation(
                        yaw=yaw,
                        pitch=pitch,
                        roll=roll
                    )
                    self._calibration_status = calibration
                    
                    # Dati di movimento
                    linear_accel, angular_velocity = self._serial.motion_data
                    
                    # Converti velocità angolare da rad/s a °/s
                    gyro_deg = tuple(g * 57.2958 for g in angular_velocity)
                    
                    self._current_motion = MotionData(
                        linear_accel=linear_accel,
                        gyro=gyro_deg,
                        gravity=(0.0, 0.0, 9.8)  # Gravità non inviata, default
                    )
                else:
                    # BNO085 non ancora rilevato dall'Arduino
                    pass
            else:
                # Nessuna sorgente dati
                self._use_simulation = True
                self._logger.warning("Nessuna SerialInterface, passo a simulazione")
    
    def _simulate_data(self):
        """Simula dati giroscopio per testing."""
        import random
        noise = lambda: random.uniform(-0.5, 0.5)
        
        self._current_orientation = Orientation(
            yaw=self._sim_yaw + noise(),
            pitch=self._sim_pitch + noise() * 0.5,
            roll=self._sim_roll + noise() * 0.5
        )
        
        self._current_motion = MotionData(
            linear_accel=(noise() * 0.1, noise() * 0.1, 9.8 + noise()),
            gyro=(noise(), noise(), noise()),
            gravity=(0.0, 0.0, 9.8)
        )
        
        # Simula calibrazione completa
        self._calibration_status = (3, 3, 3, 3)
        self._is_connected = True
    
    @property
    def is_connected(self) -> bool:
        """True se il sensore è connesso."""
        return self._is_connected
    
    @property
    def is_simulation(self) -> bool:
        """True se in modalità simulazione."""
        return self._use_simulation
    
    @property
    def orientation(self) -> Orientation:
        """Orientamento attuale (copia)."""
        with self._lock:
            return Orientation(
                yaw=self._current_orientation.yaw,
                pitch=self._current_orientation.pitch,
                roll=self._current_orientation.roll
            )
    
    @property
    def motion(self) -> MotionData:
        """Dati di movimento attuali (copia)."""
        with self._lock:
            return MotionData(
                linear_accel=self._current_motion.linear_accel,
                gyro=self._current_motion.gyro,
                gravity=self._current_motion.gravity
            )
    
    @property
    def calibration_status(self) -> Tuple[int, int, int, int]:
        """Stato calibrazione (sys, gyro, accel, mag). 3=calibrato."""
        return self._calibration_status
    
    @property
    def is_calibrated(self) -> bool:
        """True se tutto calibrato."""
        return all(c == 3 for c in self._calibration_status)
    
    def get_yaw(self) -> float:
        """Restituisce yaw normalizzato 0-360°."""
        return self.orientation.normalized_yaw()
    
    def get_pitch(self) -> float:
        """Restituisce pitch."""
        return self.orientation.pitch
    
    def get_roll(self) -> float:
        """Restituisce roll."""
        return self.orientation.roll
    
    def set_simulated_orientation(self, yaw: float = 0, pitch: float = 0, roll: float = 0):
        """Imposta orientamento in modalità simulazione (per testing)."""
        if self._use_simulation:
            self._sim_yaw = yaw
            self._sim_pitch = pitch
            self._sim_roll = roll
    
    def turn_to_angle(self, target_angle: float, tolerance: float = 5.0) -> bool:
        """Verifica se l'angolo target è raggiunto.
        
        Parameters
        ----------
        target_angle : float
            Angolo target 0-360°
        tolerance : float
            Tolleranza in gradi
            
        Returns
        -------
        bool
            True se angolo raggiunto
        """
        current = self.get_yaw()
        diff = abs(current - target_angle)
        if diff > 180:
            diff = 360 - diff
        return diff <= tolerance
    
    def calculate_turn_direction(self, target_angle: float) -> str:
        """Calcola direzione turn più corta verso target.
        
        Returns
        -------
        str
            'cw' (clockwise), 'ccw' (counter-clockwise), o 'stop' se già arrivato
        """
        current = self.get_yaw()
        diff = (target_angle - current) % 360
        
        if diff <= 5 or diff >= 355:
            return 'stop'
        elif diff < 180:
            return 'cw'  # Destra
        else:
            return 'ccw'  # Sinistra
    
    def is_level(self, tolerance: float = 3.0) -> bool:
        """Verifica se il robot è in piano.
        
        Parameters
        ----------
        tolerance : float
            Tolleranza in gradi
            
        Returns
        -------
        bool
            True se pitch e roll sono entro tolleranza
        """
        orient = self.orientation
        return abs(orient.pitch) <= tolerance and abs(orient.roll) <= tolerance
    
    def get_inclination(self) -> float:
        """Restituisce inclinazione totale (combina pitch e roll)."""
        orient = self.orientation
        return math.sqrt(orient.pitch**2 + orient.roll**2)
    
    def register_orientation_callback(self, callback: Callable, threshold: float = 5.0):
        """Registra callback per cambi orientamento."""
        self._on_orientation_change = callback
        self._orientation_change_threshold = threshold
    
    def get_status_dict(self) -> dict:
        """Restituisce stato completo come dizionario."""
        return {
            'connected': self._is_connected,
            'simulation': self._use_simulation,
            'calibrated': self.is_calibrated,
            'calibration': self._calibration_status,
            'yaw': round(self.get_yaw(), 1),
            'pitch': round(self.get_pitch(), 1),
            'roll': round(self.get_roll(), 1),
            'stuck': self.stuck_detector.is_stuck,
            'level': self.is_level()
        }


# Istanza singleton (inizializzata senza serial, verrà configurata da main.py)
_gyro_instance = None


def get_gyro(serial_interface=None) -> GyroscopeInterface:
    """Restituisce istanza giroscopio.
    
    Parameters
    ----------
    serial_interface : SerialInterface, optional
        Se fornito alla prima chiamata, crea il giroscopio con questa seriale.
        Se il giroscopio esiste già e serial_interface è fornito, aggiorna la seriale.
    """
    global _gyro_instance
    
    if _gyro_instance is None:
        _gyro_instance = GyroscopeInterface(serial_interface)
    elif serial_interface is not None:
        _gyro_instance.set_serial(serial_interface)
    
    return _gyro_instance


def wait_for_calibration(timeout: float = 30.0) -> bool:
    """Attende calibrazione completa.
    
    Parameters
    ----------
    timeout : float
        Timeout in secondi
        
    Returns
    -------
    bool
        True se calibrato, False se timeout
    """
    gyro = get_gyro()
    start = time.time()
    while time.time() - start < timeout:
        if gyro.is_calibrated:
            return True
        time.sleep(0.5)
    return False
