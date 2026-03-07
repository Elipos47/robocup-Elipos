# ===========================================================================
# logic_controller.py – Logica decisionale avanzata con Smart Recovery + Giroscopio
# ===========================================================================
# Quando perde la linea: Smart Recovery automatico (stile Overengineered)
# Integra: state_machine, timer, PID, recovery_manager, gap_detector, giroscopio
# ===========================================================================

import time
import numpy as np
from state_machine import current_state, RobotState
from timer import timer
from moving_average import sensor_averages
from config_manager import config_manager
from logger import main_logger, get_logger
from gap_detector import gap_detector, GapInfo
from gyroscope_interface import get_gyro, Orientation
from recovery_manager import get_recovery_manager, RecoveryState

# Configurazione globale 
# Vengono impostate da main.py all'avvio
DISABLE_OBSTACLE_DETECTION = False
DISABLE_GAP_DETECTION = False

def set_detection_disabled(obstacle=False, gap=False):
    """Imposta quali rilevamenti disabilitare."""
    global DISABLE_OBSTACLE_DETECTION, DISABLE_GAP_DETECTION
    DISABLE_OBSTACLE_DETECTION = obstacle
    DISABLE_GAP_DETECTION = gap
    if obstacle:
        main_logger.info("Obstacle detection DISABLED")
    if gap:
        main_logger.info("Gap detection DISABLED")

# ── Parametri configurabili ────────────────────────────────────────────────
# Deadband e soglie angolo
DEADBAND_CENTER = 0.15
HYSTERESIS_MARGIN = 0.20  # Aumentato da 0.08 - isteresi più violenta per evitare oscillazioni
ANGLE_THRESHOLD = 25
ANGLE_DEADBAND = 8

# Lock comandi verdi
# NOTA: Scalato per 60 FPS (era 45 a 30 FPS = ~1.5s, ora 90 a 60 FPS = ~1.5s)
GREEN_LOCK_DURATION = 90

# Frame width (deve corrispondere a config.ini [camera] width)
FRAME_WIDTH = 448

# Soglie per stati (da config.ini)
LINE_LOSS_THRESHOLD = config_manager.read_variable("detection", "line_loss_threshold", 5)
GAP_VALIDATION_FRAMES = config_manager.read_variable("detection", "gap_validation_frames", 3)
OBSTACLE_DISTANCE_CM = config_manager.read_variable("detection", "obstacle_distance_cm", 15)

# Timeout safety
STOP_TIMEOUT = config_manager.read_variable("control", "stop_timeout", 5.0)

# Parametri curve (da config.ini)
CURVE_ENTRY_DELAY = config_manager.read_variable("control", "curve_entry_delay", 1)
CURVE_EXIT_THRESHOLD = config_manager.read_variable("control", "curve_exit_threshold", 10)
CURVE_EXIT_FRAMES = config_manager.read_variable("control", "curve_exit_frames", 2)
CURVE_FORWARD_RATIO = config_manager.read_variable("control", "curve_forward_ratio", 4)

# Soglia seesaw (da config.ini)
SEESAW_PITCH_THRESHOLD = config_manager.read_variable("control", "seesaw_pitch_threshold", -8)
SEESAW_MIN_FRAMES = config_manager.read_variable("control", "seesaw_min_frames", 5)
# ───────────────────────────────────────────────────────────────────────────

# Comandi validi
CMD_FORWARD = "A"
CMD_STOP = "S"
CMD_GENTLE_RIGHT = "gd"
CMD_GENTLE_LEFT = "gs"
CMD_TURN_RIGHT = "cd"
CMD_TURN_LEFT = "cs"
CMD_U_TURN = "iu"
CMD_OBSTACLE = "obj"
CMD_BACKWARD = "ind"


