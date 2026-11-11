# Firmware technical reference

For installation, use the [Arduino flashing guide](README.md). This page contains wiring and protocol details.

## Hardware and pinout

Target: **classic Arduino Nano, ATmega328P, 5 V**. Library: **Adafruit NeoPixel**
(install using Arduino IDE's Library Manager).

This is the sketch's target, not confirmation of the exact purchased board variant
or USB interface chip. See the [hardware guide](../hardware/README.md) for component
selections and build status. The DIY build requires soldering; this firmware guide
does not replace the PCB assembly and component-retention instructions.

| Function | Pins / arrangement |
| --- | --- |
| Four potentiometer wipers | `A0`, `A1`, `A2`, `A3` |
| Four local channel-mute switches | `D2`, `D3`, `D4`, `D5` |
| Previous / play-pause / next | `D7`, `D8`, `D9` |
| Discord deafen / mute | `D10`, `D11` |
| WS2812B data | `D12` |
| LEDs | 40 total: four consecutive groups of ten, `NEO_GRB + NEO_KHZ800` |

Connect each switch between its digital pin and GND. The firmware configures
`INPUT_PULLUP`, so released is `1` and pressed is `0`. Potentiometer outer terminals
connect to 5 V and GND; the middle wiper connects to its analog pin. The sketch
inverts the analog reading and maps its calibrated range (factory `8-1015`) to `0-1023`. The v1.1.0 app can [record a separate range for each slider](../docs/CALIBRATION.md).

LED channel groups follow slider order. Groups 2 and 4 reverse their pixel order
for serpentine wiring. Use a power arrangement suitable for your LEDs and enclosure,
with a common GND; this pin table is not a complete power-distribution schematic.
The [Adafruit NeoPixel power guide](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels)
covers supply sizing and wiring considerations.

## Serial protocol

USB serial runs at **9600 baud**, with newline-terminated ASCII messages.

Nano → companion:

```text
slider1|slider2|slider3|slider4|previous|playPause|next|deafen|discordMute\n
```

Slider values are `0–1023`; the four local mute switches report their channel as
zero while muted. The five transmitted button levels are active LOW. Local mute
switches are not extra fields in this nine-field frame.

Companion → Nano:

```text
B,brightness\n          # brightness: 0–255
C,channel,R,G,B\n       # channel: 0–3; RGB: 0–255
E,ch1,ch2,ch3,ch4\n     # levels: 0–100; -1 restores the static volume display
H,1\n                 # renew five-second host lighting lease
H,0\n                 # explicit blackout until next heartbeat
```

The companion enters audio-reactive mode after 1.5 seconds without fader movement.
The Nano handles the LED decay and sub-pixel fade. In this sketch, the falling
level decreases by `0.45` LED per update; the app's display decay is approximate.

## Slider calibration (v1.1.0)

The app sends `V\n` and the firmware replies `V,CAL,1\n` to confirm support.
`K,START\n` switches to raw endpoint frames `R,r1,r2,r3,r4,mask\n`; these replace
the regular input frame during recording. `K,STOP\n` restores normal reporting.
`K,channel,min,max\n` applies a validated range to physical channel 0-3.
The raw readings are smoothed, inverted ADC values; the mask contains local mute
bits. Normal input scanning and local mute handling continue during capture.
Capture ends if the host-lighting lease expires. Ranges live in RAM; the app
persists them per device and reapplies them after reconnecting. No EEPROM writes
are added.

[Back to the project](../README.md)
