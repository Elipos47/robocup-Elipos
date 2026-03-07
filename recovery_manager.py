# ===========================================================================
# recovery_manager.py – Smart Recovery System (stile Overengineered)
# ===========================================================================
# Gestisce recovery automatico quando il robot perde la linea.
# Implementa: Image Similarity Check, Recovery Progressivo, Jiggle Maneuvers
# ===========================================================================

import time
import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque

from logger import get_logger
from timer import timer
from state_machine import current_state, RobotState


class RecoveryState(Enum):
    """Stati del recovery system."""
    IDLE = auto()                # Normale operazione
    LINE_LOST = auto()           # Linea persa, iniziando recovery
    BACKUP = auto()              # Fase 1: Indietro
    JIGGLE_RIGHT = auto()        # Fase 2: Jiggle destra
    JIGGLE_LEFT = auto()         # Fase 3: Jiggle sinistra  
    WIDE_SEARCH = auto()         # Fase 4: Ricerca ampia
    FINAL_BACKUP = auto()        # Fase 5: Backup finale
    FAILED = auto()              # Recovery fallito


@dataclass
class ImageSimilarityResult:
    """Risultato del check similarità immagini."""
    is_stuck: bool = False
    similarity: float = 1.0
    frames_stuck: int = 0


@dataclass
class RecoveryInfo:
    """Informazioni sullo stato del recovery."""
    state: RecoveryState = RecoveryState.IDLE
    attempt: int = 0
    start_time: float = 0.0
    last_similarity: float = 1.0
    frames_stuck: int = 0

    def reset(self):
        self.state = RecoveryState.IDLE
        self.attempt = 0
        self.start_time = 0.0
        self.last_similarity = 1.0
        self.frames_stuck = 0


