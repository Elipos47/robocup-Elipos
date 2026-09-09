"""Macchina a stati principale (SPEC §5)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic


class State(str, Enum):
    """Stati della FSM."""

    SEGUILINEA = "SEGUILINEA"
    OSTACOLO = "OSTACOLO"
    VERDE_DX = "VERDE_DX"
    VERDE_SX = "VERDE_SX"
    STANZA = "STANZA"
    UTURN = "UTURN"


TRANSITIONS: dict[State, set[State]] = {
    State.SEGUILINEA: {State.OSTACOLO, State.VERDE_DX, State.VERDE_SX, State.STANZA, State.UTURN},
    State.OSTACOLO: {State.SEGUILINEA},
    State.VERDE_DX: {State.SEGUILINEA},
    State.VERDE_SX: {State.SEGUILINEA},
    State.STANZA: {State.SEGUILINEA},
    State.UTURN: {State.SEGUILINEA},
}


@dataclass
class Perception:
    """Input percepiti in un tick."""

    line_deviation: float | None = None  # px, None = linea persa
    obstacle_cm: float | None = None
    green_right: bool = False
    green_left: bool = False
    silver_line: bool = False
    uturn_marker: bool = False
    line_lost_ms: int = 0


class StateMachine:
    """FSM con transizioni validate + debounce (robusta ai glitch dei sensori)."""

    def __init__(self, debounce_ms: int = 200) -> None:
        from src.utils.config import STATE_DEBOUNCE_MS

        self.state = State.SEGUILINEA
        self.debounce_ms = debounce_ms or STATE_DEBOUNCE_MS
        self._pending: State | None = None
        self._pending_since: float = 0.0
        self.history: list[str] = []

    def _request(self, target: State) -> None:
        now = monotonic() * 1000
        if target == self._pending:
            if now - self._pending_since >= self.debounce_ms:
                if target in TRANSITIONS[self.state]:
                    self.state = target
                    self.history.append(target.value)
                self._pending = None
        else:
            self._pending = target
            self._pending_since = now

    def update(self, p: Perception) -> State:
        """Avanza di un tick; restituisce lo stato attivo."""
        if self.state == State.SEGUILINEA:
            if p.obstacle_cm is not None:
                from src.utils.config import OBSTACLE_DISTANCE_CM

                if p.obstacle_cm < OBSTACLE_DISTANCE_CM:
                    self._request(State.OSTACOLO)
            if p.green_right:
                self._request(State.VERDE_DX)
            elif p.green_left:
                self._request(State.VERDE_SX)
            elif p.silver_line:
                self._request(State.STANZA)
            elif p.uturn_marker:
                self._request(State.UTURN)
        else:
            # Stati foglia: rientro in SEGUILINEA gestito dal controller di moto
            # quando l'azione e completata (finishing flag esterno).
            pass
        return self.state

    def finish_action(self) -> State:
        """Segnala azione completata: torna a SEGUILINEA (se consentito)."""
        if State.SEGUILINEA in TRANSITIONS[self.state]:
            self.state = State.SEGUILINEA
            self.history.append(State.SEGUILINEA.value)
        return self.state
