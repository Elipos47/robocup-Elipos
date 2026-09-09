"""Test seguilineanera M1 + mapping PWM->rad/s (solo CPU, no Webots)."""


def test_black_line_centered_returns_zero():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    img = np.full((120, 160, 3), 255, dtype=np.uint8)
    img[:, 70:90] = 0  # striscia nera centrata (centro=80)
    dev, _ang = detect_black_line(img)
    assert dev is not None
    assert abs(dev) < 2.0


def test_black_line_offset_sign():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    img = np.full((120, 160, 3), 255, dtype=np.uint8)
    img[:, 110:130] = 0  # striscia a destra
    dev, _ang = detect_black_line(img)
    assert dev is not None
    assert dev > 30.0


def test_black_line_absent_returns_none():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    white = np.full((120, 160, 3), 255, dtype=np.uint8)
    assert detect_black_line(white) == (None, None)


def test_pwm_to_velocity_full_scale():
    from src.control.motor_control import pwm_to_velocity
    from src.utils.config import MAX_WHEEL_RAD_S, MOTOR_MAX_PWM, WHEEL_DIRECTION

    assert pwm_to_velocity(0) == 0.0
    assert pwm_to_velocity(MOTOR_MAX_PWM) == WHEEL_DIRECTION * MAX_WHEEL_RAD_S
    assert pwm_to_velocity(-MOTOR_MAX_PWM) == -WHEEL_DIRECTION * MAX_WHEEL_RAD_S


def test_tank_mix_positive_correction_turns_right():
    from src.control.motor_control import tank_mix

    left, right = tank_mix(120, 50.0)
    assert left > right  # svolta a destra = sx piu' veloce (dx rallenta)


def test_curve_base_pwm_slows_with_deviation():
    from src.control.motor_control import curve_base_pwm
    from src.utils.config import CURVE_SLOW_DEV_REF, CURVE_SLOW_GAIN

    assert curve_base_pwm(120, 0.0) == 120
    assert curve_base_pwm(120, CURVE_SLOW_DEV_REF) == int(120 * (1.0 - CURVE_SLOW_GAIN))
    assert curve_base_pwm(120, 0.2) < 120


def test_curve_slow_factor_bounds():
    from src.control.motor_control import curve_slow_factor
    from src.utils.config import CURVE_SLOW_DEV_REF, CURVE_SLOW_GAIN

    assert curve_slow_factor(0.0) == 1.0
    assert curve_slow_factor(CURVE_SLOW_DEV_REF) == 1.0 - CURVE_SLOW_GAIN
    assert curve_slow_factor(10.0) == 1.0 - CURVE_SLOW_GAIN  # saturato
    assert 0.0 < curve_slow_factor(0.3) < 1.0


def test_tank_mix_clamps_correction_no_pivot():
    from src.control.motor_control import tank_mix

    left, right = tank_mix(60, 200.0, 70)
    assert (left, right) == (130, -10)  # yaw forte, mai pivot (264/-144 senza clamp)


def test_slew_limit_ramps():
    from src.control.motor_control import slew_limit

    assert slew_limit(0, 100, 25) == 25
    assert slew_limit(0, -100, 25) == -25
    assert slew_limit(0, 10, 25) == 10
    assert slew_limit(50, 55, 25) == 55


def test_pid_freezes_integral_when_saturated():
    from src.control.motor_control import PIDController

    pid = PIDController(kp=100.0, ki=50.0, kd=0.0)
    for _ in range(200):
        out = pid.update(1.0, 0.032)
    assert out == 204  # saturo (100 + 50*I > 204 da I>2.08)
    assert pid._integral < 3.0  # congelato (senza anti-windup sarebbe 6.4)
    pid2 = PIDController(kp=10.0, ki=10.0, kd=0.0)
    for _ in range(10):
        pid2.update(0.1, 0.032)
    assert abs(pid2._integral - 0.032) < 1e-9  # non saturo: accumula


def test_black_line_angle_vertical_near_zero():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    img = np.full((120, 160, 3), 255, dtype=np.uint8)
    img[:, 70:90] = 0  # verticale
    dev, ang = detect_black_line(img)
    assert dev is not None and ang is not None
    assert abs(ang) < 0.1


def test_black_line_angle_sign():
    pytest = __import__("pytest")
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    from src.vision.line_detector import detect_black_line

    backslash = np.full((120, 160, 3), 255, dtype=np.uint8)
    cv2.line(backslash, (40, 0), (100, 119), (0, 0, 0), 12)  # \ = davanti a sinistra
    _d1, a1 = detect_black_line(backslash)
    slash = np.full((120, 160, 3), 255, dtype=np.uint8)
    cv2.line(slash, (120, 0), (60, 119), (0, 0, 0), 12)  # / = davanti a destra
    _d2, a2 = detect_black_line(slash)
    assert a1 is not None and a2 is not None
    assert a1 < -0.2 and a2 > 0.2
