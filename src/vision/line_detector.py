"""Rilevamento linea nera + marker verdi (SPEC §7.1).

M1: la pista Rescue Line ha linea NERA su fondo bianco -> detect_black_line.
I marker VERDI indicano solo svolte/incroci (M2) -> detect_line.
"""

from __future__ import annotations


def _largest_blob_deviation_angle(mask: object, image_width: int) -> tuple[float | None, float | None]:
    """Deviazione + angolo del blob piu' grande, o (None, None) se assente.

    Args:
        mask: Maschera binaria (numpy array HxW, uint8).
        image_width: Larghezza frame in pixel.

    Returns:
        (deviazione px orizzontale, angolo rad dalla verticale visto dal robot:
        + = la linea davanti punta a destra). Angolo da fitLine sul contorno,
        robusto anche a blob tagliati dal bordo/ROI.
    """
    import cv2
    import math

    import numpy as np

    from src.utils.config import LINE_MIN_CONTOUR_AREA

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= LINE_MIN_CONTOUR_AREA]
    if not contours:
        return None, None
    largest = max(contours, key=cv2.contourArea)
    x, _y, w, _h = cv2.boundingRect(largest)
    dev = float(x + w / 2 - image_width / 2)
    vx, vy, _x0, _y0 = cv2.fitLine(largest, cv2.DIST_L2, 0, 0.01, 0.01)
    vx, vy = float(np.asarray(vx).flat[0]), float(np.asarray(vy).flat[0])
    if vy > 0:  # verso convenzionale: punta in alto (avanti), vy <= 0
        vx, vy = -vx, -vy
    ang = math.atan2(vx, -vy) if abs(vy) > 1e-6 else math.copysign(math.pi / 2, vx)
    return dev, ang


def detect_black_line(image_bgr: object) -> tuple[float | None, float | None]:
    """Trova la linea nera (threshold sul canale V).

    Args:
        image_bgr: Frame BGR (numpy array HxWx3).

    Returns:
        (deviazione px, angolo rad): >0 = linea a destra / linea che punta a
        destra davanti. (None, None) se non trovata.
    """
    import cv2
    import numpy as np

    from src.utils.config import LINE_BLACK_MAX_V, LINE_ROI_TOP_FRAC

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, 0]),
        np.array([180, 255, LINE_BLACK_MAX_V]),
    )
    top = int(mask.shape[0] * LINE_ROI_TOP_FRAC)
    mask[:top, :] = 0  # ROI: solo sotto l'orizzonte (via ombre/luci in alto)
    return _largest_blob_deviation_angle(mask, image_bgr.shape[1])


def detect_line(image_bgr: object) -> float | None:
    """Trova un marker VERDE (svolte/incroci M2, non la linea).

    Args:
        image_bgr: Frame BGR (numpy array HxWx3).

    Returns:
        Deviazione orizzontale in pixel (>0 = marker a destra), None se non trovato.
    """
    import cv2
    import numpy as np

    from src.utils.config import LINE_HSV_LOWER, LINE_HSV_UPPER

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(LINE_HSV_LOWER), np.array(LINE_HSV_UPPER))
    dev, _ang = _largest_blob_deviation_angle(mask, image_bgr.shape[1])
    return dev
