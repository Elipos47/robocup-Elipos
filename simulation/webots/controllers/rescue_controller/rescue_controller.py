"""Controller Webots (SPEC §6.4): camera verde -> linea nera -> PID -> motori.

M1: seguilineanera con P-control su errore normalizzato ±1.
Linea persa: stop + reset integrale (ricerca ostacolo/stanza in M2).
Eseguito dentro Webots; fuori Webots resta importabile solo src/.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from controller import Robot  # noqa: E402  (iniettato da Webots a runtime)

from src.control.motor_control import PIDController, pwm_to_velocity, tank_mix  # noqa: E402
from src.utils.config import BASE_PWM, LINE_KP  # noqa: E402
from src.vision.line_detector import detect_black_line  # noqa: E402

robot = Robot()
timestep = int(robot.getBasicTimeStep())
dt = timestep / 1000.0

camera_green = robot.getDevice("camera_green")
camera_green.enable(timestep)
width = camera_green.getWidth()
height = camera_green.getHeight()

motor_left = robot.getDevice("motor_left")
motor_right = robot.getDevice("motor_right")
motor_left.setPosition(float("inf"))
motor_right.setPosition(float("inf"))

pid = PIDController(kp=LINE_KP)

while robot.step(timestep) != -1:
    frame = np.frombuffer(camera_green.getImage(), dtype=np.uint8)
    frame = frame.reshape((height, width, 4))[:, :, :3]  # BGRA -> BGR
    deviation = detect_black_line(frame)
    if deviation is None:
        pid.reset()
        pwm_left, pwm_right = 0, 0
    else:
        correction = pid.update(deviation / (width / 2), dt)
        pwm_left, pwm_right = tank_mix(BASE_PWM, correction)
    motor_left.setVelocity(pwm_to_velocity(pwm_left))
    motor_right.setVelocity(pwm_to_velocity(pwm_right))
