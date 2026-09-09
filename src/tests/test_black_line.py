"""Test seguilineanera M1 + mapping PWM->rad/s (solo CPU, no Webots)."""


def test_black_line_centered_returns_zero():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    img = np.full((120, 160, 3), 255, dtype=np.uint8)
    img[:, 70:90] = 0  # striscia nera centrata (centro=80)
    dev = detect_black_line(img)
    assert dev is not None
    assert abs(dev) < 2.0


def test_black_line_offset_sign():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    img = np.full((120, 160, 3), 255, dtype=np.uint8)
    img[:, 110:130] = 0  # striscia a destra
    dev = detect_black_line(img)
    assert dev is not None
    assert dev > 30.0


def test_black_line_absent_returns_none():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    assert detect_black_line(white) is None


def test_pwm_to_velocity_full_scale():
    from src.control.motor_control import pwm_to_velocity
    from src.utils.config import MAX_WHEEL_RAD_S, MOTOR_MAX_PWM, WHEEL_DIRECTION

    assert pwm_to_velocity(0) == 0.0
    assert pwm_to_velocity(MOTOR_MAX_PWM) == WHEEL_DIRECTION * MAX_WHEEL_RAD_S
    assert pwm_to_velocity(-MOTOR_MAX_PWM) == -WHEEL_DIRECTION * MAX_WHEEL_RAD_S


def test_tank_mix_positive_correction_turns_right():
    from src.control.motor_control import tank_mix

    left, right = tank_mix(120, 50.0)
    assert left > right  # svolta a destra = sx piu' veloce
