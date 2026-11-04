#pragma once
#include <stdint.h>

// Pure integer helpers; the animation never changes the strip's brightness.
namespace MixerStartup {
constexpr uint32_t FILL_MS = 1000;
constexpr uint32_t HOLD_MS = 150;
constexpr uint32_t FADE_MS = 450;
constexpr uint32_t TOTAL_MS = FILL_MS + HOLD_MS + FADE_MS;
constexpr uint8_t BRIGHTNESS_CAP = 45;

constexpr uint16_t physicalPixel(uint8_t channel, uint8_t level, uint8_t count) {
  return (uint16_t)channel * count + ((channel % 2 == 0) ? level : count - 1 - level);
}

// Fixed-point fill: each LED occupies 255 units, including a fractional tip.
constexpr uint16_t fillPosition(uint32_t elapsed, uint8_t count) {
  return elapsed >= FILL_MS ? (uint16_t)count * 255 : elapsed * count * 255 / FILL_MS;
}

constexpr uint8_t coverage(uint16_t fill, uint8_t level) {
  return fill >= ((uint16_t)level + 1) * 255 ? 255 :
         fill <= (uint16_t)level * 255 ? 0 : fill - (uint16_t)level * 255;
}

constexpr uint8_t normalWeight(uint32_t elapsed) {
  return elapsed <= FILL_MS + HOLD_MS ? 0 : elapsed >= TOTAL_MS ? 255 :
         (elapsed - FILL_MS - HOLD_MS) * 255 / FADE_MS;
}

// Match NeoPixel's brightness+1 scaling, capped at the existing boot value.
constexpr uint8_t blueByte(uint8_t component, uint8_t brightness) {
  return (uint16_t)component * ((brightness < BRIGHTNESS_CAP ? brightness : BRIGHTNESS_CAP) + 1) / 256;
}

constexpr uint8_t atLevel(uint8_t value, uint8_t weight) {
  return ((uint16_t)value * weight + 127) / 255;
}

constexpr uint8_t blend(uint8_t normal, uint8_t blue, uint8_t weight) {
  return ((uint16_t)normal * weight + (uint16_t)blue * (255 - weight) + 127) / 255;
}
}
