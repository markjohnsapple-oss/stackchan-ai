# AHL ASL Companion v6: controlled listening and learning enhancement

Based on the physical-device-tested v5 firmware (blue eyes, wake-up animation,
approved voice greeting, AI Q&A and camera photography). The original firmware,
approved animation files, greeting asset, all factory apps and the v5 recovery ZIP
are unchanged.

Enhancements:
- Reduce the idle re-listen retry interval from 15 to 6 seconds and the
  post-greeting pause from 2.5 to 1 second. These are latency candidates, not
  proof that network TTS or playback stutter is fixed.
- Wait for the original audio playback queue to drain before automatically
  re-arming listening, to avoid cutting off spoken responses.
- Run the experimental camera motion watcher only in ASL Companion Mode and
  only when the AI is idle. This does NOT recognise faces or people.
- Allow explicit 'learn that ...', 'please learn that ...', and
  'teach you that ...' commands, alongside existing 'remember that ...'.
  Increase bounded local NVS note capacity from 16 to 32; leave its existing
  semantic-hash retrieval and erase commands unchanged.

Not completed: arbitrary AI responses in the approved custom animated voice,
face recognition/enrolment, a 500 MB microSD brain, encyclopaedia indexing,
or autonomous unrestricted self-learning. The original XiaoZhi server controls
synthesised response speech. The approved animated voice still plays the intro.

Safety and testing: compile-validated through GitHub ESP-IDF v6.1 + ESP32-S3,
not hardware-tested for this release. Flash only after checking original backup
and matching flash offsets; do not erase settings/NVS.

This branch is separate from main and v5. No auto-flashing or OTA deployment.
