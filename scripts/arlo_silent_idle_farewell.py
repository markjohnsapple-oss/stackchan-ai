#!/usr/bin/env python3
"""ARLO silent idle-farewell guard on top of the verified hands-free/name master.

Manufacturer voice server can send a spontaneous TTS farewell after 30s idle.
The upstream XiaoZhi server sends STT before normal speech, but its idle
end_prompt sends TTS without a fresh STT. Suppress only that idle, unsolicited
TTS on the DEVICE; do not touch Wi-Fi, MQTT, cloud server configuration,
AI voice, microphone, VAD, camera, movement, NVS or device hardware IDs.

Network callbacks and incoming audio run on different FreeRTOS tasks. Use
atomics for their shared fields. Never create a new task/timer/audio pipeline.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "upstream/firmware"
APP = ROOT / "xiaozhi-esp32/main/application.cc"
HEAD = ROOT / "xiaozhi-esp32/main/application.h"


def once(text: str, old: str, new: str, label: str) -> str:
    hits = text.count(old)
    if hits != 1:
        raise RuntimeError(f"STOP: {label}: expected 1, found {hits}")
    return text.replace(old, new, 1)


def apply():
    app = APP.read_text(encoding="utf-8")
    header = HEAD.read_text(encoding="utf-8")
    if "ARLO_HANDSFREE" not in app or "arlo_last_open_attempt_us_" not in header:
        raise RuntimeError("STOP: exact previously successful ARLO hands-free/name base absent")

    header = once(header,
                  "#include <cstdint>\n",
                  "#include <cstdint>\n#include <atomic>\n",
                  "C++ atomic header")
    header = once(header,
                  "    uint64_t arlo_last_open_attempt_us_ = 0;\n",
                  """    uint64_t arlo_last_open_attempt_us_ = 0;
    // Server can start an unsolicited goodbye TTS after idle. Preserve replies
    // triggered by real STT, and suppress only unprompted idle TTS audio.
    std::atomic<bool> arlo_fresh_user_stt_{false};
    std::atomic<bool> arlo_mute_idle_goodbye_{false};
    std::atomic<int64_t> arlo_last_tts_end_us_{0};
