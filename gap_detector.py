# ===========================================================================
# gap_detector.py – Rilevamento e validazione gap avanzata (stile Overengineered)
# ===========================================================================
# FASE 2: Gap detection con validazione robusta e orientamento iterativo
# Implementa validazione stile Overengineered con backup/orientamento multi-step
# ===========================================================================

import cv2
import numpy as np
import time
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from state_machine import current_state, RobotState
from timer import timer as timer_manager
from logger import get_logger

# ── Parametri configurabili ────────────────────────────────────────────────
# Validazione gap (stile Overengineered)
GAP_VALIDATION_MIN_FRAMES = 3
GAP_VALIDATION_MAX_DISTANCE = 50
GAP_MIN_CONFIDENCE = 0.7
GAP_MIN_AREA = 1000
GAP_MAX_AREA = 20000

# Orientamento gap (multi-step)
GAP_ORIENTATION_TIME = 0.35
GAP_BACKUP_TIME_SHORT = 0.15  # Primo backup (stile Overengineered)
GAP_BACKUP_TIME_LONG = 0.30   # Secondo backup
GAP_FORWARD_ALIGN_TIME = 0.25
GAP_CHECK_SILVER_TIME = 0.20

# Attraversamento gap
GAP_CROSS_SPEED = 0.7
GAP_CROSS_TIME_MIN = 0.5
GAP_CROSS_TIME_MAX = 1.5
GAP_CROSS_TIME_BASE = 0.25

# Correzioni
GAP_ANGLE_TOLERANCE = 15
GAP_POSITION_TOLERANCE = 20

# Iterazioni massime orientamento (stile Overengineered: 7 iterazioni)
GAP_MAX_ORIENTATION_ITERATIONS = 7
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class GapInfo:
    """Informazioni su un gap rilevato."""
    detected: bool = False
    validated: bool = False
    angle: float = -181.0
    center_x: int = -181
    center_y: int = -1
    confidence: float = 0.0
    width: int = 0
    height: int = 0
    area: int = 0


