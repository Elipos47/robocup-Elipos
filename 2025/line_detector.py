# ===========================================================================
# line_detector.py – Rilevamento intelligente ibrido (OLD + OVERENGINEERED)
# ===========================================================================
# Architettura ibrida: ROI OLD per seguilinea perfetto + logica OVERENGINEERED
# ===========================================================================

import cv2
import numpy as np
from typing import Optional, Tuple, List, Any
from config_manager import config_manager
from state_machine import current_state, RobotState

# ── Parametri camera (devono corrispondere a config.ini [camera]) ──────────
# Usati solo per inizializzazione default, la funzione detect_line_advanced()
# legge le dimensioni reali dal frame (h, w = frame.shape[:2])
CAMERA_WIDTH = 448
CAMERA_HEIGHT = 252

# ── HSV Dinamico per il NERO (da Overengineered) ──────────────────────────
# Soglie ridotte per evitare falsi positivi con ombre
BLACK_MIN = np.array([0, 0, 0])
_bt = config_manager.read_variable("detection", "black_threshold_top", 65)
_bb = config_manager.read_variable("detection", "black_threshold_bottom", 95)
BLACK_MAX_NORMAL_TOP = np.array([_bt, _bt, _bt])
BLACK_MAX_NORMAL_BOTTOM = np.array([_bb, _bb, _bb])
BLACK_MAX_SILVER_VALIDATE_TOP_OFF = np.array([50, 50, 50])
BLACK_MAX_SILVER_VALIDATE_BOTTOM_OFF = np.array([48, 48, 48])
BLACK_MAX_SILVER_VALIDATE_TOP_ON = np.array([60, 60, 60])
BLACK_MAX_SILVER_VALIDATE_BOTTOM_ON = np.array([80, 80, 80])
BLACK_MAX_RAMP_DOWN_TOP = np.array([40, 40, 40])

# ── Filtro anti-ombre in HSV ──────────────────────────────────────────────
# Le ombre hanno Value medio (40-120) e Saturation variabile.
# La linea nera vera ha Value molto basso (<50) e Saturation bassa.
SHADOW_V_MIN = config_manager.read_variable("detection", "shadow_v_min", 100)    # Sotto questo V è nero vero, sopra potrebbe essere ombra (era 60, causava asimmetria L/R)
SHADOW_S_MAX = 80    # Se S è alto con V medio, è ombra colorata

# ── Parametri origine OLD (ottimi per seguilinea) ─────────────────────────
ROI_HEIGHT_START_OLD = 0.20  # Vede bene la posizione centrale
ROI_HEIGHT_END_OLD = 0.60    # Non arriva troppo in basso

# ── Parametri per compensazione camera avanti ────────────────────────────
VERTICAL_THRESHOLD = 15      # Sotto questi gradi considera quasi verticale
CENTER_TOLERANCE = 0.15      # Quanto è tollerante per centro (15%)
CURVE_COMPENSATION = 5       # Gradi di ritardo per camera avanti (ridotto da 12: troppo aggressivo per curve)

# ── Marcatori colori ──────────────────────────────────────────────────────
GREEN_MIN = np.array([40, 50, 45])
GREEN_MAX = np.array([85, 255, 255])
RED_MIN_1 = np.array([0, 100, 90])
RED_MAX_1 = np.array([10, 255, 255])
RED_MIN_2 = np.array([170, 100, 100])
RED_MAX_2 = np.array([180, 255, 255])

# ── Parametri gap (scalati per 448x252, rapporto area vs 640x480 ≈ 0.49) ──
GAP_MIN_AREA = 490
GAP_MAX_AREA = 9800
GAP_MIN_WIDTH = 21
GAP_MIN_HEIGHT = 14

# ── Parametri marker (scalati per 448x252) ────────────────────────────────
ASPECT_RATIO_TOL = 0.3
GREEN_MIN_AREA = 1225
RED_MIN_AREA = 735

# ── Tracciamento storico ──────────────────────────────────────────────────
x_last = CAMERA_WIDTH / 2
y_last = CAMERA_HEIGHT / 2


