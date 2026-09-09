"""Controllo motori: PID differenziale con saturazione PWM (SPEC §2.1)."""

from __future__ import annotations

from src.utils.config import (
    MAX_WHEEL_RAD_S,
    MOTOR_MAX_PWM,
    PID_KD,
    PID_KI,
    PID_KP,
    WHEEL_DIRECTION,
)


class PIDController:
    """PID discreto con anti-windup e saturazione."""

    def __init__(
        self,
        kp: float = PID_KP,
        ki: float = PID_KI,
        kd: float = PID_KD,
        out_limit: int = MOTOR_MAX_PWM,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_limit = out_limit
        self._integral = 0.0
        self._prev_error: float | None = None

    def update(self, error: float, dt: float) -> float:
        """Calcola correzione; dt in secondi (>0).

        Args:
            error: Errore corrente (es. deviazione linea).
            dt: Passo temporale in secondi.

        Returns:
            Correzione saturata a ±out_limit.
        """
        if dt <= 0:
            raise ValueError("dt deve essere > 0")
        self._integral += error * dt
        derivative = 0.0 if self._prev_error is None else (error - self._prev_error) / dt
        self._prev_error = error
        out = self.kp * error + self.ki * self._integral + self.kd * derivative
        return max(-self.out_limit, min(self.out_limit, out))

    def reset(self) -> None:
        """Azzera stato integrale/derivativo (cambio stato FSM)."""
        self._integral = 0.0
        self._prev_error = None


def tank_mix(base_pwm: int, correction: float) -> tuple[int, int]:
    """Miscela differenziale: correzione >0 (linea a destra) = svolta a destra.

    Svolta a destra = ruota sinistra piu' veloce, destra piu' lenta.
    Output saturati a ±MOTOR_MAX_PWM.
    """
    left = max(-MOTOR_MAX_PWM, min(MOTOR_MAX_PWM, int(base_pwm + correction)))
    right = max(-MOTOR_MAX_PWM, min(MOTOR_MAX_PWM, int(base_pwm - correction)))
    return left, right


def pwm_to_velocity(pwm: int) -> float:
    """Mappa PWM con segno -> rad/s (segno di marcia avanti incluso).

    Usato dal controller Webots; su hardware reale il PWM va diretto ad Arduino.

    Args:
        pwm: Valore PWM con segno.

    Returns:
        Velocita' angolare ruota in rad/s.
    """
    return WHEEL_DIRECTION * (pwm / MOTOR_MAX_PWM) * MAX_WHEEL_RAD_S
