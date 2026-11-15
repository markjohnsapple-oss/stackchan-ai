#!/usr/bin/env python3
"""ARLO: pre-empt server idle farewell by quietly rotating idle audio sessions.

This replaces the ineffective after-the-fact TTS suppression from the previous
experimental firmware. It leaves normal speech and all original audio decode
and subtitle callbacks untouched.

The server can initiate an unsolicited farewell after about 30 seconds of no
speech. Once the original XiaoZhi channel has listened for 18 seconds without
local VAD, the client explicitly closes ONLY that audio channel. The existing
ARLO hands-free idle handler reopens a new session automatically. This prevents
server-generated farewell audio from being issued on the old session.

Protect audio-in-progress, playback, modem/Wi-Fi, and actual voices. No new
threads, tasks, HTTP, Bluetooth, cloud or NVS changes.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "upstream/firmware"
APP = ROOT / "xiaozhi-esp32/main/application.cc"
HEAD = ROOT / "xiaozhi-esp32/main/application.h"


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"STOP: source changed for {label}: expected once, got {n}")
    return text.replace(old, new, 1)


def patch():
    app = APP.read_text(encoding="utf-8")
    header = HEAD.read_text(encoding="utf-8")
    if "ARLO_HANDSFREE" not in app or "arlo_last_open_attempt_us_" not in header:
        raise RuntimeError("STOP: exact working ARLO hands-free/name base missing")

    # Device event loop owns all channel close commands. Network events only
    # stamp the channel's start time, using an atomic for task safety.
    header = once(
        header,
        "#include <cstdint>\n",
        "#include <cstdint>\n#include <atomic>\n",
        "atomic header",
    )
    header = once(
        header,
        "    uint64_t arlo_last_open_attempt_us_ = 0;\n",
        """    uint64_t arlo_last_open_attempt_us_ = 0;
    // ARLO idle farewell prevention. Updated from main task and network callbacks.
    std::atomic<int64_t> arlo_last_voice_activity_us_{0};
""",
        "voice activity timer",
    )

    app = once(
        app,
        """    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);""",
        """    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        // Start a NEW server inactivity interval for each actual voice session.
        arlo_last_voice_activity_us_.store(
            static_cast<int64_t>(esp_timer_get_time()), std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);""",
        "session started",
    )

    app = once(
        app,
        """    protocol_->OnAudioChannelClosed([this, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);""",
        """    protocol_->OnAudioChannelClosed([this, &board]() {
        arlo_last_voice_activity_us_.store(0, std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);""",
        "session stopped",
    )

    app = once(
        app,
        """        if (bits & MAIN_EVENT_VAD_CHANGE) {
            if (GetDeviceState() == kDeviceStateListening) {
                auto led = Board::GetInstance().GetLed();""",
        """        if (bits & MAIN_EVENT_VAD_CHANGE) {
            if (GetDeviceState() == kDeviceStateListening) {
                if (audio_service_.IsVoiceDetected()) {
                    arlo_last_voice_activity_us_.store(
                        static_cast<int64_t>(esp_timer_get_time()),
                        std::memory_order_relaxed);
                }
                auto led = Board::GetInstance().GetLed();""",
        "voice activity callback",
    )

    app = once(
        app,
        """        if (bits & MAIN_EVENT_CLOCK_TICK) {
            clock_ticks_++;
            auto display = Board::GetInstance().GetDisplay();
            display->UpdateStatusBar();""",
        """        if (bits & MAIN_EVENT_CLOCK_TICK) {
            clock_ticks_++;
            auto display = Board::GetInstance().GetDisplay();
            display->UpdateStatusBar();

            // ARLO_SILENT_FAREWELL_V2: stop an IDLE audio session before the
            // hosted service's unsolicited ~30s goodbye, then let the already
            // working native ARLO hands-free state machine reconnect it.
            // Never interrupt genuine detected speech or ongoing playback.
            if (arlo_wifi_connected_ && arlo_activation_completed_ && protocol_ &&
                GetDeviceState() == kDeviceStateListening &&
                protocol_->IsAudioChannelOpened() &&
                audio_service_.IsAudioProcessorRunning() &&
                audio_service_.IsPlaybackIdle()) {
                const int64_t now_us = static_cast<int64_t>(esp_timer_get_time());
                if (audio_service_.IsVoiceDetected()) {
                    arlo_last_voice_activity_us_.store(
                        now_us, std::memory_order_relaxed);
                } else {
                    const int64_t last_voice_us = arlo_last_voice_activity_us_.load(
                        std::memory_order_relaxed);
                    constexpr int64_t kMaxSilentSessionUs = 18000000LL;
                    if (last_voice_us > 0 && now_us > last_voice_us &&
                        now_us - last_voice_us >= kMaxSilentSessionUs) {
                        ESP_LOGI(TAG, "ARLO_SILENT_FAREWELL_V2: quiet idle session rotation");
                        arlo_last_voice_activity_us_.store(0, std::memory_order_relaxed);
                        protocol_->CloseAudioChannel();
                    }
                }
            }""",
        "clock-triggered guarded idle rotation",
    )

    # If the device recognises a short phrase between clock ticks, refresh the
    # timer even if VAD has already switched back to silence.
    app = once(
        app,
        """        } else if (strcmp(type->valuestring, "stt") == 0) {
            auto text = cJSON_GetObjectItem(root, "text");""",
        """        } else if (strcmp(type->valuestring, "stt") == 0) {
            arlo_last_voice_activity_us_.store(
                static_cast<int64_t>(esp_timer_get_time()), std::memory_order_relaxed);
            auto text = cJSON_GetObjectItem(root, "text");""",
        "recognised speech timestamp",
    )

    # Every normal reply remains playable; do not hide/drop TTS, audio packets,
    # system notifications or transcripts.
    preserved = (
        "board.StartNetwork();",
        "InitializeProtocol();",
        "CheckNewVersion();",
        "audio_service_.PushPacketToDecodeQueue(std::move(packet));",
        "display->SetChatMessage(\"assistant\", message.c_str());",
        "audio_service_.EnableVoiceProcessing(true);",
        "ARLO_HANDSFREE",
        "GetDefaultListeningMode()",
        "McpServer::GetInstance()",
    )
    for marker in preserved:
        if marker not in app:
            raise RuntimeError("STOP: essential working feature missing: " + marker)
    if app.count("ARLO_SILENT_FAREWELL_V2") < 2:
        raise RuntimeError("STOP: idle guard not installed")
    if "arlo_last_voice_activity_us_" not in header:
        raise RuntimeError("STOP: atomic activity timer absent")
    if "arlo_mute_idle_goodbye_" in app or "arlo_fresh_user_stt_" in app:
        raise RuntimeError("STOP: old failed voice filter unexpectedly present")

    APP.write_text(app, encoding="utf-8")
    HEAD.write_text(header, encoding="utf-8")
    print("ARLO_SILENT_FAREWELL_V2_READY: pre-empt 30-second cloud goodbye at 18 seconds.")
    print("Normal TTS/audio/subtitle code unchanged; microphone and VAD preserved.")
    print("Existing hands-free listener will reconnect after quiet client-side close.")


if __name__ == "__main__":
    patch()