class LineDetection:
    """Risultati rilevamento ibrido: OLD precisione + OVERENGINEERED logica."""

    __slots__ = (
        "has_left", "has_center", "has_right",
        "centroid_left", "centroid_center", "centroid_right",
        "global_centroid", "roi_y_start", "roi_y_end",
        "line_angle", "line_angle_y", "line_size",
        "turn_direction", "bottom_point", "top_point",
        "line_detected", "green_left", "green_right",
        "red_detected", "contour", "poi",
        "gap_detected", "gap_angle", "gap_center_x", "gap_center_y",
        "lateral_deviation", "centered"  # Aggiunte per correzione laterale
    )

    def __init__(self):
        # Stato base
        self.has_left: bool = False
        self.has_center: bool = False
        self.has_right: bool = False
        self.centroid_left: Optional[Tuple[int, int]] = None
        self.centroid_center: Optional[Tuple[int, int]] = None
        self.centroid_right: Optional[Tuple[int, int]] = None
        self.global_centroid: Optional[Tuple[int, int]] = None
        self.roi_y_start: int = 0
        self.roi_y_end: int = CAMERA_HEIGHT
        
        # Dati avanzati
        self.line_angle: int = 0
        self.line_angle_y: int = -1
        self.line_size: int = 0
        self.turn_direction: str = "straight"
        self.bottom_point: Optional[Tuple[int, int]] = None
        self.top_point: Optional[Tuple[int, int]] = None
        self.line_detected: bool = False
        
        # Marker
        self.green_left: bool = False
        self.green_right: bool = False
        self.red_detected: bool = False
        
        # Debug
        self.contour: Optional[Any] = None
        self.poi: Optional[Tuple[int, int]] = None
        
        # Gap detection
        self.gap_detected: bool = False
        self.gap_angle: float = -181.0
        self.gap_center_x: int = -181
        self.gap_center_y: int = -1
        
        # Nuovi attributi per correzione laterale
        self.lateral_deviation: float = 0.0  # Differenza da centro (-1 a 1)
        self.centered: bool = False          # Se è sufficientemente centrato


class SmartROIManager:
    """Gestione intelligente della ROI ibrida."""
    
    @staticmethod
    def get_optimal_roi(line_angle: float, global_centroid: Optional[Tuple[int, int]], 
                      frame_width: int, frame_height: int) -> Tuple[int, int]:
        """Restituisce ROI ottimale in base a situazione corrente."""
        
        angle_abs = abs(line_angle)
        
        # Caso: linea quasi verticale ma non centrale → usa ROI estesa
        if angle_abs < VERTICAL_THRESHOLD:
            if global_centroid and not SmartROIManager.is_line_centered(global_centroid, frame_width):
                # Usa ROI alta per vedere tutta la linea e correggere posizione
                start_pct = 0.10  # Vede ancora più in alto
                end_pct = 0.60
            else:
                start_pct = ROI_HEIGHT_START_OLD
                end_pct = ROI_HEIGHT_END_OLD
        # Caso: curve strette → focus sull'angolo davanti
        elif angle_abs > 30:
            start_pct = 0.35
            end_pct = 0.75
        # Caso: curve medie → compromesso
        else:
            start_pct = 0.20
            end_pct = 0.70
        
        return (int(frame_height * start_pct), int(frame_height * end_pct))
    
    @staticmethod
    def is_line_centered(centroid: Tuple[int, int], frame_width: int) -> bool:
        """Controlla se la linea è sufficientemente centrata."""
        center_x = frame_width / 2.0
        tolerance = frame_width * CENTER_TOLERANCE
        return abs(centroid[0] - center_x) <= tolerance


