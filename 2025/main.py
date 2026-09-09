# ===========================================================================
# main.py – Ciclo principale RoboCup Line (Versione FASE 5 con Giroscopio)
# ===========================================================================
# Integra: GUI CustomTkinter, state_machine, timer, moving_average, config_manager
# FASE 5: Giroscopio BNO085 + Smart Recovery + Turn precisi
# SENZA ventaglio: se perde la linea si ferma (STOP)
# ===========================================================================

import cv2
import numpy as np
import threading
import time
from multiprocessing import Process, Pipe

# Moduli propri
from usb_camera_process import usb_camera_process
from camera_manager import CameraManager
from line_detector import detect_line_advanced
from color_detector import ColorDetector
from logic_controller import LogicController, set_detection_disabled
from serial_interface import SerialInterface
from visualizer import draw_overlay
from state_machine import current_state, RobotState
from timer import timer
from gui_main import create_gui
from logger import main_logger
from gap_detector import gap_detector, GapInfo
from gyroscope_interface import get_gyro, wait_for_calibration

# ── Parametri configurabili ──────────────────────────────────────────────
DISTANCE_THRESHOLD_CM = 15       # Distanza per attivare schiva-ostacoli
OBSTACLE_PERSIST_FRAMES = 10     # Frame persistenza stato ostacolo (scalato per 60 FPS, era 5 a 30 FPS)
SHOW_ADVANCED = True             # Mostra dati avanzati nell'overlay
USE_GUI = True                   # Usa GUI CustomTkinter
GUI_WIDTH = 800                  # Larghezza GUI
GUI_HEIGHT = 480                 # Altezza GUI

# EMERGENZA: Se il sensore HC-SR04 non funziona, imposta a True
DISABLE_OBSTACLE_DETECTION = False  # Riabilitato - sensore gestisce automaticamente assenza (999)

# EMERGENZA: Se il robot vede gap ovunque, imposta a True  
DISABLE_GAP_DETECTION = False  # Riabilitato - testare funzionamento
# ───────────────────────────────────────────────────────────────────────────


