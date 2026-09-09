"""Probe headless temporaneo: logga posa RESCUEBOT e chiude la sim (solo debug)."""

from controller import Supervisor

sup = Supervisor()
timestep = int(sup.getBasicTimeStep())
bot = sup.getFromDef("RESCUEBOT")
mount = sup.getFromDef("CAM_GREEN_MOUNT")
wl = sup.getFromDef("WHEEL_RL")
wr = sup.getFromDef("WHEEL_RR")
wfl = sup.getFromDef("WHEEL_FL")
wfr = sup.getFromDef("WHEEL_FR")
for i in range(4000):
    if sup.step(timestep) == -1:
        break
    if i % 32 == 0:
        print(
            f"PROBE t={sup.getTime():.2f} pos={bot.getPosition()} "
            f"rot={bot.getOrientation()} mnt={mount.getPosition() if mount else None} "
            f"wl={wl.getVelocity() if wl else None} wr={wr.getVelocity() if wr else None} "
            f"wfl={wfl.getVelocity() if wfl else None} wfr={wfr.getVelocity() if wfr else None}",
            flush=True,
        )
sup.simulationQuit(0)
