# Mixer Hub

A four-channel desktop volume controller built around an Arduino Nano, with a 3D-printed enclosure and a Windows companion app.

I originally made this for my own setup and use it every day. This repository brings together the downloads and DIY information for the first public version.

## Download and setup

Download **MixerHub.exe** from the [latest release](https://github.com/RyGuy06/mixer-hub/releases/latest).

1. Download and run MixerHub.exe on your Windows PC. You don't need to install Python.
2. Connect your mixer using a USB cable that supports data transfer.
3. Use the companion app to configure your channel assignments and button keybinds.

The **v1.0.1 release** includes the updated Windows app, a firmware ZIP with both required sketch files, and a checksum/build manifest. **Update both the EXE and Nano firmware for automatic LED sleep.** Your profiles, colours and saved brightness are retained.

## LED sleep and blue startup

The mixer now goes dark when Windows sleeps, hibernates or shuts down, even if the USB port stays powered. The app sends a small heartbeat while connected, including in the system tray. After five seconds without one, firmware blanks the LEDs. The app also requests immediate blackout on power notifications and retries the previous connection on wake. Deliberate Disconnect is respected.

With no companion running, power-on still plays the blue sequence, then the LEDs go dark after a five-second startup grace period. The older EXE does not send heartbeats, so install the matching v1.0.1 app. See the [LED sleep guide](firmware/POWER.md) for full behaviour and checks.

## Firmware update — blue startup

The current firmware fills all four unmuted LED columns upward in blue, briefly holds, then fades into the current volume/audio display over about **1.6 seconds**. Sliders, buttons and serial processing continue during the sequence.

**Installing this update requires reflashing the Arduino. Updating or running the Windows app alone will not replace the rainbow animation.**

### Download and install

1. Download **MixerHub-firmware-v1.0.1.zip** from the [latest release](https://github.com/RyGuy06/mixer-hub/releases/latest) and extract it. Alternatively, choose **Code → Download ZIP** on the repository's main page and extract the repository.
2. In the firmware ZIP, find `MixerHub/` (or `firmware/MixerHub/` in the repository ZIP). Keep these two files together in that exact folder:

   ```text
   MixerHub/
     MixerHub.ino
     startup_animation.h
   ```

3. Open **MixerHub.ino** in Arduino IDE. **startup_animation.h** is a helper header that the IDE compiles with the sketch; you do not install or flash it separately. If the IDE reports a missing header, check that both files are extracted into the same `MixerHub` folder with their exact names.
4. Install **Arduino AVR Boards** in Boards Manager and **Adafruit NeoPixel** in Library Manager.
5. Quit Mixer Hub using **Quit Mixer Hub** in the system tray or Settings, and close Serial Monitor so the USB port is free. Clicking X only hides the companion in the tray.
6. Select **Arduino Nano**, the USB port, and the processor/bootloader matching your actual board. The sketch targets the classic **ATmega328P Nano**; the exact purchased board variant still needs confirmation.
7. Choose **Verify**, then **Upload**. Power-cycle with the app closed to check the blue fill and fade, then reconnect the companion and check the four sliders, nine buttons and normal LEDs.

The animation runs when the board powers up or resets. Opening USB serial may also reset a compatible Nano and replay it. **Blue startup is not a PC-connected or audio-ready indicator.** With the app absent, the animation briefly finishes on the board's normal volume display, then the LEDs go dark at the five-second startup grace limit.

The sketch compiled for the classic Nano with AVR core **1.8.8** and Adafruit NeoPixel **1.15.5**. The builder has tested this update successfully on the physical mixer. Check LED direction, USB reset and sleep/wake behaviour on your own setup.

See [firmware installation and pinout](firmware/README.md) and [startup behaviour and hardware checks](firmware/STARTUP.md).

## Features

- Four physical sliders for controlling individual app volumes.
- A dedicated mute button beneath each slider.
- Four strips of 10 addressable RGB LEDs.
- LEDs show the volume setting when a slider moves, then switch to that channel's audio level after 1.5 seconds of inactivity.
- Previous track, play/pause and next track buttons.
- Two additional buttons intended for Discord mute and deafen, with configurable keybinds.
- App assignments and priorities configured through the companion software.
- Automatic LED sleep, saved brightness restore and wake reconnection.

## DIY hardware

Building your own requires soldering. These are the component listings I used; select the options below when ordering.

| Component | Quantity per mixer | Listing / selected option |
|---|---:|---|
| B103 10 kΩ slide potentiometers | 4 | [Slider listing](https://www.aliexpress.com/item/1005007168285575.html) — MWSS PCB Store |
| Brown mechanical keyboard switches | 9 | [Switch listing](https://www.aliexpress.com/item/1005010773758011.html) — “Tea switch 30pcs” |
| WS2812B LED strip | 40 LEDs | [LED listing](https://www.aliexpress.com/item/1005007989207832.html) — DC5V, black PCB, 144 LEDs/m, IP30; four sections of 10 LEDs |
| Arduino Nano | 1 | [Board listing](https://www.aliexpress.com/item/1005007842646963.html) — exact purchased variant still to be documented |
| Custom PCBs | 1 main + 1 slider board | See [PCB ordering and bridge connections](hardware/gerbers/README.md) |
| 3D-printed enclosure and controls | 1 set | [Printable files and print profile on MakerWorld](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400) |
| USB data cable | 1 | Match the connector on your Nano and check enclosure clearance |

The slider dimensions, travel and pin spacing, switch model, and exact Nano variant still need documenting. B103 alone does not identify a mechanically compatible slider.

The enclosure uses no screws or heat-set inserts. Assembly instructions will explain how the printed parts and components are secured.

## Current status

**The matching Windows app and two-file Arduino firmware are available in the v1.0.1 release.** I have also downloaded and launched the Windows app on another PC.

PCB manufacturing files are available: [MainV2Gerbers.zip](hardware/MainV2Gerbers.zip) and [SliderV2Gerbers.zip](hardware/SliderV2Gerbers.zip). Each mixer needs both boards.

Printable enclosure and control files are available on [MakerWorld](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400).

The following DIY files and instructions are still being prepared:

- Complete assembly and PCB bridge-connection instructions.

Arduino library requirements and the compiled board/upload settings are documented in the [firmware guide](firmware/README.md).

The Windows companion source and repeatable build script are included. On Windows x64 with Python 3.14.7:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe tools/check_release.py
```

Build outputs go in `dist/`; personal settings and build output are excluded from Git. GitHub Actions runs the tests and builds/validates the EXE and firmware ZIP before publishing a versioned release. See [v1.0.1 release notes](docs/releases/v1.0.1.md). Editable KiCad project files have not been uploaded.

## Feedback

For bugs or suggestions, [open an issue](https://github.com/RyGuy06/mixer-hub/issues). Include what happened, what you expected, and the app version. For connection problems, include your Nano variant and any error message if you know them.

## About V1

This is the first version of the project. The enclosure is 3D printed, and the design may change as I get feedback and develop it further.
