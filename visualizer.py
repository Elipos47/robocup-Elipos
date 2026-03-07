# ===========================================================================
# visualizer.py – Overlay grafico avanzato
# ===========================================================================
# Sovrappone al frame originale:
# • Rettangolo ROI con suddivisione in 3 bande
# • Centroidi rilevati (linea)
# • Punto di interesse (POI) e angolo
# • Marker verdi con direzione calcolata
# • Angolo linea in gradi
# • Stato ricerca linea
# • Statistiche avanzate
# ===========================================================================

import cv2
import numpy as np

# ── Parametri grafici ──────────────────────────────────────────────────────
ROI_OVERLAY_ALPHA = 0.25
ROI_COLOR = (255, 200, 0)
BAND_DIVIDER_COLOR = (200, 200, 200)

CENTROID_RADIUS = 6
CENTROID_COLOR = (0, 0, 255)
CENTROID_GLOBAL_COLOR = (255, 255, 0)
POI_RADIUS = 8
POI_COLOR = (0, 255, 255)
BOTTOM_POINT_COLOR = (255, 0, 255)

LINE_COLOR = (0, 255, 0)
LINE_THICKNESS = 2
ANGLE_LINE_LENGTH = 50

GREEN_BOX_COLOR = (0, 255, 0)
RED_BOX_COLOR = (0, 0, 255)
BOX_THICKNESS = 2

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.8
FONT_COLOR = (255, 255, 255)
FONT_THICKNESS = 2
TEXT_BG_COLOR = (0, 0, 0)
TEXT_PADDING = 8
# ───────────────────────────────────────────────────────────────────────────


