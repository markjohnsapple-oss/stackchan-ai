# Arcade Home Labs | StackChan ASL Companion v9

Builds directly on the successfully compiled v8 face-animation master.
Preserves approved wake-up, idle, talking face assets, original StackChan apps,
voice greeting, XiaoZhi conversation service, camera and on-device memory.

NEW: speech playback smoothing
- Increase XiaoZhi's bounded decoded PCM playback queue from 2 to 6 frames.
- Add a 90 ms maximum prebuffer window when a speech stream begins or an
  audio queue empties. It can wait for three frames, or play whatever has
  arrived after the short timeout, so short replies do not get stuck.
- Keep packet order, Opus decoder, factory speaker driver and original
  stream-safety logic unchanged.
- NOTE: this may reduce stutter caused by short local/network jitter. It
  cannot guarantee correction of network stalls, Wi-Fi interference or slow
  server-side TTS. Physical listening test still required.
- Buffer tuning is in the shared XiaoZhi audio service, so the original
  AI Agent also receives a short prebuffer. Factory AI functions remain.

NEW: louder Companion speech
- Use the existing codec's normal maximum volume setting, 100/100.
- No software gain beyond the codec maximum and no amplifier hardware hacks.
- Preserve previous speaker level in memory and do not overwrite stored
  audio volume settings. Restore it if ASL Companion is reset.
- Users should reduce volume from the device UI if speaker sounds harsh or
  distorts; maximum setting cannot guarantee distortion-free sound.

SAFETY / TESTS
- Separate v9 branch; v8 and proven-on-device v5 untouched.
- Compile using pinned M5Stack StackChan 1.6.2 + XiaoZhi v2.5.2 original
  patch + all existing AHL overlays.
- CI must verify the 5 firmware binaries, app partition size and ZIP integrity.
- No automatic deployment or erase; keep existing NVS, Wi-Fi and memory.
- ESP32-S3 hardware untested until owner flashes and tries voice.
