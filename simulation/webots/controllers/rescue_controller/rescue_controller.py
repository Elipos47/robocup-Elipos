"""Controller Webots (SPEC §6.4): bridge sensori Webots -> src/state_machine.

Eseguito dentro Webots. Fuori Webots il modulo src/ resta importabile e testabile.
"""

from controller import Camera, DistanceSensor, Motor, Robot

robot = Robot()
timestep = int(robot.getBasicTimeStep())

camera_green = robot.getDevice("camera_green")
camera_black = robot.getDevice("camera_black")
camera_green.enable(timestep)
camera_black.enable(timestep)

motor_left = robot.getDevice("motor_left")
motor_right = robot.getDevice("motor_right")
motor_left.setPosition(float("inf"))
motor_right.setPosition(float("inf"))

while robot.step(timestep) != -1:
    # TODO Fase 2: convertire getImage() in numpy -> line_detector/victim_detector
    # TODO Fase 3: collegare StateMachine.update() -> tank_mix -> setVelocity
    motor_left.setVelocity(0.0)
    motor_right.setVelocity(0.0)