def draw_overlay(frame_rgb, line_detection, color_detection, command,
                 serial_status="", distance_status="", usb_status="", 
                 search_status="", show_advanced=True):
    """Disegna l'overlay avanzato sul frame.
    
    Parameters
    ----------
    frame_rgb : np.ndarray
        Frame originale in formato RGB
    line_detection : LineDetection
        Risultati rilevamento linea
    color_detection : ColorDetection
        Risultati rilevamento colori
    command : str
        Comando corrente
    serial_status, distance_status, usb_status, search_status : str
        Stati vari
    show_advanced : bool
        Se mostrare dati avanzati (angolo, POI, etc.)
    
    Returns
    -------
    np.ndarray
        Frame con overlay in formato BGR
    """
    # Conversione BGR per OpenCV
    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    h, w = frame.shape[:2]
    overlay = frame.copy()
    
    # ── 1. ROI e bande ───────────────────────────────────────────────
    y_start = line_detection.roi_y_start
    y_end = line_detection.roi_y_end
    
    # Rettangolo ROI
    cv2.rectangle(overlay, (0, y_start), (w, y_end), ROI_COLOR, -1)
    cv2.addWeighted(overlay, ROI_OVERLAY_ALPHA, frame, 
                    1 - ROI_OVERLAY_ALPHA, 0, frame)
    
    # Linee divisorie bande
    band_w = w // 3
    cv2.line(frame, (band_w, y_start), (band_w, y_end), 
             BAND_DIVIDER_COLOR, 1)
    cv2.line(frame, (band_w * 2, y_start), (band_w * 2, y_end), 
             BAND_DIVIDER_COLOR, 1)
    
    # ── 2. Centroidi ───────────────────────────────────────────────────
    for centroid in (line_detection.centroid_left,
                     line_detection.centroid_center,
                     line_detection.centroid_right):
        if centroid is not None:
            cv2.circle(frame, centroid, CENTROID_RADIUS, CENTROID_COLOR, -1)
    
    # Centroide globale
    if line_detection.global_centroid is not None:
        cv2.circle(frame, line_detection.global_centroid,
                   CENTROID_RADIUS + 4, CENTROID_GLOBAL_COLOR, 2)
    
    # ── 3. Visualizzazione Gap ─────────────────────────────────────────
    if hasattr(line_detection, 'gap_detected') and line_detection.gap_detected:
        # Disegna rettangolo gap
        if hasattr(line_detection, 'gap_center_x') and line_detection.gap_center_x != -181:
            gap_x = int(line_detection.gap_center_x * w / 360 + w / 2)
            gap_y = line_detection.roi_y_start + line_detection.gap_center_y if hasattr(line_detection, 'gap_center_y') else y_end - 50
            
            # Cerchio per indicare gap
            cv2.circle(frame, (gap_x, gap_y), 15, (255, 255, 0), 3)
            
            # Linea angolo gap
            if hasattr(line_detection, 'gap_angle') and line_detection.gap_angle != -181:
                angle_rad = np.deg2rad(line_detection.gap_angle)
                line_length = 40
                end_x = int(gap_x + line_length * np.sin(angle_rad))
                end_y = int(gap_y - line_length * np.cos(angle_rad))
                cv2.line(frame, (gap_x, gap_y), (end_x, end_y), (255, 255, 0), 2)
            
            # Testo gap
            gap_text = f"GAP: {line_detection.gap_angle:.1f}"
            cv2.putText(frame, gap_text, (gap_x + 20, gap_y), 
                       FONT, 0.6, (255, 255, 0), 2)
    
    # ── 3. Dati avanzati (da line_detector avanzato) ──────────────────
    if show_advanced:
        # POI
        if line_detection.poi is not None:
            cv2.circle(frame, line_detection.poi, POI_RADIUS, POI_COLOR, 2)
        
        # Bottom point
        if line_detection.bottom_point is not None:
            pt = (line_detection.bottom_point[0], 
                  line_detection.bottom_point[1] + y_start)
            cv2.circle(frame, pt, 5, BOTTOM_POINT_COLOR, -1)
        
        # Linea di riferimento per angolo
        if (line_detection.poi is not None and 
            line_detection.bottom_point is not None):
            pt1 = line_detection.poi
            pt2 = (line_detection.bottom_point[0],
                   line_detection.bottom_point[1] + y_start)
            cv2.line(frame, pt1, pt2, LINE_COLOR, LINE_THICKNESS)
        
        # Disegna contorno linea se disponibile
        if line_detection.contour is not None:
            contour = line_detection.contour.copy()
            # Aggiusta Y del contorno per offset ROI
            if len(contour) > 0:
                contour[:, :, 1] += y_start
                cv2.drawContours(frame, [contour], -1, (255, 0, 0), 2)
    
    # ── 4. Bounding box colori ─────────────────────────────────────────
    for (bx, by, bw, bh) in color_detection.green_boxes:
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh),
                     GREEN_BOX_COLOR, BOX_THICKNESS)
    
    for (bx, by, bw, bh) in color_detection.red_boxes:
        cv2.rectangle(frame, (bx, by), (bx + bw, by + bh),
                     RED_BOX_COLOR, BOX_THICKNESS)
    
    # ── 5. Testo comando (in alto a sinistra) ─────────────────────────
    tx, ty = TEXT_PADDING, 30
    
    # Sfondo nero per leggibilità
    text = f"CMD: {command}"
    (tw, th), baseline = cv2.getTextSize(text, FONT, FONT_SCALE, FONT_THICKNESS)
    cv2.rectangle(frame, (tx - TEXT_PADDING, ty - th - TEXT_PADDING),
                 (tx + tw + TEXT_PADDING, ty + baseline + TEXT_PADDING),
                 TEXT_BG_COLOR, -1)
    cv2.putText(frame, text, (tx, ty), FONT, FONT_SCALE,
               FONT_COLOR, FONT_THICKNESS, cv2.LINE_AA)
    
    # ── 6. Dati avanzati (sotto comando) ───────────────────────────────
    if show_advanced:
        y_offset = ty + baseline + TEXT_PADDING * 3
        
        # Angolo linea
        angle_text = f"Angle: {line_detection.line_angle}"
        if line_detection.line_angle_y >= 0:
            angle_text += f" (y:{line_detection.line_angle_y})"
        (aw, ah), ab = cv2.getTextSize(angle_text, FONT, 0.6, 1)
        cv2.rectangle(frame, (tx - TEXT_PADDING, y_offset - ah - TEXT_PADDING),
                     (tx + aw + TEXT_PADDING, y_offset + ab + TEXT_PADDING),
                     TEXT_BG_COLOR, -1)
        cv2.putText(frame, angle_text, (tx, y_offset), FONT, 0.6,
                   (0, 255, 255), 1, cv2.LINE_AA)
        y_offset += ah + ab + TEXT_PADDING
        
        # Turn direction
        if line_detection.turn_direction != "straight":
            turn_text = f"Turn: {line_detection.turn_direction}"
            (tw, th), tb = cv2.getTextSize(turn_text, FONT, 0.6, 1)
            cv2.rectangle(frame, (tx - TEXT_PADDING, y_offset - th - TEXT_PADDING),
                         (tx + tw + TEXT_PADDING, y_offset + tb + TEXT_PADDING),
                         TEXT_BG_COLOR, -1)
            color = (0, 255, 0) if line_detection.turn_direction == "left" else (
                (0, 0, 255) if line_detection.turn_direction == "right" else (0, 255, 255))
            cv2.putText(frame, turn_text, (tx, y_offset), FONT, 0.6,
                       color, 1, cv2.LINE_AA)
            y_offset += th + tb + TEXT_PADDING
    else:
        y_offset = ty + baseline + TEXT_PADDING * 3
    
    # ── 7. Stato seriale ──────────────────────────────────────────────
    if serial_status:
        ser_scale = 0.6
        ser_thick = 1
        (sw, sh), sb = cv2.getTextSize(serial_status, FONT, ser_scale, ser_thick)
        sy = y_offset + sh + TEXT_PADDING
        is_connected = "DISCONNESSO" not in serial_status
        ser_color = (0, 200, 0) if is_connected else (0, 0, 255)
        cv2.rectangle(frame, (tx - TEXT_PADDING, sy - sh - TEXT_PADDING),
                     (tx + sw + TEXT_PADDING, sy + sb + TEXT_PADDING),
                     TEXT_BG_COLOR, -1)
        cv2.putText(frame, serial_status, (tx, sy), FONT, ser_scale,
                   ser_color, ser_thick, cv2.LINE_AA)
        y_offset = sy + sb + TEXT_PADDING
    
    # ── 8. Stato distanza ────────────────────────────────────────────
    if distance_status:
        dist_scale = 0.6
        dist_thick = 1
        (dw, dh), db = cv2.getTextSize(distance_status, FONT, dist_scale, dist_thick)
        dy = y_offset + dh + TEXT_PADDING
        try:
            dist_val = int(distance_status.split(":")[1].replace("cm", "").strip())
            dist_color = (0, 0, 255) if dist_val <= 15 else (0, 200, 0)
        except:
            dist_color = (255, 255, 255)
        cv2.rectangle(frame, (tx - TEXT_PADDING, dy - dh - TEXT_PADDING),
                     (tx + dw + TEXT_PADDING, dy + db + TEXT_PADDING),
                     TEXT_BG_COLOR, -1)
        cv2.putText(frame, distance_status, (tx, dy), FONT, dist_scale,
                   dist_color, dist_thick, cv2.LINE_AA)
        y_offset = dy + db + TEXT_PADDING
    
    # ── 9. Stato USB ───────────────────────────────────────────────────
    if usb_status:
        usb_scale = 0.6
        usb_thick = 1
        (uw, uh), ub = cv2.getTextSize(usb_status, FONT, usb_scale, usb_thick)
        uy = y_offset + uh + TEXT_PADDING
        if "OK" in usb_status or "/dev/video" in usb_status:
            usb_color = (0, 200, 0)
        elif "NO CAM" in usb_status or "PERSA" in usb_status:
            usb_color = (0, 0, 255)
        else:
            usb_color = (0, 165, 255)
        cv2.rectangle(frame, (tx - TEXT_PADDING, uy - uh - TEXT_PADDING),
                     (tx + uw + TEXT_PADDING, uy + ub + TEXT_PADDING),
                     TEXT_BG_COLOR, -1)
        cv2.putText(frame, usb_status, (tx, uy), FONT, usb_scale,
                   usb_color, usb_thick, cv2.LINE_AA)
        y_offset = uy + ub + TEXT_PADDING
    
    # ── 10. Stato ricerca ────────────────────────────────────────────
    if search_status:
        search_scale = 0.6
        search_thick = 1
        (sw, sh), sb = cv2.getTextSize(search_status, FONT, search_scale, search_thick)
        sy_search = y_offset + sh + TEXT_PADDING
        search_color = (0, 255, 255)
        cv2.rectangle(frame, (tx - TEXT_PADDING, sy_search - sh - TEXT_PADDING),
                     (tx + sw + TEXT_PADDING, sy_search + sb + TEXT_PADDING),
                     TEXT_BG_COLOR, -1)
        cv2.putText(frame, search_status, (tx, sy_search), FONT, search_scale,
                   search_color, search_thick, cv2.LINE_AA)
    
    return frame