class ImageSimilarityChecker:
    """Rileva se il robot è bloccato confrontando frame consecutivi."""

    def __init__(self, history_size: int = 10, similarity_threshold: float = 0.90):
        """
        Parameters
        ----------
        history_size : int
            Numero di frame da confrontare (default 10 = ~0.33s a 30fps)
        similarity_threshold : float
            Soglia sopra cui considerare "stuck" (0.90 = 90% simile)
            Aumentato da 0.85 a 0.90 per ridurre falsi positivi
        """
        self._logger = get_logger("IMG_SIM")
        self._history_size = history_size
        self._similarity_threshold = similarity_threshold
        self._image_history: deque = deque(maxlen=history_size)
        self._stuck_counter = 0
        self._is_stuck = False

        # Parametri per ridurre risoluzione (performance)
        self._resize_factor = 0.25

        self._logger.info("ImageSimilarityChecker inizializzato",
                         history_size=history_size,
                         threshold=similarity_threshold)

    def update(self, frame: np.ndarray) -> ImageSimilarityResult:
        """Aggiorna il checker con un nuovo frame.

        Parameters
        ----------
        frame : np.ndarray
            Frame BGR della telecamera

        Returns
        -------
        ImageSimilarityResult
            Risultato del check
        """
        # Riduci risoluzione per performance
        small_frame = cv2.resize(frame, None, fx=self._resize_factor, fy=self._resize_factor)

        # Converti in grayscale
        if len(small_frame.shape) == 3:
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = small_frame

        # Aggiungi alla storia
        self._image_history.append(gray)

        result = ImageSimilarityResult()

        # Abbastanza frame per confrontare
        if len(self._image_history) >= 2:
            # Confronta con frame precedente
            prev = self._image_history[-2]
            curr = self._image_history[-1]

            # Calcola similarità strutturale (semplificata)
            # Usa correlazione normale invece di SSIM per velocità
            similarity = self._calculate_similarity(prev, curr)
            result.similarity = similarity

            # Verifica se stuck
            if similarity > self._similarity_threshold:
                self._stuck_counter += 1
            else:
                self._stuck_counter = max(0, self._stuck_counter - 2)

            result.frames_stuck = self._stuck_counter

            # Soglia stuck: metà della storia
            stuck_threshold = self._history_size // 2

            if self._stuck_counter >= stuck_threshold:
                if not self._is_stuck:
                    self._is_stuck = True
                    self._logger.warning("STUCK detected via image similarity",
                                        similarity=similarity,
                                        frames_stuck=self._stuck_counter)
                result.is_stuck = True
            else:
                if self._is_stuck:
                    self._is_stuck = False
                    self._logger.info("No longer stuck")

        result.is_stuck = self._is_stuck
        return result

    def _calculate_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calcola similarità tra due immagini.

        Usa correlazione normale per velocità (più veloce di SSIM).
        """
        # Normalizza
        img1_norm = img1.astype(np.float32) / 255.0
        img2_norm = img2.astype(np.float32) / 255.0

        # Correlazione
        correlation = cv2.matchTemplate(img1_norm, img2_norm, cv2.TM_CCOEFF_NORMED)
        similarity = correlation[0, 0]

        # Converti in range 0-1 dove 1 = identico
        return float((similarity + 1) / 2)

    def reset(self):
        """Reset del checker."""
        self._image_history.clear()
        self._stuck_counter = 0
        self._is_stuck = False
        self._logger.info("ImageSimilarityChecker resettato")

    @property
    def is_stuck(self) -> bool:
        return self._is_stuck


class RecoveryManager:
    """Gestisce il recovery automatico quando la linea è persa."""

    # Durate delle fasi in secondi
    BACKUP_DURATION = 0.5
    JIGGLE_DURATION = 0.4
    WIDE_SEARCH_DURATION = 0.6
    FINAL_BACKUP_DURATION = 1.0
    COOLDOWN_AFTER_RECOVERY = 2.0

    # Tentativi massimi
    MAX_ATTEMPTS = 4

    def __init__(self):
        self._logger = get_logger("RECOVERY")
        self._info = RecoveryInfo()
        self._similarity_checker = ImageSimilarityChecker()
        self._last_frame: Optional[np.ndarray] = None

        # Stato recovery
        self._recovery_active = False
        self._recovery_command: Optional[str] = None

        self._logger.info("RecoveryManager inizializzato",
                         max_attempts=self.MAX_ATTEMPTS)

    def update(self, line_detected: bool, frame: Optional[np.ndarray] = None) -> Tuple[str, bool]:
        """Aggiorna il recovery manager.

        Parameters
        ----------
        line_detected : bool
            Se la linea è attualmente rilevata
        frame : np.ndarray, optional
            Frame attuale per image similarity check

        Returns
        -------
        Tuple[str, bool]
            (comando, recovery_attivo)
        """
        # Se linea rilevata, reset
        if line_detected and self._info.state != RecoveryState.IDLE:
            self._logger.info("Line reacquired during recovery - resetting")
            self.reset()
            return "A", False

        # Image similarity check
        if frame is not None:
            similarity_result = self._similarity_checker.update(frame)
            self._info.last_similarity = similarity_result.similarity
            self._info.frames_stuck = similarity_result.frames_stuck

        # Gestisci stato corrente
        if self._info.state == RecoveryState.IDLE:
            # Non fare nulla se non in recovery
            return "A", False

        # Esegui recovery in base allo stato
        return self._execute_recovery()

    def start_recovery(self) -> str:
        """Avvia la sequenza di recovery.

        Returns
        -------
        str
            Primo comando di recovery
        """
        if self._info.state != RecoveryState.IDLE:
            self._logger.warning("Recovery già in corso")
            return "S"

        self._info.state = RecoveryState.LINE_LOST
        self._info.attempt = 0
        self._info.start_time = time.time()

        self._logger.warning("Starting recovery sequence")

        # Inizia con backup
        return self._next_recovery_step()

    def _next_recovery_step(self) -> str:
        """Passa al prossimo step di recovery.

        Returns
        -------
        str
            Comando per il prossimo step
        """
        self._info.attempt += 1
        self._info.start_time = time.time()

        if self._info.attempt > self.MAX_ATTEMPTS:
            # Recovery fallito
            self._info.state = RecoveryState.FAILED
            self._logger.error("Recovery failed after max attempts",
                             attempts=self.MAX_ATTEMPTS)
            return "S"

        # Sequenza recovery progressiva (stile Overengineered jiggle)
        sequence = [
            (RecoveryState.BACKUP, "ind", self.BACKUP_DURATION),
            (RecoveryState.JIGGLE_RIGHT, "cd", self.JIGGLE_DURATION),
            (RecoveryState.JIGGLE_LEFT, "cs", self.JIGGLE_DURATION),
            (RecoveryState.WIDE_SEARCH, "gd", self.WIDE_SEARCH_DURATION),
        ]

        if self._info.attempt <= len(sequence):
            state, command, duration = sequence[self._info.attempt - 1]
            self._info.state = state
            timer.set_timer("recovery_phase", duration)

            self._logger.info("Recovery step",
                            attempt=self._info.attempt,
                            state=state.name,
                            command=command,
                            duration=duration)

            return command
        else:
            # Tentativo finale: backup lungo
            self._info.state = RecoveryState.FINAL_BACKUP
            timer.set_timer("recovery_phase", self.FINAL_BACKUP_DURATION)
            self._logger.info("Final backup attempt")
            return "ind"

    def _execute_recovery(self) -> Tuple[str, bool]:
        """Esegue lo stato di recovery corrente.

        Returns
        -------
        Tuple[str, bool]
            (comando, recovery_attivo)
        """
        # Verifica se failed
        if self._info.state == RecoveryState.FAILED:
            return "S", True

        # Verifica timeout della fase
        if timer.get_timer("recovery_phase"):
            # Fase completata, passa alla prossima
            # MA prima verifica se abbiamo esaurito i tentativi
            if self._info.attempt >= self.MAX_ATTEMPTS:
                self._logger.warning("Recovery attempts exhausted")
                self._info.state = RecoveryState.FAILED
                return "S", True

            command = self._next_recovery_step()
            return command, True

        # Mantieni comando corrente
        state_commands = {
            RecoveryState.BACKUP: "ind",
            RecoveryState.JIGGLE_RIGHT: "cd",
            RecoveryState.JIGGLE_LEFT: "cs",
            RecoveryState.WIDE_SEARCH: "gd",
            RecoveryState.FINAL_BACKUP: "ind",
        }

        command = state_commands.get(self._info.state, "S")
        return command, True

    def reset(self):
        """Reset del recovery manager."""
        self._info.reset()
        self._similarity_checker.reset()
        # Cancella timer attivi
        if timer.has_timer("recovery_phase"):
            timer.set_timer("recovery_phase", 0)
        self._logger.info("RecoveryManager resettato")

    @property
    def is_recovering(self) -> bool:
        """True se in recovery."""
        return self._info.state != RecoveryState.IDLE

    @property
    def is_stuck(self) -> bool:
        """True se image similarity rileva stuck."""
        return self._similarity_checker.is_stuck

    @property
    def recovery_state(self) -> RecoveryState:
        """Stato corrente del recovery."""
        return self._info.state

    @property
    def attempt_number(self) -> int:
        """Numero di tentativo corrente."""
        return self._info.attempt

    def get_status_dict(self) -> dict:
        """Restituisce stato completo come dizionario."""
        return {
            'state': self._info.state.name,
            'attempt': self._info.attempt,
            'is_stuck': self._similarity_checker.is_stuck,
            'similarity': round(self._info.last_similarity, 3),
            'frames_stuck': self._info.frames_stuck
        }


# Istanza singleton
recovery_manager = RecoveryManager()


def get_recovery_manager() -> RecoveryManager:
    """Restituisce istanza del recovery manager."""
    return recovery_manager