def main():
    # Logging iniziale
    main_logger.info("=" * 60)
    main_logger.info("RoboCup Line - FASE 5 (con Giroscopio BNO085)")
    main_logger.info("=" * 60)
    main_logger.info("Feature: STOP quando perde la linea (NO ventaglio)")
    main_logger.info("Feature: Orientamento assoluto + Turn precisi")
    main_logger.info("Feature: Stuck detection avanzato via giroscopio")
    main_logger.info("GUI: 800x480 CustomTkinter")
    main_logger.info("FASE 5: Gap detection + Logging avanzato + Giroscopio")
    if DISABLE_OBSTACLE_DETECTION:
        main_logger.warning("RILEVAMENTO OSTACOLI DISABILITATO!")
    if DISABLE_GAP_DETECTION:
        main_logger.warning("RILEVAMENTO GAP DISABILITATO!")
    main_logger.info("-" * 60)
    
    print("=" * 60)
    print("RoboCup Line - FASE 5 (con Giroscopio BNO085)")
    print("=" * 60)
    print("Feature: STOP quando perde la linea (NO ventaglio)")
    print("Feature: Orientamento assoluto + Turn precisi")
    print("Feature: Stuck detection avanzato via giroscopio")
    if DISABLE_OBSTACLE_DETECTION:
        print("⚠️  ATTENZIONE: Rilevamento ostacoli DISABILITATO!")
    if DISABLE_GAP_DETECTION:
        print("⚠️  ATTENZIONE: Rilevamento gap DISABILITATO!")
    print("-" * 60)
    
    # ═══════════════════════════════════════════════════════════════════
    # Setup multiprocessing per USB
    # ═══════════════════════════════════════════════════════════════════
    parent_conn, child_conn = Pipe()
    
    usb_process = Process(target=usb_camera_process, 
                          args=(parent_conn, child_conn))
    usb_process.start()
    child_conn.close()
    
    # ═══════════════════════════════════════════════════════════════════
    # Inizializzazione componenti
    # ═══════════════════════════════════════════════════════════════════
    camera = CameraManager()
    color_det = ColorDetector()
    
    # IMPORTANTE: Seriale PRIMA di LogicController!
    # LogicController.__init__ chiama get_gyro() internamente.
    # Se la seriale non è pronta, il giroscopio parte in simulazione.
    serial = SerialInterface()
    
    # Inizializza Giroscopio via Arduino Seriale (FASE 5)
    # Il BNO085 è collegato all'Arduino, i dati arrivano via serial
    gyro = get_gyro(serial_interface=serial)
    gyro.start()
    
    # ORA possiamo creare LogicController (che chiama get_gyro() → singleton già pronto)
    logic = LogicController()
    
    # Configura disabilitazione rilevamenti
    if DISABLE_OBSTACLE_DETECTION or DISABLE_GAP_DETECTION:
        set_detection_disabled(
            obstacle=DISABLE_OBSTACLE_DETECTION,
            gap=DISABLE_GAP_DETECTION
        )
        if DISABLE_OBSTACLE_DETECTION:
            print("⚠️  Rilevamento ostacoli DISABILITATO")
        if DISABLE_GAP_DETECTION:
            print("⚠️  Rilevamento gap DISABILITATO")
    print(f"Giroscopio: {'Hardware (via Arduino)' if not gyro.is_simulation else 'Simulazione'}")
    main_logger.info(f"Giroscopio inizializzato: {'Hardware (via Arduino)' if not gyro.is_simulation else 'Simulazione'}")
    
    # BNO085 si calibra automaticamente in background, non serve aspettare
    print("Giroscopio BNO085 si calibra automaticamente durante l'uso")
    
    # Inizializza GUI
    gui = None
    if USE_GUI:
        gui = create_gui(GUI_WIDTH, GUI_HEIGHT)
        # NOTA: Non avviare in thread separato! Tkinter non è thread-safe
        # La GUI verrà aggiornata nel loop principale con update()
    
    # Buffer frame USB
    latest_usb_frame = None
    obstacle_detected = False
    obstacle_percentage = 0.0
    
    # Sensore distanza
    current_distance_cm = 999
    obstacle_persist_counter = 0
    
    # Stato USB
    usb_status = "USB: INIT"

    # Ultimo angolo
    last_angle = 0

    # Frame counter per GUI update
    frame_counter = 0

    # Timer generale (inizializzazione)
    start_time = time.time()

    print("Sistema pronto. Premi 'q' per uscire, 'c' per calibrazione")
    print("-" * 60)
    
    try:
        while True:
            # ── 1. Acquisizione CSI ────────────────────────────────────
            frame_csi = camera.get_frame()
            
            # ── 2. Rilevamento avanzato ──────────────────────────────
            ramp_ahead = logic.is_ramp_ahead if hasattr(logic, 'is_ramp_ahead') else False
            line_result = detect_line_advanced(frame_csi, last_angle, ramp_ahead=ramp_ahead)
            color_result = color_det.detect(frame_csi)
            
            # Aggiorna ultimo angolo
            if line_result.line_detected:
                last_angle = line_result.line_angle
            
            # ── 3. Ricezione dati USB (ostacoli) ────────────────────
            if parent_conn.poll(0.001):
                try:
                    msg = parent_conn.recv()
                    if isinstance(msg, dict):
                        if "error" in msg:
                            usb_status = "USB: ERR"
                        elif "status" in msg:
                            status = msg["status"]
                            if status == "waiting_camera":
                                usb_status = "USB: NO CAM"
                                latest_usb_frame = None
                            elif status == "camera_connected":
                                usb_status = f"USB: OK"
                            elif status == "camera_lost":
                                usb_status = "USB: PERSA"
                                latest_usb_frame = None
                        elif "obstacle" in msg:
                            obstacle_detected = msg.get("obstacle", False)
                            obstacle_percentage = msg.get("percentage", 0.0)
                            frame_bytes = msg.get("frame")
                            if frame_bytes:
                                nparr = np.frombuffer(frame_bytes, np.uint8)
                                latest_usb_frame = cv2.imdecode(nparr, 
                                    cv2.IMREAD_COLOR)
                                latest_usb_frame = cv2.flip(latest_usb_frame, -1)
                except Exception as e:
                    usb_status = "USB: ERR"
            
            # ── 4. Lettura sensore distanza ──────────────────────────
            current_distance_cm = serial.read_distance()
            
            # DEBUG: Log distanza ogni 60 frame (~1s a 60 FPS)
            if frame_counter % 60 == 0:
                print(f"[DEBUG] Distanza: {current_distance_cm}cm")
            
            # Controlla se disabilitare rilevamento ostacoli
            if DISABLE_OBSTACLE_DETECTION:
                sensor_obstacle = False  # Ignora completamente il sensore
            else:
                # Solo sensore HC-SR04, ignora telecamera USB per ostacoli
                sensor_obstacle = (current_distance_cm != 999 and 
                                 current_distance_cm <= DISTANCE_THRESHOLD_CM)
                if sensor_obstacle and frame_counter % 20 == 0:
                    print(f"[OSTACOLO] Distanza: {current_distance_cm}cm <= {DISTANCE_THRESHOLD_CM}cm")
            
            # ── 5. Estrazione gap info ───────────────────────────────
            gap_info = None
            # Solo se gap detection non è disabilitato
            if not DISABLE_GAP_DETECTION and hasattr(line_result, 'gap_detected') and line_result.gap_detected:
                gap_info = GapInfo(
                    detected=True,
                    validated=getattr(line_result, 'gap_validated', False),
                    angle=getattr(line_result, 'gap_angle', -181),
                    center_x=getattr(line_result, 'gap_center_x', -181),
                    center_y=getattr(line_result, 'gap_center_y', -1),
                    confidence=getattr(line_result, 'gap_confidence', 0.5)
                )
            
            # ── 6. Decisione comando ─────────────────────────────────
            # NOTA: Usiamo SOLO il sensore di distanza HC-SR04 per ostacoli
            # La telecamera USB viene ignorata per evitare falsi positivi
            # Passiamo il frame per image similarity check nel recovery system
            command = logic.decide(line_result, color_result,
                                  sensor_obstacle,  # Solo sensore distanza, non telecamera USB
                                  current_distance_cm, gap_info,
                                  frame_csi)  # Frame per Smart Recovery
            
            # Gestione persistenza ostacolo
            if sensor_obstacle:
                obstacle_persist_counter = OBSTACLE_PERSIST_FRAMES
            elif obstacle_persist_counter > 0:
                obstacle_persist_counter -= 1
            
            # ── 7. Invio seriale ─────────────────────────────────────
            serial.send(command)
            
            # Logging periodico (ogni 60 frame ~1s a 60 FPS)
            if frame_counter % 60 == 0:
                main_logger.debug("Main loop status",
                                frame=frame_counter,
                                state=logic.current_state_name,
                                line_detected=line_result.line_detected,
                                gap_detected=gap_info.detected if gap_info else False,
                                distance=current_distance_cm,
                                command=command)
            
            # ── 8. Aggiornamento GUI ────────────────────────────────
            if gui is not None:
                frame_counter += 1
                
                # Aggiorna frame video ogni 4 frame (~15 FPS display a 60 FPS camera)
                if frame_counter % 4 == 0:
                    # Stato
                    gui.queue_update('state',
                                    state=logic.current_state_name,
                                    command=command)
                    
                    # Telemetria
                    gui.queue_update('telemetry',
                                    angle=line_result.line_angle,
                                    gap_detected=getattr(line_result, 'gap_detected', False),
                                    gap_angle=getattr(line_result, 'gap_angle', -181),
                                    has_left=line_result.has_left,
                                    has_center=line_result.has_center,
                                    has_right=line_result.has_right,
                                    green_left=color_result.green_left,
                                    green_right=color_result.green_right,
                                    red_detected=color_result.red_detected)
                    
                    # Hardware + Giroscopio + Timer + Recovery
                    elapsed_time = time.time() - start_time
                    gyro_data = gyro.get_status_dict()
                    recovery_status = logic._recovery_manager.get_status_dict() if hasattr(logic, '_recovery_manager') else {}
                    gui.queue_update('hardware',
                                    elapsed_time=elapsed_time,
                                    distance=current_distance_cm,
                                    obstacle=obstacle_detected or sensor_obstacle,
                                    serial_connected=serial.is_connected,
                                    serial_port=serial.port_name if serial.is_connected else 'N/A',
                                    gyro_connected=gyro_data['connected'],
                                    gyro_simulation=gyro_data['simulation'],
                                    gyro_yaw=gyro_data['yaw'],
                                    gyro_pitch=gyro_data['pitch'],
                                    gyro_roll=gyro_data['roll'],
                                    gyro_calibrated=gyro_data['calibrated'],
                                    gyro_calibration=gyro_data.get('calibration', (0,0,0,0)),
                                    gyro_stuck=gyro_data['stuck'],
                                    gyro_level=gyro_data['level'],
                                    recovery_state=recovery_status.get('state', 'IDLE'),
                                    recovery_attempt=recovery_status.get('attempt', 0),
                                    is_stuck=recovery_status.get('is_stuck', False))
                    
                    # Frame video
                    display_frame_csi = draw_overlay(
                        frame_csi.copy(), line_result, color_result, command,
                        serial_status="" if serial.is_connected else "DISCONNESSO",
                        distance_status=f"{current_distance_cm}cm" if current_distance_cm != 999 else "",
                        usb_status=usb_status,
                        search_status=logic.current_state_name,
                        show_advanced=SHOW_ADVANCED
                    )
                    gui.set_csi_frame(display_frame_csi)
                    
                    if latest_usb_frame is not None:
                        gui.set_usb_frame(latest_usb_frame)
                
                # Aggiorna Tkinter SEMPRE (per reattività finestre e code)
                gui.update()
                
                # Controlla se utente ha premuto Esci
                if gui.should_exit:
                    print("Uscita richiesta dall'utente (GUI)")
                    break
            
            # ── 9. Visualizzazione OpenCV (se GUI disabilitata) ───────
            if not USE_GUI:
                ser_status = (f"SER: {serial.port_name}" 
                           if serial.is_connected 
                           else "SER: DISCONNESSO")
                
                dist_status = f"DIST: {current_distance_cm}cm"
                show_distance = (current_distance_cm > 0 and 
                               current_distance_cm != 999)
                
                display_frame_csi = draw_overlay(
                    frame_csi, line_result, color_result, command,
                    serial_status=ser_status,
                    distance_status=dist_status if show_distance else "",
                    usb_status=usb_status,
                    search_status=logic.current_state_name,
                    show_advanced=SHOW_ADVANCED
                )
                
                if latest_usb_frame is not None:
                    csi_h, csi_w = display_frame_csi.shape[:2]
                    usb_h, usb_w = latest_usb_frame.shape[:2]
                    
                    if usb_w != csi_w:
                        scale = csi_w / usb_w
                        new_h = int(usb_h * scale)
                        latest_usb_frame = cv2.resize(latest_usb_frame, 
                                                      (csi_w, new_h))
                    
                    csi_h = display_frame_csi.shape[0]
                    usb_h = latest_usb_frame.shape[0]
                    
                    if usb_h != csi_h:
                        scale = csi_h / usb_h
                        new_w = int(latest_usb_frame.shape[1] * scale)
                        latest_usb_frame = cv2.resize(latest_usb_frame, 
                                                      (new_w, csi_h))
                    
                    final_display = np.hstack([display_frame_csi, latest_usb_frame])
                else:
                    final_display = display_frame_csi
                
                cv2.imshow("RoboCup Line - FASE 5", final_display)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("c"):
                    print("Calibrazione non disponibile in modalità OpenCV")
                
                # Piccolo delay per non saturare la CPU
                time.sleep(0.001)  # 1ms - camera a 60 FPS già limita il loop
            
            # Delay quando GUI è attiva
            if USE_GUI:
                time.sleep(0.002)  # 2ms - minimo per non saturare CPU, camera già limita a 60 FPS
    
    except KeyboardInterrupt:
        print("\nInterruzione da tastiera...")
        main_logger.info("KeyboardInterrupt received - shutting down")
    
    except Exception as e:
        main_logger.error(f"Unexpected error: {e}", error=str(e))
        raise
    
    finally:
        print("Pulizia risorse...")
        main_logger.info("Cleaning up resources...")
        
        # 1. GUI per prima! Così non ci sono callback Tkinter che
        #    tentano di accedere a risorse già chiuse.
        if USE_GUI and gui is not None:
            gui.close()
        else:
            cv2.destroyAllWindows()
        
        # 2. Ferma giroscopio
        print("Arresto giroscopio...")
        gyro.stop()
        
        # 3. Processo USB
        try:
            parent_conn.send("STOP")
        except Exception:
            pass
        usb_process.join(timeout=2)
        if usb_process.is_alive():
            usb_process.terminate()
        
        try:
            parent_conn.close()
        except Exception:
            pass
        
        # 4. Seriale e camera
        serial.close()
        camera.close()
        
        # 5. Esporta log per debug
        try:
            main_logger.export_to_json("logs/session_final.json")
            print("Log esportato in logs/session_final.json")
        except Exception as e:
            print(f"Errore esportazione log: {e}")
        
        main_logger.close()
        print("Sistema arrestato.")


if __name__ == "__main__":
    main()
