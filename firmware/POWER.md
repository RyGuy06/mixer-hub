# Automatic LED sleep (v1.0.1)

Install the **v1.0.1 Windows app and matching Nano firmware together** from the
[latest release](https://github.com/RyGuy06/mixer-hub/releases/latest). Installing
the EXE does not flash the Arduino. If you already uploaded these current firmware
files while testing, you do not need to flash them again for the EXE update.

## Install

1. Download `MixerHub.exe` and `MixerHub-firmware-v1.0.1.zip`.
2. Quit the old companion using **Quit Mixer Hub** in its tray menu or Settings.
   Clicking X only hides it, leaving the serial port open.
3. Extract the firmware ZIP. Keep both files in the same folder:

   ```text
   MixerHub/
     MixerHub.ino
     startup_animation.h
   ```

4. Open `MixerHub.ino` in Arduino IDE. The header compiles with the sketch; do not
   flash it separately. Install **Arduino AVR Boards** and **Adafruit NeoPixel**.
5. Choose your classic **Arduino Nano / ATmega328P**, matching processor/bootloader
   and USB port. Close Serial Monitor, then **Verify** and **Upload**.
6. Replace the old EXE with the new one and run it. Existing profiles, colours and
   brightness remain in `%APPDATA%\MixerHub`; no Python installation is needed.
   Connect to the mixer, or let your existing Auto-connect setting connect it.

The repository ZIP also contains both firmware files under `firmware/MixerHub/`.
The old `sketch_sep22a.ino` attachment in v1.0.0 is superseded.

## What to expect

- While the companion is connected, it renews a small lighting heartbeat once per
  second. This continues while the dashboard is hidden in the system tray.
- Sleep, hibernation and shutdown notifications request an immediate blackout.
  **Within five seconds without a heartbeat, the firmware blanks the LEDs** even
  if the motherboard still supplies USB power or Windows stops the app too quickly
  for its final serial write. If USB power is removed, the LEDs simply lose power.
- On wake, a previously requested connection is retried every two seconds for up
  to 30 seconds while USB returns. This works even when Auto-connect is off.
  Deliberately clicking Disconnect cancels this wake retry. Auto-connect, when
  enabled, also retains its normal retry behaviour.
- A reconnect reapplies the saved brightness and colours. Blackout never saves
  brightness zero. Local mute state is left alone by blackout, but a board reset
  still resets volatile firmware state in the usual way.
- Quit, Disconnect, a crashed app or unplugging the data connection also stops
  the heartbeat, so a still-powered mixer goes dark. The sliders and switches
  continue to be scanned while the LEDs are blanked.
- Power-on/reset still plays the restrained blue sequence. After a five-second
  startup grace period, LEDs stay dark until the app sends a heartbeat. This is
  intentional, including when the PC is off but its USB ports remain powered.
  The blue animation is a board-startup animation, not a PC-ready confirmation.

The matching app is required: the v1.0.0 EXE sends no heartbeat, so the new firmware
goes dark after five seconds with that app. With old firmware, the new app attempts
`B,0` on disconnect/suspend, but reliable loss-of-host detection requires the
firmware update. Do not rely on USB power disappearing when Windows sleeps.

## Protocol and implementation

Serial remains 9600 baud, newline-delimited ASCII. `B`, `C`, `E` and the nine-field
input frame keep their previous meaning. Two exact commands are added:

| Command | Effect |
| --- | --- |
| `H,1\n` | Renew the five-second host lighting lease and clear explicit blackout |
| `H,0\n` | Explicit blackout until the next heartbeat |

The existing serial worker sends the heartbeat after applying settings, and tries
`H,0\nB,0\n` before closing. There is one serial writer; the UI and Windows power
callback request a stop without waiting for I/O. The timeout uses unsigned millis
subtraction so timer wraparound is handled. No EEPROM writes are added.

## Checks

The Python regression suite and a hidden-window integration check cover heartbeat
renewal, blackout, preserving saved brightness, wake/retry with Auto-connect off,
rapid suspend/resume, cancelled shutdown and deliberate disconnect. Integration
checks use simulated serial/audio and messages to the test app's own window;
they do not put Windows to sleep. The firmware compiles for
`arduino:avr:nano:cpu=atmega328` with AVR core 1.8.8 and NeoPixel 1.15.5
(9998 bytes flash, 313 bytes static RAM). Compile-time checks cover timeout
boundaries, renewal, explicit blackout and timer wraparound. The builder also
reported successful testing on the physical mixer.

After flashing, check on your own PC:

1. Connect; check colours, brightness, all sliders/buttons and the audio visualizer.
2. Hide the window with X; the LEDs should continue working while it runs in tray.
3. Sleep or hibernate Windows. If USB stays powered, LEDs should go dark within
   five seconds. Wake Windows and confirm the previous connection and brightness
   return once USB is available.
4. Repeat with shutdown, then restart and connect. Enable Start with Windows and
   Auto-connect if you want automatic operation after signing in.
5. Quit the app or Disconnect; confirm the powered mixer goes dark. Run it again
   and reconnect; confirm brightness zero has not been saved.
6. With the app absent, power-cycle the mixer: blue startup, then dark after the
   startup grace period. Check USB-reset behaviour separately when reconnecting.

See [flashing and pinout](README.md) and [startup details](STARTUP.md).