class LogicController:
    """Controllore decisionale avanzato con Smart Recovery + Giroscopio."""

    def __init__(self, frame_width=FRAME_WIDTH):
        self._frame_width = frame_width
        self._frames_line_lost = 0

        # Stato lock verdi
        self._green_lock_frames = 0
        self._green_lock_command = None

        # Stato isteresi
        self._last_direction = 0
        self._last_angle = 0

        # Stato gap
        self._gap_validation_frames = 0
        self._current_gap_info: GapInfo = GapInfo()
        self._last_gap_time = 0

        # PID per controllo sterzo
        self._last_error = 0
        self._integral = 0

        # Logger
        self._logger = get_logger("LOGIC_CTRL")

        # Smart Recovery Manager (NUOVO)
        self._recovery_manager = get_recovery_manager()
        self._last_frame = None  # type: ignore

        # Giroscopio
        self._gyro = get_gyro()
        self._turn_target_angle = None
        self._turn_start_orientation = None
        self._last_gyro_check = 0

        # Stuck detection avanzata con giroscopio
        self._stuck_recovery_angle = 0
        self._stuck_recovery_attempts = 0
        
        # Curve
        self._curve_entry_counter = 0       # Frame di entry delay rimasti
        self._curve_frame_counter = 0       # Counter per forward interleaving
        self._was_in_curve = False           # Se era in curva nel frame precedente
        self._curve_exit_counter = 0         # Isteresi uscita curva
        
        # Seesaw detection
        self._seesaw_frames = 0               # Frame consecutivi con pitch inclinato
        self._seesaw_active = False            # Se seesaw/rampa attiva
        
        # Inizializza stato
        current_state.reset(RobotState.LINE_DETECTED)

        self._logger.info("LogicController inizializzato (con Smart Recovery + Giroscopio)")
        self._logger.info("Configurazione",
                         line_loss_threshold=LINE_LOSS_THRESHOLD,
                         gap_validation_frames=GAP_VALIDATION_FRAMES,
                         obstacle_distance=OBSTACLE_DISTANCE_CM,
                         smart_recovery=True,
                         gyroscope_enabled=True,
                         curve_persist="proportional",
                         curve_entry_delay=CURVE_ENTRY_DELAY)

    def decide(self, line_detection, color_detection, obstacle_detected=False, 
               distance_cm=999, gap_info=None, frame=None):
        """Decide il comando da inviare ad Arduino.

        Parameters
        ----------
        line_detection : LineDetection
            Risultato dal line_detector
        color_detection : ColorDetection
            Risultato dal color_detector
        obstacle_detected : bool
            True se ostacolo rilevato da telecamera USB
        distance_cm : float
            Distanza dal sensore HC-SR04
        gap_info : GapInfo, optional
            Informazioni sul gap rilevato
        frame : np.ndarray, optional
            Frame corrente per image similarity check
            
        Returns
        -------
        str
            Comando valido
        """
        # Aggiorna medie mobili
        if line_detection.line_detected:
            sensor_averages.update_line(
                line_detection.line_angle,
                line_detection.line_size
            )
        
        sensor_averages.update_distance(distance_cm)
        
        # Aggiorna gap info
        if gap_info is not None:
            self._current_gap_info = gap_info
        elif hasattr(line_detection, 'gap_detected') and line_detection.gap_detected:
            # Estrai da line_detection se disponibile
            self._current_gap_info = GapInfo(
                detected=True,
                validated=getattr(line_detection, 'gap_validated', False),
                angle=getattr(line_detection, 'gap_angle', -181),
                center_x=getattr(line_detection, 'gap_center_x', -181),
                center_y=getattr(line_detection, 'gap_center_y', -1)
            )
        
        # Decrementa lock verdi
        if self._green_lock_frames > 0:
            self._green_lock_frames -= 1
            if self._green_lock_frames == 0:
                self._green_lock_command = None
            else:
                # Durante lock, continua comando verde
                self._frames_line_lost = 0
                return self._green_lock_command
        
        # Seesaw/rampa detection via giroscopio
        self._update_seesaw_state()
        
        # Gestione stati
        command = self._handle_states(
            line_detection, color_detection,
            obstacle_detected, distance_cm, frame
        )

        # Log comando
        self._logger.command_sent(command, {
            'state': current_state.state_name,
            'line_detected': line_detection.line_detected,
            'gap_detected': self._current_gap_info.detected if self._current_gap_info else False,
            'recovery': self._recovery_manager.recovery_state.name
        })

        return command

    def _handle_states(self, line_detection, color_detection, 
                       obstacle_detected, distance_cm, frame=None):
        """Gestisce la macchina a stati."""
        
        current = current_state.current_state
        
        # PRIORITÀ 1: ROSSO = STOP immediato
        if color_detection.red_detected:
            if current != RobotState.STOP:
                current_state.transition_to(RobotState.STOP, "red_detected")
                timer.set_timer("stop_timeout", STOP_TIMEOUT)
            return CMD_STOP
        
        # PRIORITÀ 2: OSTACOLO (solo se non disabilitato)
        if not DISABLE_OBSTACLE_DETECTION:
            sensor_obstacle = (distance_cm != 999 and 
                              distance_cm <= OBSTACLE_DISTANCE_CM)
            
            if sensor_obstacle or obstacle_detected:
                if current != RobotState.OBSTACLE_DETECTED:
                    current_state.transition_to(
                        RobotState.OBSTACLE_DETECTED, 
                        f"obstacle_sensor:{distance_cm}cm"
                    )
                return CMD_OBSTACLE
        
        # Se ostacolo disabilitato ma siamo già in stato ostacolo, forza uscita
        if DISABLE_OBSTACLE_DETECTION and current in [RobotState.OBSTACLE_DETECTED, RobotState.OBSTACLE_AVOID]:
            self._logger.info("Obstacle detection disabled - forcing LINE_DETECTED")
            current_state.transition_to(RobotState.LINE_DETECTED, "obstacle_disabled")
            return CMD_FORWARD
        
        # Gestione per stato corrente
        if current == RobotState.LINE_DETECTED:
            return self._state_line_detected(line_detection, color_detection)
        
        elif current == RobotState.GAP_DETECTED:
            return self._state_gap_detected(line_detection)
        
        elif current == RobotState.GAP_AVOID:
            return self._state_gap_avoid(line_detection)
        
        elif current == RobotState.OBSTACLE_DETECTED:
            return self._state_obstacle_detected(line_detection)
        
        elif current == RobotState.OBSTACLE_AVOID:
            return self._state_obstacle_avoid(line_detection)
        
        elif current == RobotState.STOP:
            return self._state_stop(line_detection, frame)
        
        # Default
        return CMD_STOP

    def _state_line_detected(self, line_detection, color_detection):
        """Gestione stato LINE_DETECTED con rilevamento gap."""
        
        # Linea rilevata?
        if line_detection.line_detected:
            self._frames_line_lost = 0
            self._gap_validation_frames = 0
            
            # Controlla marker verdi
            if color_detection.green_left and color_detection.green_right:
                self._green_lock_frames = GREEN_LOCK_DURATION
                self._green_lock_command = CMD_U_TURN
                self._logger.info("U-turn triggered by green markers")
                return CMD_U_TURN
            
            if color_detection.green_left:
                self._green_lock_frames = GREEN_LOCK_DURATION
                self._green_lock_command = CMD_TURN_LEFT
                self._logger.info("Turn left triggered by green marker")
                return CMD_TURN_LEFT
            
            if color_detection.green_right:
                self._green_lock_frames = GREEN_LOCK_DURATION
                self._green_lock_command = CMD_TURN_RIGHT
                self._logger.info("Turn right triggered by green marker")
                return CMD_TURN_RIGHT
            
            # Line-following normale
            return self._follow_line(line_detection)
        
        else:
            # Linea non rilevata - incrementa contatore
            self._frames_line_lost += 1
            
            # Verifica se è un gap validato (solo se gap detection abilitato)
            if not DISABLE_GAP_DETECTION and self._current_gap_info and self._current_gap_info.validated:
                self._logger.info("Gap validated - transitioning to GAP_DETECTED",
                                gap_angle=self._current_gap_info.angle,
                                gap_confidence=self._current_gap_info.confidence)
                current_state.transition_to(
                    RobotState.GAP_DETECTED,
                    f"gap_validated_conf{self._current_gap_info.confidence:.2f}"
                )
                return CMD_STOP  # Fermati per iniziare sequenza gap
            
            # Verifica se è un gap in rilevamento (solo se gap detection abilitato)
            if not DISABLE_GAP_DETECTION and self._current_gap_info and self._current_gap_info.detected:
                self._gap_validation_frames += 1
                if self._gap_validation_frames >= GAP_VALIDATION_FRAMES:
                    self._logger.info("Gap detection validated",
                                    validation_frames=self._gap_validation_frames)
                    current_state.transition_to(
                        RobotState.GAP_DETECTED,
                        f"gap_detected_{self._gap_validation_frames}frames"
                    )
                    return CMD_STOP
            
            # Se persa per troppi frame -> STOP
            if self._frames_line_lost >= LINE_LOSS_THRESHOLD:
                self._logger.warning("Line lost - STOP",
                                   frames_lost=self._frames_line_lost)
                current_state.transition_to(
                    RobotState.STOP, 
                    f"line_lost_{self._frames_line_lost}_frames"
                )
                timer.set_timer("stop_timeout", STOP_TIMEOUT)
                return CMD_STOP
            
            # Per breve tempo: continua con ultima direzione nota
            return self._follow_last_known()

    def _update_seesaw_state(self):
        """Aggiorna stato seesaw/rampa dal giroscopio."""
        pitch = self._gyro.orientation.pitch if self._gyro.is_connected else 0
        
        if pitch < SEESAW_PITCH_THRESHOLD:
            self._seesaw_frames += 1
            if self._seesaw_frames >= SEESAW_MIN_FRAMES and not self._seesaw_active:
                self._seesaw_active = True
                self._logger.info("Seesaw/rampa rilevata",
                                 pitch=pitch,
                                 frames=self._seesaw_frames)
        else:
            if self._seesaw_active and self._seesaw_frames > 0:
                self._logger.info("Seesaw/rampa terminata")
            self._seesaw_frames = 0
            self._seesaw_active = False

    @property
    def is_ramp_ahead(self):
        """True se il robot e' su una seesaw/rampa."""
        return self._seesaw_active

    def _follow_line(self, line_detection):
        """Segue la linea. Semplificato: entry delay + forward interleaving.

        - Entry delay: 1 frame avanti quando si entra in curva
        - Forward interleaving: 1 frame avanti ogni 3 frame di curva (SEMPRE)
        - Isteresi uscita: serve angolo < 10 per 2 frame per uscire da curva
        - Nessuna persistenza, nessuna anti-oscillazione
        """

        if not hasattr(line_detection, 'line_angle'):
            return self._follow_centroid(line_detection)

        angle = line_detection.line_angle
        self._last_angle = angle
        abs_angle = abs(angle)

        # Determina se siamo in curva (con isteresi uscita)
        in_curve = False
        if abs_angle > 15:
            in_curve = True
            self._curve_exit_counter = 0
        elif self._was_in_curve:
            if abs_angle < CURVE_EXIT_THRESHOLD:
                self._curve_exit_counter += 1
                if self._curve_exit_counter < CURVE_EXIT_FRAMES:
                    in_curve = True
            else:
                in_curve = True
                self._curve_exit_counter = 0

        # ── FASE 1: IN CURVA ──
        if in_curve:
            self._integral = 0

            # Direzione curva
            if angle < 0:
                desired_direction = 1
                cmd = CMD_GENTLE_RIGHT
            else:
                desired_direction = -1
                cmd = CMD_GENTLE_LEFT

            # Entry delay (solo all'ingresso in curva)
            if not self._was_in_curve:
                self._curve_entry_counter = CURVE_ENTRY_DELAY
                self._was_in_curve = True
                self._curve_frame_counter = 0

            if self._curve_entry_counter > 0:
                self._curve_entry_counter -= 1
                return CMD_FORWARD

            # Forward interleaving: 1 avanti ogni CURVE_FORWARD_RATIO frame
            self._curve_frame_counter += 1
            if self._curve_frame_counter % CURVE_FORWARD_RATIO == 0:
                return CMD_FORWARD

            # Altrimenti: curva nella direzione rilevata
            self._last_direction = desired_direction
            return cmd

        # ── FASE 2: RETTILINEO ──
        self._was_in_curve = False
        self._curve_entry_counter = 0
        self._curve_frame_counter = 0
        self._curve_exit_counter = 0

        centroid = getattr(line_detection, 'global_centroid', None)
        if centroid is None:
            self._last_direction = 0
            return CMD_FORWARD

        cx = centroid[0]
        center_x = self._frame_width / 2.0

        deadband = self._frame_width * DEADBAND_CENTER
        hysteresis = self._frame_width * HYSTERESIS_MARGIN
        offset = cx - center_x

        if self._last_direction == -1:
            threshold = deadband + hysteresis
            if offset > threshold:
                self._last_direction = 1
                return CMD_GENTLE_RIGHT
            elif offset > -threshold:
                self._last_direction = 0
                return CMD_FORWARD
            else:
                return CMD_GENTLE_LEFT

        elif self._last_direction == 1:
            threshold = deadband + hysteresis
            if offset < -threshold:
                self._last_direction = -1
                return CMD_GENTLE_LEFT
            elif offset < threshold:
                self._last_direction = 0
                return CMD_FORWARD
            else:
                return CMD_GENTLE_RIGHT

        else:
            if abs(offset) <= deadband:
                self._last_direction = 0
                return CMD_FORWARD
            elif offset < -deadband:
                self._last_direction = -1
                return CMD_GENTLE_LEFT
            else:
                self._last_direction = 1
                return CMD_GENTLE_RIGHT

    def _follow_centroid(self, line_detection):
        """Fallback: segue la linea usando il centroide."""
        if line_detection.global_centroid is None:
            self._last_direction = 0
            return CMD_FORWARD
        
        cx = line_detection.global_centroid[0]
        center_x = self._frame_width / 2.0
        deadband = self._frame_width * DEADBAND_CENTER
        hysteresis = self._frame_width * HYSTERESIS_MARGIN
        
        offset = cx - center_x
        
        # Isteresi
        if self._last_direction == -1:
            threshold = deadband + hysteresis
            if offset > threshold:
                self._last_direction = 1
                return CMD_GENTLE_RIGHT
            elif offset > -threshold:
                self._last_direction = 0
                return CMD_FORWARD
            else:
                return CMD_GENTLE_LEFT
        
        elif self._last_direction == 1:
            threshold = deadband + hysteresis
            if offset < -threshold:
                self._last_direction = -1
                return CMD_GENTLE_LEFT
            elif offset < threshold:
                self._last_direction = 0
                return CMD_FORWARD
            else:
                return CMD_GENTLE_RIGHT
        
        else:
            if abs(offset) <= deadband:
                self._last_direction = 0
                return CMD_FORWARD
            elif offset < -deadband:
                self._last_direction = -1
                return CMD_GENTLE_LEFT
            else:
                self._last_direction = 1
                return CMD_GENTLE_RIGHT

    def _follow_last_known(self):
        """Continua con ultima direzione nota quando linea non rilevata temporaneamente."""
        if self._last_direction == -1:
            return CMD_GENTLE_LEFT
        elif self._last_direction == 1:
            return CMD_GENTLE_RIGHT
        return CMD_FORWARD

    def _state_gap_detected(self, line_detection):
        """Gestione stato GAP_DETECTED - Orientamento e preparazione."""
        
        # Se linea tornata, esci dallo stato gap
        if line_detection.line_detected and self._frames_line_lost == 0:
            self._logger.info("Line reacquired during gap detection")
            current_state.transition_to(RobotState.LINE_DETECTED, "line_reacquired")
            return CMD_FORWARD
        
        # Usa gap_detector per sequenza di orientamento
        if not gap_detector._orientation_phase:
            gap_detector.start_orientation()
            self._logger.info("Gap orientation started",
                            gap_angle=self._current_gap_info.angle if self._current_gap_info else -181)
        
        # Ottieni comando di orientamento
        orient_cmd = gap_detector.get_orientation_command(self._current_gap_info)
        
        # Se orientamento completato (ritorna 'S' quando finito)
        if orient_cmd == "S" and gap_detector._orientation_phase == 0:
            # Orientamento completato, inizia attraversamento
            self._logger.info("Gap orientation completed - starting crossing")
            current_state.transition_to(RobotState.GAP_AVOID, "orientation_complete")
            gap_detector.start_crossing()
            return CMD_FORWARD
        
        return orient_cmd

    def _state_gap_avoid(self, line_detection):
        """Gestione stato GAP_AVOID - Attraversamento gap."""
        
        # Verifica se attraversamento completato
        if gap_detector.is_crossing_complete():
            self._logger.info("Gap crossing completed")
            
            # Se linea rilevata, torna a LINE_DETECTED
            if line_detection.line_detected:
                current_state.transition_to(
                    RobotState.LINE_DETECTED, 
                    "line_reacquired_after_gap"
                )
                return CMD_FORWARD
            else:
                # Linea non ancora rilevata, continua avanti
                self._logger.warning("Gap crossed but line not detected yet")
                timer.set_timer("gap_search_line", 1.0)
                return CMD_FORWARD
        
        # Durante attraversamento: avanti dritto
        return gap_detector.get_crossing_command()

    def _state_obstacle_detected(self, line_detection):
        """Gestione stato OBSTACLE_DETECTED."""
        # Attende che l'Arduino gestisca l'ostacolo
        # Timer per evitare stallo
        if not timer.has_timer("obstacle_timeout"):
            timer.set_timer("obstacle_timeout", 10.0)
            self._logger.warning("Obstacle detected - timeout started")
        
        # Verifica timeout ostacolo
        if timer.get_timer("obstacle_timeout"):
            self._logger.error("Obstacle timeout - forcing exit")
            current_state.transition_to(RobotState.OBSTACLE_AVOID, "timeout")
        
        return CMD_OBSTACLE

    def _state_obstacle_avoid(self, line_detection):
        """Gestione stato OBSTACLE_AVOID."""
        # Rileva quando ostacolo superato
        if line_detection.line_detected:
            self._logger.info("Line reacquired after obstacle")
            current_state.transition_to(
                RobotState.LINE_DETECTED, 
                "line_reacquired_after_obstacle"
            )
            return CMD_FORWARD
        
        # Se timeout ostacolo scaduto, prova a recuperare
        if timer.get_timer("obstacle_timeout"):
            self._logger.warning("Obstacle timeout expired - attempting recovery")
            # Prova a muoverti lentamente per trovare la linea
            return CMD_FORWARD
        
        return CMD_OBSTACLE

    def _state_stop(self, line_detection, frame=None):
        """Gestione stato STOP con Smart Recovery automatico + Giroscopio."""
        
        # Image similarity check (se frame disponibile)
        if frame is not None:
            similarity_result = self._recovery_manager._similarity_checker.update(frame)
            if similarity_result.is_stuck:
                self._logger.warning("STUCK detected via image similarity",
                                    similarity=similarity_result.similarity,
                                    frames_stuck=similarity_result.frames_stuck)
        
        # Verifica anche stuck detector del giroscopio
        if self._gyro.stuck_detector.is_stuck:
            self._logger.warning("STUCK detected by gyroscope",
                                stuck_frames=self._gyro.stuck_detector.stuck_frames)
        
        # Se recovery in corso, continua sequenza
        if self._recovery_manager.is_recovering:
            command, _ = self._recovery_manager.update(
                line_detection.line_detected, 
                frame
            )
            
            # Se linea ritrovata durante recovery
            if line_detection.line_detected:
                self._logger.info("Line reacquired during recovery - success!")
                self._recovery_manager.reset()
                self._frames_line_lost = 0
                self._stuck_recovery_attempts = 0
                current_state.transition_to(
                    RobotState.LINE_DETECTED, 
                    "recovery_successful"
                )
                return CMD_FORWARD
            
            return command
        
        # Verifica timeout
        timeout_expired = timer.get_timer("stop_timeout")
        
        if timeout_expired:
            self._logger.warning("STOP timeout expired - starting Smart Recovery")
            
            # Avvia Smart Recovery
            recovery_command = self._recovery_manager.start_recovery()
            return recovery_command
        
        # Rimanere in STOP finché linea non torna o timeout
        if line_detection.line_detected:
            self._frames_line_lost = 0
            self._recovery_manager.reset()
            self._stuck_recovery_attempts = 0
            self._logger.info("Line reacquired - resuming operation")
            current_state.transition_to(
                RobotState.LINE_DETECTED,
                "line_reacquired"
            )
            return CMD_FORWARD
        
        return CMD_STOP
    
    def _handle_stuck_recovery(self):
        """Recovery avanzato quando bloccato (usa giroscopio)."""
        self._stuck_recovery_attempts += 1
        
        if self._stuck_recovery_attempts == 1:
            # Primo tentativo: torna indietro di 20cm (usa timer)
            self._logger.info("Stuck recovery: backup")
            timer.set_timer("stuck_backup", 0.8)
            return CMD_BACKWARD
        
        elif self._stuck_recovery_attempts == 2:
            # Secondo tentativo: ruota di 90° usando giroscopio
            self._logger.info("Stuck recovery: 90° turn")
            self._turn_target_angle = (self._gyro.get_yaw() + 90) % 360
            self._turn_start_orientation = self._gyro.orientation
            return self._execute_precise_turn()
        
        elif self._stuck_recovery_attempts == 3:
            # Terzo tentativo: ruota di -90° (altro lato)
            self._logger.info("Stuck recovery: -90° turn")
            self._turn_target_angle = (self._gyro.get_yaw() - 90) % 360
            self._turn_start_orientation = self._gyro.orientation
            return self._execute_precise_turn()
        
        else:
            # Troppi tentativi, resetta e riprova più tardi
            self._logger.error("Stuck recovery failed after 3 attempts - giving up")
            self._stuck_recovery_attempts = 0
            timer.set_timer("stuck_retry_delay", 3.0)
            return CMD_STOP
    
    def _perform_oriented_recovery(self):
        """Recovery con orientamento preciso (usa giroscopio)."""
        # Salva orientamento attuale
        current_yaw = self._gyro.get_yaw()
        
        if self._stuck_recovery_angle == 0:
            # Primo tentativo: muoviti leggermente a destra
            self._logger.info("Oriented recovery: gentle right")
            self._stuck_recovery_angle = current_yaw
            timer.set_timer("recovery_attempt", 0.5)
            return CMD_GENTLE_RIGHT
        
        elif self._stuck_recovery_attempts < 2:
            # Secondo tentativo: ruota di 45° e avanza
            self._logger.info("Oriented recovery: 45° turn and forward")
            self._turn_target_angle = (current_yaw + 45) % 360
            self._turn_start_orientation = self._gyro.orientation
            timer.set_timer("recovery_turn", 1.0)
            return self._execute_precise_turn()
        
        else:
            # Reset e riprova
            self._logger.info("Oriented recovery: resetting")
            self._stuck_recovery_attempts = 0
            self._stuck_recovery_angle = 0
            return CMD_STOP
    
    def _execute_precise_turn(self) -> str:
        """Esegue turn preciso verso target angle (usa giroscopio).
        
        Returns
        -------
        str
            Comando per Arduino
        """
        if self._turn_target_angle is None:
            return CMD_STOP
        
        # Verifica se angolo raggiunto
        if self._gyro.turn_to_angle(self._turn_target_angle, tolerance=5.0):
            self._logger.info(f"Precise turn completed: {self._turn_target_angle:.1f}°")
            self._turn_target_angle = None
            self._turn_start_orientation = None
            return CMD_FORWARD
        
        # Calcola direzione turn
        direction = self._gyro.calculate_turn_direction(self._turn_target_angle)
        
        if direction == 'cw':
            return CMD_TURN_RIGHT
        elif direction == 'ccw':
            return CMD_TURN_LEFT
        else:
            return CMD_STOP
    
    def start_precise_turn(self, degrees: float) -> str:
        """Inizia un turn preciso di N gradi.
        
        Parameters
        ----------
        degrees : float
            Gradi da girare (positivo = destra, negativo = sinistra)
            
        Returns
        -------
        str
            Primo comando del turn
        """
        current_yaw = self._gyro.get_yaw()
        self._turn_target_angle = (current_yaw + degrees) % 360
        self._turn_start_orientation = self._gyro.orientation
        
        self._logger.info(f"Starting precise turn: {degrees:+.1f}° (target: {self._turn_target_angle:.1f}°)")
        
        return self._execute_precise_turn()

    def reset(self):
        """Reset completo del controllore."""
        self._frames_line_lost = 0
        self._green_lock_frames = 0
        self._green_lock_command = None
        self._last_direction = 0
        self._last_angle = 0
        self._last_error = 0
        self._integral = 0
        self._gap_validation_frames = 0
        self._current_gap_info = GapInfo()
        self._stuck_recovery_attempts = 0
        self._stuck_recovery_angle = 0
        self._curve_entry_counter = 0
        self._curve_frame_counter = 0
        self._was_in_curve = False
        self._curve_exit_counter = 0
        self._seesaw_frames = 0
        self._seesaw_active = False

        # Reset gap detector
        gap_detector.reset()
        
        # Reset recovery manager
        self._recovery_manager.reset()

        # Reset stato
        current_state.reset(RobotState.LINE_DETECTED)

        self._logger.info("LogicController resettato")
        main_logger.info("System reset completed")

    @property
    def is_searching(self):
        """Sempre False (ricerca a V rimossa)."""
        return False

    @property
    def search_state_name(self):
        """Nome stato ricerca (sempre STOP)."""
        return "STOP"
    
    @property
    def current_state_name(self):
        """Nome stato corrente della state machine."""
        return current_state.state_name
    
    @property
    def status_message(self):
        """Messaggio di stato per debug."""
        gap_status = ""
        if self._current_gap_info and self._current_gap_info.detected:
            gap_status = f" | Gap: {self._current_gap_info.confidence:.0%}"
        
        return f"State: {self.current_state_name} | Lost: {self._frames_line_lost}f{gap_status}"


# Funzione compatibilità
from line_detector import LineDetection
from color_detector import ColorDetection
