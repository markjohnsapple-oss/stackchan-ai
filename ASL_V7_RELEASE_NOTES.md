# StackChan ASL Companion v7 | Arcade Home Labs

Builds on v6, retaining the v5-tested ASL menu, blue-eyed animations,
recorded cartoon-voice greeting, cloud conversation and photo capability.

NEW: opt-in natural personal learning. "Start learning about me" persists the
mode and "stop learning about me" disables it. Default OFF. While ON, short
first-person personal facts ("my name is", "my favourite", "I enjoy", "I like",
"I prefer", "I am working on") are stored locally, excluding several sensitive
data keywords. Direct "remember that" and "learn that" commands still work.

New read-only XiaoZhi MCP tools: ahl.memory.list, ahl.memory.status,
ahl.companion.capabilities. Existing ahl.memory.search retained.
Memory capacity is still 32 short notes on separate NVS. No arbitrary
transcripts, camera images or raw audio recorded into memory.

NOT YET IMPLEMENTED: custom TTS voice for *all* online AI replies (controlled
by XiaoZhi server TTS config), on-device face identity recognition, 500MB
microSD brain, offline LLM or unrestricted autonomous internet learning.
microSD shares hardware pins with display; no unsafe SD pin initialisation.

TESTING: GitHub Actions builds the exact pinned official StackChan 1.6.2 +
original AHL brain + approved ASL v4 artwork + v5 patches + v6 tweaks +
these v7 changes. ESP-IDF v6.1 ESP32-S3 build and partition test required.
Not tested on hardware until owner flashes it. No auto-flash, no erase.
Original and v5 backup firmware remain untouched.

MORNING TEST: enter ASL Companion, say "start learning about me", then
"My favourite colour is blue". Ask "What do you remember about my favourite
colour?" and "How many things do you remember?" Tool responses depend on
the connected XiaoZhi server. Voice lag may still occur due to server/WiFi.
