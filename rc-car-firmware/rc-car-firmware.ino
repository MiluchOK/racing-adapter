/*
 * RC Car Firmware — MQTT steering + throttle
 *
 * Connects to WiFi, subscribes to MQTT topics "f1/steering" and
 * "f1/throttle", and drives the steering servo + motor accordingly.
 *
 * MQTT broker: 10.0.0.102:1883  (must match MqttPublisher in Python)
 *
 * Steering:  float string, -1.0 (full left) … 1.0 (full right)
 *            Servo mapping:  -1.0 → 0°,  0.0 → 90°,  1.0 → 180°
 * Throttle:  float string, 0.0 (idle) … 1.0 (full throttle)
 *            Motor mapping:  0.0 → PWM 0,  1.0 → PWM 255
 *
 * Pin assignments (Arduino Motor Shield Rev3):
 *   Servo:        A2   (TinkerKit IN2 connector)
 *   Motor A DIR:  D12
 *   Motor A PWM:  D3
 *   Motor A BRK:  D9   (set LOW to release brake)
 *
 * Required libraries (install via Library Manager):
 *   - ArduinoMqttClient
 *   - WiFiS3  (bundled with UNO R4 WiFi board package)
 */

#include <WiFiS3.h>
#include <ArduinoMqttClient.h>
#include <Servo.h>
#include "Arduino_LED_Matrix.h"
#include "DriveData.h"
#include "arduino_secrets.h"

// ── Config ──────────────────────────────────────────────────────────
const char* MQTT_BROKER     = "10.0.0.102";
const int   MQTT_PORT       = 1883;
const char* TOPIC_STEERING  = "f1/steering";
const char* TOPIC_THROTTLE  = "f1/throttle";

const int SERVO_PIN       = A2;   // TinkerKit IN2
const int MOTOR_DIR_PIN   = 12;   // Motor Shield Ch A direction
const int MOTOR_PWM_PIN   = 3;    // Motor Shield Ch A PWM
const int MOTOR_BRAKE_PIN = 9;    // Motor Shield Ch A brake

// ── Objects ─────────────────────────────────────────────────────────
WiFiClient   wifiClient;
MqttClient   mqttClient(wifiClient);
ArduinoLEDMatrix matrix;
DriveData    driveData;
Servo        steeringServo;

// LED matrix frame buffer (8 rows × 12 columns)
uint8_t frame[8][12] = {0};

// Throttle LED updates to avoid I2C overhead every loop
unsigned long lastMatrixMs = 0;
const unsigned long MATRIX_INTERVAL_MS = 100;  // 10 Hz

// Throttle serial debug to avoid blocking
unsigned long lastDebugMs = 0;
const unsigned long DEBUG_INTERVAL_MS = 500;

// ── WiFi ────────────────────────────────────────────────────────────
void connectWifi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  while (WiFi.begin(WIFI_SSID, WIFI_PASS) != WL_CONNECTED) {
    Serial.println("  retrying…");
    delay(3000);
  }

  Serial.print("Connected — IP: ");
  Serial.println(WiFi.localIP());
}

// ── MQTT ────────────────────────────────────────────────────────────
void connectMqtt() {
  Serial.print("Connecting to MQTT broker ");
  Serial.print(MQTT_BROKER);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  while (!mqttClient.connect(MQTT_BROKER, MQTT_PORT)) {
    Serial.print("  MQTT error: ");
    Serial.println(mqttClient.connectError());
    delay(2000);
  }

  mqttClient.subscribe(TOPIC_STEERING);
  mqttClient.subscribe(TOPIC_THROTTLE);
  Serial.println("Subscribed to f1/steering + f1/throttle");
}

// Cached latest values for deferred LED / debug output
float lastSteer = 0.0f;
float lastThrottle = 0.0f;

// ── Steering ────────────────────────────────────────────────────────
void applySteering(float steerValue) {
  int angle = (int)((steerValue + 1.0f) * 0.5f * 180.0f);
  if (angle < 0)   angle = 0;
  if (angle > 180) angle = 180;

  steeringServo.write(angle);
  lastSteer = steerValue;
}

// ── Throttle ────────────────────────────────────────────────────────
void applyThrottle(float throttleValue) {
  if (throttleValue < 0.0f) throttleValue = 0.0f;
  if (throttleValue > 1.0f) throttleValue = 1.0f;

  if (throttleValue < 0.01f) {
    digitalWrite(MOTOR_BRAKE_PIN, HIGH);
    analogWrite(MOTOR_PWM_PIN, 0);
  } else {
    int pwm = (int)(throttleValue * 255.0f);
    if (pwm > 255) pwm = 255;
    digitalWrite(MOTOR_BRAKE_PIN, LOW);
    digitalWrite(MOTOR_DIR_PIN, HIGH);
    analogWrite(MOTOR_PWM_PIN, pwm);
  }
  lastThrottle = throttleValue;
}

// ── Arduino entry points ────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  matrix.begin();

  steeringServo.attach(SERVO_PIN);
  steeringServo.write(90);  // center

  pinMode(MOTOR_DIR_PIN, OUTPUT);
  pinMode(MOTOR_PWM_PIN, OUTPUT);
  pinMode(MOTOR_BRAKE_PIN, OUTPUT);
  digitalWrite(MOTOR_DIR_PIN, LOW);
  analogWrite(MOTOR_PWM_PIN, 0);
  digitalWrite(MOTOR_BRAKE_PIN, HIGH);  // brake until commanded

  connectWifi();
  connectMqtt();

  Serial.println("RC Car ready — listening for MQTT steering + throttle");
}

void loop() {
  // Reconnect if needed
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }
  if (!mqttClient.connected()) {
    connectMqtt();
  }

  // Poll MQTT, then drain up to 20 queued messages before yielding
  // back so the WiFi stack stays healthy.
  mqttClient.poll();

  for (int i = 0; i < 20 && mqttClient.parseMessage(); i++) {
    String topic = mqttClient.messageTopic();

    char buf[32];
    int len = 0;
    while (mqttClient.available() && len < (int)sizeof(buf) - 1) {
      buf[len++] = (char)mqttClient.read();
    }
    buf[len] = '\0';

    float value = atof(buf);

    if (topic == TOPIC_STEERING) {
      applySteering(value);
    } else if (topic == TOPIC_THROTTLE) {
      applyThrottle(value);
    }
  }

  // LED matrix at 10 Hz (not every message)
  unsigned long now = millis();
  if (now - lastMatrixMs >= MATRIX_INTERVAL_MS) {
    lastMatrixMs = now;
    float norm = (lastSteer + 1.0f) * 0.5f;
    driveData.setSteer(norm);
    driveData.renderSteer(frame);
    matrix.renderBitmap(frame, 8, 12);
  }

  // Debug output at 2 Hz
  if (now - lastDebugMs >= DEBUG_INTERVAL_MS) {
    lastDebugMs = now;
    Serial.print("Steer ");
    Serial.print(lastSteer, 2);
    Serial.print("  Throttle ");
    Serial.println(lastThrottle, 2);
  }
}
