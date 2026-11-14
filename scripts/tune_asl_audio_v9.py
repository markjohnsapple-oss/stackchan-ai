#!/usr/bin/env python3
"""AHL ASL Companion v9: safely tune live XiaoZhi playback and Companion loudness.
Run only on a temporary CI checkout after original StackChan patches and dependencies.
Never modify the protected verified-v8 branch or factory sound effects.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/firmware"
LIVE = UP / "main/apps/app_asl_companion/asl_live_mode.cpp"
AUDIO_H = UP / "xiaozhi-esp32/main/audio/audio_service.h"
AUDIO_CC = UP / "xiaozhi-esp32/main/audio/audio_service.cc"

def replace_once(s, a, b, marker):
    n = s.count(a)
    if n != 1:
        raise RuntimeError(f"STOP: unexpected {marker}: {n} matches")
    return s.replace(a, b, 1)

def apply():
    files = {p: p.read_text(encoding="utf-8") for p in (LIVE, AUDIO_H, AUDIO_CC)}
    live = files[LIVE]
    h = files[AUDIO_H]
    cc = files[AUDIO_CC]
    # Never exceed the existing codec's supported 0-100 scale.
    # Keep the original stored user volume; the 100 boost is temporary while
    # the Companion speech mode is active. The stock AI Agent stays unchanged.
    live = replace_once(
        live, "std::atomic<uint32_t> greeting_end_ms{0};",
        "std::atomic<uint32_t> greeting_end_ms{0};\n"
        "std::atomic<bool> asl_max_volume_active{false};\n"
        "uint8_t asl_previous_volume{70};",
        "ASL sound state")
    live = replace_once(
        live, "    if (!requested() || !agent_standby_seen.load()) return;",
        "    if (!requested() || !agent_standby_seen.load()) return;\n"
        "    bool expected_volume = false;\n"
        "    if (asl_max_volume_active.compare_exchange_strong(expected_volume, true)) {\n"
        "        asl_previous_volume = hal_bridge::board_get_speaker_volume();\n"
        "        hal_bridge::board_set_speaker_volume(100, false);\n"
        "        ESP_LOGI(\"ASL_LIVE\", \"Companion speaker at codec max (100), saved normal volume %u\",\n"
        "                 static_cast<unsigned>(asl_previous_volume));\n"
        "    }",
        "volume applied when voice comes online")
    live = replace_once(
        live, "    mode_requested.store(false);",
        "    if (asl_max_volume_active.exchange(false)) {\n"
        "        hal_bridge::board_set_speaker_volume(asl_previous_volume, false);\n"
        "    }\n"
        "    mode_requested.store(false);",
        "restore normal level when Companion resets")
    # Retain all original packet decoding and ordering logic; use a modest 6-frame
    # PCM staging queue (was 2) for extra jitter tolerance.
    h = replace_once(
        h, "#define MAX_PLAYBACK_TASKS_IN_QUEUE 2",
        "#define MAX_PLAYBACK_TASKS_IN_QUEUE 6",
        "bounded PCM queue")
    cc = replace_once(
        cc, '#include "audio_service.h"\n',
        '#include "audio_service.h"\n#include <chrono>\n',
        "timer header")
    # Wait at most 90ms for >=3 predecoded frames before draining an empty-to-
    # active queue. Also limits stutters after a network underrun. Never block
    # until 3 frames unconditionally: very short utterances must still play.
    cc = replace_once(
        cc,
        """        if (service_stopped_.load()) {
            break;
        }

        auto task = std::move(audio_playback_queue_.front());""",
        """        // AHL v9: small finite prebuffer on stream start/packet underrun.
        // The condition-variable releases its mutex while decoders fill the queue.
        if (!service_stopped_.load() && audio_playback_queue_.size() < 3) {
            audio_queue_cv_.wait_for(
                lock, std::chrono::milliseconds(90), [this]() {
                    return service_stopped_.load() || audio_playback_queue_.size() >= 3;
                });
        }
        if (service_stopped_.load()) {
            break;
        }

        auto task = std::move(audio_playback_queue_.front());""",
        "audio-output prebuffer")
    protected = {
        "user's approved talking face": ("asl_face::Sequence::Talking", live),
        "approved recorded intro": ("greeting_begin", live),
        "original automatic listening": ("auto_listen_enabled", live),
        "local memory": ("GetAudioService().IsPlaybackIdle()", live),
        "original decode": ("esp_opus_dec_decode", cc),
        "original speaker write": ("codec_->OutputData(task.pcm)", cc),
        "existing packet collection": ("audio_decode_queue_", cc),
    }
    for label, (marker, text) in protected.items():
        if marker not in text:
            raise RuntimeError("STOP: protected v8 function missing: " + label)
    for p, s in ((LIVE, live), (AUDIO_H, h), (AUDIO_CC, cc)):
        p.write_text(s, encoding="utf-8")
    print("ASL v9: codec volume 100 for Companion (non-permanent), "
          "restorable normal volume, 6 PCM playback frames, 90ms max prebuffer.")

if __name__ == "__main__":
    apply()
