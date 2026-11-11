#pragma once
#include <stdint.h>

namespace MixerCalibration {
constexpr uint16_t DEFAULT_MIN = 8;
constexpr uint16_t DEFAULT_MAX = 1015;

constexpr bool valid(uint16_t low, uint16_t high) {
  return high <= 1023 && high >= low && high - low >= 256;
}

constexpr uint16_t position(uint16_t raw, uint16_t low, uint16_t high) {
  return raw <= low ? 0 : raw >= high ? 1023 :
         (uint32_t)(raw - low) * 1023 / (high - low);
}

// Reject malformed/partial settings rather than converting them to zero.
inline bool number(const char *&p, uint16_t &value) {
  if (*p < '0' || *p > '9') return false;
  value = 0;
  while (*p >= '0' && *p <= '9') {
    value = value * 10 + (*p++ - '0');
    if (value > 1023) return false;
  }
  return true;
}

inline bool parse(const char *p, uint16_t &channel, uint16_t &low, uint16_t &high) {
  if (p[0] != 'K' || p[1] != ',') return false;
  p += 2;
  return number(p, channel) && *p++ == ',' && number(p, low) &&
         *p++ == ',' && number(p, high) && *p == '\0' && channel < 4 && valid(low, high);
}
}
