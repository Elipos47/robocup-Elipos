// ==========================================================================
//  go_straight.ino – Test: robot va dritto
// ==========================================================================
//  Sketch minimale che accende entrambi i motori in avanti alla stessa
//  velocità, senza bisogno del Raspberry Pi.
//
//  Pin e velocità presi da robo_arduino.ino (ponte H L298N).
//
//  COMPORTAMENTO:
//    - Accende i motori avanti a SPEED_FORWARD per DRIVE_DURATION_MS
//    - Si ferma
//    - Ripete dopo PAUSE_DURATION_MS
//
//  Per fermare: togliere alimentazione o caricare un altro sketch.
// ==========================================================================

// ── Pin motore sinistro (L298N) ──────────────────────────────────────────
const int MOTOR_LEFT_EN  = 44;  // PWM
const int MOTOR_LEFT_IN1 = 23;
const int MOTOR_LEFT_IN2 = 24;

// ── Pin motore destro (L298N) ────────────────────────────────────────────
const int MOTOR_RIGHT_EN  = 45; // PWM
const int MOTOR_RIGHT_IN1 = 25;
const int MOTOR_RIGHT_IN2 = 26;

// ── Parametri regolabili ─────────────────────────────────────────────────
const int  SPEED_FORWARD      = 200;   // PWM 0-255 (stessa velocità di robo_arduino)
const unsigned long DRIVE_DURATION_MS = 5000;  // Quanto tempo va dritto (ms)
const unsigned long PAUSE_DURATION_MS = 2000;  // Pausa tra una corsa e l'altra (ms)

// ==========================================================================
void setup() {
  Serial.begin(115200);

  // Configura pin motori come output
  pinMode(MOTOR_LEFT_EN,   OUTPUT);
  pinMode(MOTOR_LEFT_IN1,  OUTPUT);
  pinMode(MOTOR_LEFT_IN2,  OUTPUT);
  pinMode(MOTOR_RIGHT_EN,  OUTPUT);
  pinMode(MOTOR_RIGHT_IN1, OUTPUT);
  pinMode(MOTOR_RIGHT_IN2, OUTPUT);

  // Assicurati che i motori siano fermi all'avvio
  stopMotors();

  Serial.println("== go_straight test ==");
  Serial.println("Attendo 2 secondi prima di partire...");
  delay(2000);
}

// ==========================================================================
void loop() {
  Serial.println("AVANTI");
  goForward(SPEED_FORWARD);

  delay(DRIVE_DURATION_MS);

  Serial.println("STOP");
  stopMotors();

  delay(PAUSE_DURATION_MS);
}

// ==========================================================================
//  Entrambi i motori avanti alla stessa velocità
// ==========================================================================
void goForward(int speed) {
  // Motore sinistro: IN1=HIGH, IN2=LOW → avanti
  digitalWrite(MOTOR_LEFT_IN1, HIGH);
  digitalWrite(MOTOR_LEFT_IN2, LOW);
  analogWrite(MOTOR_LEFT_EN, speed);

  // Motore destro: IN1=HIGH, IN2=LOW → avanti
  digitalWrite(MOTOR_RIGHT_IN1, HIGH);
  digitalWrite(MOTOR_RIGHT_IN2, LOW);
  analogWrite(MOTOR_RIGHT_EN, speed);
}

// ==========================================================================
//  Ferma entrambi i motori
// ==========================================================================
void stopMotors() {
  analogWrite(MOTOR_LEFT_EN, 0);
  analogWrite(MOTOR_RIGHT_EN, 0);
  digitalWrite(MOTOR_LEFT_IN1, LOW);
  digitalWrite(MOTOR_LEFT_IN2, LOW);
  digitalWrite(MOTOR_RIGHT_IN1, LOW);
  digitalWrite(MOTOR_RIGHT_IN2, LOW);
}
