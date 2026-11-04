// Compile-only regression assertions on the AVR target (16-bit int arithmetic).
#include "../../firmware/MixerHub/startup_animation.h"
using namespace MixerStartup;

static_assert(TOTAL_MS == 1600, "Boot animation must remain about 1-2 seconds");
static_assert(physicalPixel(0, 0, 10) == 0 && physicalPixel(0, 9, 10) == 9, "Column 1 wiring");
static_assert(physicalPixel(1, 0, 10) == 19 && physicalPixel(1, 9, 10) == 10, "Column 2 reversed wiring");
static_assert(physicalPixel(2, 0, 10) == 20 && physicalPixel(2, 9, 10) == 29, "Column 3 wiring");
static_assert(physicalPixel(3, 0, 10) == 39 && physicalPixel(3, 9, 10) == 30, "Column 4 reversed wiring");
static_assert(fillPosition(0, 10) == 0, "Start dark");
static_assert(fillPosition(50, 10) == 127, "Fractional first LED");
static_assert(fillPosition(500, 10) == 1275, "Half fill");
static_assert(fillPosition(1000, 10) == 2550, "Full fill");
static_assert(fillPosition(1600, 10) == 2550, "Hold fill through fade");
static_assert(coverage(127, 0) == 127 && coverage(127, 1) == 0, "Smooth bottom-up tip");
static_assert(coverage(1275, 4) == 255 && coverage(1275, 5) == 0, "Five LEDs at halfway");
static_assert(coverage(2550, 9) == 255, "Top LED fully lit");
static_assert(normalWeight(1000) == 0 && normalWeight(1150) == 0, "Hold blue");
static_assert(normalWeight(1375) == 127, "Halfway fade");
static_assert(normalWeight(1600) == 255 && normalWeight(2000) == 255, "Finish at normal display");
static_assert(blueByte(204, 0) == 0, "Brightness zero stays dark");
static_assert(blueByte(204, 20) == 16, "Respect lower brightness");
static_assert(blueByte(204, 45) == 36, "Default brightness");
static_assert(blueByte(204, 255) == 36, "Cap startup despite maximum app brightness");
static_assert(atLevel(36, 0) == 0 && atLevel(36, 255) == 36, "Tip opacity endpoints");
static_assert(blend(255, 36, 0) == 36 && blend(255, 36, 255) == 255, "Crossfade endpoints");
static_assert(blend(255, 255, 127) == 255, "No 16-bit overflow at maximum byte values");
static_assert(blend(0, 0, 127) == 0, "Muted/dark pixels remain dark");
static_assert((uint32_t)((uint32_t)20 - (uint32_t)0xFFFFFFF0UL) == 36, "millis subtraction wraps safely");
