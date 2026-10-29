# Mixer Hub

A four-channel desktop volume controller built around an Arduino Nano, with a 3D-printed enclosure and a Windows companion app.

I originally made this for my own setup and use it every day. This repository is where I’m putting the software, firmware and DIY build files as I prepare the first public version.

## Download

Download **MixerHub.exe** from the [latest release](https://github.com/RyGuy06/mixer-hub/releases/latest).

The Windows app is packaged as an executable, so you don’t need to install Python. Arduino firmware for DIY builds is also included in the release.

Complete DIY assembly instructions are still being prepared.

## Features

- Four physical sliders for controlling individual app volumes.
- A dedicated mute button beneath each slider.
- Four strips of 10 addressable RGB LEDs.
- LEDs show the volume setting when a slider moves, then switch to that channel’s audio level after about three seconds of inactivity.
- Previous track, play/pause and next track buttons.
- Two additional buttons intended for Discord mute and deafen, with configurable keybinds.
- App assignments and priorities configured through the companion software.

## Current status

The hardware and software are working in my own setup. I’m currently refining the software and preparing the downloads and build instructions for V1.

**A packaged Windows download and complete DIY instructions are not available here yet.** I’ll add links as they become available.

## Hardware

Each controller uses:

- An Arduino Nano.
- Four B103 10 kΩ slide potentiometers.
- Nine brown mechanical keyboard switches.
- Forty WS2812B addressable LEDs.
- Two custom PCBs.
- A 3D-printed enclosure and controls.

Building your own requires soldering.

## Planned files

- Windows companion app and Python source.
- Arduino firmware.
- Gerber files for both PCBs.
- Parts list and assembly instructions.
- A link to the printable files on MakerWorld.

## About V1

This is the first version of the project. The enclosure is 3D printed, and the design may change as I get feedback and develop it further.
