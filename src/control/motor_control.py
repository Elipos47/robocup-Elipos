"""Controllo motori: PID differenziale con saturazione PWM (SPEC §2.1)."""

from __future__ import annotations

from src.utils.config import (
    CURVE_SLOW_DEV_REF,
    CURVE_SLOW_GAIN,
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
            Correzione saturata a ±out_limit, con conditional integration
            (l'integrale si congela in saturazione: niente windup).
        """
        if dt <= 0:
            raise ValueError("dt deve essere > 0")
        derivative = 0.0 if self._prev_error is None else (error - self._prev_error) / dt
        self._prev_error = error
        trial_integral = self._integral + error * dt
        out = self.kp * error + self.ki * trial_integral + self.kd * derivative
        saturated = out > self.out_limit or out < -self.out_limit
        if not saturated or (error > 0) != (out > 0):
            self._integral = trial_integral
            return max(-self.out_limit, min(self.out_limit, out))
        return max(-self.out_limit, min(self.out_limit, out))

    def reset(self) -> None:
        """Azzera stato integrale/derivativo (cambio stato FSM)."""
        self._integral = 0.0
        self._prev_error = None


def tank_mix(base_pwm: int, correction: float, max_correction: int = MOTOR_MAX_PWM) -> tuple[int, int]:
    """Miscela differenziale: correzione >0 (linea a destra) = svolta a destra.

    Svolta a destra = ruota sinistra piu' veloce (la destra rallenta):
    destra = -X per marcia avanti +Z (right = forward x up).
    Dispositivo motor_left sul lato fisico sinistro (+X, vedi .wbt).
    Output saturati a ±MOTOR_MAX_PWM.

    Args:
        base_pwm: Avanzamento base (PWM con segno).
        correction: Correzione sterzo (+ = linea a destra).
        max_correction: Clamp anti-pivot su |correzione|. In curva con base
            rallentata serve la correzione piena ma MAI il pivot
            (base+204/-156): il clamp tiene lo yaw forte senza far girare
            il robot su se stesso.
    """
    correction = max(-max_correction, min(max_correction, correction))
    left = max(-MOTOR_MAX_PWM, min(MOTOR_MAX_PWM, int(base_pwm + correction)))
    right = max(-MOTOR_MAX_PWM, min(MOTOR_MAX_PWM, int(base_pwm - correction)))
    return left, right


def curve_slow_factor(dev_norm: float) -> float:
    """Fattore di rallentamento in curva (1 = dritto, 1-GAIN = curva stretta).

    Va applicato a base E correzione insieme: scala velocita' e yaw dello
    stesso fattore cosi' il raggio di sterzata resta invariato (solo piu'
    tempo per assestarsi). Applicarlo alla sola base renderebbe le svolte
    relativamente piu' brusche (pivot) — vietato.

    Args:
        dev_norm: Deviazione linea normalizzata ±1.

    Returns:
        Fattore <= 1.0 (mai negativo con GAIN < 1).
    """
    return 1.0 - CURVE_SLOW_GAIN * min(1.0, abs(dev_norm) / CURVE_SLOW_DEV_REF)


def curve_base_pwm(base_pwm: int, dev_norm: float) -> int:
    """Base PWM ridotta in curva, proporzionale a |deviazione normalizzata|.

    Rallentare stringe il raggio di sterzata (stesso differenziale, meno
    avanzamento): a |dev_norm| >= CURVE_SLOW_DEV_REF la base scende a
    base*(1-CURVE_SLOW_GAIN). Guidato da dev (anticipo geometrico), non
    dalla correzione (che arriva tardi a KP bassi).

    Args:
        base_pwm: Avanzamento base sul dritto.
        dev_norm: Deviazione linea normalizzata ±1 (stessa di tank_mix/PID).

    Returns:
        Base PWM scalata (<= base_pwm, mai negativa con GAIN < 1).
    """
    return int(base_pwm * curve_slow_factor(dev_norm))


def slew_limit(prev_pwm: int, target_pwm: int, max_delta: int) -> int:
    """Limita la variazione PWM per step (anti-jerk).

    I motori reali (L298N+DC) non fanno gradini: rampe dolci evitano
    sobbalzi/beccheggio che in sim eccitano rollio e rimbalzi. Testabile.

    Args:
        prev_pwm: PWM applicato allo step precedente.
        target_pwm: PWM richiesto dal controllo.
        max_delta: Variazione massima per step (>= 0).

    Returns:
        PWM effettivo, a max max_delta da prev_pwm verso target_pwm.
    """
    delta = target_pwm - prev_pwm
    if delta > max_delta:
        return prev_pwm + max_delta
    if delta < -max_delta:
        return prev_pwm - max_delta
    return target_pwm


def pwm_to_velocity(pwm: int) -> float:
    """Mappa PWM con segno -> rad/s (segno di marcia avanti incluso).

    Usato dal controller Webots; su hardware reale il PWM va diretto ad Arduino.

    Args:
        pwm: Valore PWM con segno.

    Returns:
        Velocita' angolare ruota in rad/s.
    """
    return WHEEL_DIRECTION * (pwm / MOTOR_MAX_PWM) * MAX_WHEEL_RAD_S
