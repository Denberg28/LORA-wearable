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
| SOS button | D0 | Onboard Wio-SX1262 momentary button, active low by default |
| GNSS TX -> XIAO RX | D7 | 9600 baud NMEA, optional |
| XIAO TX -> GNSS RX | D6 | optional; not required for passive NMEA |
| Sensor supply | 3V3 / GND | use regulated 3.3 V logic, never 5 V output into GPIO |

The Wio radio also uses internal DIO2 switching and a 1.8 V TCXO, configured by
RadioLib. Do not reuse D4/D5 as I2C. The official L76K expansion may use D0 for
standby and conflict with the touch input: it is not plug-and-play with this
default wiring. Use a separately wired UART GNSS leaving D0 free.

The header-connected Wio-SX1262 V1.0 schematic shows the onboard K1 button
pulling D0 to ground through a normally-open switch, with a 10 kOhm pull-up.
`TOUCH_ACTIVE_HIGH false` is the default so this button works without a separate
sensor. To use a 3.3 V active-high momentary capacitive touch module, set
`TOUCH_ACTIVE_HIGH true`; verify D0 voltage and isolate/disconnect the onboard
button to avoid driving the module output against ground during a press.
Never drive D0 with 5 V. For touch modules configure momentary mode, not
latching/toggle. Sensor boot calibration, sweat/rain, enclosure thickness and
ESD behavior require hardware testing. Other board revisions must be inspected
before relying on the default polarity.

Source schematic: https://files.seeedstudio.com/products/113010003/Wio-SX1262%20for%20XIAO%20V1.0.pdf

No battery percentage is reported in this candidate. Battery ADC pin/divider
variants and power measurement have not been validated. The public build uses
10 dBm only as a disabled configuration example. Set permitted radio parameters
explicitly before private builds. Antenna, gain, power and applicable airtime
restrictions must be considered for the installation.
