# Arcade Home Labs StackChan ASL Companion: firmware build handover

## Source lineage
- GitHub repository: `markjohnsapple-oss/stackchan-ai`
- This **isolated build branch** starts from the existing user's main branch at `1782d8a9ad898db04c06f912acdd357d6c4eb063`.
- Official M5Stack StackChan 1.6.2 source revision: `28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400`.
- User's supplied original firmware ZIP SHA-256: `fbafe96ac7cdc6a2530d7a35b871ef8a40e257c1fd29ec9a2badbbb09b7b8984`.
- **Approved ASL Companion v4 local source ZIP** SHA-256: `3170052c03ca44bf55d6b04156c342ad169a424c128e8bd3565147df28795925`.

## Build currently configured
This workflow compiles the existing companion-brain branch code, **not** the separate ASL v4 visual/voice patch. Its output must never be labelled as the final ASL v4 firmware.

## Safe next integration
Copy the exact approved v4 package source and encoded animation assets into an isolated branch. Apply its safe patcher only against the verified upstream source after checking coexistence with the existing companion-brain patch. Resolve modifications to shared HAL and display files explicitly; do not replace the latest code or drop features. Compile via ESP-IDF 6.1 and check firmware partition size. Validate behaviour on physical ESP32-S3 hardware before recommending flashing.

## Privacy and preservation
Do not commit private transcripts, medical details, API keys, user memories, or credentials to this public repository.
Do not touch the original 1.6.2 binary, the `main` branch or the original M5Stack firmware source. Do not substitute generated artwork for the user's approved three GIFs or replace their approved voice sample.
