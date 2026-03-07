# ===========================================================================
#  camera_manager.py – Gestione telecamera CSI (Raspberry Pi Camera Module 3)
# ===========================================================================
#  Utilizza picamera2 per acquisire frame in formato RGB (NumPy array).
#  Ottimizzato per alta velocità: 448x252 @ 60 FPS con focus manuale.
#  Ispirato al setup del team Overengineered (RoboCup 2024 World Champion).
# ===========================================================================

from picamera2 import Picamera2
from libcamera import controls as libcamera_controls
from config_manager import config_manager

# ── Parametri configurabili (da config.ini [camera]) ──────────────────────
CAMERA_WIDTH = config_manager.read_variable("camera", "width", 448)
CAMERA_HEIGHT = config_manager.read_variable("camera", "height", 252)
CAMERA_RESOLUTION = (CAMERA_WIDTH, CAMERA_HEIGHT)

CAMERA_FPS = config_manager.read_variable("camera", "fps", 60)

# Focus manuale: LensPosition 6.5 = ~15cm (macro, ideale per line-following)
# Evita la latenza dell'autofocus continuo della IMX708 Camera Module 3
CAMERA_LENS_POSITION = config_manager.read_variable("camera", "lens_position", 6.5)

# Usa il path specifico della camera CSI per evitare conflitti con USB
# Il path si ottiene da: v4l2-ctl --list-devices
CSI_CAMERA_ID = "/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a"
# ───────────────────────────────────────────────────────────────────────────


class CameraManager:
    """Gestisce l'acquisizione dei frame dalla telecamera CSI.
    
    Configurazione ottimizzata:
    - Risoluzione ridotta (448x252) per processing più veloce (~57% pixel in meno)
    - FrameDurationLimits fissato a 60 FPS per framerate costante
    - Autofocus disabilitato, focus manuale a distanza fissa (macro)
    - Risultato: ~60 FPS reali vs ~30 FPS della configurazione precedente (640x480)
    """

    def __init__(self, resolution=CAMERA_RESOLUTION, fps=CAMERA_FPS,
                 lens_position=CAMERA_LENS_POSITION):
        # Inizializza picamera2 - usa la prima camera disponibile (dovrebbe essere la CSI)
        # Se ci sono problemi con USB, assicurati che la USB usi OpenCV, non libcamera
        self._picam = Picamera2(camera_num=0)

        # Calcola durata frame per FPS desiderato
        # FrameDurationLimits è in microsecondi: 1_000_000 / fps
        frame_duration_us = 1_000_000 // fps

        config = self._picam.create_preview_configuration(
            main={"format": "RGB888", "size": resolution},
            controls={
                # Fissa il framerate: min = max = durata target
                "FrameDurationLimits": (frame_duration_us, frame_duration_us),
                # Disabilita autofocus → focus manuale a distanza fissa
                # AfMode 0 = Manual (libcamera)
                "AfMode": libcamera_controls.AfModeEnum.Manual,
                "LensPosition": lens_position,
            }
        )
        self._picam.configure(config)
        self._picam.start()

        self._fps = fps
        self._resolution = resolution
        print(f"[CAMERA] CSI inizializzata: {resolution[0]}x{resolution[1]} @ {fps} FPS"
              f" | Focus manuale: {lens_position}")

    # ── Acquisizione ──────────────────────────────────────────────────────
    def get_frame(self):
        """Restituisce il frame corrente come array NumPy in formato RGB.

        Nota: picamera2 con formato 'RGB888' restituisce in realtà BGR.
        I canali vengono invertiti qui per garantire un vero RGB.
        """
        frame = self._picam.capture_array()
        return frame[:, :, ::-1]  # BGR → RGB

    @property
    def resolution(self):
        """Risoluzione corrente (width, height)."""
        return self._resolution

    @property
    def fps(self):
        """FPS target configurato."""
        return self._fps

    # ── Chiusura ──────────────────────────────────────────────────────────
    def close(self):
        """Arresta la telecamera e rilascia le risorse."""
        self._picam.stop()
        self._picam.close()
