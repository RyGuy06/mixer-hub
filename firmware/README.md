# Flash the Arduino

Use this guide for a DIY build or firmware update. An already updated mixer does not need flashing each time you run the app. Installing the EXE does not update the Arduino.

## Download the complete firmware folder

Download **[MixerHub-firmware-v1.1.0.zip](https://github.com/RyGuy06/mixer-hub/releases/download/V1.1.0/MixerHub-firmware-v1.1.0.zip)** and extract it. Keep this folder intact:

```text
MixerHub/
  MixerHub.ino
  startup_animation.h
  slider_calibration.h
```

Open **MixerHub.ino**, not the header. Arduino IDE compiles both headers with the sketch; they are not separate uploads. All three files must stay in the same `MixerHub` folder.

The same files are available in [MixerHub/](MixerHub/) in this repository. Use the complete current folder, not the old standalone `sketch_sep22a.ino` from v1.0.0.

## Flash

1. Install [Arduino IDE](https://www.arduino.cc/en/software/). In Boards Manager install **Arduino AVR Boards**; in Library Manager install **Adafruit NeoPixel**.
2. Quit the Windows app using **Quit Mixer Hub** in its tray menu or Settings, and close Serial Monitor. Clicking X only hides the app and can leave the USB port busy.
3. Open the extracted **MixerHub/MixerHub.ino**.
4. Select **Arduino Nano**, the correct USB port, and the processor/bootloader matching your board. The sketch targets the classic **5 V ATmega328P Nano**. Some boards need **ATmega328P (Old Bootloader)**.
5. Click **Verify**, then **Upload**.
6. Run the matching [v1.1.0 Windows app](https://github.com/RyGuy06/mixer-hub/releases/download/V1.1.0/MixerHub.exe), connect, and check all four sliders, mute buttons, media buttons and LEDs.

**Slider calibration needs the v1.1.0 app and firmware.** After connecting, follow the [calibration guide](../docs/CALIBRATION.md). If your board already has this calibration firmware, there is no need to flash again.

The v1.1.0 EXE still supports ordinary mixing and LED sleep with v1.0.1 firmware, but calibration stays disabled. The older v1.0.0 EXE has no lighting heartbeat. Existing app profiles and saved brightness are retained when replacing the EXE.

After flashing, expect a brief blue startup. With no app connected, the LEDs go dark after five seconds. The animation indicates a board reset, not a confirmed PC connection.

For a missing-header error, check that you extracted the ZIP and kept all three files together. For a busy port, missing device or upload problem, see **[Troubleshooting](../docs/TROUBLESHOOTING.md)**.

## Hardware and pinout

See the [pinout and wiring reference](REFERENCE.md#hardware-and-pinout) and [parts list](../hardware/README.md). The exact purchased Nano variant and USB interface chip still need documenting.

## Serial protocol

The [technical reference](REFERENCE.md#serial-protocol) covers the unchanged input frame and LED commands, including the host-lighting heartbeat.

## More detail

- [LED sleep and wake behaviour](POWER.md)
- [Blue startup timing and hardware checks](STARTUP.md)
- [Arduino's board and upload guide](https://docs.arduino.cc/software/ide-v2/tutorials/getting-started/ide-v2-uploading-a-sketch/)

[Back to downloads](../README.md)
