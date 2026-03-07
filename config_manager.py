# ===========================================================================
# config_manager.py – Gestione configurazione da file INI
# ===========================================================================
# Permette di salvare e caricare parametri configurabili come:
# - Soglie HSV per colori
# - Parametri morfologia
# - Soglie rilevamento
# ===========================================================================

import configparser
import json
import os
from pathlib import Path


class ConfigManager:
    """Gestisce la lettura e scrittura di parametri su file config.ini."""

    def __init__(self, config_file="config.ini"):
        """
        Parameters
        ----------
        config_file : str
            Percorso del file di configurazione
        """
        self._config_file = config_file
        self._config = configparser.ConfigParser()
        
        # Crea file se non esiste
        if not os.path.exists(config_file):
            self._create_default_config()
        else:
            self._config.read(config_file)

    def _create_default_config(self):
        """Crea configurazione di default."""
        # Sezione colori
        self._config['color_values'] = {
            'green_hsv_low': json.dumps([40, 50, 45]),
            'green_hsv_high': json.dumps([85, 255, 255]),
            'red_hsv_low_1': json.dumps([0, 100, 90]),
            'red_hsv_high_1': json.dumps([10, 255, 255]),
            'red_hsv_low_2': json.dumps([170, 100, 100]),
            'red_hsv_high_2': json.dumps([180, 255, 255]),
            'black_threshold_top': '65',
            'black_threshold_bottom': '95',
            'black_min_area': '500'
        }
        
        # Sezione linea
        self._config['line_params'] = {
            'roi_height_start': '0.30',
            'roi_height_end': '0.70',
            'line_crop_factor': '0.48',
            'min_line_width': '20',
            'max_line_width_ratio': '0.25'
        }
        
        # Sezione morfologia
        self._config['morphology'] = {
            'kernel_size': '3',
            'erode_iterations_line': '3',
            'dilate_iterations_line': '13',
            'erode_iterations_line_2': '7',
            'erode_iterations_gap': '3',
            'dilate_iterations_gap': '8',
            'erode_iterations_gap_2': '0'
        }
        
        # Sezione rilevamento
        self._config['detection'] = {
            'green_min_area': '2500',
            'red_min_area': '1500',
            'aspect_ratio_tol': '0.3',
            'line_loss_threshold': '5',
            'gap_min_area': '1000',
            'shadow_v_min': '100'
        }
        
        # Sezione controllo
        self._config['control'] = {
            'deadband_center': '0.15',
            'hysteresis_margin': '0.20',
            'angle_threshold': '25',
            'angle_deadband': '8',
            'green_lock_duration': '45',
            'curve_persist_frames': '5',
            'curve_entry_delay': '2',
            'curve_forward_ratio': '4'
        }
        
        # Salva
        self._save_config()

    def _save_config(self):
        """Salva la configurazione su file."""
        with open(self._config_file, 'w') as f:
            self._config.write(f)

    def write_variable(self, section, variable, value):
        """Scrive una variabile nel file di configurazione.
        
        Parameters
        ----------
        section : str
            Nome della sezione
        variable : str
            Nome della variabile
        value : any
            Valore da salvare (liste verranno convertite in JSON)
        """
        if not self._config.has_section(section):
            self._config.add_section(section)
        
        # Converte liste in JSON
        if isinstance(value, (list, tuple)):
            value = json.dumps(value)
        else:
            value = str(value)
        
        self._config.set(section, variable, value)
        self._save_config()

    def read_variable(self, section, variable, default=None):
        """Legge una variabile dal file di configurazione.
        
        Parameters
        ----------
        section : str
            Nome della sezione
        variable : str
            Nome della variabile
        default : any
            Valore di default se la variabile non esiste
            
        Returns
        -------
        any
            Il valore letto (liste come numpy array, numeri come int/float)
        """
        if not self._config.has_option(section, variable):
            return default
        
        value = self._config.get(section, variable)
        
        # Tenta di parsare come JSON (per liste)
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                import numpy as np
                return np.array(parsed, dtype=np.uint8 if all(isinstance(x, int) for x in parsed) else np.float32)
            return parsed
        except json.JSONDecodeError:
            pass
        
        # Prova a convertire in numero
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Ritorna come stringa
        return value

    def get_section(self, section):
        """Restituisce tutta una sezione come dizionario.
        
        Parameters
        ----------
        section : str
            Nome della sezione
            
        Returns
        -------
        dict
            Dizionario con tutte le variabili della sezione
        """
        if not self._config.has_section(section):
            return {}
        
        result = {}
        for key, value in self._config.items(section):
            result[key] = self.read_variable(section, key)
        return result

    def reset_to_defaults(self):
        """Ripristina la configurazione ai valori di default."""
        self._config.clear()
        self._create_default_config()


# Istanza singleton per uso globale
config_manager = ConfigManager()


# Funzioni di convenienza
def save_color_calibration(green_low, green_high, red_low_1, red_high_1, 
                            red_low_2, red_high_2):
    """Salva i valori HSV calibrati."""
    config_manager.write_variable('color_values', 'green_hsv_low', green_low.tolist())
    config_manager.write_variable('color_values', 'green_hsv_high', green_high.tolist())
    config_manager.write_variable('color_values', 'red_hsv_low_1', red_low_1.tolist())
    config_manager.write_variable('color_values', 'red_hsv_high_1', red_high_1.tolist())
    config_manager.write_variable('color_values', 'red_hsv_low_2', red_low_2.tolist())
    config_manager.write_variable('color_values', 'red_hsv_high_2', red_high_2.tolist())


def load_color_calibration():
    """Carica i valori HSV calibrati."""
    import numpy as np
    return {
        'green_low': config_manager.read_variable('color_values', 'green_hsv_low'),
        'green_high': config_manager.read_variable('color_values', 'green_hsv_high'),
        'red_low_1': config_manager.read_variable('color_values', 'red_hsv_low_1'),
        'red_high_1': config_manager.read_variable('color_values', 'red_hsv_high_1'),
        'red_low_2': config_manager.read_variable('color_values', 'red_hsv_low_2'),
        'red_high_2': config_manager.read_variable('color_values', 'red_hsv_high_2')
    }
