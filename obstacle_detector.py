# ===========================================================================
#  obstacle_detector.py – Rilevamento ostacoli con telecamera USB frontale
# ===========================================================================
#  Gestisce la logica di rilevamento ostacoli usando un VideoCapture
#  già aperto (passato dal main).
# ===========================================================================

import cv2
import numpy as np

# ── Parametri configurabili ────────────────────────────────────────────────
# ROI ostacolo (centro dell'immagine)
ROI_OBSTACLE_Y_START = 0.2         # Inizio ROI verticale (frazione)
ROI_OBSTACLE_Y_END = 0.8           # Fine ROI verticale (frazione)
ROI_OBSTACLE_X_START = 0.2         # Inizio ROI orizzontale (frazione)
ROI_OBSTACLE_X_END = 0.8           # Fine ROI orizzontale (frazione)

OBSTACLE_THRESHOLD_PERCENT = 60    # Percentuale pixel scuri per triggerare ostacolo
DARK_PIXEL_THRESHOLD = 50          # Soglia sotto cui un pixel è considerato "scuro" (0-255)
# ───────────────────────────────────────────────────────────────────────────


class ObstacleDetector:
    """Rileva ostacoli usando un VideoCapture già aperto."""

    def __init__(self, video_capture):
        """
        Parameters
        ----------
        video_capture : cv2.VideoCapture
            VideoCapture già aperto e configurato per la telecamera USB.
        """
        self._cap = video_capture

    def detect(self):
        """Rileva ostacolo nel frame corrente.
        
        Returns
        -------
        tuple
            (bool, np.ndarray) - (ostacolo rilevato, frame annotato o None)
        """
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return False, None

        h, w = frame.shape[:2]
        
        # Coordinate ROI
        y_start = int(h * ROI_OBSTACLE_Y_START)
        y_end = int(h * ROI_OBSTACLE_Y_END)
        x_start = int(w * ROI_OBSTACLE_X_START)
        x_end = int(w * ROI_OBSTACLE_X_END)
        
        # Estrai ROI
        roi = frame[y_start:y_end, x_start:x_end]
        
        # Scala di grigi
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Conta pixel scuri
        dark_pixels = np.sum(gray < DARK_PIXEL_THRESHOLD)
        total_pixels = gray.size
        dark_percentage = (dark_pixels / total_pixels) * 100
        
        obstacle_detected = dark_percentage >= OBSTACLE_THRESHOLD_PERCENT
        
        # Disegna ROI sul frame
        roi_color = (0, 0, 255) if obstacle_detected else (0, 255, 0)
        cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), roi_color, 3)
        
        # Testo
        text = f"Ostacolo: {dark_percentage:.1f}%"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, roi_color, 2)
        cv2.putText(frame, "USB (Frontale)", (10, 60), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2)
        
        return obstacle_detected, frame