""",
                  "idle farewell guard members")

    app = once(app,
        """    protocol_->OnIncomingAudio([this](std::unique_ptr<AudioStreamPacket> packet) {
        if (GetDeviceState() == kDeviceStateSpeaking) {
            audio_service_.PushPacketToDecodeQueue(std::move(packet));
        }
    });""",
        """    protocol_->OnIncomingAudio([this](std::unique_ptr<AudioStreamPacket> packet) {
        // ARLO: a server-initiated idle farewell is never decoded or played.
        if (!arlo_mute_idle_goodbye_.load(std::memory_order_relaxed) &&
            GetDeviceState() == kDeviceStateSpeaking) {
            audio_service_.PushPacketToDecodeQueue(std::move(packet));
        }
    });""",
        "audio callback gate")

    app = once(app,
        """    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);""",
        """    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        // Begin a fresh idle interval on each session, not the previous one.
        arlo_fresh_user_stt_.store(false, std::memory_order_relaxed);
        arlo_mute_idle_goodbye_.store(false, std::memory_order_relaxed);
        arlo_last_tts_end_us_.store(
            static_cast<int64_t>(esp_timer_get_time()), std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);""",
        "new audio channel initialization")

    app = once(app,
        """    protocol_->OnAudioChannelClosed([this, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);""",
        """    protocol_->OnAudioChannelClosed([this, &board]() {
        arlo_mute_idle_goodbye_.store(false, std::memory_order_relaxed);
        arlo_fresh_user_stt_.store(false, std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);""",
        "audio channel cleanup")

    app = once(app,
        """            if (strcmp(state->valuestring, "start") == 0) {
                Schedule([this]() {
                    aborted_ = false;
                    SetDeviceState(kDeviceStateSpeaking);
                });
            } else if (strcmp(state->valuestring, "stop") == 0) {
                Schedule([this]() {
                    if (GetDeviceState() == kDeviceStateSpeaking) {""",
        """            if (strcmp(state->valuestring, "start") == 0) {
                // Normal voice replies have a preceding user STT; the server's
                // idle-generated goodbye starts TTS without user STT. Check
                // both that distinction and at least 20s of no reply.
                constexpr int64_t kArloIdleFarewellThresholdUs = 20000000LL;
                const int64_t now_us = static_cast<int64_t>(esp_timer_get_time());
                const int64_t last_end_us =
                    arlo_last_tts_end_us_.load(std::memory_order_relaxed);
                const bool prompted =
                    arlo_fresh_user_stt_.exchange(false, std::memory_order_relaxed);
                if (!prompted && last_end_us > 0 && now_us > last_end_us &&
                    now_us - last_end_us >= kArloIdleFarewellThresholdUs) {
                    arlo_mute_idle_goodbye_.store(true, std::memory_order_relaxed);
                    ESP_LOGI(TAG, "ARLO_SILENT_FAREWELL: muting unsolicited idle TTS");
                    // Keep the existing listening state. Do not queue speech.
                    return;
                }
                arlo_mute_idle_goodbye_.store(false, std::memory_order_relaxed);
                Schedule([this]() {
                    aborted_ = false;
                    SetDeviceState(kDeviceStateSpeaking);
                });
            } else if (strcmp(state->valuestring, "stop") == 0) {
                if (arlo_mute_idle_goodbye_.exchange(
                        false, std::memory_order_relaxed)) {
                    ESP_LOGI(TAG, "ARLO_SILENT_FAREWELL: server farewell ended quietly");
                    return;
                }
                arlo_last_tts_end_us_.store(
                    static_cast<int64_t>(esp_timer_get_time()),
                    std::memory_order_relaxed);
                Schedule([this]() {
                    if (GetDeviceState() == kDeviceStateSpeaking) {""",
        "TTS start/stop guard")

    app = once(app,
        """            } else if (strcmp(state->valuestring, "sentence_start") == 0) {
                auto text = cJSON_GetObjectItem(root, "text");""",
        """            } else if (strcmp(state->valuestring, "sentence_start") == 0) {
                // Hide the unsolicited goodbye subtitle as well as its audio.
                if (arlo_mute_idle_goodbye_.load(std::memory_order_relaxed)) return;
                auto text = cJSON_GetObjectItem(root, "text");""",
        "farewell subtitle guard")

    app = once(app,
        """        } else if (strcmp(type->valuestring, "stt") == 0) {
            auto text = cJSON_GetObjectItem(root, "text");""",
        """        } else if (strcmp(type->valuestring, "stt") == 0) {
            // Genuine conversation STT precedes its corresponding TTS.
            // Server idle end_prompt has no STT in the upstream protocol.
            arlo_fresh_user_stt_.store(true, std::memory_order_relaxed);
            auto text = cJSON_GetObjectItem(root, "text");""",
        "user speech marker")

    required = (
        "ARLO_HANDSFREE", "ARLO_SILENT_FAREWELL",
        "board.StartNetwork();", "InitializeProtocol();", "CheckNewVersion();",
        "McpServer::GetInstance()", "audio_service_.EnableVoiceProcessing(true);",
        "OnIncomingJson", "OnIncomingAudio", "OnAudioChannelClosed",
    )
    for marker in required:
        if marker not in app:
            raise RuntimeError("STOP: lost protected native feature: " + marker)
    if "std::atomic<bool> arlo_mute_idle_goodbye_" not in header:
        raise RuntimeError("STOP: audio thread safety missing")
    APP.write_text(app, encoding="utf-8")
    HEAD.write_text(header, encoding="utf-8")
    print("ARLO_SILENT_FAREWELL_READY: quiet idle end_prompt TTS at device protocol boundary.")
    print("Original working ARLO hands-free, identity, camera, Wi-Fi, voice and motor control retained.")
    print("Hardware test required: unsolicited goodbyes should be quiet; normal replies must still speak.")


if __name__ == "__main__":
    apply()
