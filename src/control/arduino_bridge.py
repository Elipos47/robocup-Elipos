"""Bridge seriale Pi ↔ Arduino (SPEC §8.1/8.2). Protocollo: <CMD><VALUE>\\n."""

from __future__ import annotations


class ArduinoBridge:
    """Wrapper seriale con lazy-import (testabile senza hardware/pyserial)."""

    def __init__(self, port: str = "", baudrate: int = 0, timeout: float = 1.0) -> None:
        from src.utils.config import ARDUINO_BAUDRATE, ARDUINO_PORT

        import serial

        self.serial = serial.Serial(
            port or ARDUINO_PORT, baudrate or ARDUINO_BAUDRATE, timeout=timeout
        )

    def set_motor(self, motor_id: int, speed: int) -> None:
        """Imposta motore 1|2, speed -255..255.

        Raises:
            ValueError: Se motor_id o speed fuori range.
        """
        if motor_id not in (1, 2):
            raise ValueError("motor_id deve essere 1 o 2")
        if not -255 <= speed <= 255:
            raise ValueError("speed deve stare in -255..255")
        self.serial.write(f"M{motor_id}{speed}\n".encode())

    def read_sensors(self) -> list[str]:
        """Richiede stato sensori ad Arduino."""
        self.serial.write(b"S?\n")
        return self.serial.readline().decode(errors="replace").strip().split(",")
