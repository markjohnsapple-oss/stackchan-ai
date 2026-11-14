#!/usr/bin/env python3
"""StackChan Slim v2: native XiaoZhi wake-word-free hands-free listening.

Tightly scoped, fail-closed patch against the official pinned StackChan 1.6.2
and its pinned, manufacturer-patched XiaoZhi 2.5.2 dependency. No new
companion, no assets, no background thread, no change to functioning camera.
The original Slim v1 and factory images are untouched.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "upstream/firmware"
APP = ROOT / "xiaozhi-esp32/main/application.cc"
HEAD = ROOT / "xiaozhi-esp32/main/application.h"
AFE = ROOT / "xiaozhi-esp32/main/audio/engines/afe_audio_engine.cc"

def once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"STOP: {label}: expected exactly one match; got {count}")
    return text.replace(old, new, 1)

def apply():
    original = {p: p.read_text(encoding="utf-8") for p in (APP, HEAD, AFE)}
    app, header, afe = original[APP], original[HEAD], original[AFE]

    header = once(
        header,
        "    bool pending_listening_start_ = false;  // Waiting for playback to drain before starting listening (auto mode)\n",
        """    bool pending_listening_start_ = false;  // Waiting for playback to drain before starting listening (auto mode)
    // AHL Slim v2: native always-ready conversational mode (not another AI).
    // A touch of the stock AI face explicitly pauses or resumes the microphone.
    bool ahl_handsfree_enabled_ = true;
    bool ahl_activation_ready_ = false;
    bool ahl_network_online_ = false;
    uint64_t ahl_last_retry_us_ = 0;
