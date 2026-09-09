"""Rilevamento linea verde (SPEC §7.1): blob detection OpenCV su maschera HSV."""

from __future__ import annotations


def detect_line(image_bgr: object) -> float | None:
    """Restituisce la deviazione in pixel dal centro immagine, o None se linea assente.

    Args:
        image_bgr: Frame BGR (numpy array HxWx3).

    Returns:
        Deviazione orizzontale in pixel (>0 = linea a destra), None se non trovata.
    """
    import cv2
    import numpy as np

    from src.utils.config import LINE_HSV_LOWER, LINE_HSV_UPPER, LINE_MIN_CONTOUR_AREA

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(LINE_HSV_LOWER), np.array(LINE_HSV_UPPER))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= LINE_MIN_CONTOUR_AREA]
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    x, _y, w, _h = cv2.boundingRect(largest)
    center_x = x + w / 2
    image_center = image_bgr.shape[1] / 2
    return float(center_x - image_center)
