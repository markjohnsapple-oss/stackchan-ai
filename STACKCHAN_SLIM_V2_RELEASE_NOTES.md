# Arcade Home Labs | StackChan Slim v2: native hands-free voice

## Master / recovery
- Based on verified working Slim v1 at commit `1bba0c70328efd61fbf45d011296d1abf7a24134`.
- Uses exact official StackChan v1.6.2 `28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400` and pinned XiaoZhi v2.5.2 with the manufacturer's compatibility patch.
- Slim v1 original firmware and face-art archives remain unchanged.

## Improvements included in test build
1. The original, slimmed XiaoZhi AI starts listening automatically after Wi-Fi and successful cloud activation: no "Hey StackChan" wake word.
2. The original acoustic front-end retains its VAD/echo cancellation, but the WakeNet/MultiNet detector is not initialised. This saves the detector's runtime allocations without disabling normal voice processing.
3. Microphone safety: tap the AI face to pause audio listening, and tap again to resume. This uses the existing touch callback and original AI state machine. It is not a hardware microphone kill-switch.
4. Recovery after an ordinary channel closure attempts reconnection only when online, activated, idle, not paused, and with at least 8s between attempts. This is a normal cloud AI connection, not an offline private assistant.
5. Serial memory diagnostics report free internal SRAM, largest internal block, free PSRAM, and largest PSRAM block every 10 seconds.

## Kept intact
- Successfully tested Slim v1 camera and visual descriptions, native audio/speech, XiaoZhi connection, display and eyes, motors, remote-control app, recovery settings, persistent Wi-Fi and volume preferences.
- Manufacturer OTA partition layout and flash image addresses.
- No additional ASL Companion system, camera watcher, wake-up GIF player or second listening process.

## MicroSD long-term memory: **NOT YET ENABLED**
- Your 16GB microSD card is suitable for long-term summaries.
- Official M5Stack documentation specifies GPIO35 as **SD MISO**, but the original StackChan display driver also configures **GPIO35 as display D/C** (while sharing MOSI GPIO37 and SCLK GPIO36). The active display owns this pin in the verified firmware.
- Adding an independent standard SD SPI driver blindly could conflict electrically or disrupt the screen/camera. Slim v2 deliberately does not touch the card, format it or store memories on it.
- Next step after hands-free verification: validate a safe bus arbitration scheme / board-specific card interface on real hardware, then add bounded persistent memory files and voice-controlled review/forget operations.
- Card capacity does **not** increase internal or PSRAM memory.

## Testing limits
GitHub compile and image verification only; the new live listening state machine must be tested on the real StackChan before we can claim it works.
Record: standby heap values, idle microphone state, smoothness during 2-minute conversation, tap-to-pause, camera capture and spoken response, reconnection following network interruption.
Do not erase NVS or overwrite verified Slim v1 recovery files.
