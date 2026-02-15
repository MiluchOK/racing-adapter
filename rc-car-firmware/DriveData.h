#ifndef DRIVEDATA_H
#define DRIVEDATA_H

#include <Arduino.h>
#include <string.h>

class DriveData {
public:
  DriveData() : steer(0.5f), throttle(0.0f), brake(0.0f), hasData(false) {}

  // Parse simple RC protocol: "RC:<steer>,<throttle>,<brake>\n"
  // Values are 0-255 integers
  void update(const char* buffer, int size) {
    if (size < 9) return;  // Minimum: "RC:0,0,0" = 8 chars + null

    // Check for "RC:" prefix
    if (buffer[0] != 'R' || buffer[1] != 'C' || buffer[2] != ':') return;

    int s, t, b;
    if (sscanf(buffer + 3, "%d,%d,%d", &s, &t, &b) != 3) return;

    // Validate ranges
    if (s < 0 || s > 255 || t < 0 || t > 255 || b < 0 || b > 255) return;

    steer = s / 255.0f;       // 0..255 → 0..1
    throttle = t / 255.0f;    // 0..255 → 0..1
    brake = b / 255.0f;       // 0..255 → 0..1
    hasData = true;
  }

  // Set steering value directly (normalised 0.0 - 1.0)
  void setSteer(float value) {
    steer = value;
    if (steer < 0.0f) steer = 0.0f;
    if (steer > 1.0f) steer = 1.0f;
    hasData = true;
  }

  // Returns steering value normalized to 0.0 (left) - 1.0 (right)
  float getSteer() {
    return steer;
  }

  // Returns throttle value normalized to 0.0 - 1.0
  float getThrottle() {
    return throttle;
  }

  // Returns brake value normalized to 0.0 - 1.0
  float getBrake() {
    return brake;
  }

  // Returns true if we've received valid telemetry data
  bool isReady() {
    return hasData;
  }

  // Render steering bar on LED matrix (lights columns from left based on steer)
  void renderSteer(uint8_t frame[8][12]) {
    memset(frame, 0, 8 * 12);

    int litColumns = (int)(steer * 12);
    if (litColumns > 12) litColumns = 12;

    for (int col = 0; col < litColumns; col++) {
      for (int row = 0; row < 8; row++) {
        frame[row][col] = 1;
      }
    }
  }

private:
  float steer;     // Normalized 0-1
  float throttle;  // Normalized 0-1
  float brake;     // Normalized 0-1
  bool hasData;    // True once we've received valid data
};

#endif
