/*
 * Arcade Home Labs companion integration, based on M5Stack StackChan AI Agent.
 * Retains the existing Xiaozhi startup path. No camera or microphone
 * detection is claimed until the hardware callbacks are wired.
 */
#include "app_ai_agent.h"
#include <hal/hal.h>
#include <mooncake.h>
#include <mooncake_log.h>
#include <assets/assets.h>
#include <smooth_lvgl.hpp>
#include <stackchan/stackchan.h>
#include <apps/common/common.h>
#include "companion_core.h"

using namespace mooncake;
using namespace smooth_ui_toolkit::lvgl_cpp;
namespace { ahl::CompanionCore companion; }

AppAiAgent::AppAiAgent() {
    setAppInfo().name = "AI.AGENT";
    static auto icon = assets::get_image("icon_ai_agent.bin");
    setAppInfo().icon = (void*)&icon;
    static uint32_t theme_color = 0x33CC99;
    setAppInfo().userData = (void*)&theme_color;
}
void AppAiAgent::onCreate() {
    mclog::tagInfo(getAppInfo().name, "AHL companion core initialised");
}
void AppAiAgent::onOpen() {
    mclog::tagInfo(getAppInfo().name, "AHL companion session opened");
    companion.setState(ahl::State::Idle);
    GetHAL().requestXiaozhiStart();
}
void AppAiAgent::onRunning() {
    // Presence, speech and response callbacks are intentionally NOT fabricated.
    // CompanionCore is ready to receive real events from hardware/services.
}
void AppAiAgent::onClose() {
    companion.onPresence(false, GetHAL().millis());
    mclog::tagInfo(getAppInfo().name, "AHL companion session closed");
}
