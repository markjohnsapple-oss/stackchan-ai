# Arcade Home Labs | ARLO Slim v1 Hands-Free + Local Identity

## Proven working master
- Exact user-installed source package: AHL_StackChan_Slim_v1_Compiled_Firmware (1).zip
- Verified application sha256: f89fc5f77c1b8bf6bb3c1318a7db26d33aa98258fb034b71bd385c73591071ef
- Manufacturer source pinned at StackChan 1.6.2: 28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400
- This is a separate new build. The uploaded master and original GitHub branch remain untouched.

## Exactly two requested updates
1. Wake phrase is no longer required. The **original XiaoZhi** microphone and AI conversation automatically begin listening when Wi-Fi, AI activation and the cloud protocol are ready. On idle, reopen attempts are limited to one per eight seconds. All original voice processing, VAD, camera and motor code is preserved.
2. Device display changes: **ARLO** appears on the startup screen, in the AI launcher and in the Setup AI section.

## Important: spoken personality
The online AI's *spoken self-identification* and personality are controlled by the **StackChan World AI Agent profile**, not by a plain-text constant in this local firmware. The firmware alone cannot guarantee that the cloud AI will stop calling itself StackChan. Please rename the AI Agent profile to **ARLO** in StackChan World if the online AI still introduces itself by its old name. No cloud account settings are modified by this build.

## Preservation
Wi-Fi provisioning, account and pairing identifiers, original api.tenclass.net cloud/OTA configuration, bootloader, partition map, generated assets, NVS, XiaoZhi AI logic, voice output, mic VAD/AEC, camera, face artwork, servo/motor logic, launcher recovery and ESP-NOW Remote have not been replaced. Names used inside manufacturer API identifiers and class names MUST remain intact to protect hardware and cloud pairing. No Bluetooth or HTTP joystick features were added.

## Flash and test
Use the same known-good ESP Flash Download Tool procedure and addresses:
- bootloader/bootloader.bin = 0x0
- partition_table/partition-table.bin = 0x8000
- ota_data_initial.bin = 0xD000
- stack-chan.bin = 0x20000
- generated_assets.bin = 0xA00000

DIO / 80 MHz / 16 MB. **Do not ERASE or reset NVS.**

GitHub compilation and static checks cannot confirm actual mic, Wi-Fi or voice behaviour until flashed and tested on ARLO. Keep the verified Slim v1 package available for immediate rollback.
