# Blue startup animation

## Where it runs and what needs updating

The original rainbow ran in `playStartupSequence()` from the Nano's `setup()`.
It filled the whole strip with changing rainbow colours using blocking delays.
It was not an animation sent by the Windows companion.

The replacement lives in `MixerHub/MixerHub.ino` and its local
`startup_animation.h` helper. **It requires uploading the updated firmware to the
Nano.** An EXE update cannot change what the board displays on power-up without
that firmware upload. The separate old sketch outside this repository has not
been modified; open this repository's `firmware/MixerHub/MixerHub.ino` to flash
the blue version.

On the standard classic Nano design, the USB serial interface can pulse reset
through DTR. Opening a serial connection can therefore restart the firmware and
replay the same boot animation. Actual behaviour depends on the purchased board
and USB interface, which remain to be confirmed. See the official
[Nano auto-reset description](https://store.arduino.cc/products/arduino-nano).

The current companion opens serial at 9600 baud, waits 1.5 seconds, then sends
the existing `B,...`, `C,...` and `E,...` settings. v1.0.1 also sends `H,1` once
per second to keep the LEDs awake. It sends no animation command.
There is no startup acknowledgement or PC-ready handshake in this protocol.
**The blue sequence means the board is booting/resetting; it does not confirm
that the app is connected, audio is ready, or the device has passed a self-test.**

## Behaviour

| Time since firmware starts the animation | LED display |
| --- | --- |
| 0–1000 ms | All unmuted columns fill together from logical bottom to top; the leading LED fades in fractionally |
| 1000–1150 ms | Full blue columns briefly hold |
| 1150–1600 ms | Blue crossfades into the normal display recalculated on each loop |
| At/after 1600 ms | Normal rendering is used directly; the startup overlay stops |
| At/after 5000 ms without an app heartbeat | LEDs are blanked until the matching app connects |

The blue is RGB **64, 127, 204** before brightness scaling. Its intensity is
capped at **45/255**, matching the existing boot brightness, or at a lower
current brightness if the companion sends one. Brightness zero stays dark.
The fade ends at the current normal display and its requested brightness;
the overlay does not permanently restrict normal brightness settings.

The normal loop continues reading sliders and all nine switches, sending its
nine-field serial frame, and processing existing commands during the animation.
There are no added animation delays, waits for the app or extra LED frame buffers.
The existing loop delay, button debounce delay and serial read timeout are retained.
Frame cadence and bootloader/reset delay affect the observed wall-clock timing;
the programmed animation itself is 1.6 seconds, sampled on normal display updates.

The existing serpentine mapping is preserved: logical bottom corresponds to
physical pixel **0, 19, 20, 39** for columns 1–4. Muting a channel keeps its entire
column dark, including during startup. The fade targets current slider levels,
mute state, channel colours and EQ state, not a cached boot snapshot. With the
app absent, it briefly finishes on the default-colour volume display, then goes
dark at the five-second startup grace limit. See [automatic LED sleep](POWER.md).

The overlay blends the freshly rendered raw GRB pixel bytes without repeatedly
changing NeoPixel's brightness or rescaling the normal frame through colour
readback. Adafruit documents the brightness/readback rounding constraints in
its [library guide](https://learn.adafruit.com/adafruit-neopixel-uberguide/arduino-library-use).
After startup expires, the normal renderer's output is left untouched while the
host lighting lease is active; explicit blackout or heartbeat timeout blanks it.

## Flash this version

Follow the **[Arduino flashing guide](README.md)** for the firmware ZIP, both required
files, board selection and upload steps. Use the matching v1.0.1 app for LED sleep.

## Hardware checks to perform after flashing

1. **App absent:** quit the app, put the sliders at different levels, then power
   the mixer. Confirm the four columns fill upward together, briefly hold, and
   smoothly resolve to their current default-colour volume bars without waiting
   for a PC connection. Then confirm they go dark after the five-second startup
   grace period. Check both reversed columns for the correct direction.
2. **Inputs during boot:** move a slider and press/release each local mute during
   the sequence. Confirm the final bar follows the new position, and a muted
   column stays dark. With the app connected and reading frames, check the five
   media/Discord buttons too; the board continues transmitting their levels.
   The app's existing 1.5-second connection wait means presses entirely within
   that wait are not guaranteed to be acted upon by Windows.
3. **App connection:** connect the app and observe whether your Nano resets.
   If it does, the same blue sequence should replay. Confirm saved colours and
   brightness take effect and no rainbow appears. A blue animation is not proof
   of connection; check actual slider control and the app's device state.
4. **Brightness:** once connected, check 0, a low value, the default 45, and a
   higher normal setting. Zero should be dark. If a brightness command arrives
   while startup is running, its lower limit should apply immediately; a higher
   setting must not raise the blue source above the boot cap. Confirm the fade
   reaches the requested normal brightness without an endpoint flash.
5. **Normal use:** verify all four app/master assignments and local mutes, the
   three media buttons, both Discord shortcuts, saved channel colours and EQ
   after 1.5 seconds without fader movement. Silent channels should return to
   their static volume display. Check reconnect and power-cycle behaviour.

These checks require the physical mixer. Electrical timing, real colour/brightness,
USB reset behaviour, physical LED orientation and switch responsiveness have not
been verified by compiling the code alone.

## Selectable startup animations — assessment only

A few procedural choices are practical for the current ATmega328P target without
changing the mixer hardware. The compiled blue version with LED sleep uses
**9998 / 30720 bytes** of program storage and **313 / 2048 bytes** of static RAM
with the toolchain below.
The RAM report excludes runtime allocations such as NeoPixel's pixel buffer and
Arduino `String` storage; it is not a measurement of peak runtime free memory.
Simple generated patterns would be preferable to stored animation frames.

That larger feature would need:

- **Firmware:** defined animation IDs, the same nonblocking timing approach,
  validated settings and a safe default. Decide whether a setting applies next
  boot or can explicitly replay a preview; receiving a preference should not
  accidentally restart an in-progress animation.
- **Protocol:** a new, documented selection command (for example `A,mode\n`,
  **not supported now**) plus a way to discover support and acknowledge the
  accepted setting. The UI must not report a selection as applied on legacy
  firmware that simply ignores an unknown command. A true PC-ready indication
  would also require a defined handshake rather than using the boot animation.
- **Companion setting:** a device-level selection in Settings, compatibility
  handling for older firmware, and sending the desired value after connecting
  with acknowledgement/error feedback.
- **Persistence:** JSON can remember the desired app setting, but cannot control
  a standalone power-on before the PC connects. The Nano would need to retain
  the selected mode in onboard EEPROM, using a versioned/validated record and
  writing only when it changes, with blue as the fallback for invalid data.

No animation selector, animation command, acknowledgement, animation preference
or EEPROM write is implemented. The separate LED sleep change adds the `H,1`
and `H,0` host-lighting commands documented in the [serial protocol reference](REFERENCE.md#serial-protocol).

## Verification performed

- Full sketch compiled for **`arduino:avr:nano:cpu=atmega328`**, AVR core **1.8.8**,
  Adafruit NeoPixel **1.15.5**, using the installed Arduino CLI.
- `tests/firmware/startup_math.cpp` compiled on the AVR target with warnings as
  errors. Its compile-time assertions cover all four columns' endpoint mapping,
  fractional fill, hold/fade boundaries, lower/zero/capped brightness, blend
  endpoints, maximum-byte arithmetic, unsigned timer wraparound and the
  five-second host-lighting timeout/renewal/explicit blackout boundaries.
- The startup replacement preserves slider smoothing, pin definitions, button
  handling and normal display calculations. The subsequent LED sleep change
  adds heartbeat parsing and an early blackout check; input scanning continues.

To repeat the compile (Arduino CLI available on PATH):

```powershell
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 --build-path build/firmware-blue --warnings all firmware/MixerHub
```

To repeat the integer assertions with the Arduino toolchain's `avr-g++` on PATH:

```powershell
avr-g++ -std=gnu++11 -mmcu=atmega328p -Os -Wall -Wextra -Werror -c tests/firmware/startup_math.cpp -o build/startup-math.o
```

The Arduino core emits existing unused-parameter warnings in `new.cpp`; the sketch
and assertion compile completed successfully. Compilation did not upload anything
to a physical board. The builder subsequently reported successful physical
testing. Other Nano variants and motherboard sleep behaviour still need checking
on the actual setup; use the matching app and firmware from v1.0.1.
