# Automatic LED sleep (v1.0.1)

<a id="install"></a>
For installation and compatibility, use the **[Arduino flashing guide](README.md)**.
Installing the EXE does not flash the board. This page explains LED behaviour and checks.

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

The [serial protocol reference](REFERENCE.md#serial-protocol) defines the heartbeat and blackout commands.

The existing serial worker sends the heartbeat after applying settings, and tries
`H,0\nB,0\n` before closing. There is one serial writer; the UI and Windows power
callback request a stop without waiting for I/O. The timeout uses unsigned millis
subtraction so timer wraparound is handled. No EEPROM writes are added.

## Checks

The Python regression suite and a hidden-window integration check cover heartbeat
renewal, blackout, preserving saved brightness, wake/retry with Auto-connect off,
rapid suspend/resume, cancelled shutdown and deliberate disconnect. Integration
checks use simulated serial/audio and messages to the test app's own window;
they do not put Windows to sleep. Firmware compile details are recorded under
[startup verification](STARTUP.md#verification-performed). The builder also reported
successful testing on the physical mixer.

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

See [flashing](README.md), [pinout](REFERENCE.md#hardware-and-pinout) and [startup details](STARTUP.md).
