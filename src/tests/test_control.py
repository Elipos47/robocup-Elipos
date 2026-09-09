"""Test controllo motori: PID e tank_mix."""


def test_pid_zero_error_zero_output():
    from src.control.motor_control import PIDController

    pid = PIDController()
    assert pid.update(0.0, 0.02) == 0.0


def test_pid_rejects_nonpositive_dt():
    import pytest

    from src.control.motor_control import PIDController

    with pytest.raises(ValueError):
        PIDController().update(1.0, 0.0)


def test_tank_mix_saturates():
    from src.control.motor_control import tank_mix

    left, right = tank_mix(200, 500.0)
    assert abs(left) <= 255 and abs(right) <= 255


def test_arduino_bridge_validates_motor_id():
    import pytest

    from src.control import arduino_bridge

    class Dummy:
        def write(self, b):
            pass

        def readline(self):
            return b"ok\n"

    pytest = __import__("pytest")
    pytest.importorskip("serial")

    br = arduino_bridge.ArduinoBridge.__new__(arduino_bridge.ArduinoBridge)
    br.serial = Dummy()
    with pytest.raises(ValueError):
        br.set_motor(3, 100)
