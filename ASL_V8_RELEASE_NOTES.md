# Arcade Home Labs | StackChan ASL Companion v8 | Face-only update

Built from the exact v7 Git commit c7001452a84a07ecde9bf470e635fbd6daf3c58b
on a separate branch. The original v7 firmware and v5 recovery copy are unchanged.

CHANGED
- Wake-up face animation: new cyan eyes/eyebrows/mouth only, 9 frames.
- Idle face animation: corrected eyes with natural blink and steady smile, 9 frames.
- Talking face animation: expressive mouth movement, 12 frames.
All graphics use 320x240 RGB565 48-colour per-frame indexed LZ4. No extra
robot body, helmet, ears or face frame was included.

PRESERVED
- Original StackChan apps, controls, camera, and AI service.
- Existing ASL Companion mode selection and welcome voice recording.
- v5 and v6 conversation handling, v7 opt-in local learning and memory.
- Menu icon and all six other original ASL overlay files.
- Factory firmware baseline and independent Git recovery branches.

VERIFICATION
- New and original face archives compared; only the 2 encoded face-data
  files change. Exact archive checksum enforced during GitHub CI.
- Native host decoder successfully decoded all 30 frames with full bounds
  checks and tested malformed frame rejection.
- GitHub CI must compile ESP32-S3 image and check partition fit.
- Do not claim physical device testing until owner flashes v8.

FLASH
Use flasher_args.json in compiled artifact for exact addresses.
Never click ERASE. Preserve v7/v5 backups.
