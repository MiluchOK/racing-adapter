/*
 * Circuitry Diagnostics — Automated hardware test
 *
 * Runs a suite of tests and reports results over serial in a
 * machine-readable format so the CLI can parse and display them.
 *
 * Protocol:  DIAG:START / TEST:<name>:<PASS|FAIL|WARN|INFO>:<detail> / DIAG:END
 *
 * Tests:
 *   1. Pin readback   — verify each control pin can drive HIGH/LOW
 *   2. Analog baseline — check for unexpected voltages on analog pins
 *   3. LED matrix      — display test pattern
 *   4. Servo sweep     — sweep servo on pin 9 through 0°→180°→90°
 *   5. Motor ramp      — ramp PWM on pin 6 with direction on pin 5
 *
 * After running, use `racing-adapter firmware_upload` to restore normal firmware.
 */

#include <Servo.h>
#include "Arduino_LED_Matrix.h"

const int PIN_MOTOR_DIR = 5;
const int PIN_MOTOR_PWM = 6;
const int PIN_SERVO     = 9;

Servo testServo;
ArduinoLEDMatrix matrix;

// ── Helpers ──────────────────────────────────────────────────────────

void report(const char* test, const char* status, const char* detail) {
  Serial.print("TEST:");
  Serial.print(test);
  Serial.print(":");
  Serial.print(status);
  Serial.print(":");
  Serial.println(detail);
}

// ── Test 1: Pin readback ─────────────────────────────────────────────
// Drive a pin HIGH then LOW and read back the actual pin level.
// On Renesas RA4M1 (UNO R4), digitalRead on an OUTPUT pin reads the
// physical pin state, so a short to GND/VCC will show up.

void testPinReadback(int pin, const char* name) {
  char buf[80];

  pinMode(pin, OUTPUT);

  // Drive HIGH, read back
  digitalWrite(pin, HIGH);
  delay(10);
  int readHigh = digitalRead(pin);

  // Drive LOW, read back
  digitalWrite(pin, LOW);
  delay(10);
  int readLow = digitalRead(pin);

  if (readHigh == HIGH && readLow == LOW) {
    snprintf(buf, sizeof(buf), "Pin %d toggles OK", pin);
    report(name, "PASS", buf);
  } else if (readHigh == LOW && readLow == LOW) {
    snprintf(buf, sizeof(buf), "Pin %d stuck LOW — possible short to GND", pin);
    report(name, "FAIL", buf);
  } else if (readHigh == HIGH && readLow == HIGH) {
    snprintf(buf, sizeof(buf), "Pin %d stuck HIGH — possible short to VCC", pin);
    report(name, "FAIL", buf);
  } else {
    snprintf(buf, sizeof(buf), "Pin %d unexpected (HIGH→%d, LOW→%d)", pin, readHigh, readLow);
    report(name, "FAIL", buf);
  }

  digitalWrite(pin, LOW);
}

// ── Test 2: Analog baseline ─────────────────────────────────────────
// Read all six analog inputs. A properly disconnected pin reads near 0
// or floats unpredictably. A pin shorted to VCC reads near 1023.

void testAnalogBaseline() {
  char buf[80];
  char vStr[8];

  for (int i = 0; i <= 5; i++) {
    int raw = analogRead(i);
    float voltage = raw * (5.0 / 1023.0);
    dtostrf(voltage, 4, 2, vStr);

    if (raw > 950) {
      snprintf(buf, sizeof(buf), "A%d = %d (%sV) — near VCC, possible short to 5V", i, raw, vStr);
      report("analog_baseline", "WARN", buf);
    } else if (raw > 100) {
      snprintf(buf, sizeof(buf), "A%d = %d (%sV) — unexpected mid-range voltage", i, raw, vStr);
      report("analog_baseline", "WARN", buf);
    } else {
      snprintf(buf, sizeof(buf), "A%d = %d (%sV)", i, raw, vStr);
      report("analog_baseline", "INFO", buf);
    }
  }
}

// ── Test 3: LED matrix ──────────────────────────────────────────────

void testLedMatrix() {
  uint8_t frame[8][12];

  // All on
  memset(frame, 1, sizeof(frame));
  matrix.renderBitmap(frame, 8, 12);
  delay(600);

  // All off
  memset(frame, 0, sizeof(frame));
  matrix.renderBitmap(frame, 8, 12);
  delay(400);

  // Checkerboard
  for (int r = 0; r < 8; r++)
    for (int c = 0; c < 12; c++)
      frame[r][c] = (r + c) % 2;
  matrix.renderBitmap(frame, 8, 12);

  report("led_matrix", "PASS", "Pattern displayed — verify visually");
}

// ── Test 4: Servo sweep ─────────────────────────────────────────────

void testServoSweep() {
  char buf[80];

  testServo.attach(PIN_SERVO);
  delay(200);

  int positions[] = {0, 45, 90, 135, 180, 90};
  int numPos = 6;

  for (int i = 0; i < numPos; i++) {
    testServo.write(positions[i]);
    delay(500);
    snprintf(buf, sizeof(buf), "Commanded %d deg", positions[i]);
    report("servo_sweep", "INFO", buf);
  }

  testServo.detach();
  report("servo_sweep", "PASS", "Sweep complete — verify servo moved physically");
}

// ── Test 5: Motor ramp ──────────────────────────────────────────────

void testMotorRamp() {
  char buf[80];

  pinMode(PIN_MOTOR_DIR, OUTPUT);
  pinMode(PIN_MOTOR_PWM, OUTPUT);

  digitalWrite(PIN_MOTOR_DIR, HIGH);
  report("motor_ramp", "INFO", "Direction FORWARD (pin 5 HIGH)");

  int steps[] = {0, 64, 128, 192, 255, 0};
  int numSteps = 6;

  for (int i = 0; i < numSteps; i++) {
    analogWrite(PIN_MOTOR_PWM, steps[i]);
    int pct = (steps[i] * 100) / 255;
    snprintf(buf, sizeof(buf), "PWM %d (%d%%)", steps[i], pct);
    report("motor_ramp", "INFO", buf);
    delay(800);
  }

  digitalWrite(PIN_MOTOR_DIR, LOW);
  analogWrite(PIN_MOTOR_PWM, 0);
  report("motor_ramp", "PASS", "Ramp complete — verify motor responded");
}

// ── Entry point ─────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1500);  // wait for serial monitor / CLI to connect

  Serial.println("DIAG:START");

  testPinReadback(PIN_MOTOR_DIR, "pin_motor_dir");
  testPinReadback(PIN_MOTOR_PWM, "pin_motor_pwm");
  testPinReadback(PIN_SERVO,     "pin_servo");

  testAnalogBaseline();

  matrix.begin();
  testLedMatrix();

  testServoSweep();

  testMotorRamp();

  Serial.println("DIAG:END");
}

void loop() {
  // Diagnostics run once in setup; idle forever.
  delay(60000);
}
