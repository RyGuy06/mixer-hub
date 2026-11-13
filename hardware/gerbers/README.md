# PCB manufacturing files

## V1.1 (recommended for new builds)

| Board | Gerber and drill ZIP |
| --- | --- |
| Button board (main board with Arduino Nano) | [MixerHub-V1.1-Button-Gerbers.zip](../MixerHub-V1.1-Button-Gerbers.zip) |
| Slider board (sliders and RGB LEDs) | [MixerHub-V1.1-Slider-Gerbers.zip](../MixerHub-V1.1-Slider-Gerbers.zip) |

Order one of each board from the same revision. Open each file link and use GitHub's download button, then upload each ZIP separately to your PCB manufacturer. Both boards use two copper layers and 1.6 mm board thickness. The nominal outlines are 99.5 × 60 mm for the button board and 99.5 × 90.5 mm for the slider board.

### Connecting the V1.1 boards

V1.1 replaces the edge-pad solder bridges with a row of seven plated through-holes on each board. The footprints use 2.54 mm pitch and 1.0 mm drill holes. Fit matching headers and a cable, or solder seven short, flexible wires directly through the holes. Support each board in the enclosure and leave enough slack that the wires and solder joints carry no mechanical load from the boards.

| Pin | Signal |
| --- | --- |
| 1 | 5V |
| 2 | DIN (LED data) |
| 3 | S1 |
| 4 | S2 |
| 5 | S3 |
| 6 | S4 |
| 7 | GND |

Match each signal on the button board to the same signal on the slider board. Check the orientation at both ends before soldering.

## V1 archive (strongly discouraged for new builds)

**Use V1.1 for new builds.** V1 connects the boards by soldering directly across copper pads at the board edges. The pads can lift easily when the boards move or flex, breaking the connection. The V1 files are kept for reference and existing builds.

| Board | Gerber and drill ZIP |
| --- | --- |
| Button board (main board with Arduino Nano) | [MixerHub-V1-Button-Gerbers.zip](../MixerHub-V1-Button-Gerbers.zip) |
| Slider board (sliders and RGB LEDs) | [MixerHub-V1-Slider-Gerbers.zip](../MixerHub-V1-Slider-Gerbers.zip) |

These archives were previously named `MainV2Gerbers.zip` and `SliderV2Gerbers.zip`. If a manufacturer asks about the overhanging bridge pads on **V1**, those pads are intentional.

[Back to Mixer Hub](../../README.md)
