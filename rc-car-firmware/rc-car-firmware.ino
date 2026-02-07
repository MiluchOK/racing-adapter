/*
 * RC Car Firmware
 *
 * Listens for RC commands over Serial and controls LED matrix.
 * Protocol: "RC:<steer>,<throttle>,<brake>\n"
 * Values: 0-255
 */

#include "Arduino_LED_Matrix.h"
#include "DriveData.h"

ArduinoLEDMatrix matrix;
DriveData driveData;

// LED matrix frame buffer (8 rows x 12 columns)
uint8_t frame[8][12] = {0};

// Serial input buffer
char inputBuffer[64];
int bufferIndex = 0;

void setup() {
  Serial.begin(115200);
  matrix.begin();
  Serial.println("RC Car ready. Send: RC:<steer>,<throttle>,<brake>");
}

void loop() {
  // Read serial data
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      // End of line - process command
      if (bufferIndex > 0) {
        inputBuffer[bufferIndex] = '\0';
        driveData.update(inputBuffer, bufferIndex);

        // Update LED display
        driveData.renderSteer(frame);
        matrix.renderBitmap(frame, 8, 12);
      }
      bufferIndex = 0;
    } else if (bufferIndex < sizeof(inputBuffer) - 1) {
      inputBuffer[bufferIndex++] = c;
    }
  }
}
