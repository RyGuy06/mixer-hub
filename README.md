# Mixer Hub

A four-channel desktop volume controller built around an Arduino Nano, with a 3D-printed enclosure and a Windows companion app.

I originally made this for my own setup and use it every day. This repository brings together the downloads and DIY information for the first public version.

## Download and setup

Download **MixerHub.exe** from the [latest release](https://github.com/RyGuy06/mixer-hub/releases/latest).

1. Download and run MixerHub.exe on your Windows PC. You don't need to install Python.
2. Connect your mixer using a USB cable that supports data transfer.
3. Use the companion app to configure your channel assignments and button keybinds.

The release also includes **sketch_sep22a.ino**, the Arduino firmware for DIY builds, and **build-manifest.json**, which records build details and the executable's checksum.

Save the Arduino sketch in a folder named **sketch_sep22a** before opening it in the Arduino IDE. If your mixer already has the firmware installed, you don't need to upload it again.

## Features

- Four physical sliders for controlling individual app volumes.
- A dedicated mute button beneath each slider.
- Four strips of 10 addressable RGB LEDs.
- LEDs show the volume setting when a slider moves, then switch to that channel's audio level after about three seconds of inactivity.
- Previous track, play/pause and next track buttons.
- Two additional buttons intended for Discord mute and deafen, with configurable keybinds.
- App assignments and priorities configured through the companion software.

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

**The Windows app and Arduino firmware are available in the v1.0.0 release.** I have also downloaded and launched the Windows app on another PC.

PCB manufacturing files are available: [MainV2Gerbers.zip](hardware/MainV2Gerbers.zip) and [SliderV2Gerbers.zip](hardware/SliderV2Gerbers.zip). Each mixer needs both boards.

Printable enclosure and control files are available on [MakerWorld](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400).

The following DIY files and instructions are still being prepared:

- Complete assembly and PCB bridge-connection instructions.
- Arduino library requirements and tested board/upload settings.

The Python source and editable KiCad project files have not been uploaded.

## Feedback

For bugs or suggestions, [open an issue](https://github.com/RyGuy06/mixer-hub/issues). Include what happened, what you expected, and the app version. For connection problems, include your Nano variant and any error message if you know them.

## About V1

This is the first version of the project. The enclosure is 3D printed, and the design may change as I get feedback and develop it further.