class HSVColorManager:
    """Gestione colori HSV dinamica."""
    
    @staticmethod
    def get_black_thresholds(ramp_ahead: bool = False) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Restituisce soglie HSV per il nero in base alla situazione."""
        
        black_max_top = BLACK_MAX_NORMAL_TOP
        black_max_bottom = BLACK_MAX_NORMAL_BOTTOM
        
        if ramp_ahead:
            black_max_top = BLACK_MAX_RAMP_DOWN_TOP
        
        return BLACK_MIN, black_max_top, black_max_bottom


def detect_line_advanced(frame_rgb: np.ndarray,
                         last_angle: float = 0,
                         ramp_ahead: bool = False,
                         for_calibration: bool = False) -> LineDetection:
    """Rilevamento ibrido: ROI DINAMICO + OVERENGINEERED logica."""

    h, w = frame_rgb.shape[:2]
    result = LineDetection()

    # ─────────────────────────────────────────────────────────────────────
    # 1. CALCOLO ROI DINAMICO BASATO SULLA SITUAZIONE
    # ─────────────────────────────────────────────────────────────────────

    # ROI ampio e fisso: usa sempre tutta la zona utile del frame.
    # A 448x252, la ROI deve essere abbastanza grande da catturare le curve
    # anche quando last_angle è ancora ~0 (inizio curva).
    # L'approccio precedente (ROI dipendente da last_angle) creava una 
    # "spirale della morte": angolo basso → ROI stretta → curva non vista →
    # angolo resta basso → linea persa.
    roi_start_pct = 0.20
    roi_end_pct = 0.85

    roi_start = int(h * roi_start_pct)
    roi_end = int(h * roi_end_pct)

    result.roi_y_start = roi_start
    result.roi_y_end = roi_end
    
    # ─────────────────────────────────────────────────────────────────────
    # 2. CONVERSIONE HSV e SOGLIE DINAMICHE (da Overengineered)
    # ─────────────────────────────────────────────────────────────────────
    
    hsv_image = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2HSV)
    
    black_min, black_max_top, black_max_bottom = HSVColorManager.get_black_thresholds(ramp_ahead)
    
    # Applica inRange con soglie differenziate
    black_image_bottom = cv2.inRange(frame_rgb, black_min, black_max_bottom)
    black_image_top = cv2.inRange(frame_rgb, black_min, black_max_top)
    
    black_image = black_image_bottom.copy()
    h_threshold = int(h * 0.4)
    black_image[0:h_threshold, :] = black_image_top[0:h_threshold, :]
    
    # ── Filtro anti-ombre: rimuovi pixel con V medio-alto (ombre) ─────
    # Le ombre hanno Value > SHADOW_V_MIN ma non sono nere vere.
    # Creiamo una maschera delle ombre e la sottraiamo.
    v_channel = hsv_image[:, :, 2]  # Value channel
    s_channel = hsv_image[:, :, 1]  # Saturation channel
    # Ombra: V abbastanza alto (non nero) OPPURE S alto con V medio
    shadow_mask = ((v_channel > SHADOW_V_MIN) & (v_channel < 160)).astype(np.uint8) * 255
    black_image = cv2.subtract(black_image, shadow_mask)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3. SOTTRAZIONE COLORI VERDI (da Overengineered)
    # ─────────────────────────────────────────────────────────────────────
    
    green_mask = cv2.inRange(hsv_image, GREEN_MIN, GREEN_MAX)
    black_image = cv2.subtract(black_image, green_mask)
    black_image[black_image < 2] = 0
    
    # ─────────────────────────────────────────────────────────────────────
    # 4. RILEVAMENTO RAMPA (da Overengineered)
    # ─────────────────────────────────────────────────────────────────────
    
    dark_ahead = False
    if not for_calibration:
        black_mean = np.mean(black_image[0:int(h * 0.25), :])
        if black_mean > 90:
            black_image_ramp = cv2.inRange(frame_rgb, black_min, BLACK_MAX_RAMP_DOWN_TOP)
            black_image_ramp = cv2.subtract(black_image_ramp, green_mask)
            black_mean_ramp = np.mean(black_image_ramp[0:int(h * 0.25), :])
            
            if black_mean_ramp + 30 < black_mean:
                black_image[0:int(h * 0.4), :] = black_image_ramp[0:int(h * 0.4), :]
                dark_ahead = True
    
    # ─────────────────────────────────────────────────────────────────────
    # 5. APPLICA ROI CALCOLATA (nuovo: ricalcola ROI dopo rilevamento)
    # ─────────────────────────────────────────────────────────────────────
    
    roi_black = black_image[roi_start:roi_end, :]
    
    # ─────────────────────────────────────────────────────────────────────
    # 6. MORFOLOGIA ADATTIVA (da Overengineered)
    # ─────────────────────────────────────────────────────────────────────
    
    _ks = config_manager.read_variable("morphology", "kernel_size", 3)
    kernel = np.ones((_ks, _ks), np.uint8)
    state = getattr(current_state, 'current_state', RobotState.LINE_DETECTED)
    
    if state == RobotState.GAP_AVOID:
        # GAP_AVOID: 2-step only (no final erode)
        # Net dilation bias keeps the line thick so it's easier to reacquire after gap
        erode1 = config_manager.read_variable("morphology", "erode_iterations_gap", 3)
        dilate_iter = config_manager.read_variable("morphology", "dilate_iterations_gap", 8)
        erode2 = config_manager.read_variable("morphology", "erode_iterations_gap_2", 0)
    else:
        # Normal line following: erode(3) → dilate(13) → erode(7)
        # Ridotto rispetto a Overengineered (5/17/9) perché sul nostro robot
        # la linea curva appare più sottile (diverso montaggio camera/altezza)
        erode1 = config_manager.read_variable("morphology", "erode_iterations_line", 3)
        dilate_iter = config_manager.read_variable("morphology", "dilate_iterations_line", 13)
        erode2 = config_manager.read_variable("morphology", "erode_iterations_line_2", 7)
    
    roi_black = cv2.erode(roi_black, kernel, iterations=erode1)
    roi_black = cv2.dilate(roi_black, kernel, iterations=dilate_iter)
    if erode2 > 0:
        roi_black = cv2.erode(roi_black, kernel, iterations=erode2)
    
    # ─────────────────────────────────────────────────────────────────────
    # 7. RILEVAMENTO CONTORNI
    # ─────────────────────────────────────────────────────────────────────
    
    contours_blk, _ = cv2.findContours(roi_black, cv2.RETR_LIST, 
                                       cv2.CHAIN_APPROX_NONE)
    
    min_line_size = 250  # Scalato per 448x252 (era 500 a 640x480)
    contours_blk = [c for c in contours_blk 
                   if cv2.contourArea(c) > min_line_size]
    
    # ─────────────────────────────────────────────────────────────────────
    # 8. RILEVAMENTO GAP
    # ─────────────────────────────────────────────────────────────────────
    
    gap_info = _detect_gap(contours_blk, roi_black, w, roi_end - roi_start)
    result.gap_detected = gap_info['detected']
    result.gap_angle = gap_info['angle']
    result.gap_center_x = gap_info['center_x']
    result.gap_center_y = gap_info['center_y']
    
    # ─────────────────────────────────────────────────────────────────────
    # 9. PROCESSAMENTO LINEA CON CORREZIONE LATERALE (ibrido!)
    # ─────────────────────────────────────────────────────────────────────
    
    if contours_blk:
        result.line_detected = True
        
        # Seleziona linea (usando logica OLD per ROI ma dati OVERENGINEERED)
        blackline, blackline_crop = _select_correct_line_hybrid(
            contours_blk, w, roi_end - roi_start, last_angle
        )
        
        if blackline is not None:
            result.contour = blackline
            
            # Calcola centroidi con offset ROI
            _calculate_band_centroids(result, blackline, w, roi_start)
            
            # Calcola angolo (compensato per camera avanti)
            uncompensated_angle, poi, bottom_point, top_point = _calculate_angle(
                blackline, blackline_crop, w, roi_end - roi_start, last_angle
            )
            
            # Compensa l'angolo per camera avanti
            compensated_angle = _compensate_camera_angle(uncompensated_angle, state)
            
            result.line_angle = int(compensated_angle)
            result.poi = poi
            result.bottom_point = bottom_point
            result.top_point = top_point
            result.line_angle_y = (poi[1] + roi_start) if poi else -1
            result.line_size = cv2.contourArea(blackline)
            
            # Calcola deviazione laterale e stato centrale
            if result.global_centroid:
                center_x = w / 2.0
                result.lateral_deviation = (result.global_centroid[0] - center_x) / (w / 2.0)
                result.centered = abs(result.lateral_deviation) <= CENTER_TOLERANCE
            else:
                result.centered = True
    
    # ─────────────────────────────────────────────────────────────────────
    # 10. MARKER VERDI e ROSSI (da Overengineered)
    # ─────────────────────────────────────────────────────────────────────
    
    # Usa la zona completa per i marker (non solo ROI)
    full_green_mask = cv2.inRange(hsv_image, GREEN_MIN, GREEN_MAX)
    contours_grn, _ = cv2.findContours(full_green_mask, cv2.RETR_LIST, 
                                       cv2.CHAIN_APPROX_SIMPLE)
    
    if contours_grn:
        result.turn_direction = _analyze_green_markers(contours_grn, black_image, w, h)
        
        for cnt in contours_grn:
            if cv2.contourArea(cnt) < GREEN_MIN_AREA:
                continue
            
            x, y, bw, bh = cv2.boundingRect(cnt)
            cx = x + bw // 2
            
            if abs(bw / bh - 1.0) > ASPECT_RATIO_TOL:
                continue
            
            if cx < w // 3:
                result.green_left = True
            elif cx > 2 * w // 3:
                result.green_right = True
    
    red_mask_1 = cv2.inRange(hsv_image, RED_MIN_1, RED_MAX_1)
    red_mask_2 = cv2.inRange(hsv_image, RED_MIN_2, RED_MAX_2)
    red_mask = cv2.bitwise_or(red_mask_1, red_mask_2)
    
    contours_red, _ = cv2.findContours(red_mask, cv2.RETR_LIST, 
                                       cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours_red:
        if cv2.contourArea(cnt) >= RED_MIN_AREA:
            result.red_detected = True
            break
    
    return result


def _compensate_camera_angle(raw_angle: float, state) -> float:
    """Compensa la visione anticipata per camera avanti.
    
    NOTA: La compensazione originale di 12 gradi era troppo aggressiva.
    Riduceva un angolo reale di 25° a 13°, che combinato con il crop factor
    e il filtro IIR portava l'angolo vicino a 0 → il robot non curvava.
    Ridotta a 5° per preservare la risposta alle curve.
    """
    if state in [RobotState.LINE_DETECTED, None]:
        compensation = 5  # Ridotto da 12 a 5 per non mascherare le curve
        
        # Non compensare se l'angolo è già piccolo
        if abs(raw_angle) <= compensation:
            return int(raw_angle)
        
        effective_angle = (abs(raw_angle) - compensation) * np.sign(raw_angle)
        return int(effective_angle)
    
    return int(raw_angle)


def _select_correct_line_hybrid(contours_blk, frame_w, roi_h, last_angle) -> Tuple:
    """Selezione linea ibrida: logica Overengineered con ROI OLD."""
    
    if len(contours_blk) == 0:
        return None, None
    
    if len(contours_blk) == 1:
        blackline = contours_blk[0]
        blackline_crop = _crop_contour(blackline, frame_w, roi_h, 0.20)
        return blackline, blackline_crop
    
    # Usa logica Overengineered ma con impostazioni più conservative
    candidates = []
    
    for i, contour in enumerate(contours_blk):
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        cx = x + w // 2
        cy = y + h // 2
        
        # Preferisci linee che continuano la direzione precedente
        direction_preference = 0
        if last_angle != 0:
            # Se ultimo angolo era sinistra, favorisci linee a sinistra
            if last_angle < 0 and cx < frame_w / 2:
                direction_preference = 50
            elif last_angle > 0 and cx > frame_w / 2:
                direction_preference = 50
        
        # Score composito (simile a Overengineered ma più bilanciato)
        bottom_score = y + h
        center_score = -abs(cx - frame_w // 2) * 0.3  # Favorisce centro ma non troppo
        area_score = area * 0.01
        continuity_score = direction_preference
        
        total_score = bottom_score * 2 + center_score + area_score + continuity_score
        candidates.append((total_score, i, contour))
    
    candidates.sort(reverse=True)
    blackline = candidates[0][2]
    blackline_crop = _crop_contour(blackline, frame_w, roi_h, 0.20)
    
    return blackline, blackline_crop


def _crop_contour(contour, frame_w, roi_h, line_crop_factor):
    """Crea versione crop del contorno.
    
    NOTA: line_crop_factor controlla quanta parte SUPERIORE del contorno viene scartata.
    Un valore troppo alto (es. 0.48) elimina la parte curva della linea,
    rendendo impossibile calcolare l'angolo delle curve.
    Valori consigliati: 0.15-0.25 per preservare la curvatura.
    """
    
    points = contour[:, 0, :]
    crop_y = int(roi_h * line_crop_factor)
    cropped = points[points[:, 1] > crop_y]
    
    if len(cropped) == 0:
        return contour
    
    return np.array([[[x, y]] for x, y in cropped], 
                    dtype=np.int32).reshape(-1, 1, 2)


def _calculate_angle(blackline, blackline_crop, frame_w, roi_h, last_angle) -> Tuple:
    """Calcola l'angolo della linea."""
    
    points = blackline[:, 0, :]
    
    top_idx = np.argmin(points[:, 1])
    bottom_idx = np.argmax(points[:, 1])
    
    top_point = tuple(points[top_idx])
    bottom_point = tuple(points[bottom_idx])
    
    poi = top_point
    
    if blackline_crop is not None and len(blackline_crop) > 0:
        crop_points = blackline_crop[:, 0, :]
        if len(crop_points) > 0:
            crop_top_idx = np.argmin(crop_points[:, 1])
            poi = tuple(crop_points[crop_top_idx])
    
    dx = bottom_point[0] - poi[0]
    dy = bottom_point[1] - poi[1]
    
    if dy == 0:
        angle = 0
    else:
        angle = np.arctan2(dx, dy) * 180 / np.pi
    
    angle = np.clip(angle, -180, 180)
    
    # Smooth transition
    # A 60 FPS il filtro IIR viene applicato 2x più spesso, quindi usiamo
    # coefficiente più alto (0.85 vs 0.7) per mantenere reattività simile
    # ma leggermente più veloce (vantaggio dei 60 FPS per le curve)
    if abs(angle - last_angle) < 90:
        angle = 0.85 * angle + 0.15 * last_angle
    
    return int(angle), poi, bottom_point, top_point


