# Mixer Hub firmware

Open **[MixerHub/MixerHub.ino](MixerHub/MixerHub.ino)** in Arduino IDE. The sketch
and its enclosing directory share a name so the IDE opens it without moving files.
The sketch now replaces the original rainbow boot animation with a timed blue
bottom-to-top fill, brief hold and fade into the live display. **Reflash the Nano
to install this change**; updating the Windows EXE alone cannot replace power-on
firmware. Keep **`startup_animation.h`** beside `MixerHub.ino` when opening/uploading
the sketch. Serial commands, slider calibration, buttons and normal LED rendering
retain their existing behaviour.

See **[Startup behaviour, flashing and hardware checks](STARTUP.md)** for the
power-on/serial-reset distinction and the assessment of selectable animations.

## Download both files together

On the repository's **main** page, choose **Code → Download ZIP**, then extract
the ZIP. Open the sketch inside the extracted folder, keeping this structure:

```text
firmware/
  MixerHub/
    MixerHub.ino
    startup_animation.h
```

`startup_animation.h` is a helper header compiled automatically with the sketch.
It is not a separate app or a separate upload. Open **MixerHub.ino**, and keep the
header in that same **MixerHub** folder with its exact filename. Uploading the
sketch installs both files' code on the Nano. If the IDE says the header is missing,
check that you extracted the ZIP and did not download only the `.ino` file.

The existing **v1.0.0 Release** still contains the older standalone
`sketch_sep22a.ino`. To install the blue startup, use the current two-file sketch
from **main**, not that legacy release attachment or its tagged source ZIP.
The existing Windows EXE works with this firmware; it does not need reinstalling
to change the board's boot animation.

## Hardware and pinout

Target: **classic Arduino Nano, ATmega328P, 5 V**. Library: **Adafruit NeoPixel**
(install using Arduino IDE's Library Manager).

This is the sketch's target, not confirmation of the exact purchased board variant
or USB interface chip. See the [project README](../README.md) for component
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
inverts the analog reading and maps its calibrated range (`8–1015`) to `0–1023`.

LED channel groups follow slider order. Groups 2 and 4 reverse their pixel order
for serpentine wiring. Use a power arrangement suitable for your LEDs and enclosure,
with a common GND; this pin table is not a complete power-distribution schematic.
The [Adafruit NeoPixel power guide](https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels)
covers supply sizing and wiring considerations.

## Flash

1. Install Arduino IDE, **Arduino AVR Boards**, and **Adafruit NeoPixel**.
   The updated sketch was compiled with AVR core **1.8.8** and NeoPixel **1.15.5**.
2. Open `MixerHub/MixerHub.ino` and choose **Arduino Nano** under Boards.
3. Choose the USB port and the matching **Processor**. Some older boards use
   **ATmega328P (Old Bootloader)**; use the option appropriate to your Nano.
4. Keep `startup_animation.h` in the sketch directory. Quit the desktop app
   through its tray **Quit** menu and close Serial Monitor, then **Verify** and
   **Upload**. Closing the app window with X only hides it and can leave the port open.
5. Reopen Mixer Hub and connect to the device. No firmware upload is required on
   subsequent launches unless you are updating the sketch.

Arduino's [upload documentation](https://docs.arduino.cc/software/ide-v2/tutorials/getting-started/ide-v2-uploading-a-sketch/)
explains board and port selection.

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
```

The companion enters audio-reactive mode after 1.5 seconds without fader movement.
The Nano handles the LED decay and sub-pixel fade. In this sketch, the falling
level decreases by `0.45` LED per update; the app's display decay is approximate.

[Back to the project](../README.md)