class GapDetector:
    """Rilevamento e validazione avanzata dei gap (stile Overengineered)."""

    def __init__(self):
        """Inizializza il detector gap."""
        self._logger = get_logger("GAP_DET")
        self._validation_frames = 0
        self._last_gap_info = GapInfo()
        self._orientation_phase = 0
        self._orientation_iteration = 0
        self._crossing_active = False
        self._validation_buffer: List[GapInfo] = []
        self._validation_in_progress = False

    def detect(self, contours: list, black_mask: np.ndarray, 
               frame_w: int, roi_h: int) -> GapInfo:
        """Rileva gap nella maschera nera."""

        # Trova aree bianche (non nere) nella maschera
        white_mask = cv2.bitwise_not(black_mask)

        # Escludi bordi
        margin = 10
        white_mask[:margin, :] = 0
        white_mask[-margin:, :] = 0
        white_mask[:, :margin] = 0
        white_mask[:, -margin:] = 0

        # Trova contorni aree bianche
        white_contours, _ = cv2.findContours(white_mask, cv2.RETR_LIST, 
                                             cv2.CHAIN_APPROX_SIMPLE)

        # Trova il miglior candidato gap
        best_gap = None
        best_score = 0

        for cnt in white_contours:
            area = cv2.contourArea(cnt)
            if not (1000 < area < 20000):
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w < 30 or h < 20:
                continue

            score = self._calculate_gap_score(cnt, frame_w, roi_h)

            if score > best_score:
                best_score = score
                best_gap = cnt

        if best_gap is None:
            self._validation_frames = 0
            self._validation_buffer = []
            return GapInfo()

        gap_info = self._extract_gap_info(best_gap, frame_w, roi_h)

        # Validazione temporale
        self._validation_buffer.append(gap_info)
        if len(self._validation_buffer) > GAP_VALIDATION_MIN_FRAMES:
            self._validation_buffer.pop(0)

        if len(self._validation_buffer) >= GAP_VALIDATION_MIN_FRAMES:
            if self._validate_consistency():
                gap_info.validated = True
                gap_info.confidence = len(self._validation_buffer) / GAP_VALIDATION_MIN_FRAMES

        self._last_gap_info = gap_info
        return gap_info

    def _calculate_gap_score(self, contour, frame_w, roi_h) -> float:
        """Calcola score per un candidato gap."""
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)

        area_score = min(area / 5000, 1.0)
        center_x = x + w // 2
        center_score = 1.0 - abs(center_x - frame_w // 2) / (frame_w // 2)
        aspect = w / h if h > 0 else 1
        shape_score = 1.0 - abs(aspect - 2.0) / 2.0
        bottom_y = y + h
        vert_score = bottom_y / roi_h

        return (area_score * 0.3 + center_score * 0.3 + 
                shape_score * 0.2 + vert_score * 0.2)

    def _extract_gap_info(self, contour, frame_w, roi_h) -> GapInfo:
        """Estrae informazioni da un contorno gap."""
        x, y, w, h = cv2.boundingRect(contour)
        center_x = x + w // 2
        center_y = y + h // 2

        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.intp(box)

        angle = -181.0
        if len(box) >= 2:
            box_sorted = box[box[:, 1].argsort()]
            p1 = box_sorted[0]
            p2 = box_sorted[-1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            if dy != 0:
                angle = np.arctan2(dx, dy) * 180 / np.pi

        return GapInfo(
            detected=True,
            angle=angle,
            center_x=int((center_x - frame_w / 2) / (frame_w / 2) * 180),
            center_y=center_y,
            width=w,
            height=h,
            area=cv2.contourArea(contour)
        )

    def _validate_consistency(self) -> bool:
        """Verifica che i gap rilevati siano consistenti."""
        if len(self._validation_buffer) < GAP_VALIDATION_MIN_FRAMES:
            return False

        centers_x = [g.center_x for g in self._validation_buffer]
        centers_y = [g.center_y for g in self._validation_buffer]

        if len(centers_x) < 2:
            return False

        dx = max(centers_x) - min(centers_x)
        dy = max(centers_y) - min(centers_y)

        return dx < GAP_VALIDATION_MAX_DISTANCE and dy < GAP_VALIDATION_MAX_DISTANCE

    def start_orientation(self):
        """Avvia sequenza di orientamento al gap (stile Overengineered)."""
        self._orientation_phase = 0
        self._orientation_iteration = 0
        timer_manager.set_timer("gap_orientation", GAP_ORIENTATION_TIME)
        self._logger.info("Gap orientation started")

    def get_orientation_command(self, gap_info: GapInfo) -> str:
        """Restituisce comando per orientamento gap (stile Overengineered)."""

        if not gap_info.validated:
            return "S"

        if timer_manager.get_timer("gap_orientation"):
            self._orientation_phase += 1
            self._orientation_iteration += 1

            if self._orientation_iteration > GAP_MAX_ORIENTATION_ITERATIONS:
                self._logger.warning("Max orientation iterations reached")
                self._orientation_phase = 5

            if self._orientation_phase == 1:
                timer_manager.set_timer("gap_orientation", GAP_BACKUP_TIME_SHORT)
                self._logger.debug("Gap orientation: short backup")
                return "ind"
            elif self._orientation_phase == 2:
                timer_manager.set_timer("gap_orientation", GAP_FORWARD_ALIGN_TIME)
                self._logger.debug("Gap orientation: forward alignment")
                return "A"
            elif self._orientation_phase == 3:
                timer_manager.set_timer("gap_orientation", GAP_CHECK_SILVER_TIME)
                self._logger.debug("Gap orientation: check silver")
                return "S"
            elif self._orientation_phase == 4:
                timer_manager.set_timer("gap_orientation", GAP_BACKUP_TIME_LONG)
                self._logger.debug("Gap orientation: long backup")
                return "ind"
            else:
                self._orientation_phase = 0
                self._logger.info("Gap orientation completed")
                return "S"

        # Continua fase corrente
        if self._orientation_phase == 0:
            return "S"
        elif self._orientation_phase == 1:
            return "ind"
        elif self._orientation_phase == 2:
            return "A"
        elif self._orientation_phase == 3:
            return "S"
        elif self._orientation_phase == 4:
            return "ind"
        else:
            return "S"

    def start_crossing(self):
        """Avvia attraversamento gap."""
        self._crossing_active = True
        timer_manager.set_timer("gap_crossing", GAP_CROSS_TIME_MIN)

    def is_crossing_complete(self) -> bool:
        """Verifica se l'attraversamento è completato."""
        if not self._crossing_active:
            return True
        if timer_manager.get_timer("gap_crossing"):
            self._crossing_active = False
            return True
        return False

    def get_crossing_command(self) -> str:
        """Restituisce comando durante attraversamento."""
        if self._crossing_active:
            return "A"
        return "S"

    def reset(self):
        """Resetta lo stato del detector."""
        self._validation_frames = 0
        self._validation_buffer = []
        self._orientation_phase = 0
        self._orientation_iteration = 0
        self._crossing_active = False
        self._last_gap_info = GapInfo()
        self._logger.info("GapDetector resettato")


def validate_gap_orientation(gap_info: GapInfo, 
                             current_angle: float) -> bool:
    """Valida se l'orientamento al gap è corretto.
    
    Parameters
    ----------
    gap_info : GapInfo
        Informazioni sul gap
    current_angle : float
        Angolo attuale del robot
        
    Returns
    -------
    bool
        True se orientamento valido
    """
    if not gap_info.validated:
        return False
    
    # Verifica angolo gap
    if abs(gap_info.angle) > GAP_ANGLE_TOLERANCE:
        return False
    
    # Verifica posizione
    if abs(gap_info.center_x) > GAP_POSITION_TOLERANCE:
        return False
    
    return True


def calculate_gap_distance(gap_info: GapInfo, 
                            camera_params: dict) -> float:
    """Calcola distanza approssimativa dal gap.
    
    Parameters
    ----------
    gap_info : GapInfo
        Informazioni sul gap
    camera_params : dict
        Parametri camera (focal_length, pixel_size, etc.)
        
    Returns
    -------
    float
        Distanza stimata in cm
    """
    # Approssimazione semplice basata sull'altezza nel frame
    if gap_info.center_y <= 0:
        return -1
    
    # Distanza inversamente proporzionale alla posizione Y
    # (più in basso = più vicino)
    roi_h = camera_params.get('roi_h', 200)
    focal_length = camera_params.get('focal_length', 500)
    
    # Stima semplice
    normalized_y = gap_info.center_y / roi_h
    distance = 100 / (normalized_y + 0.1)  # cm
    
    return distance


# Istanza singleton
gap_detector = GapDetector()
