#include <Adafruit_NeoPixel.h>
#include "startup_animation.h"

#define LED_PIN         12
#define NUM_SLIDERS     4
#define LEDS_PER_SLIDER 10
#define TOTAL_LEDS      (NUM_SLIDERS * LEDS_PER_SLIDER)

uint8_t SLIDER_COLORS[NUM_SLIDERS][3] = {
  {160, 0,   255}, {30,  215, 96}, {235, 50,  35}, {88,  101, 242}
};

const int RAW_MIN = 8;
const int RAW_MAX = 1015;

Adafruit_NeoPixel strip(TOTAL_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

const int sliderPins[NUM_SLIDERS] = {A0, A1, A2, A3};
const int mutePins[NUM_SLIDERS]   = {2, 3, 4, 5};
const int prevPin       = 7;
const int playPausePin  = 8;
const int nextPin       = 9;
const int deafenPin     = 10;
const int discordMutePin = 11;

bool isMuted[NUM_SLIDERS] = {false, false, false, false};
int lastMuteButtonStates[NUM_SLIDERS] = {HIGH, HIGH, HIGH, HIGH};

int eqLevels[NUM_SLIDERS] = {-1, -1, -1, -1};
float currentEq[NUM_SLIDERS] = {0, 0, 0, 0}; // Tracks the smooth falling animation

uint32_t startupStartedAt = 0;
bool startupActive = true;
uint32_t lastHostHeartbeat = 0;
bool hostLightingOff = false;

void setSliderPixel(int slider, int levelIndex, uint8_t r, uint8_t g, uint8_t b) {
  if (levelIndex < 0 || levelIndex >= LEDS_PER_SLIDER) return;
  int actualIndex = MixerStartup::physicalPixel(slider, levelIndex, LEDS_PER_SLIDER);
  strip.setPixelColor(actualIndex, strip.Color(r, g, b));
}

void applyStartupOverlay() {
  if (!startupActive) return;
  uint32_t elapsed = (uint32_t)(millis() - startupStartedAt);
  if (elapsed >= MixerStartup::TOTAL_MS) {
    startupActive = false;
    return; // Leave the freshly rendered normal frame untouched.
  }

  uint8_t *pixels = strip.getPixels();
  if (!pixels) return;
  uint16_t fill = MixerStartup::fillPosition(elapsed, LEDS_PER_SLIDER);
  uint8_t weight = MixerStartup::normalWeight(elapsed);
  uint8_t brightness = strip.getBrightness();
  // This strip is NEO_GRB. Blend its already brightness-scaled bytes directly,
  // avoiding lossy getPixelColor()/setBrightness() round trips and extra buffers.
  const uint8_t blueGRB[3] = {
    MixerStartup::blueByte(127, brightness),
    MixerStartup::blueByte(64, brightness),
    MixerStartup::blueByte(204, brightness)
  };
  for (uint8_t s = 0; s < NUM_SLIDERS; s++) {
    if (isMuted[s]) continue; // The normal renderer has already cleared it.
    for (uint8_t level = 0; level < LEDS_PER_SLIDER; level++) {
      uint16_t offset = MixerStartup::physicalPixel(s, level, LEDS_PER_SLIDER) * 3;
      uint8_t amount = MixerStartup::coverage(fill, level);
      for (uint8_t component = 0; component < 3; component++) {
        pixels[offset + component] = MixerStartup::blend(
          pixels[offset + component], MixerStartup::atLevel(blueGRB[component], amount), weight);
      }
    }
  }
}

int readSmoothed(int pin) {
  long sum = 0;
  for (int i = 0; i < 8; i++) sum += analogRead(pin);
  return sum / 8;
}

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(10);
  for (int i = 0; i < NUM_SLIDERS; i++) pinMode(mutePins[i], INPUT_PULLUP);
  pinMode(prevPin, INPUT_PULLUP); pinMode(playPausePin, INPUT_PULLUP); pinMode(nextPin, INPUT_PULLUP);
  pinMode(deafenPin, INPUT_PULLUP); pinMode(discordMutePin, INPUT_PULLUP);

  strip.begin();
  strip.setBrightness(45);
  strip.show();
  startupStartedAt = millis(); // Power/reset animation, not a PC-ready signal.
  lastHostHeartbeat = startupStartedAt;
}

