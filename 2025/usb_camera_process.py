# ===========================================================================
#  usb_camera_process.py – Processo separato per la telecamera USB
# ===========================================================================
#  Questo processo gestisce esclusivamente la telecamera USB usando solo OpenCV.
#  Non importa picamera2/libcamera, quindi nessun conflitto.
#  Comunica con il processo principale tramite pipe multiprocessing.
#  Supporta hot-plug: riconnette automaticamente se la telecamera si disconnette.
# ===========================================================================

import cv2
import numpy as np
import time
import os
from multiprocessing import Pipe

# Parametri ostacolo
ROI_OBSTACLE_Y_START = 0.1         # Aumenta ROI per rilevare ostacoli più lontani
ROI_OBSTACLE_Y_END = 0.9
ROI_OBSTACLE_X_START = 0.1
ROI_OBSTACLE_X_END = 0.9
OBSTACLE_THRESHOLD_PERCENT = 20    # Soglia più bassa per rilevare prima
OBSTACLE_DEBOUNCE_FRAMES = 5       # Frame consecutivi necessari per confermare
DARK_PIXEL_THRESHOLD = 50

# Parametri riconnessione
MAX_CAMERAS_TO_TRY = 10            # Prova da /dev/video0 a /dev/video9
RECONNECT_DELAY = 1.0              # Secondi tra tentativi di riconnessione
FRAME_FAIL_THRESHOLD = 30          # Frame persi consecutivi prima di riconnettere


def find_usb_camera():
    """Trova una telecamera USB disponibile tra /dev/video0-9."""
    for i in range(MAX_CAMERAS_TO_TRY):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            # Prova ad aprire
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if cap.isOpened():
                # Verifica che produca effettivamente frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.release()
                    return device
                cap.release()
    return None


def usb_camera_process(pipe_parent, pipe_child):
    """Funzione eseguita nel processo separato per la USB."""
    # Chiudi il lato parent nel processo figlio
    pipe_parent.close()
    
    cap = None
    consecutive_frames = 0
    frame_fail_count = 0
    camera_device = None
    
    try:
        while True:
            # Controlla se ci sono comandi dal parent
            if pipe_child.poll():
                msg = pipe_child.recv()
                if msg == "STOP":
                    break
            
            # Se non abbiamo una telecamera aperta, cerca e apri
            if cap is None or not cap.isOpened():
                camera_device = find_usb_camera()
                if camera_device is None:
                    # Nessuna telecamera trovata, aspetta e riprova
                    pipe_child.send({"status": "waiting_camera"})
                    time.sleep(RECONNECT_DELAY)
                    continue
                
                # Apri telecamera trovata
                cap = cv2.VideoCapture(camera_device, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(camera_device)
                
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    frame_fail_count = 0
                    pipe_child.send({"status": "camera_connected", "device": camera_device})
                else:
                    time.sleep(RECONNECT_DELAY)
                    continue
            
            # Acquisisci frame
            ret, frame = cap.read()
            
            if not ret or frame is None:
                frame_fail_count += 1
                if frame_fail_count >= FRAME_FAIL_THRESHOLD:
                    # Telecamera probabilmente scollegata
                    cap.release()
                    cap = None
                    pipe_child.send({"status": "camera_lost"})
                continue
            
            # Frame letto con successo, reset counter
            frame_fail_count = 0
            
            # Rileva ostacolo
            h, w = frame.shape[:2]
            y_start = int(h * ROI_OBSTACLE_Y_START)
            y_end = int(h * ROI_OBSTACLE_Y_END)
            x_start = int(w * ROI_OBSTACLE_X_START)
            x_end = int(w * 0.8)
            
            roi = frame[y_start:y_end, x_start:x_end]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            dark_pixels = np.sum(gray < DARK_PIXEL_THRESHOLD)
            dark_percentage = (dark_pixels / gray.size) * 100
            
            # Sistema debounce
            if dark_percentage >= OBSTACLE_THRESHOLD_PERCENT:
                consecutive_frames += 1
            else:
                consecutive_frames = 0
            
            obstacle_detected = consecutive_frames >= OBSTACLE_DEBOUNCE_FRAMES
            
            # Invia risultato
            frame_encoded = cv2.imencode('.jpg', frame)[1].tobytes()
            pipe_child.send({
                "obstacle": obstacle_detected,
                "percentage": dark_percentage,
                "frame": frame_encoded
            })
            
    finally:
        if cap is not None:
            cap.release()
        pipe_child.close()
