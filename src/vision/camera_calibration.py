"""Calibrazione manuale camere (SPEC §4.1.5: niente auto-calibrazione).

I valori misurati vanno documentati in docs/calibration.md e riportati in config.py.
Questo modulo offre solo helper di misura, mai regolazione automatica a runtime.
"""

from __future__ import annotations


def measure_hsv_sample(image_bgr: object, region: tuple[int, int, int, int]) -> dict[str, float]:
    """Misura HSV medio in una ROI (x, y, w, h) per taratura manuale.

    Args:
        image_bgr: Frame BGR.
        region: Tupla (x, y, w, h) della regione campione.

    Returns:
        Dizionario con h_mean, s_mean, v_mean da trascrivere in calibration.md.
    """
    import cv2
    import numpy as np

    x, y, w, h = region
    roi = image_bgr[y : y + h, x : x + w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mean = np.mean(hsv.reshape(-1, 3), axis=0)
    return {"h_mean": float(mean[0]), "s_mean": float(mean[1]), "v_mean": float(mean[2])}
