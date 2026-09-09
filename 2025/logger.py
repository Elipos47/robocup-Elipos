# ===========================================================================
# logger.py – Sistema di logging avanzato per debug
# ===========================================================================
# FASE 4: Logging strutturato con livelli, rotazione e statistiche
# ===========================================================================

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from collections import deque
import json
import threading

# ── Configurazione ─────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

MAX_LOG_FILES = 5
MAX_MEMORY_LOGS = 1000
# ───────────────────────────────────────────────────────────────────────────


@dataclass
class LogEntry:
    """Singola entry di log strutturata."""
    timestamp: datetime
    level: str
    component: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'component': self.component,
            'message': self.message,
            'data': self.data
        }
    
    def __str__(self) -> str:
        data_str = f" | {self.data}" if self.data else ""
        return f"[{self.timestamp.strftime('%H:%M:%S.%f')[:-3]}] " \
               f"[{self.level:8}] [{self.component:15}] {self.message}{data_str}"


class RobotLogger:
    """Logger avanzato per il robot con memoria circolare."""
    
    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    def __init__(self, component: str = "ROBOT", 
                 log_to_file: bool = True,
                 log_to_console: bool = True,
                 min_level: str = "INFO"):
        """
        Parameters
        ----------
        component : str
            Nome componente per il log
        log_to_file : bool
            Se True, salva su file
        log_to_console : bool
            Se True, stampa su console
        min_level : str
            Livello minimo di log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.component = component
        self.min_level = self.LEVELS.get(min_level, 20)
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        
        # Memory buffer circolare
        self._memory_logs: deque = deque(maxlen=MAX_MEMORY_LOGS)
        self._lock = threading.Lock()
        
        # File handler
        self._file_handler = None
        if log_to_file:
            self._setup_file_logging()
        
        # Statistiche
        self._stats = {
            'total_logs': 0,
            'by_level': {k: 0 for k in self.LEVELS.keys()},
            'by_component': {}
        }
    
    def _setup_file_logging(self):
        """Configura logging su file con rotazione."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"robot_{timestamp}.log"
        
        self._file_handler = open(log_file, 'w', encoding='utf-8')
        self._file_handler.write(f"# RoboCup Robot Log - {timestamp}\n")
        self._file_handler.write(f"# Component: {self.component}\n")
        self._file_handler.write("=" * 80 + "\n")
        
        # Rotazione file vecchi
        self._rotate_old_logs()
    
    def _rotate_old_logs(self):
        """Mantiene solo gli ultimi N file di log."""
        log_files = sorted(LOG_DIR.glob("robot_*.log"), 
                          key=lambda x: x.stat().st_mtime, 
                          reverse=True)
        
        for old_file in log_files[MAX_LOG_FILES:]:
            try:
                old_file.unlink()
            except Exception:
                pass
    
    def _log(self, level: str, message: str, **kwargs):
        """Registra un messaggio di log."""
        level_val = self.LEVELS.get(level, 20)
        
        if level_val < self.min_level:
            return
        
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            component=self.component,
            message=message,
            data=kwargs
        )
        
        with self._lock:
            # Aggiorna statistiche
            self._stats['total_logs'] += 1
            self._stats['by_level'][level] += 1
            self._stats['by_component'][self.component] = \
                self._stats['by_component'].get(self.component, 0) + 1
            
            # Salva in memoria
            self._memory_logs.append(entry)
            
            # Scrivi su file
            if self._file_handler:
                self._file_handler.write(str(entry) + "\n")
                self._file_handler.flush()
            
            # Stampa su console
            if self.log_to_console:
                color = self._get_color(level)
                reset = "\033[0m"
                print(f"{color}{entry}{reset}")
    
    def _get_color(self, level: str) -> str:
        """Restituisce il codice colore ANSI per il livello."""
        colors = {
            'DEBUG': "\033[36m",      # Cyan
            'INFO': "\033[32m",       # Green
            'WARNING': "\033[33m",    # Yellow
            'ERROR': "\033[31m",      # Red
            'CRITICAL': "\033[35m"    # Magenta
        }
        return colors.get(level, "")
    
    def debug(self, message: str, **kwargs):
        """Log livello DEBUG."""
        self._log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log livello INFO."""
        self._log('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log livello WARNING."""
        self._log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log livello ERROR."""
        self._log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log livello CRITICAL."""
        self._log('CRITICAL', message, **kwargs)
    
    def state_transition(self, from_state: str, to_state: str, reason: str = ""):
        """Log specifico per transizioni di stato."""
        self.info(f"State Transition: {from_state} -> {to_state}",
                 from_state=from_state,
                 to_state=to_state,
                 reason=reason)
    
    def command_sent(self, command: str, context: dict = None):
        """Log specifico per comandi inviati."""
        data = {'command': command}
        if context:
            data.update(context)
        self.debug(f"Command Sent: {command}", **data)
    
    def sensor_reading(self, sensor_type: str, value: Any, **kwargs):
        """Log specifico per letture sensori."""
        self.debug(f"Sensor [{sensor_type}]: {value}",
                  sensor=sensor_type,
                  value=value,
                  **kwargs)
    
    def get_recent_logs(self, n: int = 50, level: Optional[str] = None) -> list:
        """Restituisce gli ultimi N log dalla memoria.
        
        Parameters
        ----------
        n : int
            Numero di log da restituire
        level : str, optional
            Filtra per livello specifico
            
        Returns
        -------
        list
            Lista di LogEntry
        """
        with self._lock:
            logs = list(self._memory_logs)
            
        if level:
            logs = [l for l in logs if l.level == level]
        
        return logs[-n:]
    
    def get_stats(self) -> dict:
        """Restituisce statistiche di logging."""
        with self._lock:
            return self._stats.copy()
    
    def export_to_json(self, filepath: str):
        """Esporta tutti i log in memoria su file JSON."""
        logs = self.get_recent_logs(MAX_MEMORY_LOGS)
        data = {
            'export_time': datetime.now().isoformat(),
            'stats': self.get_stats(),
            'logs': [log.to_dict() for log in logs]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
    
    def close(self):
        """Chiude il logger e i file aperti."""
        if self._file_handler:
            self._file_handler.close()
            self._file_handler = None


# Logger globale
main_logger = RobotLogger("MAIN")


def get_logger(component: str) -> RobotLogger:
    """Restituisce un logger per un componente specifico."""
    return RobotLogger(component, log_to_file=False, log_to_console=True)


# Decoratore per logging automatico delle funzioni
def logged(component: str = None, level: str = "DEBUG"):
    """Decoratore per logging automatico di funzioni.
    
    Usage:
        @logged("LINE_DETECTOR")
        def my_function():
            pass
    """
    def decorator(func):
        logger = get_logger(component or func.__module__)
        
        def wrapper(*args, **kwargs):
            logger_method = getattr(logger, level.lower())
            logger_method(f"Calling {func.__name__}", 
                         args_count=len(args), 
                         kwargs_keys=list(kwargs.keys()))
            try:
                result = func(*args, **kwargs)
                logger_method(f"Completed {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Exception in {func.__name__}: {e}",
                           exception=str(e))
                raise
        return wrapper
    return decorator
