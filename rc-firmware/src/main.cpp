#include <Arduino.h>

constexpr uint8_t LED_PIN = 5;

void setup() {
    Serial.begin(115200);
    pinMode(LED_PIN, OUTPUT);
    Serial.println("RC firmware started");
}

void loop() {
    digitalWrite(LED_PIN, LOW);   // LED on (sink current)
    delay(500);
    digitalWrite(LED_PIN, HIGH);  // LED off
    delay(500);
}
