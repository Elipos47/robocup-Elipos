// ==========================================================================
//  robo_arduino.ino – Sketch Arduino Mega per RoboCup Line
// ==========================================================================
//  Riceve comandi via seriale dal Raspberry Pi (terminati da '\n') e
//  controlla i motori tramite ponte H.
//
//  DESIGN: Il Pi invia comandi continuamente (~60 Hz). Arduino li esegue
//  immediatamente e tiene i motori accesi finché arrivano comandi.
//  Se la seriale tace per SERIAL_TIMEOUT_MS → safety stop.
//
//  SENSORI:
//    HC-SR04: sensore distanza (pin 30/31)
//    BNO085:  IMU 9-DOF via I2C (SDA=20, SCL=21, indirizzo 0x4A)
//
//  PROTOCOLLO SERIALE (Arduino → Pi):
//    "D:<distanza>\n"                                     → HC-SR04
//    "G:<yaw>,<pitch>,<roll>,<accuracy>\n"                → BNO085 orientamento
//    "M:<lin_x>,<lin_y>,<lin_z>,<gyr_x>,<gyr_y>,<gyr_z>\n" → BNO085 movimento
//
// COMANDI SUPPORTATI (Pi → Arduino):
// "A" → Avanti
// "S" → Stop (immediato)
// "gd" → Correzione a destra (pivot: SX avanti, DX indietro)
// "gs" → Correzione a sinistra (pivot: DX avanti, SX indietro)
// "cd" → Curva 90° a destra
// "cs" → Curva 90° a sinistra
// "iu" → Inversione a U
// "obj" → Schiva ostacolo (sequenza autonoma Arduino)
// "ind" → Marcia indietro
// ==========================================================================

#include <Adafruit_BNO08x.h>
#include <Wire.h>

// ── Pin motore sinistro ──────────────────────────────────────────────────
// NOTA: EN deve essere su un pin PWM! Su Arduino Mega i pin PWM sono:
//       2-13, 44-46. I pin 22-27 sono solo digitali e analogWrite()
//       li tratta come LOW (<128) o HIGH (>=128), senza gradazione.
const int MOTOR_LEFT_EN = 44;   // PWM pin (era 22 — non PWM!)
const int MOTOR_LEFT_IN1 = 23;
const int MOTOR_LEFT_IN2 = 24;

// ── Pin motore destro ────────────────────────────────────────────────────
const int MOTOR_RIGHT_EN = 45;  // PWM pin (era 27 — non PWM!)
const int MOTOR_RIGHT_IN1 = 25;
const int MOTOR_RIGHT_IN2 = 26;

// ── Pin sensore distanza HC-SR04 ─────────────────────────────────────────
const int HC_TRIG = 30;
const int HC_ECHO = 31;
const unsigned long DISTANCE_INTERVAL_MS = 100; // Era 50 — ridotto a 10Hz per non bloccare il loop

// ── Velocità PWM (0-255) ────────────────────────────────────────────────
const int SPEED_FORWARD = 120;
const int SPEED_GENTLE = 160;
const int SPEED_TURN = 180;
const int SPEED_TURN_45 = 180;
const int SPEED_UTURN = 160;
const int SPEED_BACKWARD = 180;

// ── Watchdog seriale ─────────────────────────────────────────────────────
// Se nessun comando arriva entro questo tempo → safety stop.
// Il Pi manda comandi a ~60Hz (~17ms), quindi 300ms = ~18 comandi mancati.
const unsigned long SERIAL_TIMEOUT_MS = 300;

// ── Baudrate ─────────────────────────────────────────────────────────────
const long BAUD_RATE = 115200;

// ── BNO085 ───────────────────────────────────────────────────────────────
const unsigned long GYRO_INTERVAL_MS = 50; // 20 Hz
Adafruit_BNO08x bno085;
bool bnoConnected = false;
unsigned long lastGyroTime = 0;

// Report IDs per il BNO085
sh2_SensorValue_t sensorValue;

// ── Variabili globali ────────────────────────────────────────────────────
String inputBuffer = "";
unsigned long lastCommandTime = 0;

