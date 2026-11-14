#!/usr/bin/env python3
"""AHL ARLO v1 | Soft-silence refresh for Slim v2's original XiaoZhi connection.

Our known-good Slim v2 stays unchanged. The M5Stack/XiaoZhi cloud service can
generate a *spoken* farewell on an inactive session; changing the device's
personality prompt alone cannot reliably override server-side idle policies.
This optional firmware-side workaround quietly refreshes the connection after
75 seconds of *detected silence*, before the common 120-second server threshold.

Important: This does not disable a goodbye on a remote server with a shorter
threshold; the ideal fix is to disable the idle end_prompt on that server.
A reconnect may also start a new cloud dialogue session, depending on provider.
"""
from pathlib import Path

APPROOT = Path(__file__).resolve().parents[1] / "upstream/firmware/xiaozhi-esp32/main"
HEAD = APPROOT / "application.h"
APP = APPROOT / "application.cc"

def only(text: str, old: str, new: str, label: str) -> str:
    matches = text.count(old)
    if matches != 1:
        raise RuntimeError(f"STOP: source drift in {label}: expected 1, got {matches}")
    return text.replace(old, new, 1)

def patch():
    hd = HEAD.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    if "ahl_handsfree_enabled_" not in hd or "AHL_SLIM_V2_MEM" not in app:
        raise RuntimeError("STOP: required original Slim v2 not present")

    hd = only(hd, '#include <cstdint>\n', '#include <cstdint>\n#include <atomic>\n',
              'atomic header')
    hd = only(
        hd,
        '    uint64_t ahl_last_retry_us_ = 0;\n',
        '''    uint64_t ahl_last_retry_us_ = 0;
    // ARLO: monitor real user speech; no artificial wake words or scripted
    // time-based chat. This counter is shared with network callbacks.
    std::atomic<uint64_t> arlo_last_voice_us_{0};
''',
        'voice timestamp')

    # Real microphone VAD is already provided by the original ESP-SR pipeline.
    # This tracks activity without introducing a new task or camera competition.
    app = only(
        app,
        '''        if (bits & MAIN_EVENT_VAD_CHANGE) {
            if (GetDeviceState() == kDeviceStateListening) {
                auto led = Board::GetInstance().GetLed();
                led->OnStateChanged();
            }
        }''',
        '''        if (bits & MAIN_EVENT_VAD_CHANGE) {
            if (GetDeviceState() == kDeviceStateListening) {
                if (audio_service_.IsVoiceDetected()) {
                    arlo_last_voice_us_.store(
                        static_cast<uint64_t>(esp_timer_get_time()), std::memory_order_relaxed);
                }
                auto led = Board::GetInstance().GetLed();
                led->OnStateChanged();
            }
        }''',
        'voice activity event')

    app = only(
        app,
        '''    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);''',
        '''    protocol_->OnAudioChannelOpened([this, codec, &board]() {
        arlo_last_voice_us_.store(
            static_cast<uint64_t>(esp_timer_get_time()), std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::PERFORMANCE);''',
        'voice timer initialisation')

    app = only(
        app,
        '''    protocol_->OnAudioChannelClosed([this, &board]() {
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);''',
        '''    protocol_->OnAudioChannelClosed([this, &board]() {
        arlo_last_voice_us_.store(0, std::memory_order_relaxed);
        board.SetPowerSaveLevel(PowerSaveLevel::LOW_POWER);''',
        'voice timer reset')

    # Even in a noisy room where local VAD does not catch speech, an actual STT
    # response from the service is evidence of interaction.
    app = only(
        app,
        '''                ESP_LOGI(TAG, ">> %s", text->valuestring);
                Schedule([display, message = std::string(text->valuestring),''',
        '''                ESP_LOGI(TAG, ">> %s", text->valuestring);
                arlo_last_voice_us_.store(
                    static_cast<uint64_t>(esp_timer_get_time()), std::memory_order_relaxed);
                Schedule([display, message = std::string(text->valuestring),''',
        'cloud recognised speech')

    app = only(
        app,
        '''            display->UpdateStatusBar();
            // AHL Slim v2: start native XiaoZhi automatically after activation,''',
        '''            display->UpdateStatusBar();
            // ARLO: preserve the conversational AI, yet avoid the common
            // server-generated goodbye after ~120 seconds of no human speech.
            // The refresh is silent, only while native AI is LISTENING, and
            // never during speech, audio playback, or user-requested pause.
            // It is a protocol refresh, not a device reboot or an idle goodbye.
            constexpr uint64_t kArloSilentRefreshUs = 75000000ULL;
            const uint64_t arlo_now_us = static_cast<uint64_t>(esp_timer_get_time());
            const uint64_t arlo_last_us =
                arlo_last_voice_us_.load(std::memory_order_relaxed);
            if (ahl_handsfree_enabled_ && ahl_network_online_ &&
                GetDeviceState() == kDeviceStateListening &&
                protocol_ && protocol_->IsAudioChannelOpened() &&
                !audio_service_.IsVoiceDetected() && audio_service_.IsPlaybackIdle() &&
                arlo_last_us > 0 && arlo_now_us > arlo_last_us &&
                arlo_now_us - arlo_last_us >= kArloSilentRefreshUs) {
                // Prevent duplicate triggers while the close callback runs.
                arlo_last_voice_us_.store(arlo_now_us, std::memory_order_relaxed);
                ESP_LOGI(TAG, "ARLO_SILENCE: quiet connection refresh, no farewell");
                protocol_->CloseAudioChannel();
            }
            // AHL Slim v2: start native XiaoZhi automatically after activation,''',
        'safe bounded silence refresh')

    for label, marker in {
        "native v2 handsfree retained": "ahl_handsfree_enabled_",
        "manual tap-to-pause retained": 'Mic paused: tap face to resume',
        "native vision unchanged": "camera",
        "original VAD retained": "audio_service_.IsVoiceDetected()",
        "bounded refresh": "kArloSilentRefreshUs",
        "ARLO diagnostic": "ARLO_SILENCE",
        "v2 memory counters": "AHL_SLIM_V2_MEM",
    }.items():
        if marker not in app:
            raise RuntimeError("STOP: feature regression check failed: " + label)
    HEAD.write_text(hd, encoding="utf-8")
    APP.write_text(app, encoding="utf-8")
    print("ARLO SILENCE SAFEGUARD OK: 75s real-silence session refresh with native VAD.")
    print("No hard-coded goodbye; unchanged native voice/camera/touch/visuals.")
    print("User-facing AI name and ADHD-support persona MUST be changed in StackChan World AI Agent profile.")
    print("Remote server timeout policy unknown. Hardware test needed.")

if __name__ == "__main__":
    patch()
