# ===========================================================================
# timer.py – Sistema di timer avanzato
# ===========================================================================
# Timer con nome e durata, utili per gestire cooldown e timeout.
# Simile alla classe Timer di robot_v.3 ma semplificata.
# ===========================================================================

import time
from typing import Dict, Optional


class Timer:
    """Gestore di timer multipli con nome."""

    def __init__(self):
        """Inizializza il gestore timer."""
        self._timers: Dict[str, Dict] = {}

    def set_timer(self, name: str, duration: float):
        """Imposta un timer con nome e durata.
        
        Parameters
        ----------
        name : str
            Nome identificativo del timer
        duration : float
            Durata in secondi
        """
        self._timers[name] = {
            'start_time': time.perf_counter(),
            'duration': duration,
            'expired': False
        }

    def remove_timer(self, name: str):
        """Rimuove un timer.
        
        Parameters
        ----------
        name : str
            Nome del timer da rimuovere
        """
        if name in self._timers:
            del self._timers[name]

    def get_timer(self, name: str) -> bool:
        """Verifica se un timer è scaduto.
        
        Parameters
        ----------
        name : str
            Nome del timer
            
        Returns
        -------
        bool
            True se il timer è scaduto, False altrimenti
            (se il timer non esiste, restituisce True)
        """
        if name not in self._timers:
            return True
        
        timer = self._timers[name]
        elapsed = time.perf_counter() - timer['start_time']
        timer['expired'] = elapsed > timer['duration']
        
        return timer['expired']

    def get_elapsed(self, name: str) -> float:
        """Restituisce il tempo trascorso da quando il timer è stato impostato.
        
        Parameters
        ----------
        name : str
            Nome del timer
            
        Returns
        -------
        float
            Secondi trascorsi, 0 se il timer non esiste
        """
        if name not in self._timers:
            return 0.0
        
        return time.perf_counter() - self._timers[name]['start_time']

    def get_remaining(self, name: str) -> float:
        """Restituisce il tempo rimanente prima della scadenza.
        
        Parameters
        ----------
        name : str
            Nome del timer
            
        Returns
        -------
        float
            Secondi rimanenti, 0 se scaduto o non esistente
        """
        if name not in self._timers:
            return 0.0
        
        timer = self._timers[name]
        remaining = timer['duration'] - (time.perf_counter() - timer['start_time'])
        return max(0.0, remaining)

    def reset_timer(self, name: str):
        """Resetta il timer (ricomincia da capo).
        
        Parameters
        ----------
        name : str
            Nome del timer da resettare
        """
        if name in self._timers:
            self._timers[name]['start_time'] = time.perf_counter()
            self._timers[name]['expired'] = False

    def has_timer(self, name: str) -> bool:
        """Verifica se un timer esiste.
        
        Parameters
        ----------
        name : str
            Nome del timer
            
        Returns
        -------
        bool
            True se il timer esiste
        """
        return name in self._timers

    def clear_all(self):
        """Rimuove tutti i timer."""
        self._timers.clear()

    def list_timers(self) -> list:
        """Restituisce la lista dei timer attivi.
        
        Returns
        -------
        list
            Lista di nomi timer attivi
        """
        return list(self._timers.keys())


# Istanza singleton
timer = Timer()


# Funzioni di convenienza per uso globale
def set_cooldown(name: str, duration: float):
    """Imposta un cooldown (timer che scade dopo un certo tempo)."""
    timer.set_timer(name, duration)


def is_cooldown_active(name: str) -> bool:
    """Verifica se un cooldown è ancora attivo (non scaduto)."""
    return not timer.get_timer(name)


def wait_for_cooldown(name: str, duration: float) -> bool:
    """Imposta un cooldown se non esiste, e verifica se è scaduto.
    
    Returns
    -------
    bool
        True se il cooldown è scaduto (prima chiamata), False altrimenti
    """
    if not timer.has_timer(name):
        timer.set_timer(name, duration)
        return True
    return timer.get_timer(name)
