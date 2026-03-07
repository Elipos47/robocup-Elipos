# ===========================================================================
# moving_average.py – Media mobile temporale
# ===========================================================================
# Buffer circolare che mantiene valori con timestamp.
# Calcola la media degli ultimi N secondi.
# Simile al sistema di robot_v.3 ma semplificato.
# ===========================================================================

import time
from collections import deque
from typing import List, Optional, Union
import numpy as np


class MovingAverage:
    """Buffer per media mobile temporale."""

    def __init__(self, max_age: float = 2.0, max_samples: int = 100):
        """
        Parameters
        ----------
        max_age : float
            Durata massima in secondi per i campioni (default: 2.0)
        max_samples : int
            Numero massimo di campioni da mantenere (default: 100)
        """
        self._max_age = max_age
        self._max_samples = max_samples
        self._samples: deque = deque(maxlen=max_samples)
        
    def add(self, value: Union[int, float]):
        """Aggiunge un campione con timestamp corrente.
        
        Parameters
        ----------
        value : int or float
            Valore da aggiungere
        """
        self._samples.append({
            'value': value,
            'timestamp': time.perf_counter()
        })
        
        # Rimuovi campioni troppo vecchi
        self._cleanup_old_samples()
    
    def _cleanup_old_samples(self):
        """Rimuove campioni più vecchi di max_age."""
        now = time.perf_counter()
        while self._samples and (now - self._samples[0]['timestamp']) > self._max_age:
            self._samples.popleft()
    
    def get_average(self, seconds: Optional[float] = None) -> float:
        """Calcola la media degli ultimi N secondi.
        
        Parameters
        ----------
        seconds : float, optional
            Intervallo temporale in secondi (default: max_age)
            
        Returns
        -------
        float
            Media dei valori, 0.0 se non ci sono campioni
        """
        if not self._samples:
            return 0.0
        
        if seconds is None:
            seconds = self._max_age
        
        now = time.perf_counter()
        cutoff = now - seconds
        
        # Filtra campioni nel range temporale
        values = [s['value'] for s in self._samples if s['timestamp'] > cutoff]
        
        if not values:
            return 0.0
        
        return sum(values) / len(values)
    
    def get_average_weighted(self, seconds: Optional[float] = None) -> float:
        """Calcola media pesata (più recente = più peso).
        
        Parameters
        ----------
        seconds : float, optional
            Intervallo temporale (default: max_age)
            
        Returns
        -------
        float
            Media pesata, 0.0 se non ci sono campioni
        """
        if not self._samples:
            return 0.0
        
        if seconds is None:
            seconds = self._max_age
        
        now = time.perf_counter()
        cutoff = now - seconds
        
        values = []
        weights = []
        
        for sample in self._samples:
            if sample['timestamp'] > cutoff:
                # Peso inversamente proporzionale all'età
                age = now - sample['timestamp']
                weight = 1.0 - (age / seconds) if seconds > 0 else 1.0
                values.append(sample['value'])
                weights.append(max(0.1, weight))
        
        if not values:
            return 0.0
        
        return np.average(values, weights=weights)
    
    def get_last(self) -> Optional[float]:
        """Restituisce l'ultimo valore aggiunto.
        
        Returns
        -------
        float or None
            Ultimo valore, None se buffer vuoto
        """
        if not self._samples:
            return None
        return self._samples[-1]['value']
    
    def get_last_n(self, n: int) -> List[float]:
        """Restituisce gli ultimi N valori.
        
        Parameters
        ----------
        n : int
            Numero di valori da restituire
            
        Returns
        -------
        list
            Lista degli ultimi N valori
        """
        return [s['value'] for s in list(self._samples)[-n:]]
    
    def is_stable(self, threshold: float = 1.0, seconds: Optional[float] = None) -> bool:
        """Verifica se i valori sono stabili (variazione sotto soglia).
        
        Parameters
        ----------
        threshold : float
            Soglia di variazione massima
        seconds : float, optional
            Intervallo da considerare
            
        Returns
        -------
        bool
            True se i valori sono stabili
        """
        if seconds is None:
            seconds = self._max_age
        
        values = self.get_last_n(10)
        if len(values) < 5:
            return False
        
        return max(values) - min(values) < threshold
    
    def clear(self):
        """Svuota il buffer."""
        self._samples.clear()
    
    def count(self, seconds: Optional[float] = None) -> int:
        """Conta il numero di campioni nell'intervallo.
        
        Parameters
        ----------
        seconds : float, optional
            Intervallo in secondi
            
        Returns
        -------
        int
            Numero di campioni
        """
        if seconds is None:
            return len(self._samples)
        
        now = time.perf_counter()
        cutoff = now - seconds
        return sum(1 for s in self._samples if s['timestamp'] > cutoff)
    
    def is_unchanged(self, seconds: float = 1.0, tolerance: float = 0.5) -> bool:
        """Verifica se il valore non è cambiato significativamente.
        
        Utile per stuck detection.
        
        Parameters
        ----------
        seconds : float
            Intervallo da controllare
        tolerance : float
            Tolleranza di variazione
            
        Returns
        -------
        bool
            True se il valore è rimasto costante
        """
        now = time.perf_counter()
        cutoff = now - seconds
        
        values = [s['value'] for s in self._samples if s['timestamp'] > cutoff]
        
        if len(values) < 3:
            return False
        
        return max(values) - min(values) < tolerance


# Factory per creare array di medie mobili
def create_moving_averages(names: List[str], max_age: float = 2.0) -> dict:
    """Crea un dizionario di MovingAverage.
    
    Parameters
    ----------
    names : list
        Lista di nomi per le medie mobili
    max_age : float
        Durata massima per i campioni
        
    Returns
    -------
    dict
        Dizionario {nome: MovingAverage}
    """
    return {name: MovingAverage(max_age) for name in names}


# Istanze globali per i sensori principali
class SensorAverages:
    """Gestore centralizzato delle medie mobili per i sensori."""
    
    def __init__(self):
        self.line_angle = MovingAverage(max_age=0.5)
        self.line_size = MovingAverage(max_age=1.0)
        self.distance = MovingAverage(max_age=0.3)
        self.obstacle_confidence = MovingAverage(max_age=0.5)
        
        # Per stuck detection
        self.line_similarity = MovingAverage(max_age=3.0)
    
    def update_line(self, angle: float, size: float):
        """Aggiorna valori linea."""
        self.line_angle.add(angle)
        self.line_size.add(size)
    
    def update_distance(self, distance: float):
        """Aggiorna distanza sensore."""
        self.distance.add(distance)
    
    def update_similarity(self, similarity: float):
        """Aggiorna similarità immagine per stuck detection."""
        self.line_similarity.add(similarity)


# Istanza singleton
sensor_averages = SensorAverages()
