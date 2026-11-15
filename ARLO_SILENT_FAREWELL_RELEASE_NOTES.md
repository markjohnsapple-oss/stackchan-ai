# ARLO Silent Farewell Firmware

## Verified master preserved
Builds on the successful ARLO Slim v1 wake-free / on-device name branch and the exact Slim v1 bootloader, partition table, OTA metadata, flash manifests and generated assets. The newly compiled app is the only flash image changed.

## Firmware adjustment
The server may produce an unprompted goodbye after inactivity. In the XiaoZhi server protocol, ordinary conversation replies normally follow an STT (recognised user speech) message, while its idle end_prompt produces TTS without new STT. This build identifies TTS that starts at least 20 seconds after the preceding reply/session start **without fresh STT**, and suppresses both its audio and on-screen subtitle. The native AI then continues or reopens according to the original existing logic. No new timers, threads, sensors, HTTP servers, or custom AI components.

## Preserved
Existing ARLO boot/launcher identity, wake-free listening, Wi-Fi and OTA, original cloud and microphone audio, camera and MCP tools, motors, face, memory/NVS, setup and ESP-NOW recovery.

## Testing and limits
GitHub validates compile, image hashes and feature markers. Real-world farewell suppression and ordinary conversation quality must be verified on the physical ARLO. Third-party cloud behavior may vary; a server that emits unsolicited TTS with a synthetic STT or within 20 seconds cannot be perfectly distinguished from normal replies by this rule. No cloud account settings have been modified.

## Installation
Use the same five-image flash offsets and settings as the working master. Do not ERASE NVS. Keep the previous successful ARLO ZIP for rollback.
