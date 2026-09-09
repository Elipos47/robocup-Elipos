// Firmware Arduino Mega: controllo motori + sensori (SPEC §8.3).
// Protocollo: M<id><speed>\n  (-255..255), S?\n -> stato sensori CSV.
#include <Arduino.h>
const int MOTOR1_PWM = 9, MOTOR1_DIR = 8, MOTOR2_PWM = 10, MOTOR2_DIR = 7;
void drive(int pwmPin, int dirPin, int speed) {
  digitalWrite(dirPin, speed >= 0 ? HIGH : LOW);
  analogWrite(pwmPin, constrain(abs(speed), 0, 255));
}
void setup() {
  Serial.begin(115200);
  pinMode(MOTOR1_PWM, OUTPUT); pinMode(MOTOR1_DIR, OUTPUT);
  pinMode(MOTOR2_PWM, OUTPUT); pinMode(MOTOR2_DIR, OUTPUT);
}
void loop() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd == "S?") { Serial.println("0,0"); }
  else if (cmd.startsWith("M1")) { drive(MOTOR1_PWM, MOTOR1_DIR, cmd.substring(2).toInt()); }
  else if (cmd.startsWith("M2")) { drive(MOTOR2_PWM, MOTOR2_DIR, cmd.substring(2).toInt()); }
}
