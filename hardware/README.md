# Build your own Mixer Hub

The build requires soldering. Start with the [printed enclosure and controls on MakerWorld](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400), then the parts below.

## Parts list — one mixer

These are the component listings used by the builder, with the selected options.

| Component | Quantity | Listing / selected option |
| --- | ---: | --- |
| B103 10 kΩ slide potentiometers | 4 | [MWSS PCB Store](https://www.aliexpress.com/item/1005007168285575.html) |
| Brown mechanical keyboard switches | 9 | [Switch listing](https://www.aliexpress.com/item/1005010773758011.html) — “Tea switch 30pcs”; exact manufacturer/model unknown |
| WS2812B LEDs | 40 | [LED listing](https://www.aliexpress.com/item/1005007989207832.html) — DC5V, black PCB, 144 LEDs/m, IP30; four sections of 10 |
| Arduino Nano | 1 | [Board listing](https://www.aliexpress.com/item/1005007842646963.html) — exact purchased variant and USB interface still to be confirmed |
| Custom PCBs | 2 | One [MainV2Gerbers.zip](MainV2Gerbers.zip) and one [SliderV2Gerbers.zip](SliderV2Gerbers.zip) |
| 3D-printed enclosure and controls | 1 set | [MakerWorld files](https://makerworld.com/en/models/3527114-mixer-hub-4-channel-desktop-volume-controller#profileId-4032400); complete printed-parts inventory still to be confirmed |
| USB data cable | 1 | Match your Nano's connector and check enclosure clearance; a specific cable has not been confirmed |

Confirm slider dimensions, travel and pin spacing against the design before substituting parts. **B103 alone does not identify a slider that will physically fit.**

## PCBs and assembly

Both boards are two-layer, 1.6 mm designs. See **[PCB ordering and bridge connections](gerbers/README.md)** before ordering. Each mixer needs one of each board.

There are no screws or heat-set inserts. Complete assembly instructions, the bridge-connection photo/diagram and the method of securing the enclosure/components are still being documented. Do not assume the enclosure is snap-fit or glued.

## Firmware

Use the **[Arduino flashing guide](../firmware/README.md)**. The [technical reference](../firmware/REFERENCE.md#hardware-and-pinout) lists pins and LED wiring order.

[Back to downloads](../README.md)
