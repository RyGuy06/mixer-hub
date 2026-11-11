# Calibrate your sliders

Use calibration if a slider does not reach exactly 0% or 100%, or reaches an end
too early. Each of the four sliders gets its own measured range and end dead zone.

## Before you start

- Run [Mixer Hub v1.1.0 or later](https://github.com/RyGuy06/mixer-hub/releases/latest).
- Install the [v1.1.0 Arduino firmware](../firmware/README.md) once if your board
  still has older firmware. Installing the EXE does not flash the Arduino.
- Connect your mixer and unmute all four channels.

The new app still supports ordinary mixing with v1.0.1 firmware. Calibration
stays disabled until the connected firmware confirms support. If you have already
flashed the calibration firmware while testing, you do not need to flash it again.

## Record the ends

1. Open **Device settings → Slider calibration → Calibrate sliders**.
2. Move all four physical sliders fully down. Hold them still, then choose
   **Record 0%**. Each slider is measured independently.
3. Move all four sliders fully up, hold them still, then choose **Record 100%**.
4. Adjust **Dead zone at each end** if needed. The default is **1%**; the allowed
   range is 0–5%. This margin snaps a small part of the measured travel at each
   end to exactly 0% or 100%.
5. **Move the sliders back to normal listening levels before choosing
   Save calibration.** Volume follows their physical position when recording ends.

Windows volume and media/Discord actions pause during recording. The mixer's
local mute switches still work. Recordings need steady, fresh readings for at
least half a second; muted channels, stale data or an invalid range cannot be saved.

**Cancel** keeps your previous calibration. **Start again** discards the draft
measurements. **Reset calibration** in Device settings restores the factory
endpoints for this connected mixer.

## Saved settings

Calibration is saved with your app settings and reapplied when the mixer
reconnects. It belongs to the physical device, so changing profiles or moving
channel cards does not move the calibration to a different physical slider.

Most boards are identified by USB serial number. If a board has no serial number,
its COM port is used; moving it to a different COM port may require calibration
again. The Arduino does not store these ranges after losing power by itself—the
app restores them on connection.

If the button says a firmware update is needed, follow the
[flashing guide](../firmware/README.md). For connection or upload problems, see
[Troubleshooting](TROUBLESHOOTING.md).

[Back to downloads](../README.md)