""",
        "native hands-free fields")

    app = once(
        app,
        "#include <esp_log.h>\n",
        "#include <esp_log.h>\n#include <esp_heap_caps.h>\n",
        "heap metrics header")

    app = once(
        app,
        "void Application::HandleNetworkConnectedEvent() {\n    ESP_LOGI(TAG, \"Network connected\");",
        """void Application::HandleNetworkConnectedEvent() {
    ahl_network_online_ = true;
    ESP_LOGI(TAG, "Network connected");""",
        "network online state")

    app = once(
        app,
        "void Application::HandleNetworkDisconnectedEvent() {\n    // Close current conversation when network disconnected",
        """void Application::HandleNetworkDisconnectedEvent() {
    ahl_network_online_ = false;
    // Close current conversation when network disconnected""",
        "network offline state")

    app = once(
        app,
        "void Application::HandleActivationDoneEvent() {\n    ESP_LOGI(TAG, \"Activation done\");",
        """void Application::HandleActivationDoneEvent() {
    ahl_activation_ready_ = true;
    ESP_LOGI(TAG, "Activation done");""",
        "activation ready state")

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
            // AHL Slim v2: start native XiaoZhi automatically after activation,
            // and retry only when idle, online, and at least 8s after an attempt.
            // No wake word, separate ASL UI, busy loop or hot microphone task.
            if (ahl_handsfree_enabled_ && ahl_network_online_ && ahl_activation_ready_ &&
                protocol_ && GetDeviceState() == kDeviceStateIdle && !notify_player_.IsBusy() &&
                last_error_message_.empty()) {
                const uint64_t now_us = static_cast<uint64_t>(esp_timer_get_time());
                if (now_us - ahl_last_retry_us_ >= 8000000ULL) {
                    ahl_last_retry_us_ = now_us;
                    ESP_LOGI(TAG, "AHL_HANDSFREE: starting original XiaoZhi listening");
                    HandleToggleChatEvent();
                }
            }""",
        "periodic bounded auto-listen")

    app = once(
        app,
        """                SystemInfo::PrintHeapStats();
                // SystemInfo::PrintTaskList();""",
        """                SystemInfo::PrintHeapStats();
                ESP_LOGI(TAG, "AHL_SLIM_V2_MEM internal_free=%u internal_largest=%u psram_free=%u psram_largest=%u",
                         static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
                         static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)),
                         static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
                         static_cast<unsigned>(heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM)));
                // SystemInfo::PrintTaskList();""",
        "RAM and largest-block diagnostics")

    app = once(
        app,
        """    if (state == kDeviceStateIdle) {
        ListeningMode mode = GetDefaultListeningMode();""",
        """    if (state == kDeviceStateIdle) {
        // User taps the existing AI face to resume wake-word-free conversation.
        ahl_handsfree_enabled_ = true;
        ListeningMode mode = GetDefaultListeningMode();""",
        "tap to resume")

    app = once(
        app,
        """    } else if (state == kDeviceStateSpeaking) {
        AbortSpeaking(kAbortReasonNone);
    } else if (state == kDeviceStateListening) {
        protocol_->CloseAudioChannel();
    }
}""",
        """    } else if (state == kDeviceStateSpeaking) {
        // Privacy pause also works when the AI is speaking.
        ahl_handsfree_enabled_ = false;
        AbortSpeaking(kAbortReasonNone);
        protocol_->CloseAudioChannel();
        Board::GetInstance().GetDisplay()->ShowNotification("Mic paused: tap face to resume", 3500);
    } else if (state == kDeviceStateListening) {
        // A deliberate tap stops streaming; the automatic timer respects this.
        ahl_handsfree_enabled_ = false;
        protocol_->CloseAudioChannel();
        Board::GetInstance().GetDisplay()->ShowNotification("Mic paused: tap face to resume", 3500);
    }
}""",
        "tap to pause, without auto restart")

    app = once(
        app,
        """            audio_service_.EnableVoiceProcessing(false);
            audio_service_.EnableWakeWordDetection(true);
            break;""",
        """            audio_service_.EnableVoiceProcessing(false);
            audio_service_.EnableWakeWordDetection(false);
            break;""",
        "idle wake word disabled")

    app = once(
        app,
        """                audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());
            }
            audio_service_.ResetDecoder();
            break;""",
        """                audio_service_.EnableWakeWordDetection(false);
            }
            audio_service_.ResetDecoder();
            break;""",
        "speaking wake word disabled")

    app = once(
        app,
        """            audio_service_.EnableVoiceProcessing(false);
            audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());
            break;""",
        """            audio_service_.EnableVoiceProcessing(false);
            audio_service_.EnableWakeWordDetection(false);
            break;""",
        "notification wake word disabled")

    app = once(
        app,
        """    audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());
#else
    // Disable wake word detection in listening mode""",
        """    audio_service_.EnableWakeWordDetection(false);
#else
    // Disable wake word detection in listening mode""",
        "listening wake word disabled")

    # The original ESP-SR acoustic front end is retained for microphone
    # processing, voice activity detection and echo cancellation.
    # Do not allocate *either* WakeNet or MultiNet wake detector.
    afe = once(
        afe,
        """    char* wakenet_model_name = nullptr;
    char* multinet_model_name = nullptr;""",
        """    char* wakenet_model_name = nullptr;
    char* multinet_model_name = nullptr;
    constexpr bool ahl_wake_model_enabled = false;  // v2 native VAD only""",
        "wake detector selection constant")
    afe = once(
        afe,
        "    if (multinet_model_name != nullptr) {",
        "    if (ahl_wake_model_enabled && multinet_model_name != nullptr) {",
        "no MultiNet allocation")
    afe = once(
        afe,
        "    } else if (wakenet_model_name != nullptr) {",
        "    } else if (ahl_wake_model_enabled && wakenet_model_name != nullptr) {",
        "no WakeNet allocation")

    required = {
        "original voice start": "SetListeningMode(mode);",
        "original camera integration": 'McpServer::GetInstance()',
        "original speaking decoder": 'audio_service_.ResetDecoder();',
        "original voice processing": "audio_service_.EnableVoiceProcessing(true);",
        "safe tap pause": 'ahl_handsfree_enabled_ = false;',
        "local AFE VAD": "afe_config->vad_init = kUseAfeForVoiceProcessing;",
        "local AFE echo cancellation": "afe_config->aec_init = codec_->input_reference();",
        "automatic bounded retry": "ahl_last_retry_us_",
    }
    combined = app + "\n" + afe
    for name, marker in required.items():
        if marker not in combined:
            raise RuntimeError("STOP: missing protected behaviour: " + name)

    for p, text in ((APP, app), (HEAD, header), (AFE, afe)):
        p.write_text(text, encoding="utf-8")
    print("AHL SLIM V2: native wake-word-free XiaoZhi, 8-second bounded retry, face-tap privacy pause.")
    print("ESP-SR VAD/AEC retained; WakeNet/MultiNet no longer initialised.")
    print("Memory diagnostics: free and largest allocatable internal SRAM and PSRAM.")
    print("SD not mounted: GPIO35 conflicts with active display DC. Keep Slim v1 recovery.")
if __name__ == "__main__":
    apply()