// Stato corrente motori: memorizza l'ultimo comando per non re-applicare
// lo stesso identico stato dei motori ad ogni frame.
String lastCommand = "";

// ── Sequenza schiva-ostacolo ─────────────────────────────────────────────
enum ObstacleState {
  OBJ_IDLE,
  OBJ_STEP1_TURN_RIGHT,
  OBJ_STEP2_FORWARD,
  OBJ_STEP3_TURN_LEFT_1,
  OBJ_STEP4_FORWARD,
  OBJ_STEP5_TURN_LEFT_2,
  OBJ_STEP6_FORWARD,
  OBJ_STEP7_TURN_RIGHT
};
ObstacleState obstacleState = OBJ_IDLE;
bool obstacleSequenceActive = false;
unsigned long obstacleStepStart = 0;
unsigned long obstacleStepDuration = 0;

// ── Sensore distanza ─────────────────────────────────────────────────────
unsigned long lastDistanceTime = 0;
int currentDistance = 999;

// =========================================================================
//  Attivazione report BNO085
// =========================================================================
void setReports() {
  // Rotation Vector (quaternioni → convertiti in Euler nel codice)
  if (!bno085.enableReport(SH2_ROTATION_VECTOR, 50000)) { // 50ms = 20Hz
    Serial.println("G:REPORT_RV_FAIL");
  }
  // Accelerazione lineare (senza gravità)
  if (!bno085.enableReport(SH2_LINEAR_ACCELERATION, 50000)) {
    Serial.println("G:REPORT_LA_FAIL");
  }
  // Giroscopio calibrato
  if (!bno085.enableReport(SH2_GYROSCOPE_CALIBRATED, 50000)) {
    Serial.println("G:REPORT_GY_FAIL");
  }
}

// =========================================================================
//  SETUP
// =========================================================================
void setup() {
  Serial.begin(BAUD_RATE);

  // Motori
  pinMode(MOTOR_LEFT_EN, OUTPUT);
  pinMode(MOTOR_LEFT_IN1, OUTPUT);
  pinMode(MOTOR_LEFT_IN2, OUTPUT);
  pinMode(MOTOR_RIGHT_EN, OUTPUT);
  pinMode(MOTOR_RIGHT_IN1, OUTPUT);
  pinMode(MOTOR_RIGHT_IN2, OUTPUT);

  // Sensore HC-SR04
  pinMode(HC_TRIG, OUTPUT);
  pinMode(HC_ECHO, INPUT);

  stopMotors();

  // Inizializza BNO085 via I2C (indirizzo default 0x4A)
  if (bno085.begin_I2C(0x4A)) {
    bnoConnected = true;
    setReports();
    Serial.println("G:BNO085_OK");
  } else {
    bnoConnected = false;
    Serial.println("G:BNO085_FAIL");
  }

  lastCommandTime = millis();
}

// =========================================================================
//  LOOP
// =========================================================================
void loop() {
  // ── 1. Lettura seriale (PRIORITÀ MASSIMA) ────────────────────────────
  // Legge TUTTI i byte disponibili e processa ogni comando completo.
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processCommand(inputBuffer);
        lastCommandTime = millis();
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }

  // ── 2. Gestione sequenza schiva-ostacoli ──────────────────────────────
  if (obstacleSequenceActive) {
    processObstacleSequence();
  }

  // ── 3. Watchdog: safety stop se Pi non comunica ───────────────────────
  // NOTA: Non ferma durante sequenza ostacolo (è autonoma).
  if (!obstacleSequenceActive &&
      (millis() - lastCommandTime > SERIAL_TIMEOUT_MS)) {
    stopMotors();
    lastCommand = "";
  }

  // ── 4. Lettura distanza HC-SR04 (NON BLOCCANTE) ──────────────────────
  if (millis() - lastDistanceTime >= DISTANCE_INTERVAL_MS) {
    currentDistance = readDistanceNonBlocking();
    Serial.print("D:");
    Serial.println(currentDistance);
    lastDistanceTime = millis();
  }

  // ── 5. Lettura BNO085 ────────────────────────────────────────────────
  if (bnoConnected && (millis() - lastGyroTime >= GYRO_INTERVAL_MS)) {
    readAndSendBNO085();
    lastGyroTime = millis();
  }
}