def _calculate_band_centroids(result, contour, frame_w, y_offset):
    """Calcola centroidi per le 3 bande."""
    
    points = contour[:, 0, :] if len(contour.shape) > 2 else contour
    
    band_w = frame_w // 3
    
    left_mask = points[:, 0] < band_w
    center_mask = (points[:, 0] >= band_w) & (points[:, 0] < 2 * band_w)
    right_mask = points[:, 0] >= 2 * band_w
    
    if np.any(left_mask):
        left_points = points[left_mask]
        result.has_left = True
        result.centroid_left = (int(np.mean(left_points[:, 0])),
                               int(np.mean(left_points[:, 1])) + y_offset)
    
    if np.any(center_mask):
        center_points = points[center_mask]
        result.has_center = True
        result.centroid_center = (int(np.mean(center_points[:, 0])),
                                 int(np.mean(center_points[:, 1])) + y_offset)
    
    if np.any(right_mask):
        right_points = points[right_mask]
        result.has_right = True
        result.centroid_right = (int(np.mean(right_points[:, 0])),
                                int(np.mean(right_points[:, 1])) + y_offset)
    
    if len(points) > 0:
        result.global_centroid = (int(np.mean(points[:, 0])),
                                 int(np.mean(points[:, 1])) + y_offset)


