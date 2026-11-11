# Wiring and configuration

Target: Seeed XIAO nRF52840, Seeed nRF52 non-mbed BSP, header-connected Wio-SX1262
as supplied in nRF52840 kit SKU 102010710. Verify silkscreen/schematic revision.
The ESP32-S3 B2B module has different assignments and is not supported here.

| Function | XIAO pin | Notes |
|---|---|---|
| LoRa DIO1 | D1 | interrupt |
| LoRa reset | D2 | active low |
| LoRa busy | D3 | busy input |
| LoRa NSS | D4 | chip select |
| External RX gate | D5 | RadioLib RF switch RX enable |
| SPI SCK / MISO / MOSI | D8 / D9 / D10 | board SPI |
| Touch output | D0 | 3.3 V momentary digital, active high default |
| GNSS TX -> XIAO RX | D7 | 9600 baud NMEA, optional |
| XIAO TX -> GNSS RX | D6 | optional; not required for passive NMEA |
| Sensor supply | 3V3 / GND | use regulated 3.3 V logic, never 5 V output into GPIO |

The Wio radio also uses internal DIO2 switching and a 1.8 V TCXO, configured by
RadioLib. Do not reuse D4/D5 as I2C. The official L76K expansion may use D0 for
standby and conflict with the touch input: it is not plug-and-play with this
default wiring. Use a separately wired UART GNSS leaving D0 free.

An active-low physical momentary button to ground is supported by
`TOUCH_ACTIVE_HIGH false` and the internal pull-up. For touch modules, configure
momentary mode, not toggle/latch. Sensor boot calibration, sweat/rain, enclosure
thickness and electrostatic behavior require testing. A user button may be
missing on some kit revisions; this project expects an external input.

No battery percentage is reported in this candidate. Battery ADC pin/divider
variants and power measurement have not been validated. The public build uses
10 dBm only as a disabled configuration example. Set permitted radio parameters
explicitly before private builds. Antenna, gain, power and applicable airtime
restrictions must be considered for the installation.
