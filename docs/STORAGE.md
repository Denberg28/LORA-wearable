# First commissioning and persistent SOS state

## Defect corrected in 0.1.0-rc.4

Do not deploy rc.1–rc.3. Their normal startup called the pinned Seeed BSP's
`InternalFS.begin()`. In Seeed nRF52 1.1.13 this method erases the filesystem
region and reformats when mounting fails. That can discard a saved SOS and
roll back ordering counters. The earlier documentation's fail-on-corruption
claim did not cover that BSP behavior.

Normal rc.4 startup explicitly calls the non-formatting `Adafruit_LittleFS`
base implementation. Mount failure, no state record, any corrupt record, or
counter exhaustion produces `persistent_state_error` and disables RF. It
never initializes missing state as an idle device. Native regression checks
exercise the actual dispatch helper with an auto-erasing derived filesystem;
physical flash/power-cut validation remains required.

Primary source: [pinned BSP implementation](https://github.com/Seeed-Studio/Adafruit_nRF52_Arduino/blob/1.1.13/libraries/InternalFileSytem/src/InternalFileSystem.cpp).

## New device only

This is a deliberate commissioning operation on a **new, unenrolled device**.
Never use it to fix corrupt storage on an existing identity. It may erase an
unmountable filesystem. A repaired/replaced device must use a new device ID or
a newly provisioned network and monitor database, so reset counters cannot be
confused with old traffic.

1. Compile the `storage-init` configuration with `python scripts/build_firmware.py`,
   or open the same sketch in Arduino IDE with a copy of `Config.example.h` named
   `Config.h`, setting `INITIALIZE_NEW_STORAGE true`. No network key is needed.
2. Upload that image to the new device. It has no RF initialization/transmission.
3. Open Serial Monitor at 115200 baud, with newline enabled. Send exactly
   `INITIALIZE NEW DEVICE`. Existing readable `/lw0` or `/lw1` records cause
   `existing_state_refused`; they are never overwritten by the initializer.
4. Require `initialized_upload_normal_firmware`. A verified initial idle record
   with generation zero has been written. Green LED indicates this completion.
5. Close Serial Monitor. Upload the device's privately provisioned **normal**
   firmware, with `INITIALIZE_NEW_STORAGE false` (or omitted for older private
   configs). Normal startup advances the generation before enabling RF.
6. Exercise SOS, reboot, cancellation and power-cut tests in HIL.md. Remove the
   maintenance image from operational devices; it cannot act as a wearable/base.

Existing valid rc.3 records are format-compatible with rc.4: upload normal
firmware without initialization. Preserve private configs and PC data first.
Do not downgrade to rc.3 to bypass a storage fault. Diagnose/replace the device
and deliberately re-enroll under a new identity instead.
