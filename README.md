# Mixer Hub

**[Download MixerHub.exe for Windows](https://github.com/RyGuy06/mixer-hub/releases/latest/download/MixerHub.exe)**

<a id="current-status"></a>
Windows 10/11 · 64-bit · No Python installation needed. [Release notes](https://github.com/RyGuy06/mixer-hub/releases/latest).

<a id="features"></a>
<a id="about-v1"></a>
Four physical sliders for your games, music, browser and voice chat, with RGB level meters and media/Discord buttons.

## Software v1.1.0

[Calibrate slider endpoints and dead zones](docs/CALIBRATION.md), search running and remembered apps, and edit Priority lists inside the main window. Existing settings and profiles are retained. [See what changed](https://github.com/RyGuy06/mixer-hub/releases/tag/V1.1.0).

## V1.1 hardware update — 10 November 2026

I'm continuing work on V1.1 of the physical Mixer Hub. The update is planned to include a refreshed enclosure design, improved fit and tighter tolerances, and a more robust connection between the two PCBs.

The hardware release has been delayed while I resolve fit and connection issues and test the changes. Exams are next week, so progress may be slower for a little while. Development is still ongoing, and I'll share an update once the revised hardware has been tested. There is no confirmed release date yet.

<a id="download-and-setup"></a>
## Quick setup

1. Download the EXE, put it somewhere permanent, and run it.
2. Plug in the mixer using a USB data cable, then click **Connect device**.
3. Choose an app for each channel. In **Device settings**, optionally enable **Auto-connect device** and **Start with Windows**.

Closing the window with **X** keeps Mixer Hub running in the system tray. Use **Quit Mixer Hub** in the tray menu to stop it.

<a id="firmware-update--blue-startup"></a>
<a id="led-sleep-and-blue-startup"></a>
<a id="download-and-install"></a>
## Arduino firmware

Building a mixer or updating older firmware? Follow the **[Arduino flashing guide](firmware/README.md)**. Keep `MixerHub.ino`, `startup_animation.h` and `slider_calibration.h` together when flashing.

Slider calibration needs the v1.1.0 firmware once. Existing v1.0.1 firmware still supports ordinary mixing and LED sleep; if you have already flashed calibration firmware, you do not need to flash it again.

<a id="diy-hardware"></a>
## Make your own

- [Enclosure and printed parts on MakerWorld](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400)
- PCB files: [Main board](hardware/MainV2Gerbers.zip) · [Slider board](hardware/SliderV2Gerbers.zip) — one of each is needed.
- [Parts list and PCB ordering notes](hardware/README.md)

<a id="feedback"></a>
## Help

See **[Troubleshooting](docs/TROUBLESHOOTING.md)** for connection, Windows download warnings and LED issues. For bugs or suggestions, [open an issue](https://github.com/RyGuy06/mixer-hub/issues) with your app version and what happened.
