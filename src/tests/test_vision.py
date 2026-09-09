"""Test visione: line_detector su maschera sintetica (no cv2 reale richiesto per import)."""


def test_detect_line_importable():
    from src.vision import line_detector

    assert callable(line_detector.detect_line)


def test_detect_line_black_image_returns_none():
    pytest = __import__("pytest")
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from src.vision.line_detector import detect_line

    black = np.zeros((120, 160, 3), dtype=np.uint8)
    assert detect_line(black) is None
