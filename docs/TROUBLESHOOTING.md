# Mixer Hub troubleshooting

[Download the Windows app](https://github.com/RyGuy06/mixer-hub/releases/latest/download/MixerHub.exe) · [Arduino flashing guide](../firmware/README.md)

## Windows shows a download warning

The V1 EXE is unsigned, so Windows SmartScreen may show “Windows protected your PC.” Confirm that you downloaded it from **RyGuy06/mixer-hub** and trust the file before choosing **More info → Run anyway**, if offered.

You do not need Python or the repository's source ZIP to run MixerHub.exe.

## The mixer will not connect

- Use a USB cable that supports data, not a charging-only cable.
- Close Arduino Serial Monitor and other programs using the device's serial port.
- In **Device settings**, refresh the device list and select your mixer. A remembered device that is absent will not automatically switch to another board.
- If Windows does not list the board, check Device Manager and the driver requirements for your actual Nano/USB interface. The exact purchased board variant is not yet documented.

Enable **Auto-connect device** to connect on launch and retry after unplugging. Clicking Disconnect pauses those attempts for the current session; click Connect to resume.

## A game or app is missing

Play some audio in that app, then use **Refresh apps**. Mixer Hub detects Windows audio sessions on the default playback device. A program without an audio session may not appear yet.

With a Priority list, the first available app wins, even if it is currently silent. Add Master last only if you want a system-volume fallback.

## The window disappeared or a second launch does nothing

**X** hides Mixer Hub to the system tray; check the hidden-icons menu near the clock. Open Mixer Hub from its tray icon. Only one copy runs per Windows session.

To replace the EXE or free the port for flashing, choose **Quit Mixer Hub** from the tray menu or Settings.

## Arduino upload fails

- **Missing startup_animation.h or slider_calibration.h:** extract the complete firmware ZIP and keep both headers beside `MixerHub.ino` inside `MixerHub/`. Do not download only the sketch or open files inside the ZIP.
- **Port busy:** quit Mixer Hub from its tray menu and close Serial Monitor.
- **Board/processor error:** choose the classic Nano, your USB port and the bootloader that matches your board. Some clones need **ATmega328P (Old Bootloader)**.

Follow the single **[flashing guide](../firmware/README.md)** for the complete sequence.

## LEDs go dark, stay on, or do not return after wake

The current firmware intentionally goes dark within five seconds without the connected app, even when USB power remains on. For LED sleep to work reliably, use the **v1.0.1 or later app and heartbeat-capable firmware**.

A connection that was active before sleep is retried for up to 30 seconds after wake. If USB takes longer, click Connect; Auto-connect provides ongoing retries when enabled. A deliberate Disconnect is respected.

See **[LED sleep behaviour and checks](../firmware/POWER.md)** for details, and **[startup behaviour](../firmware/STARTUP.md)** if the question concerns the blue animation or a USB reset.

## A slider does not reach 0% or 100%

Use [Slider calibration](CALIBRATION.md) in Device settings. Update both the app and firmware to v1.1.0 to enable it. Unmute all four channels and hold the sliders still when recording. Move the sliders back to normal listening levels before saving.

## Resizing or changing monitors pauses briefly

The app holds its content layout during a border drag, then redraws at the final size. Different monitor scaling can still cause a noticeable pause after dropping the window. If reporting a problem, include each monitor's resolution, scaling percentage and graphics/dock connection.

## Settings, logs and support

The packaged app stores settings in `%APPDATA%\MixerHub\mixer_config.json` and logs in `%APPDATA%\MixerHub\MixerHub.log`. Back up settings before changing or removing them. Logs rotate automatically.

[Open an issue](https://github.com/RyGuy06/mixer-hub/issues) with your app version, Windows version, what happened, and any relevant log excerpt or error message. Review logs before posting them publicly.