void loop() {
  while (Serial.available() > 0) {
    String inData = Serial.readStringUntil('\n');
    inData.trim();
    
    if (inData == "H,1") {
      lastHostHeartbeat = millis();
      hostLightingOff = false;
    }
    else if (inData == "H,0") {
      hostLightingOff = true;
    }
    else if (inData.startsWith("B,")) {
      strip.setBrightness(inData.substring(2).toInt());
    } 
    else if (inData.startsWith("C,")) {
      int c1 = inData.indexOf(',', 2); int c2 = inData.indexOf(',', c1 + 1); int c3 = inData.indexOf(',', c2 + 1);
      if (c1 > 0 && c2 > 0 && c3 > 0) {
        int idx = inData.substring(2, c1).toInt();
        if (idx >= 0 && idx < NUM_SLIDERS) {
          SLIDER_COLORS[idx][0] = inData.substring(c1 + 1, c2).toInt();
          SLIDER_COLORS[idx][1] = inData.substring(c2 + 1, c3).toInt();
          SLIDER_COLORS[idx][2] = inData.substring(c3 + 1).toInt();
        }
      }
    }
    else if (inData.startsWith("E,")) {
      int c1 = inData.indexOf(',', 2); int c2 = inData.indexOf(',', c1 + 1); int c3 = inData.indexOf(',', c2 + 1);
      if (c1 > 0 && c2 > 0 && c3 > 0) {
        eqLevels[0] = inData.substring(2, c1).toInt();
        eqLevels[1] = inData.substring(c1 + 1, c2).toInt();
        eqLevels[2] = inData.substring(c2 + 1, c3).toInt();
        eqLevels[3] = inData.substring(c3 + 1).toInt();
      }
    }
  }

  for (int i = 0; i < NUM_SLIDERS; i++) {
    int btnState = digitalRead(mutePins[i]);
    if (btnState == LOW && lastMuteButtonStates[i] == HIGH) { isMuted[i] = !isMuted[i]; delay(20); }
    lastMuteButtonStates[i] = btnState;
  }

  for (int i = 0; i < NUM_SLIDERS; i++) {
    int cleanVal = constrain(map(1023 - readSmoothed(sliderPins[i]), RAW_MIN, RAW_MAX, 0, 1023), 0, 1023);
    Serial.print(isMuted[i] ? 0 : cleanVal); Serial.print("|");
  }

  Serial.print(digitalRead(prevPin)); Serial.print("|"); Serial.print(digitalRead(playPausePin)); Serial.print("|");
  Serial.print(digitalRead(nextPin)); Serial.print("|"); Serial.print(digitalRead(deafenPin)); Serial.print("|");
  Serial.println(digitalRead(discordMutePin));

  updateLEDs();
  delay(30);
}

void updateLEDs() {
  if (MixerHostLighting::shouldBlank(millis(), lastHostHeartbeat, hostLightingOff)) {
    startupActive = false;
    strip.clear();
    strip.show();
    return;
  }
  strip.clear();
  for (int s = 0; s < NUM_SLIDERS; s++) {
    if (isMuted[s]) continue;
    
    uint8_t bR = SLIDER_COLORS[s][0];
    uint8_t bG = SLIDER_COLORS[s][1];
    uint8_t bB = SLIDER_COLORS[s][2];

    // --- NEW SMOOTH EQ RENDERER ---
    if (eqLevels[s] >= 0) {
      // Convert incoming 0-100 percentage to a precise float (0.00 to 10.00)
      float targetLevel = (eqLevels[s] / 100.0f) * (float)LEDS_PER_SLIDER;

      // Gravity Physics: Fast jump up, smooth glide down
      if (targetLevel >= currentEq[s]) {
        currentEq[s] = targetLevel; 
      } else {
        currentEq[s] -= 0.45f; // Adjust this number (0.2 to 0.8) to change how fast it falls
        if (currentEq[s] < targetLevel) currentEq[s] = targetLevel;
      }
      
      float exactLevel = currentEq[s];
      int fullLeds = (int)exactLevel;
      float remainder = exactLevel - fullLeds;
      
      for (int l = 0; l < fullLeds && l < LEDS_PER_SLIDER; l++) setSliderPixel(s, l, bR, bG, bB);
      
      // Sub-pixel fade for the topmost LED
      if (fullLeds < LEDS_PER_SLIDER && remainder > 0.02f) {
        setSliderPixel(s, fullLeds, (uint8_t)(bR * remainder), (uint8_t)(bG * remainder), (uint8_t)(bB * remainder));
      }
    } 
    // --- STANDARD VOLUME RENDERER ---
    else {
      currentEq[s] = 0.0f; // Reset physics
      int cleanVal = constrain(map(1023 - readSmoothed(sliderPins[s]), RAW_MIN, RAW_MAX, 0, 1023), 0, 1023);
      if (cleanVal <= 0) continue;
      
      float exactLevel = (cleanVal / 1023.0f) * (float)LEDS_PER_SLIDER;
      int fullLeds = (int)exactLevel;
      float remainder = exactLevel - fullLeds;
      
      for (int l = 0; l < fullLeds && l < LEDS_PER_SLIDER; l++) setSliderPixel(s, l, bR, bG, bB);
      if (fullLeds < LEDS_PER_SLIDER && remainder > 0.02f) {
        setSliderPixel(s, fullLeds, (uint8_t)(bR * remainder), (uint8_t)(bG * remainder), (uint8_t)(bB * remainder));
      }
    }
  }
  applyStartupOverlay();
  strip.show();
}
