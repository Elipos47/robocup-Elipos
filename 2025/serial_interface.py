# ===========================================================================
#  serial_interface.py – Comunicazione seriale con Arduino Mega
# ===========================================================================
#  Apre una connessione seriale a 115200 baud e invia comandi terminati
#  da '\n'.  Riceve dati: D: (distanza), G: (giroscopio), M: (movimento).
#  Gli errori di scrittura vengono ignorati per non bloccare
#  il ciclo principale.
# ===========================================================================

import time
import serial

from logger import get_logger

# ── Parametri configurabili ────────────────────────────────────────────────
SERIAL_PORTS = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]
BAUD_RATE    = 115200
BOOT_DELAY   = 2.0    # Secondi di attesa dopo l'apertura (reset Arduino)
# ───────────────────────────────────────────────────────────────────────────


class SerialInterface:
    """Interfaccia seriale verso Arduino Mega (non bloccante).
    
    Gestisce comunicazione bidirezionale:
    - Invio comandi motore (Pi → Arduino)
    - Ricezione dati sensori (Arduino → Pi):
      - D:<distanza>  → HC-SR04
      - G:<yaw>,<pitch>,<roll>,<sys>,<gyro>,<accel>,<mag>  → BNO085 orientamento
      - M:<lin_x>,<lin_y>,<lin_z>,<gyr_x>,<gyr_y>,<gyr_z>  → BNO085 movimento
    """

    def __init__(self, ports=SERIAL_PORTS, baud=BAUD_RATE):
        self._logger = get_logger("SERIAL")
        self._ser = None
        self._port_name = None
        self._last_distance = 999  # Ultima distanza letta valida

        # Dati giroscopio BNO085 (ricevuti da Arduino)
        self._gyro_yaw = 0.0
        self._gyro_pitch = 0.0
        self._gyro_roll = 0.0
        self._gyro_calibration = (0, 0, 0, 0)  # sys, gyro, accel, mag
        self._gyro_connected = False  # True quando riceviamo almeno un G:

        # Buffer per lettura non bloccante
        self._read_buffer = ""
        self._linear_accel = (0.0, 0.0, 0.0)  # x, y, z in m/s²
        self._angular_velocity = (0.0, 0.0, 0.0)  # x, y, z in rad/s

        # Prova ciascuna porta finché una si apre
        for port in ports:
            try:
                self._ser = serial.Serial(port, baud, timeout=0)  # timeout=0 -> non bloccante
                self._port_name = port
                # Attesa reset Arduino (il DTR causa un reboot del bootloader)
                time.sleep(BOOT_DELAY)
                self._logger.info(f"Seriale connessa su {port}")
                break
            except (serial.SerialException, OSError):
                continue

    # ── Stato connessione ─────────────────────────────────────────────────
    @property
    def is_connected(self):
        """True se la porta seriale è aperta e funzionante."""
        return self._ser is not None and self._ser.is_open

    @property
    def port_name(self):
        """Nome della porta aperta, oppure None."""
        return self._port_name

    # ── Dati giroscopio ───────────────────────────────────────────────────
    @property
    def gyro_connected(self):
        """True se il BNO085 è connesso (abbiamo ricevuto almeno un G:)."""
        return self._gyro_connected

    @property
    def gyro_yaw(self):
        """Yaw in gradi (0-360)."""
        return self._gyro_yaw

    @property
    def gyro_pitch(self):
        """Pitch in gradi."""
        return self._gyro_pitch

    @property
    def gyro_roll(self):
        """Roll in gradi."""
        return self._gyro_roll

    @property
    def gyro_calibration(self):
        """Stato calibrazione (sys, gyro, accel, mag). 3=calibrato."""
        return self._gyro_calibration

    @property
    def gyro_data(self):
        """Restituisce tuple (yaw, pitch, roll, calibration)."""
        return (self._gyro_yaw, self._gyro_pitch, self._gyro_roll, 
                self._gyro_calibration)

    @property
    def motion_data(self):
        """Restituisce tuple (linear_accel, angular_velocity)."""
        return (self._linear_accel, self._angular_velocity)

    # ── Invio comando ─────────────────────────────────────────────────────
    def send(self, command):
        """Invia il comando (stringa) seguito da '\\n'.

        Se la porta non è disponibile o si verifica un errore di
        scrittura, l'eccezione viene silenziata.
        """
        if not self.is_connected:
            return
        try:
            self._ser.write((command + "\n").encode())
        except (serial.SerialException, OSError):
            pass

    # ── Lettura dati da Arduino ────────────────────────────────────────────
    def read_all(self):
        """Legge tutte le linee disponibili dall'Arduino.
        
        Parsa automaticamente D: (distanza), G: (giroscopio), M: (movimento).
        
        Returns
        -------
        int
            Distanza in cm, o 999 se non disponibile.
        """
        if not self.is_connected:
            return 999

        try:
            # Leggi tutti i byte disponibili e aggiungili al buffer
            if self._ser.in_waiting > 0:
                raw_data = self._ser.read(self._ser.in_waiting).decode('utf-8', errors='ignore')
                self._read_buffer += raw_data
            
            # Estrai tutte le linee complete dal buffer
            while "\n" in self._read_buffer:
                line, self._read_buffer = self._read_buffer.split("\n", 1)
                line = line.strip()
                
                if not line:
                    continue

                if line.startswith("D:"):
                    self._parse_distance(line)
                elif line.startswith("G:"):
                    self._parse_gyro(line)
                elif line.startswith("M:"):
                    self._parse_motion(line)
                    
        except (serial.SerialException, OSError) as e:
            self._logger.error(f"Errore lettura seriale: {e}")

        return self._last_distance

    def read_distance(self):
        """Legge la distanza dall'Arduino (compatibilità con codice esistente).
        
        Chiama read_all() che parsa anche i dati giroscopio.
        
        Returns
        -------
        int
            Distanza in cm, o 999 se non disponibile.
        """
        return self.read_all()

    def _parse_distance(self, line):
        """Parsa una linea D:<distanza>."""
        try:
            dist = int(line[2:])
            if dist > 0:
                self._last_distance = dist
            else:
                self._last_distance = 999
        except ValueError:
            pass

    def _parse_gyro(self, line):
        """Parsa una linea G:<yaw>,<pitch>,<roll>,<sys>,<gyro>,<accel>,<mag>.
        
        Gestisce anche i messaggi speciali G:BNO085_OK e G:BNO085_FAIL.
        """
        data = line[2:]
        
        # Messaggi di stato inizializzazione (BNO085)
        if data == "BNO085_OK":
            self._gyro_connected = True
            self._logger.info(f"Giroscopio connesso su Arduino ({data})")
            return
        elif data == "BNO085_FAIL":
            self._gyro_connected = False
            self._logger.warning(f"Giroscopio NON trovato su Arduino ({data})")
            return
        elif data.startswith("REPORT_"):
            self._logger.warning(f"BNO085 report error: {data}")
            return
        
        try:
            parts = data.split(",")
            if len(parts) >= 7:
                self._gyro_yaw = float(parts[0])
                self._gyro_pitch = float(parts[1])
                self._gyro_roll = float(parts[2])
                self._gyro_calibration = (
                    int(parts[3]),  # sys
                    int(parts[4]),  # gyro
                    int(parts[5]),  # accel
                    int(parts[6])   # mag
                )
                self._gyro_connected = True
        except (ValueError, IndexError) as e:
            self._logger.debug(f"Errore parsing G: {e}")

    def _parse_motion(self, line):
        """Parsa una linea M:<lin_x>,<lin_y>,<lin_z>,<gyr_x>,<gyr_y>,<gyr_z>."""
        try:
            parts = line[2:].split(",")
            if len(parts) >= 6:
                self._linear_accel = (
                    float(parts[0]),
                    float(parts[1]),
                    float(parts[2])
                )
                self._angular_velocity = (
                    float(parts[3]),
                    float(parts[4]),
                    float(parts[5])
                )
        except (ValueError, IndexError) as e:
            self._logger.debug(f"Errore parsing M: {e}")

    # ── Chiusura ──────────────────────────────────────────────────────────
    def close(self):
        """Chiude la connessione seriale in modo sicuro."""
        if self.is_connected:
            try:
                self._ser.close()
            except (serial.SerialException, OSError):
                pass
