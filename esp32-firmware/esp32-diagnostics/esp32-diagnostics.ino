/*
 * ESP32 Diagnostics — Automated hardware test
 *
 * Runs a suite of tests and reports results over serial in a
 * machine-readable format so the CLI can parse and display them.
 *
 * Protocol:  DIAG:START / TEST:<name>:<PASS|FAIL|WARN|INFO>:<detail> / DIAG:END
 *
 * Tests:
 *   1. Pin readback   — verify GPIO18 and GPIO19 can drive HIGH/LOW
 *   2. Servo sweep    — sweep servo on GPIO19 through 0->90->180->90
 *   3. ESC ramp       — ramp ESC on GPIO18: neutral -> 25% -> 50% -> neutral
 *   4. Analog baseline — check ADC pins for unexpected voltages
 *
 * Pin assignments:
 *   GPIO19 -> Steering servo
 *   GPIO18 -> ESC
 *
 * After running, use `racing-adapter esp32-firmware-upload` to restore
 * normal firmware.
 *
 * Board: ESP32 DEVKITV1 (DOIT)
 * Required library: ESP32Servo
 */

#include <ESP32Servo.h>

const int PIN_SERVO = 19;
const int PIN_ESC   = 18;

Servo testServo;
Servo testEsc;

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
    snprintf(buf, sizeof(buf), "GPIO%d toggles OK", pin);
    report(name, "PASS", buf);
  } else if (readHigh == LOW && readLow == LOW) {
    snprintf(buf, sizeof(buf), "GPIO%d stuck LOW — possible short to GND", pin);
    report(name, "FAIL", buf);
  } else if (readHigh == HIGH && readLow == HIGH) {
    snprintf(buf, sizeof(buf), "GPIO%d stuck HIGH — possible short to VCC", pin);
    report(name, "FAIL", buf);
  } else {
    snprintf(buf, sizeof(buf), "GPIO%d unexpected (HIGH->%d, LOW->%d)", pin, readHigh, readLow);
    report(name, "FAIL", buf);
  }

  digitalWrite(pin, LOW);
}

// ── Test 2: Servo sweep ─────────────────────────────────────────────
// Sweep steering servo: 0 -> 90 -> 180 -> 90 degrees.

void testServoSweep() {
  char buf[80];

  testServo.attach(PIN_SERVO, 1000, 2000);
  delay(200);

  int positions[] = {0, 90, 180, 90};
  int numPos = 4;

  for (int i = 0; i < numPos; i++) {
    testServo.write(positions[i]);
    delay(600);
    snprintf(buf, sizeof(buf), "Commanded %d deg", positions[i]);
    report("servo_sweep", "INFO", buf);
  }

  testServo.detach();
  report("servo_sweep", "PASS", "Sweep complete — verify servo moved physically");
}

// ── Test 3: ESC ramp ────────────────────────────────────────────────
// Ramp ESC: neutral -> 25% -> 50% -> neutral.
// 25% = 1625us, 50% = 1750us (within the 1500-2000us forward range).

void testEscRamp() {
  char buf[80];

  testEsc.attach(PIN_ESC, 1500, 2000);
  delay(200);

  // Arm: hold neutral for 3 seconds
  testEsc.writeMicroseconds(1500);
  report("esc_ramp", "INFO", "Arming ESC (neutral 1500us for 3s)");
  delay(3000);
  report("esc_ramp", "INFO", "ESC armed");

  struct { const char* label; int us; } steps[] = {
    {"neutral",  1500},
    {"25%",      1625},
    {"50%",      1750},
    {"neutral",  1500},
  };
  int numSteps = 4;

  for (int i = 0; i < numSteps; i++) {
    testEsc.writeMicroseconds(steps[i].us);
    snprintf(buf, sizeof(buf), "%s (%dus)", steps[i].label, steps[i].us);
    report("esc_ramp", "INFO", buf);
    delay(1000);
  }

  testEsc.detach();
  report("esc_ramp", "PASS", "Ramp complete — verify ESC/motor responded");
}

// ── Test 4: Analog baseline ─────────────────────────────────────────
// Read ADC-capable pins. ESP32 ADC uses 12-bit (0-4095), 3.3V reference.
// Pins 32-39 are ADC1 (safe to use alongside WiFi).

void testAnalogBaseline() {
  char buf[80];

  int adcPins[] = {32, 33, 34, 35, 36, 39};
  int numPins = 6;

  for (int i = 0; i < numPins; i++) {
    int raw = analogRead(adcPins[i]);
    float voltage = raw * (3.3f / 4095.0f);

    // Use dtostrf for float formatting on ESP32
    char vStr[8];
    dtostrf(voltage, 4, 2, vStr);

    if (raw > 3900) {
      snprintf(buf, sizeof(buf), "GPIO%d = %d (%sV) — near VCC, possible short to 3.3V", adcPins[i], raw, vStr);
      report("analog_baseline", "WARN", buf);
    } else if (raw > 400) {
      snprintf(buf, sizeof(buf), "GPIO%d = %d (%sV) — unexpected mid-range voltage", adcPins[i], raw, vStr);
      report("analog_baseline", "WARN", buf);
    } else {
      snprintf(buf, sizeof(buf), "GPIO%d = %d (%sV)", adcPins[i], raw, vStr);
      report("analog_baseline", "INFO", buf);
    }
  }
}

// ── Entry point ─────────────────────────────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1500);  // wait for serial monitor / CLI to connect

  Serial.println("DIAG:START");

  testPinReadback(PIN_ESC,   "pin_esc");
  testPinReadback(PIN_SERVO, "pin_servo");

  testServoSweep();

  testEscRamp();

  testAnalogBaseline();

  Serial.println("DIAG:END");
}

void loop() {
  // Diagnostics run once in setup; idle forever.
  delay(60000);
}
