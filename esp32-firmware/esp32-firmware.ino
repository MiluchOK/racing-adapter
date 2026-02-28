/*
 * ESP32 Firmware — WiFi/MQTT + Serial steering servo + ESC control
 *
 * Connects to WiFi, subscribes to MQTT topics "f1/steering" and
 * "f1/throttle", and drives the steering servo + ESC accordingly.
 * Serial commands (S:/T:) continue to work as a fallback for debugging.
 *
 * MQTT broker: 10.0.0.102:1883  (must match MqttPublisher in Python)
 *
 * Serial protocol (line-based):
 *   S:<float>   Steering, -1.0 (full left) to 1.0 (full right)
 *   T:<float>   Throttle, 0.0 (neutral) to 1.0 (full forward)
 *
 * PWM mapping:
 *   Steering:  -1.0 -> 1000us,  0.0 -> 1500us,  1.0 -> 2000us
 *   Throttle:   0.0 -> 1500us (neutral),  1.0 -> 2000us (full forward)
 *
 * Pin assignments:
 *   GPIO19 -> Steering servo signal (yellow)
 *   GPIO18 -> ESC signal (white)
 *
 * ESC arming: sends 1500us (neutral) for 3 seconds during setup.
 *
 * Required libraries (install via Library Manager):
 *   - ESP32Servo
 *   - PubSubClient
 *
 * Board: ESP32 DEVKITV1 (DOIT)
 */

#include <ESP32Servo.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "arduino_secrets.h"

// -- Pin assignments --
const int SERVO_PIN = 19;
const int ESC_PIN   = 18;

// -- PWM limits (microseconds) --
const int SERVO_MIN_US = 1000;
const int SERVO_MAX_US = 2000;
const int ESC_MIN_US     = 1000;
const int ESC_NEUTRAL_US = 1500;
const int ESC_MAX_US     = 2000;

// -- MQTT config --
const char* MQTT_BROKER     = "10.0.0.102";
const int   MQTT_PORT       = 1883;
const char* TOPIC_STEERING      = "f1/steering";
const char* TOPIC_THROTTLE      = "f1/throttle";
const char* TOPIC_STEERING_TRIM = "f1/steering_trim";

// -- Objects --
Servo steeringServo;
Servo esc;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

// -- Steering trim (microseconds, set via f1/steering_trim MQTT topic) --
int steeringTrimUs = 0;

// -- Serial input buffer --
String inputBuffer = "";

// ── Steering ────────────────────────────────────────────────────────
void applySteering(float value) {
  // Clamp to [-1.0, 1.0]
  if (value < -1.0f) value = -1.0f;
  if (value >  1.0f) value =  1.0f;

  // Map: -1.0 -> 1000us, 0.0 -> 1500us, 1.0 -> 2000us, then apply trim
  int us = (int)(SERVO_MIN_US + (value + 1.0f) * 0.5f * (SERVO_MAX_US - SERVO_MIN_US));
  us += steeringTrimUs;
  if (us < SERVO_MIN_US) us = SERVO_MIN_US;
  if (us > SERVO_MAX_US) us = SERVO_MAX_US;
  steeringServo.writeMicroseconds(us);

  Serial.print("Steer ");
  Serial.print(value, 2);
  Serial.print(" -> ");
  Serial.print(us);
  Serial.println("us");
}

// ── Throttle ────────────────────────────────────────────────────────
void applyThrottle(float value) {
  // Clamp to [0.0, 1.0]
  if (value < 0.0f) value = 0.0f;
  if (value > 1.0f) value = 1.0f;

  // Map: 0.0 -> 1500us (neutral), 1.0 -> 2000us (full forward)
  int us = (int)(ESC_NEUTRAL_US + value * (ESC_MAX_US - ESC_NEUTRAL_US));
  esc.writeMicroseconds(us);

  Serial.print("Throttle ");
  Serial.print(value, 2);
  Serial.print(" -> ");
  Serial.print(us);
  Serial.println("us");
}

