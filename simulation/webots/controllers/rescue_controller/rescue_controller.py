"""Controller Webots (SPEC §6.4): camera verde -> linea nera -> PID -> motori.

M1: seguilineanera con P-control su errore normalizzato ±1.
Linea persa: stop + reset integrale (ricerca ostacolo/stanza in M2).
Eseguito dentro Webots; fuori Webots resta importabile solo src/.
"""

import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from controller import Robot  # noqa: E402  (iniettato da Webots a runtime)

from src.control.motor_control import PIDController, curve_base_pwm, curve_slow_factor, pwm_to_velocity, slew_limit, tank_mix  # noqa: E402
from src.utils.config import BASE_PWM, LINE_KA, LINE_KP, SLEW_MAX_DPWM, STEER_MAX_CORR  # noqa: E402
from src.vision.line_detector import detect_black_line  # noqa: E402

robot = Robot()
timestep = int(robot.getBasicTimeStep())
dt = timestep / 1000.0
_runlog = open(os.path.join(tempfile.gettempdir(), "rescue_run.csv"), "w")
_runlog.write("step,t,dev,ang,slow,pwm_l,pwm_r\n")

camera_green = robot.getDevice("camera_green")
camera_green.enable(timestep)
width = camera_green.getWidth()
height = camera_green.getHeight()

motor_fl = robot.getDevice("motor_fl")
motor_rl = robot.getDevice("motor_rl")
motor_fr = robot.getDevice("motor_fr")
motor_rr = robot.getDevice("motor_rr")
for _m in (motor_fl, motor_rl, motor_fr, motor_rr):
    _m.setPosition(float("inf"))

pid = PIDController(kp=LINE_KP)

_dbg = 0
_prev_pwm_left, _prev_pwm_right = 0, 0
while robot.step(timestep) != -1:
    frame = np.frombuffer(camera_green.getImage(), dtype=np.uint8)
    frame = frame.reshape((height, width, 4))[:, :, :3]  # BGRA -> BGR
    deviation, line_ang = detect_black_line(frame)
    _dbg += 1
    if _dbg % 32 == 0:  # TEMP-DEBUG
        _ang_txt = "None" if line_ang is None else f"{line_ang:.2f}"
        print(f"DBG mean={frame.mean():.1f} dev={deviation} ang={_ang_txt}", flush=True)
    if _dbg == 40:  # TEMP-DEBUG: snapshot ASCII maschera nero (32x12)
        import cv2 as _cv2

        print(
            f"DBG fov={camera_green.getFov():.3f} near={camera_green.getNear()} "
            f"w={width} h={height}",
            flush=True,
        )
        camera_green.saveImage("C:/Users/elipo/AppData/Local/Temp/cam_green.png", 100)
        print("DBG saved green+black", flush=True)
    if _dbg == 1000:  # TEMP-DEBUG: snapshot alla curva (robot z~0.85, vede tutto l'arco)
        camera_green.saveImage("C:/Users/elipo/AppData/Local/Temp/cam_green_curve.png", 100)
        print("DBG saved curve frame", flush=True)

        _hsv = _cv2.cvtColor(frame, _cv2.COLOR_BGR2HSV)
        _hist, _ = np.histogram(_hsv[:, :, 2], bins=10, range=(0, 255))
        print(f"DBG Vhist={list(_hist)}", flush=True)
        _m = _cv2.inRange(_hsv, (0, 0, 0), (180, 255, 80))
        _small = _cv2.resize(_hsv[:, :, 2], (64, 24), interpolation=_cv2.INTER_NEAREST)
        print("DBG frame . =pavimento / +=ombra / #=nero (riga0=alto):", flush=True)
        for _row in _small:
            print(
                "DBG |"
                + "".join(
                    "#" if _p < 40 else ("+" if _p < 110 else ("." if _p < 185 else "s"))
                    for _p in _row
                )
                + "|",
                flush=True,
            )
    if deviation is None:
        pid.reset()
        pwm_left, pwm_right = 0, 0
        err, slow = "", ""
        if _dbg > 100 and "cam_green_lost" not in os.environ:
            camera_green.saveImage(os.path.join(tempfile.gettempdir(), "cam_green_lost.png"), 100)
            os.environ["cam_green_lost"] = "1"
            print("DBG LOST first frame saved", flush=True)
    else:
        err = deviation / (width / 2)
        correction = pid.update(err, dt) + LINE_KA * (line_ang / (math.pi / 4))
        pwm_left, pwm_right = tank_mix(curve_base_pwm(BASE_PWM, err), correction, STEER_MAX_CORR)
    pwm_left = slew_limit(_prev_pwm_left, pwm_left, SLEW_MAX_DPWM)
    pwm_right = slew_limit(_prev_pwm_right, pwm_right, SLEW_MAX_DPWM)
    _prev_pwm_left, _prev_pwm_right = pwm_left, pwm_right
    if _dbg % 8 == 0:
        _dev_str = "" if deviation is None else f"{deviation:.1f}"
        _err_str = "" if deviation is None else f"{err:.3f}"
        _ang_str = "" if line_ang is None else f"{line_ang:.3f}"
        _slow_str = "" if deviation is None else f"{curve_slow_factor(err):.3f}"
        _runlog.write(f"{_dbg},{_dbg * dt:.2f},{_dev_str},{_ang_str},{_slow_str},{pwm_left},{pwm_right}\n")
        _runlog.flush()
    motor_fl.setVelocity(pwm_to_velocity(pwm_left))
    motor_rl.setVelocity(pwm_to_velocity(pwm_left))
    motor_fr.setVelocity(pwm_to_velocity(pwm_right))
    motor_rr.setVelocity(pwm_to_velocity(pwm_right))