def _detect_gap(contours, black_mask, frame_w, roi_h) -> dict:
    """Rileva gap nella linea."""
    
    result = {
        'detected': False,
        'angle': -181.0,
        'center_x': -181,
        'center_y': -1
    }
    
    if len(contours) == 0:
        return result
    
    # Cerca contorni con forme tipiche di gap
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (GAP_MIN_AREA < area < GAP_MAX_AREA):
            continue
        
        x, y, w, h = cv2.boundingRect(cnt)
        
        if w < GAP_MIN_WIDTH or h < GAP_MIN_HEIGHT:
            continue
        
        # Calcola angolo del gap
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
        box = np.array(box, dtype=np.int32)
        
        if len(box) >= 2:
            box = np.array(sorted(box, key=lambda x: x[1]), dtype=np.int32)
            p1 = tuple(box[0])
            p2 = tuple(box[-1])
            
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            
            if dy != 0:
                angle = np.arctan2(dx, dy) * 180 / np.pi
            else:
                angle = 0
            
            result = {
                'detected': True,
                'angle': angle,
                'center_x': int((x + w//2 - frame_w / 2) / (frame_w / 2) * 180),
                'center_y': y + h//2
            }
            break
    
    return result


def _analyze_green_markers(contours_grn, black_mask, frame_w, frame_h) -> str:
    """Analizza marker verdi con contorni neri adiacenti."""
    
    if not contours_grn:
        return "straight"
    
    valid_markers = []
    
    for contour in contours_grn:
        area = cv2.contourArea(contour)
        if area < GREEN_MIN_AREA:
            continue
        
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.array(box, dtype=np.int32)
        
        w, h = rect[1]
        if h == 0:
            continue
        
        aspect = w / h
        if abs(aspect - 1.0) > ASPECT_RATIO_TOL * 2:
            continue
        
        black_directions = _check_black_around_marker(box, black_mask, 
                                                     frame_w, frame_h)
        valid_markers.append((box, black_directions))
    
    if not valid_markers:
        return "straight"
    
    turn_left = False
    turn_right = False
    
    for box, directions in valid_markers:
        bottom, top, left, right = directions
        
        if top and left and not right:
            turn_right = True
        elif top and right and not left:
            turn_left = True
    
    if turn_left and turn_right:
        return "turn_around"
    elif turn_left:
        return "left"
    elif turn_right:
        return "right"
    
    return "straight"


def _check_black_around_marker(green_box, black_mask, frame_w, frame_h) -> Tuple[bool, bool, bool, bool]:
    """Verifica presenza nero attorno al marker verde."""
    
    bottom = False
    top = False
    left = False
    right = False
    
    green_box_sorted = green_box[green_box[:, 1].argsort()]
    marker_height = green_box_sorted[-1][1] - green_box_sorted[0][1]
    
    if marker_height == 0:
        return (bottom, top, left, right)
    
    extension = int(marker_height * 0.8)
    
    # Bottom
    y1 = min(int(green_box_sorted[2][1]), frame_h - 1)
    y2 = min(y1 + extension, frame_h)
    x1 = max(int(min(green_box_sorted[2][0], green_box_sorted[3][0])), 0)
    x2 = min(int(max(green_box_sorted[2][0], green_box_sorted[3][0])), frame_w)
    
    if y2 > y1 and x2 > x1:
        roi_bottom = black_mask[y1:y2, x1:x2]
        if roi_bottom.size > 0 and np.mean(roi_bottom) > 125:
            bottom = True
    
    # Top
    y2 = max(int(green_box_sorted[1][1]), 0)
    y1 = max(y2 - extension, 0)
    x1 = max(int(min(green_box_sorted[0][0], green_box_sorted[1][0])), 0)
    x2 = min(int(max(green_box_sorted[0][0], green_box_sorted[1][0])), frame_w)
    
    if y2 > y1 and x2 > x1:
        roi_top = black_mask[y1:y2, x1:x2]
        if roi_top.size > 0 and np.mean(roi_top) > 125:
            top = True
    
    return (bottom, top, left, right)


# Funzioni per aiutare il decision-making esterno
def should_apply_lateral_correction(line_detection: LineDetection) -> bool:
    """Controlla se applicare correzione laterale."""
    # Se linea quasi verticale ma non centrata
    return (abs(line_detection.line_angle) < VERTICAL_THRESHOLD and 
            not line_detection.centered and 
            line_detection.line_detected)


def get_lateral_correction_command(line_detection: LineDetection) -> str:
    """Ottieni comando di correzione laterale."""
    if line_detection.lateral_deviation < 0:
        # Linea a sinistra → va a destra
        return "gd"  # Gentle destra
    else:
        # Linea a destra → va a sinistra
        return "gs"  # Gentle sinistra


# Wrapper per retro-compatibilità
def detect_line(frame_rgb):
    """Wrapper compatibile con mycode."""
    return detect_line_advanced(frame_rgb)