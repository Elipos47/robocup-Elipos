"""Rilevamento linea nera + marker verdi (SPEC §7.1).

M1: la pista Rescue Line ha linea NERA su fondo bianco -> detect_black_line.
I marker VERDI indicano solo svolte/incroci (M2) -> detect_line.
"""

from __future__ import annotations


def _largest_blob_deviation(mask: object, image_width: int) -> float | None:
    """Deviazione in pixel del blob piu' grande dal centro, o None se assente.

    Args:
        mask: Maschera binaria (numpy array HxW, uint8).
        image_width: Larghezza frame in pixel.

    Returns:
        Deviazione orizzontale in pixel (>0 = blob a destra), None se non trovato.
    """
    import cv2

    from src.utils.config import LINE_MIN_CONTOUR_AREA

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= LINE_MIN_CONTOUR_AREA]
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    x, _y, w, _h = cv2.boundingRect(largest)
    return float(x + w / 2 - image_width / 2)


def detect_black_line(image_bgr: object) -> float | None:
    """Trova la linea nera (threshold sul canale V).

    Args:
        image_bgr: Frame BGR (numpy array HxWx3).

    Returns:
        Deviazione orizzontale in pixel (>0 = linea a destra), None se non trovata.
    """
    import cv2
    import numpy as np

    from src.utils.config import LINE_BLACK_MAX_V

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array([0, 0, 0]),
        np.array([180, 255, LINE_BLACK_MAX_V]),
    )
    return _largest_blob_deviation(mask, image_bgr.shape[1])


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
    return _largest_blob_deviation(mask, image_bgr.shape[1])