// =========================================================================
//  LETTURA E INVIO DATI BNO085
// =========================================================================

// Variabili per accumulare i dati dai diversi report
float g_yaw = 0, g_pitch = 0, g_roll = 0;
float g_accuracy = 0;
float g_linX = 0, g_linY = 0, g_linZ = 0;
float g_gyrX = 0, g_gyrY = 0, g_gyrZ = 0;
bool hasRotation = false, hasLinAccel = false, hasGyro = false;

void readAndSendBNO085() {
  hasRotation = false;
  hasLinAccel = false;
  hasGyro = false;

  // Leggi tutti i report disponibili (non bloccante)
  while (bno085.getSensorEvent(&sensorValue)) {
    switch (sensorValue.sensorId) {
    case SH2_ROTATION_VECTOR: {
      // Converti quaternione in angoli di Eulero
      float qi = sensorValue.un.rotationVector.i;
      float qj = sensorValue.un.rotationVector.j;
      float qk = sensorValue.un.rotationVector.k;
      float qr = sensorValue.un.rotationVector.real;
      g_accuracy = sensorValue.un.rotationVector.accuracy;

      // Quaternione → Euler (in gradi)
      float siny_cosp = 2.0 * (qr * qk + qi * qj);
      float cosy_cosp = 1.0 - 2.0 * (qj * qj + qk * qk);
      g_yaw = atan2(siny_cosp, cosy_cosp) * 57.2958;

      float sinp = 2.0 * (qr * qj - qk * qi);
      if (abs(sinp) >= 1)
        g_pitch = copysign(90.0, sinp);
      else
        g_pitch = asin(sinp) * 57.2958;

      float sinr_cosp = 2.0 * (qr * qi + qj * qk);
      float cosr_cosp = 1.0 - 2.0 * (qi * qi + qj * qj);
      g_roll = atan2(sinr_cosp, cosr_cosp) * 57.2958;

      if (g_yaw < 0)
        g_yaw += 360.0;

      hasRotation = true;
      break;
    }

    case SH2_LINEAR_ACCELERATION:
      g_linX = sensorValue.un.linearAcceleration.x;
      g_linY = sensorValue.un.linearAcceleration.y;
      g_linZ = sensorValue.un.linearAcceleration.z;
      hasLinAccel = true;
      break;

    case SH2_GYROSCOPE_CALIBRATED:
      g_gyrX = sensorValue.un.gyroscope.x;
      g_gyrY = sensorValue.un.gyroscope.y;
      g_gyrZ = sensorValue.un.gyroscope.z;
      hasGyro = true;
      break;
    }
  }

  // Invia dati orientamento se disponibili
  if (hasRotation) {
    int acc_level = 0;
    if (g_accuracy < 0.1)
      acc_level = 3;
    else if (g_accuracy < 0.3)
      acc_level = 2;
    else if (g_accuracy < 0.6)
      acc_level = 1;

    Serial.print("G:");
    Serial.print(g_yaw, 1);
    Serial.print(",");
    Serial.print(g_pitch, 1);
    Serial.print(",");
    Serial.print(g_roll, 1);
    Serial.print(",");
    Serial.print(acc_level);
    Serial.print(",");
    Serial.print(acc_level);
    Serial.print(",");
    Serial.print(acc_level);
    Serial.print(",");
    Serial.println(acc_level);
  }

  // Invia dati di movimento se disponibili
  if (hasLinAccel || hasGyro) {
    Serial.print("M:");
    Serial.print(g_linX, 2);
    Serial.print(",");
    Serial.print(g_linY, 2);
    Serial.print(",");
    Serial.print(g_linZ, 2);
    Serial.print(",");
    Serial.print(g_gyrX, 2);
    Serial.print(",");
    Serial.print(g_gyrY, 2);
    Serial.print(",");
    Serial.println(g_gyrZ, 2);
  }
}

