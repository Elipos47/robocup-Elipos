# ===========================================================================
# state_machine.py – Macchina a stati per il robot
# ===========================================================================
# Gestisce gli stati del robot per il line following avanzato.
# Stati: LINE_DETECTED, GAP_DETECTED, GAP_AVOID, OBSTACLE_DETECTED,
#        OBSTACLE_AVOID, OBSTACLE_ORIENTATE, STOP
# ===========================================================================

from enum import Enum, auto
from typing import Optional, Callable
from dataclasses import dataclass


class RobotState(Enum):
    """Stati possibili del robot."""
    # Stati base
    LINE_DETECTED = auto()      # Linea rilevata, seguimento normale
    STOP = auto()               # Stop (rosso rilevato o linea persa)
    
    # Stati gap
    GAP_DETECTED = auto()       # Gap rilevato, in validazione
    GAP_AVOID = auto()          # Attraversamento gap in corso
    GAP_ORIENTATE = auto()      # Ri-orientamento dopo gap
    
    # Stati ostacoli
    OBSTACLE_DETECTED = auto()  # Ostacolo rilevato, in validazione
    OBSTACLE_AVOID = auto()     # Evitamento ostacolo in corso
    OBSTACLE_ORIENTATE = auto() # Ri-orientamento dopo ostacolo
    
    # Stati calibrazione
    CALIBRATE = auto()          # Modalità calibrazione colori
    DEBUG = auto()              # Modalità debug


@dataclass
class StateTransition:
    """Rappresenta una transizione di stato."""
    from_state: RobotState
    to_state: RobotState
    condition: str
    timestamp: float


class StateMachine:
    """Macchina a stati per il robot."""
    
    def __init__(self, initial_state: RobotState = RobotState.LINE_DETECTED):
        """
        Parameters
        ----------
        initial_state : RobotState
            Stato iniziale del robot
        """
        self._current_state = initial_state
        self._previous_state = initial_state
        self._state_entry_time = 0.0
        self._transitions: list = []
        self._state_handlers: dict = {}
        self._transition_handlers: dict = {}
        
        import time
        self._state_entry_time = time.perf_counter()
    
    @property
    def current_state(self) -> RobotState:
        """Stato corrente del robot."""
        return self._current_state
    
    @property
    def previous_state(self) -> RobotState:
        """Stato precedente del robot."""
        return self._previous_state
    
    @property
    def state_name(self) -> str:
        """Nome dello stato corrente."""
        return self._current_state.name
    
    @property
    def state_time(self) -> float:
        """Tempo trascorso nello stato corrente (secondi)."""
        import time
        return time.perf_counter() - self._state_entry_time
    
    def transition_to(self, new_state: RobotState, reason: str = "") -> bool:
        """Transiziona a un nuovo stato.
        
        Parameters
        ----------
        new_state : RobotState
            Nuovo stato
        reason : str
            Motivo della transizione
            
        Returns
        -------
        bool
            True se la transizione è avvenuta
        """
        if new_state == self._current_state:
            return False
        
        import time
        
        # Registra transizione
        transition = StateTransition(
            from_state=self._current_state,
            to_state=new_state,
            condition=reason,
            timestamp=time.perf_counter()
        )
        self._transitions.append(transition)
        
        # Chiama handler uscita stato precedente
        if self._current_state in self._state_handlers:
            handlers = self._state_handlers[self._current_state]
            if 'exit' in handlers:
                handlers['exit']()
        
        # Esegui handler transizione
        transition_key = (self._current_state, new_state)
        if transition_key in self._transition_handlers:
            self._transition_handlers[transition_key]()
        
        # Cambia stato
        self._previous_state = self._current_state
        self._current_state = new_state
        self._state_entry_time = time.perf_counter()
        
        # Chiama handler entrata nuovo stato
        if new_state in self._state_handlers:
            handlers = self._state_handlers[new_state]
            if 'enter' in handlers:
                handlers['enter']()
        
        return True
    
    def is_in_state(self, state: RobotState) -> bool:
        """Verifica se il robot è in uno specifico stato.
        
        Parameters
        ----------
        state : RobotState
            Stato da verificare
            
        Returns
        -------
        bool
            True se nello stato specificato
        """
        return self._current_state == state
    
    def is_in_any_state(self, states: list) -> bool:
        """Verifica se il robot è in uno qualsiasi degli stati specificati.
        
        Parameters
        ----------
        states : list
            Lista di stati da verificare
            
        Returns
        -------
        bool
            True se in uno degli stati
        """
        return self._current_state in states
    
    def register_state_handler(self, state: RobotState, 
                                on_enter: Optional[Callable] = None,
                                on_exit: Optional[Callable] = None):
        """Registra handler per uno stato.
        
        Parameters
        ----------
        state : RobotState
            Stato per cui registrare gli handler
        on_enter : callable, optional
            Funzione da chiamare all'entrata nello stato
        on_exit : callable, optional
            Funzione da chiamare all'uscita dallo stato
        """
        if state not in self._state_handlers:
            self._state_handlers[state] = {}
        
        if on_enter:
            self._state_handlers[state]['enter'] = on_enter
        if on_exit:
            self._state_handlers[state]['exit'] = on_exit
    
    def register_transition_handler(self, from_state: RobotState, 
                                    to_state: RobotState,
                                    handler: Callable):
        """Registra handler per una specifica transizione.
        
        Parameters
        ----------
        from_state : RobotState
            Stato di partenza
        to_state : RobotState
            Stato di arrivo
        handler : callable
            Funzione da chiamare durante la transizione
        """
        self._transition_handlers[(from_state, to_state)] = handler
    
    def get_transitions_history(self, n: int = 10) -> list:
        """Restituisce le ultime N transizioni.
        
        Parameters
        ----------
        n : int
            Numero di transizioni da restituire
            
        Returns
        -------
        list
            Lista delle transizioni
        """
        return self._transitions[-n:]
    
    def reset(self, to_state: RobotState = RobotState.LINE_DETECTED):
        """Resetta la macchina a stati.
        
        Parameters
        ----------
        to_state : RobotState
            Stato in cui resettare
        """
        import time
        self._current_state = to_state
        self._previous_state = to_state
        self._state_entry_time = time.perf_counter()
        self._transitions.clear()


# Istanza singleton
current_state = StateMachine()


# Funzioni di convenienza per uso globale
def is_line_detected() -> bool:
    """Verifica se la linea è rilevata."""
    return current_state.is_in_state(RobotState.LINE_DETECTED)


def is_gap_active() -> bool:
    """Verifica se c'è un gap attivo (rilevato o in attraversamento)."""
    return current_state.is_in_any_state([
        RobotState.GAP_DETECTED, 
        RobotState.GAP_AVOID,
        RobotState.GAP_ORIENTATE
    ])


def is_obstacle_active() -> bool:
    """Verifica se c'è un ostacolo attivo."""
    return current_state.is_in_any_state([
        RobotState.OBSTACLE_DETECTED,
        RobotState.OBSTACLE_AVOID,
        RobotState.OBSTACLE_ORIENTATE
    ])


def is_stopped() -> bool:
    """Verifica se il robot è fermo."""
    return current_state.is_in_state(RobotState.STOP)


# Enum per semplice accesso
States = RobotState
