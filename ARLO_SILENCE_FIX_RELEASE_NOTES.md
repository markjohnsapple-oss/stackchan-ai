# ARLO | quiet-session safeguard (Slim v2 follow-up)

## Source and protected work
- Created as a separate branch from verified **StackChan Slim v2** commit
  `d19d5a0dc3173bcd461957e32ab29fa1bb7c7ea9`.
- Pinned original M5Stack firmware source `28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400` and XiaoZhi v2.5.2; no changes to camera, audio codec, face, Wi-Fi, motors, radio, OTA partitions or saved NVS preferences.
- **Slim v2 remains a protected recovery firmware.** This builds a new image; it does not flash the user's robot.

## Why ARLO says unsolicited goodbyes
- Open-source XiaoZhi server implementations generate an inactivity farewell.
  Example: `xinnan-tech/xiaozhi-esp32-server` has
  `close_connection_no_voice_time: 120` and `end_prompt.enable: true`.
  Another reported XiaoZhi server can use a shorter threshold. 
- The **exact remote backend for this specific StackChan account is not verified**.
  No hard-coded phrase has been found in the pinned device's main firmware.
  Disabling idle goodbyes **on the actual server** is the cleanest fix whenever that setting is available.

## Scoped device workaround
- On the existing voice/VAD event, record real voice activity. Also record an
  accepted STT message as evidence of user speech.
- If the microphone has been silently listening for **75 seconds**, the native
  XiaoZhi client closes its existing audio connection *without speaking*
  and Slim v2's existing hands-free auto-connect brings it back.
- Only refresh in the listening state while online and **not** during voice
  activity or speech playback. The original manual tap-to-pause remains in place.
- No additional timer or long-running task is created; use the existing one-second
  status tick and native VAD.
- Local wake-word-free conversation, image capture, speakers, face, and recovery
  menu are carried over unchanged in the source.
- **Important limitation:** the provider may reset its short-term dialogue
  context when an audio session refreshes. This is not a complete removal of
  the cloud server's goodbye policy; it avoids the common 120s path.
  If the provider has a shorter timeout, a server-side fix may still be needed.

## ARLO identity is intentionally cloud-based
The official M5Stack **StackChan World** AI Agent settings include Name,
Personality and Memory. Set the name to **ARLO** there and update the profile.
Restart the device to apply. Reflashing the device **does not** change a remote
cloud AI agent's identity, and forcing a system prompt through arbitrary client
audio would risk the working conversation pipeline.
The private personalised profile text is provided separately to the user,
not committed to a public firmware repository.

## Test on actual device before treating as fully verified
1. Confirm boot-direct, natural conversation and camera as in verified v2.
2. After talking, remain silent for over 3 minutes. There should be **no**
   unsolicited spoken goodbye. Verify it still responds when spoken to.
3. Speak around the 75s threshold; ensure no clipped replies or disconnects.
4. Tap face to pause; wait 3 minutes; confirm microphone stays paused.
5. Verify saved cloud personality and any memory still work after 75s.
6. If any regression occurs, flash the preserved Slim v2 package back with
   the original address map, **without ERASE**.

GitHub Actions compilation checks firmware size, successful build and
presence of this scoped safeguard. **No on-hardware behavioural claims** are
made until these tests complete.