// =========================================================================
//  LETTURA DISTANZA HC-SR04 (CON TIMEOUT RIDOTTO)
// =========================================================================
// NOTA: pulseIn() è bloccante. Con timeout=30000µs poteva bloccare
// il loop per fino a 30ms, durante i quali i comandi seriali si accumulavano
// nel buffer RX (64 byte) e potevano essere persi.
// Ridotto a 10000µs (≈170cm max) che è più che sufficiente per 15cm threshold.
int readDistanceNonBlocking() {
  digitalWrite(HC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(HC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(HC_TRIG, LOW);

  // Timeout 10ms → max ~170cm (sufficiente per soglia 15cm)
  long duration = pulseIn(HC_ECHO, HIGH, 10000);
  if (duration == 0) {
    return 999; // Nessun eco → nessun ostacolo
  }

  int distance = duration / 29 / 2;
  if (distance < 1 || distance > 400) {
    return 999;
  }
  return distance;
}

// =========================================================================
//  PARSING COMANDI
// =========================================================================
// DESIGN CRITICO: I comandi "continui" (A, gd, gs, ind) impostano i motori
// e li LASCIANO ACCESI. Il Pi re-invia il comando ogni ~17ms (60Hz).
// Solo il watchdog (300ms senza comandi) o "S" fermano i motori.
//
// I comandi "a durata fissa" (cd, cs, iu) hanno una durata intrinseca
// perché il Pi non sa quando fermarli (turn 90° ecc.).
void processCommand(const String &cmd) {
  // Se c'è una sequenza ostacolo attiva, qualsiasi comando diverso da "obj" la interrompe
  if (obstacleSequenceActive && cmd != "obj") {
    obstacleSequenceActive = false;
    obstacleState = OBJ_IDLE;
    stopMotors();
    lastCommand = "";
  }

  // ── Comandi "continui" ──────────────────────────────────────────────
  // Il Pi li ripete ogni frame. Arduino tiene i motori accesi.
  // Se il Pi smette di inviare → watchdog ferma tutto.

  if (cmd == "A") {
    // Ottimizzazione: non re-settare i motori se già in forward
    if (lastCommand != "A") {
      setMotors(SPEED_FORWARD, true, SPEED_FORWARD, true);
      lastCommand = "A";
    }
  } else if (cmd == "S") {
    stopMotors();
    lastCommand = "S";
    obstacleSequenceActive = false;
    obstacleState = OBJ_IDLE;
  } else if (cmd == "gd") {
    if (lastCommand != "gd") {
      setMotors(SPEED_GENTLE, true, SPEED_GENTLE, false);
      lastCommand = "gd";
    }
  } else if (cmd == "gs") {
    if (lastCommand != "gs") {
      setMotors(SPEED_GENTLE, false, SPEED_GENTLE, true);
      lastCommand = "gs";
    }
  } else if (cmd == "ind") {
    if (lastCommand != "ind") {
      setMotors(SPEED_BACKWARD, false, SPEED_BACKWARD, false);
      lastCommand = "ind";
    }

  // ── Comandi "a durata fissa" ────────────────────────────────────────
  // Questi hanno una durata intrinseca gestita dalla sequenza ostacolo
  // o dal Pi che invierà "S" quando è ora di fermarsi.
  } else if (cmd == "cd") {
    setMotors(SPEED_TURN, true, SPEED_TURN, false);
    lastCommand = "cd";
  } else if (cmd == "cs") {
    setMotors(SPEED_TURN, false, SPEED_TURN, true);
    lastCommand = "cs";
  } else if (cmd == "iu") {
    setMotors(SPEED_UTURN, true, SPEED_UTURN, false);
    lastCommand = "iu";
  } else if (cmd == "obj") {
    startObstacleSequence();
    lastCommand = "obj";
  }
}

// =========================================================================
//  SEQUENZA SCHIVA-OSTACOLO
// =========================================================================
// La sequenza ostacolo è autonoma: Arduino gestisce il timing internamente.
// Il Pi continua a mandare "obj" per segnalare che l'ostacolo è ancora lì.

// Durate dei singoli step della sequenza (ms)
const unsigned long OBJ_TURN_DURATION = 300;
const unsigned long OBJ_FORWARD_DURATION = 1000;

void startObstacleSequence() {
  if (obstacleSequenceActive) return; // Già in corso
  obstacleSequenceActive = true;
  obstacleState = OBJ_STEP1_TURN_RIGHT;
  setMotors(SPEED_TURN_45, true, SPEED_TURN_45, false);
  obstacleStepStart = millis();
  obstacleStepDuration = OBJ_TURN_DURATION;
}

void processObstacleSequence() {
  // Lo step corrente non è ancora finito
  if (millis() - obstacleStepStart < obstacleStepDuration) {
    return;
  }

  // Step completato, passa al prossimo
  switch (obstacleState) {
  case OBJ_STEP1_TURN_RIGHT:
    obstacleState = OBJ_STEP2_FORWARD;
    setMotors(SPEED_FORWARD, true, SPEED_FORWARD, true);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_FORWARD_DURATION;
    break;
  case OBJ_STEP2_FORWARD:
    obstacleState = OBJ_STEP3_TURN_LEFT_1;
    setMotors(SPEED_TURN_45, false, SPEED_TURN_45, true);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_TURN_DURATION;
    break;
  case OBJ_STEP3_TURN_LEFT_1:
    obstacleState = OBJ_STEP4_FORWARD;
    setMotors(SPEED_FORWARD, true, SPEED_FORWARD, true);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_FORWARD_DURATION;
    break;
  case OBJ_STEP4_FORWARD:
    obstacleState = OBJ_STEP5_TURN_LEFT_2;
    setMotors(SPEED_TURN_45, false, SPEED_TURN_45, true);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_TURN_DURATION;
    break;
  case OBJ_STEP5_TURN_LEFT_2:
    obstacleState = OBJ_STEP6_FORWARD;
    setMotors(SPEED_FORWARD, true, SPEED_FORWARD, true);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_FORWARD_DURATION;
    break;
  case OBJ_STEP6_FORWARD:
    obstacleState = OBJ_STEP7_TURN_RIGHT;
    setMotors(SPEED_TURN_45, true, SPEED_TURN_45, false);
    obstacleStepStart = millis();
    obstacleStepDuration = OBJ_TURN_DURATION;
    break;
  case OBJ_STEP7_TURN_RIGHT:
    obstacleState = OBJ_IDLE;
    obstacleSequenceActive = false;
    stopMotors();
    lastCommand = "";
    break;
  default:
    obstacleState = OBJ_IDLE;
    obstacleSequenceActive = false;
    stopMotors();
    lastCommand = "";
    break;
  }
}

// =========================================================================
//  FUNZIONI MOTORE
// =========================================================================
void setMotors(int leftSpeed, bool leftForward, int rightSpeed,
               bool rightForward) {
  if (leftSpeed == 0) {
    analogWrite(MOTOR_LEFT_EN, 0);
    digitalWrite(MOTOR_LEFT_IN1, LOW);
    digitalWrite(MOTOR_LEFT_IN2, LOW);
  } else {
    digitalWrite(MOTOR_LEFT_IN1, leftForward ? HIGH : LOW);
    digitalWrite(MOTOR_LEFT_IN2, leftForward ? LOW : HIGH);
    analogWrite(MOTOR_LEFT_EN, leftSpeed);
  }

  if (rightSpeed == 0) {
    analogWrite(MOTOR_RIGHT_EN, 0);
    digitalWrite(MOTOR_RIGHT_IN1, LOW);
    digitalWrite(MOTOR_RIGHT_IN2, LOW);
  } else {
    digitalWrite(MOTOR_RIGHT_IN1, rightForward ? HIGH : LOW);
    digitalWrite(MOTOR_RIGHT_IN2, rightForward ? LOW : HIGH);
    analogWrite(MOTOR_RIGHT_EN, rightSpeed);
  }
}

void stopMotors() {
  analogWrite(MOTOR_LEFT_EN, 0);
  analogWrite(MOTOR_RIGHT_EN, 0);
  digitalWrite(MOTOR_LEFT_IN1, LOW);
  digitalWrite(MOTOR_LEFT_IN2, LOW);
  digitalWrite(MOTOR_RIGHT_IN1, LOW);
  digitalWrite(MOTOR_RIGHT_IN2, LOW);
}
