#!/usr/bin/env python3
"""Two narrowly scoped ARLO changes to the exact working Slim v1 source.

1. Replace the wake phrase with bounded, automatic native XiaoZhi listening,
   only after the EXISTING network/OTA/AI activation has succeeded.
2. Rebrand user-visible boot, launcher and setup labels to ARLO.

The original StackChan hardware classes, cloud protocol IDs, server address,
Wi-Fi setup, OTA, radio, voice service, camera, face, NVS and motors are NOT
renamed or reconfigured. An online AI personality is controlled separately by
the StackChan World AI Agent profile and is not silently rewritten here.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "upstream/firmware"
APP = ROOT / "xiaozhi-esp32/main/application.cc"
HEAD = ROOT / "xiaozhi-esp32/main/application.h"
BOOT = ROOT / "main/hal/hal.h"
AGENT = ROOT / "main/apps/app_ai_agent/app_ai_agent.cpp"
SETUP = ROOT / "main/apps/app_setup/app_setup.cpp"


def once(text: str, old: str, new: str, label: str) -> str:
    matches = text.count(old)
    if matches != 1:
        raise RuntimeError(f"STOP: {label} expected exactly once, found {matches}")
    return text.replace(old, new, 1)


def apply() -> None:
    files = (APP, HEAD, BOOT, AGENT, SETUP)
    original = {file: file.read_text(encoding="utf-8") for file in files}
    app = original[APP]
    header = original[HEAD]
    boot = original[BOOT]
    agent = original[AGENT]
    setup = original[SETUP]

    # No duplicate AI runtime, no BLE server and no new NVS keys.
    # State is stored in normal RAM and resets on reboot.
    header = once(header,
        "    int clock_ticks_ = 0;\n",
        """    int clock_ticks_ = 0;
    // ARLO: use the original XiaoZhi microphone/VAD and network protocol.
    bool arlo_wifi_connected_ = false;
    bool arlo_activation_completed_ = false;
    uint64_t arlo_last_open_attempt_us_ = 0;
""",
        "native state fields")

    app = once(app,
        'void Application::HandleNetworkConnectedEvent() {\n'
        '    ESP_LOGI(TAG, "Network connected");',
        'void Application::HandleNetworkConnectedEvent() {\n'
        '    arlo_wifi_connected_ = true;\n'
        '    ESP_LOGI(TAG, "Network connected");',
        "online flag")

    app = once(app,
        'void Application::HandleNetworkDisconnectedEvent() {\n'
        '    // Close current conversation when network disconnected',
        'void Application::HandleNetworkDisconnectedEvent() {\n'
        '    arlo_wifi_connected_ = false;\n'
        '    // Close current conversation when network disconnected',
        "offline flag")

    app = once(app,
        'void Application::HandleActivationDoneEvent() {\n'
        '    ESP_LOGI(TAG, "Activation done");',
        'void Application::HandleActivationDoneEvent() {\n'
        '    arlo_activation_completed_ = true;\n'
        '    ESP_LOGI(TAG, "Activation done");',
        "activation gate")

    # Preserve the entire original activation and voice initialisation.
    # Only attempt to open the existing AI channel while IDLE and healthy.
    # Use a monotonic 8-second minimum interval to avoid retry storms.
    app = once(app,
        '''        if (bits & MAIN_EVENT_CLOCK_TICK) {
            clock_ticks_++;
            auto display = Board::GetInstance().GetDisplay();
            display->UpdateStatusBar();''',
        '''        if (bits & MAIN_EVENT_CLOCK_TICK) {
            clock_ticks_++;
            auto display = Board::GetInstance().GetDisplay();
            display->UpdateStatusBar();

            // ARLO: speak normally without saying the factory wake phrase.
            // Do not run during network setup, errors, notifications or speech.
            if (arlo_wifi_connected_ && arlo_activation_completed_ &&
                protocol_ && GetDeviceState() == kDeviceStateIdle &&
                !notify_player_.IsBusy() && audio_service_.IsPlaybackIdle() &&
                last_error_message_.empty()) {
                const uint64_t now_us = static_cast<uint64_t>(esp_timer_get_time());
                if (now_us > arlo_last_open_attempt_us_ &&
                    now_us - arlo_last_open_attempt_us_ >= 8000000ULL) {
                    arlo_last_open_attempt_us_ = now_us;
                    ESP_LOGI(TAG, "ARLO_HANDSFREE: opening original XiaoZhi listening");
                    HandleToggleChatEvent();
                }
            }''',
        "bounded native listening after activation")

    # The seven existing call sites include startup/idle/speaking/notification.
    # Keep the original mic, VAD, AEC and audio engine implementation untouched.
    # Disabling the detector does not remove/rename the manufacturer models,
    # which preserves binary resource dependencies and reduces regressions.
    original_true = "audio_service_.EnableWakeWordDetection(true);"
    original_afe = "audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());"
    if app.count(original_true) != 3 or app.count(original_afe) != 4:
        raise RuntimeError(
            "STOP: manufacturer wake word call sites changed; review before patch"
        )
    app = app.replace(original_true, "audio_service_.EnableWakeWordDetection(false);")
    app = app.replace(original_afe, "audio_service_.EnableWakeWordDetection(false);")

    # Replace ONLY visible UI branding; keep hardware class identifiers and
    # remote API/device identifiers byte-for-byte to preserve cloud pairing.
    boot = once(boot, '_label_logo->setText("STACKCHAN");',
                       '_label_logo->setText("ARLO");', "power-on splash title")
    agent = once(agent, 'setAppInfo().name = "AI.AGENT";',
                         'setAppInfo().name = "ARLO";', "launcher AI title")
    setup = once(setup, '            "AI.Agent",',
                         '            "ARLO",', "setup menu AI title")

    for marker in ("board.StartNetwork();", "CheckNewVersion();",
                   "InitializeProtocol();", "GetDefaultListeningMode()",
                   "audio_service_.EnableVoiceProcessing(true);",
                   "McpServer::GetInstance()"):
        if marker not in app or marker not in original[APP]:
            raise RuntimeError("STOP: essential manufacturer AI/Wi-Fi marker lost: " + marker)
    for marker in ("arlo_wifi_connected_", "arlo_activation_completed_",
                   "arlo_last_open_attempt_us_", "ARLO_HANDSFREE",
                   "audio_service_.EnableWakeWordDetection(false);"):
        if marker not in app + header:
            raise RuntimeError("STOP: missing requested hands-free marker: " + marker)
    if "audio_service_.EnableWakeWordDetection(true);" in app or \
       "audio_service_.EnableWakeWordDetection(audio_service_.IsAfeWakeWord());" in app:
        raise RuntimeError("STOP: wake-word detection still enabled at runtime")

    # Don't touch the original source unless ALL checks have succeeded.
    for file, updated in ((APP, app), (HEAD, header), (BOOT, boot),
                          (AGENT, agent), (SETUP, setup)):
        file.write_text(updated, encoding="utf-8")

    print("ARLO_SLIM_V1_HANDSFREE_NAME_READY")
    print("Wake phrase no longer required; original XiaoZhi listens when online and ready.")
    print("On-device boot/AI launcher/setup now display ARLO.")
    print("Original Wi-Fi/OTA/protocol/camera/voice/motors and NVS are unchanged.")
    print("Spoken cloud AI personality name remains managed by StackChan World.")


if __name__ == "__main__":
    apply()