// ── Process a serial line ───────────────────────────────────────────
void processLine(const String& line) {
  if (line.length() < 3) return;

  char cmd = line.charAt(0);
  if (line.charAt(1) != ':') return;

  float value = line.substring(2).toFloat();

  if (cmd == 'S' || cmd == 's') {
    applySteering(value);
  } else if (cmd == 'T' || cmd == 't') {
    applyThrottle(value);
  } else {
    Serial.print("Unknown command: ");
    Serial.println(line);
  }
}

// ── WiFi ────────────────────────────────────────────────────────────
void connectWifi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }

  Serial.println();
  Serial.print("Connected — IP: ");
  Serial.println(WiFi.localIP());
}

// ── MQTT callback ───────────────────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Null-terminate the payload to parse as float
  char buf[32];
  unsigned int copyLen = length < sizeof(buf) - 1 ? length : sizeof(buf) - 1;
  memcpy(buf, payload, copyLen);
  buf[copyLen] = '\0';

  float value = atof(buf);

  if (strcmp(topic, TOPIC_STEERING) == 0) {
    applySteering(value);
  } else if (strcmp(topic, TOPIC_THROTTLE) == 0) {
    applyThrottle(value);
  } else if (strcmp(topic, TOPIC_STEERING_TRIM) == 0) {
    steeringTrimUs = (int)value;
    Serial.print("Steering trim set to ");
    Serial.print(steeringTrimUs);
    Serial.println("us");
  }
}

// ── MQTT connect ────────────────────────────────────────────────────
void connectMqtt() {
  Serial.print("Connecting to MQTT broker ");
  Serial.print(MQTT_BROKER);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  while (!mqttClient.connected()) {
    if (mqttClient.connect("esp32-rc-car")) {
      mqttClient.subscribe(TOPIC_STEERING);
      mqttClient.subscribe(TOPIC_THROTTLE);
      mqttClient.subscribe(TOPIC_STEERING_TRIM);
      Serial.println("Subscribed to f1/steering + f1/throttle + f1/steering_trim");
    } else {
      Serial.print("  MQTT error rc=");
      Serial.print(mqttClient.state());
      Serial.println(", retrying in 2s...");
      delay(2000);
    }
  }
}

// ── Arduino entry points ────────────────────────────────────────────
void setup() {
  // Force ESC pin LOW immediately to stop any boot-time float/noise
  // that the ESC could interpret as a throttle signal.
  pinMode(ESC_PIN, OUTPUT);
  digitalWrite(ESC_PIN, LOW);
  delay(500);

  Serial.begin(115200);
  Serial.println("ESP32 Firmware starting...");

  // Attach servo first (safe — servo won't spin on its own)
  steeringServo.attach(SERVO_PIN, SERVO_MIN_US, SERVO_MAX_US);
  steeringServo.writeMicroseconds(1500);
  Serial.println("Steering centered (1500us)");

  // Attach ESC and send neutral to arm
  esc.attach(ESC_PIN, 1000, 2000);
  esc.writeMicroseconds(ESC_NEUTRAL_US);

  // Arm ESC: hold neutral for 3 seconds
  Serial.println("Arming ESC (neutral 1500us for 3s)...");
  delay(3000);
  Serial.println("ESC armed.");

  // Connect WiFi and MQTT
  connectWifi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  connectMqtt();

  Serial.println("Ready. MQTT + serial active.");
  Serial.println("  Serial: S:<float> for steering, T:<float> for throttle.");
  Serial.println("  MQTT:   f1/steering, f1/throttle");
}

void loop() {
  // Reconnect WiFi if dropped
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  // Reconnect MQTT if dropped
  if (!mqttClient.connected()) {
    connectMqtt();
  }

  // Process MQTT messages
  mqttClient.loop();

  // Process serial commands
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      inputBuffer.trim();
      if (inputBuffer.length() > 0) {
        processLine(inputBuffer);
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}
