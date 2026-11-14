# Arcade Home Labs • StackChan Slim v1

## Objective
Create a leaner standalone StackChan based on the existing, manufacturer-supplied
XiaoZhi AI Agent, not a second ASL Companion running above it.

## Baseline and provenance
- Branch copied from verified v9 source commit b8d34ef790ae681dac830fe4554f4d349b7b3943.
- Compiles against the unchanged official M5Stack StackChan 1.6.2 source at
  28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400.
- The previously completed v5, v8 and v9 binaries and approved animation art
  remain in their original release branches. None is overwritten.

## Deliberately excluded
- Entire AHL custom Companion integration, extra mode, local memory vector
  feature, background presence watcher, custom face-player app and greeting.
- Standalone Avatar demo, Dance, EZData, App Centre and template application
  compilation. These are excluded from the linked firmware, not deleted from
  the original pinned upstream repository or previous Arcade Home Labs builds.
- Unused navigation paths in the normal power-on experience.

## Deliberately retained
- Official XiaoZhi conversation AI and original face, its current wake word,
  microphone, speaker, Wi-Fi, camera and existing image tools.
- Original StackChan motors, sensors, animation and movement primitives.
- ESP-NOW Remote receiver app and underlying radio support for future work.
- Setup, launcher and recovery access through the existing Home/warm reboot
  path in XiaoZhi mode. Default power-on loads the AI Agent directly.
- NVS storage: Wi-Fi, pairing, volume and user settings. Never use ERASE.
- Same bootloader, partition table, OTA metadata and generated-assets images
  expected by the existing flashing procedure.

## Important reality checks
- **Compile success does not prove better audio, RAM savings or camera success.**
  RAM usage requires serial measurements on physical hardware, including
  free internal SRAM, largest allocatable block and free PSRAM.
- Removing launcher apps may save flash but little runtime RAM, since the
  factory firmware already unloads the launcher before starting XiaoZhi.
- This *first slimming pass* does not implement wake-word-free continuous chat,
  move the custom cyan face onto original XiaoZhi, or integrate ESP-NOW
  remote with the live AI. Those are separate future changes.
- This edition uses factory voice playback and the user's existing persisted
  volume preference, not the untested v9 custom ASL loudness patch.

## Boot and safe recovery
Normal power-on -> native XiaoZhi.
The manufacturer's Home control -> warm reboot into reduced launcher
(AI Agent, ESP-NOW Remote, Setup), then select as needed.

## Flash notes
Use the same verified ESP Flash Download Tool procedure and original
addresses for the five binary images:
  bootloader.bin          0x0
  partition-table.bin     0x8000
  ota_data_initial.bin    0xD000
  stack-chan.bin          0x20000
  generated_assets.bin    0xA00000
SPI mode DIO / 80 MHz / 16 MB, and **do not erase**. Unmodified originals
remain available for recovery.
