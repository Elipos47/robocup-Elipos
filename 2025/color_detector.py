# ===========================================================================
# color_detector.py – Rilevamento segnali con calibrazione runtime
# ===========================================================================
# FASE 2: Aggiunta calibrazione runtime con trackbar OpenCV
# ===========================================================================

import cv2
import numpy as np
from config_manager import config_manager

# ── Soglie HSV caricabili da config ───────────────────────────────────────
def load_hsv_values():
    """Carica valori HSV dal config manager."""
    global GREEN_HSV_LOW, GREEN_HSV_HIGH
    global RED_HSV_LOW_1, RED_HSV_HIGH_1, RED_HSV_LOW_2, RED_HSV_HIGH_2

    GREEN_HSV_LOW = config_manager.read_variable('color_values', 'green_hsv_low',
                                                  np.array([40, 50, 50]))
    GREEN_HSV_HIGH = config_manager.read_variable('color_values', 'green_hsv_high',
                                                   np.array([80, 255, 255]))

    RED_HSV_LOW_1 = config_manager.read_variable('color_values', 'red_hsv_low_1',
                                                  np.array([0, 100, 50]))
    RED_HSV_HIGH_1 = config_manager.read_variable('color_values', 'red_hsv_high_1',
                                                   np.array([10, 255, 255]))
    RED_HSV_LOW_2 = config_manager.read_variable('color_values', 'red_hsv_low_2',
                                                np.array([170, 100, 50]))
    RED_HSV_HIGH_2 = config_manager.read_variable('color_values', 'red_hsv_high_2',
                                                 np.array([180, 255, 255]))

# Carica valori all'avvio
load_hsv_values()

# ── Filtri blob ────────────────────────────────────────────────────────────
GREEN_MIN_AREA       = 200       # Area minima blob verde (px²)
RED_MIN_AREA         = 300       # Area minima blob rosso (px²)
ASPECT_RATIO_TOL     = 0.3      # Tolleranza aspect-ratio rispetto a 1.0

# ── Debounce ───────────────────────────────────────────────────────────────
GREEN_DEBOUNCE_FRAMES = 3       # Frame consecutivi necessari per conferma
# ───────────────────────────────────────────────────────────────────────────


class ColorDetection:
    """Struttura dati con i risultati del rilevamento colore."""

    __slots__ = (
        "green_left", "green_right", "red_detected",
        "green_boxes", "red_boxes",
    )

    def __init__(self):
        self.green_left   = False
        self.green_right  = False
        self.red_detected = False

        # Liste di bounding box (x, y, w, h) – per overlay
        self.green_boxes = []
        self.red_boxes   = []


class ColorDetector:
    """Rilevatore di segnali colorati con debounce sui verdi."""

    def __init__(self):
        self._green_left_count  = 0
        self._green_right_count = 0

    # ── Metodo principale ─────────────────────────────────────────────────
    def detect(self, frame_rgb):
        """Analizza il frame RGB e restituisce un oggetto ColorDetection.

        Parameters
        ----------
        frame_rgb : np.ndarray
            Frame in formato RGB (H x W x 3).

        Returns
        -------
        ColorDetection
        """
        h, w = frame_rgb.shape[:2]
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        result = ColorDetection()

        # ── Rilevamento VERDE (solo fasce laterali) ───────────────────────
        green_mask = cv2.inRange(hsv, GREEN_HSV_LOW, GREEN_HSV_HIGH)
        raw_green_left, raw_green_right, green_boxes = self._find_green(
            green_mask, w
        )

        # Debounce verde sinistra
        if raw_green_left:
            self._green_left_count += 1
        else:
            self._green_left_count = 0

        # Debounce verde destra
        if raw_green_right:
            self._green_right_count += 1
        else:
            self._green_right_count = 0

        result.green_left  = self._green_left_count  >= GREEN_DEBOUNCE_FRAMES
        result.green_right = self._green_right_count >= GREEN_DEBOUNCE_FRAMES
        result.green_boxes = green_boxes

        # ── Rilevamento ROSSO (tutta l'immagine) ─────────────────────────
        red_mask_1 = cv2.inRange(hsv, RED_HSV_LOW_1, RED_HSV_HIGH_1)
        red_mask_2 = cv2.inRange(hsv, RED_HSV_LOW_2, RED_HSV_HIGH_2)
        red_mask   = cv2.bitwise_or(red_mask_1, red_mask_2)

        result.red_detected, result.red_boxes = self._find_red(red_mask)

        return result

    # ── Helpers privati ───────────────────────────────────────────────────
    @staticmethod
    def _is_square(w_box, h_box):
        """Verifica se il bounding box ha aspect ratio ≈ 1."""
        if h_box == 0:
            return False
        ar = w_box / h_box
        return (1.0 - ASPECT_RATIO_TOL) <= ar <= (1.0 + ASPECT_RATIO_TOL)

    @staticmethod
    def _find_green(mask, frame_w):
        """Trova blob verdi nelle fasce sinistra e destra dell'immagine."""
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        found_left  = False
        found_right = False
        boxes = []

        third = frame_w // 3

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < GREEN_MIN_AREA:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if not ColorDetector._is_square(bw, bh):
                continue

            cx = x + bw // 2
            if cx < third:
                found_left = True
                boxes.append((x, y, bw, bh))
            elif cx > 2 * third:
                found_right = True
                boxes.append((x, y, bw, bh))

        return found_left, found_right, boxes

    @staticmethod
    def _find_red(mask):
        """Trova blob rossi in tutta l'immagine."""
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        detected = False
        boxes = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < RED_MIN_AREA:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if not ColorDetector._is_square(bw, bh):
                continue
            detected = True
            boxes.append((x, y, bw, bh))

        return detected, boxes
