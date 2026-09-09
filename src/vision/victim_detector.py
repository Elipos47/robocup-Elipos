"""Rilevamento vittime/palline (SPEC §7.2): YOLO leggero, inferenza ONNX su Pi 5."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Victim:
    """Vittima rilevata."""

    bbox: tuple[float, float, float, float]
    confidence: float


_model: object = None


def _get_model(path: str) -> object:
    global _model
    if _model is None:
        from ultralytics import YOLO

        _model = YOLO(path)
    return _model


def detect_victims(image_bgr: object, model_path: str = "", conf: float = 0.5) -> list[Victim]:
    """Rileva vittime nel frame.

    Args:
        image_bgr: Frame BGR.
        model_path: Peso YOLO (default da config).
        conf: Soglia di confidenza.

    Returns:
        Lista di vittime rilevate (vuota se nessuna).
    """
    from src.utils.config import VICTIM_CONF_THRESHOLD, VICTIM_MODEL_PATH

    model_path = model_path or VICTIM_MODEL_PATH
    conf = conf or VICTIM_CONF_THRESHOLD
    model = _get_model(model_path)
    results = model(image_bgr, conf=conf, verbose=False)
    victims: list[Victim] = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        victims.append(Victim(bbox=(x1, y1, x2, y2), confidence=float(box.conf[0].item())))
    return victims
