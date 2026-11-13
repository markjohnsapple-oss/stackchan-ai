#!/usr/bin/env python3
"""Apply Arcade Home Labs changes to a pinned upstream StackChan tree.
Fails closed if the expected upstream source is missing.
"""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
target=root/"upstream/firmware/main/apps/app_ai_agent"
original=target/"app_ai_agent.cpp"
if not original.exists():
    raise SystemExit(f"ERROR: upstream AI agent missing: {original}")
text=original.read_text()
needle='    GetHAL().requestXiaozhiStart();'
if text.count(needle)!=1:
    raise SystemExit("ERROR: unexpected upstream AI agent; refusing to modify")
text=text.replace(needle, '    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_V1_ACTIVE");\n'+needle)
original.write_text(text)
shutil.copyfile(root/"companion/companion_core.h",target/"companion_core.h")
# Explicit marker in the compiled AI agent so builds can be distinguished.
text=original.read_text().replace('#include "app_ai_agent.h"','#include "app_ai_agent.h"\n#include "companion_core.h"')
text=text.replace('    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_V1_ACTIVE");','    auto& companion = ahl::getCompanion();\n    static bool memory_ready = companion.openMemory();\n    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_MEMORY_READY={}", memory_ready);\n    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_V1_ACTIVE");')
original.write_text(text)
hal=root/"upstream/firmware/main/hal/hal.cpp"
if not hal.exists():
    raise SystemExit(f"ERROR: missing HAL: {hal}")
hal_source=hal.read_text()
start_marker='void Hal::startXiaozhi()\n{'
if hal_source.count(start_marker)!=1:
    raise SystemExit("ERROR: unexpected startup function")
hal_source=hal_source.replace('#include "hal.h"', '#include "hal.h"\n#include "companion_core.h"\n#include "companion_brain.h"')
hal_source=hal_source.replace('static std::unique_ptr<Hal> _hal_instance;', '''namespace ahl {
CompanionCore& getCompanion() {
    static CompanionCore companion;
    return companion;
}
}
static std::unique_ptr<Hal> _hal_instance;''')
hal_source=hal_source.replace(start_marker,start_marker+'\n    auto& ahl_memory = ahl::getCompanion();\n    const bool ahl_memory_ready = ahl_memory.openMemory();\n    if (ahl_memory_ready) ahl_memory.recordVisit();\n    mclog::tagInfo(_tag, "AHL_COMPANION_BOOT visits={}", ahl_memory.visits());')
# Background camera watcher feeds actual frame-change events to the companion.
# No camera preview, shutter sound or network upload is initiated.
watcher=r'''
static void _ahl_presence_task(void*) {
    auto* camera=hal_bridge::board_get_camera();
    if (!camera) { vTaskDelete(nullptr); return; }
    unsigned moving=0, still=0;
    ahl::CompanionBrain brain;
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(2500));
        if (!hal_bridge::is_xiaozhi_ready()) continue;
        float delta=0;
        if (!camera->SamplePresenceMotion(&delta)) continue;
        if (delta>0.11f) { moving++; still=0; }
        else { still++; moving=0; }
        auto& companion=ahl::getCompanion();
        const uint32_t now=GetHAL().millis();
        if (moving>=2) { companion.onPresence(true,now); brain.presenceChanged(true,now); }
        if (still>=12) { companion.onPresence(false,now); brain.presenceChanged(false,now); }
        // Decisions are recorded but not misrepresented as spoken responses.
        // Xiaozhi needs a confirmed text-to-speech conversation transport.
        const ahl::BrainInput input{now, moving>=2 || still<12,
            hal_bridge::is_xiaozhi_ready(), hal_bridge::is_xiaozhi_idle(), false};
        const auto action=brain.decide(input);
        if (action!=ahl::BrainAction::None) {
            mclog::tagInfo(_tag,"AHL_BRAIN_ACTION_PENDING={}",static_cast<int>(action));
        }
    }
}
'''
hal_source=hal_source.replace(start_marker,watcher+'\n'+start_marker)
hal_source=hal_source.replace('    auto& ahl_memory = ahl::getCompanion();','    xTaskCreate(_ahl_presence_task,"ahl_presence",6144,nullptr,2,nullptr);\n    auto& ahl_memory = ahl::getCompanion();')
hal.write_text(hal_source)
shutil.copyfile(root/"companion/companion_core.h",root/"upstream/firmware/main/hal/companion_core.h")
shutil.copyfile(root/"companion/companion_brain.h",root/"upstream/firmware/main/hal/companion_brain.h")
# Enable AI-on-boot by default for fresh configurations, while retaining
# existing persisted user settings and the existing Xiaozhi implementation.
bridge=root/"upstream/firmware/main/hal/board/hal_bridge.h"
if not bridge.exists():
    raise SystemExit(f"ERROR: missing HAL bridge: {bridge}")
bridge_source=bridge.read_text()
setting="bool startAiAgentOnBoot          = false;"
if bridge_source.count(setting)!=1:
    raise SystemExit("ERROR: unexpected HAL bridge setting; refusing to modify")
bridge.write_text(bridge_source.replace(setting,"bool startAiAgentOnBoot          = true;"))

# Synchronise the companion with real Xiaozhi listening/speaking events.
display=root/"upstream/firmware/main/hal/board/stackchan_display.cc"
if not display.exists():
    raise SystemExit(f"ERROR: missing Xiaozhi display: {display}")
display_source=display.read_text()
status_needle='void StackChanAvatarDisplay::SetStatus(const char* status)\n{'
if display_source.count(status_needle)!=1:
    raise SystemExit("ERROR: unexpected Xiaozhi status handler")
display_source=display_source.replace('#include <hal/hal.h>', '#include <hal/hal.h>\n#include <hal/companion_core.h>')
display_source=display_source.replace(status_needle,status_needle+'''
    if (status) {
        auto& companion = ahl::getCompanion();
        const uint32_t now = GetHAL().millis();
        if (strcmp(status, Lang::Strings::LISTENING) == 0) {
            companion.speechStarted(now);
        } else if (strcmp(status, Lang::Strings::SPEAKING) == 0) {
            companion.responseStarted(now);
        } else if (strcmp(status, Lang::Strings::STANDBY) == 0) {
            if (companion.state() == ahl::State::Speaking) {
                companion.responseEnded(now);
                companion.saveTurnCount();
            } else if (companion.state() == ahl::State::Listening) {
                companion.speechEnded(now);
            }
        }
    }
''')
# Map the real cloud emotion output to the companion's adaptive mood.
emotion_needle='void StackChanAvatarDisplay::SetEmotion(const char* emotion)\n{'
if display_source.count(emotion_needle)!=1:
    raise SystemExit("ERROR: unexpected emotion handler")
display_source=display_source.replace(emotion_needle,emotion_needle+'''
    if (emotion) {
        auto& companion = ahl::getCompanion();
        if (strcmp(emotion, "happy") == 0 || strcmp(emotion, "laughing") == 0) {
            companion.setMood(ahl::Mood::Happy);
            // Xiaozhi's actual emotion event also drives the physical servos.
            auto& robot = GetStackChan();
            if (robot.hasAvatar() && !robot.motion().isMoving() &&
                !robot.motion().isModifyLocked()) {
                robot.motion().lookAtNormalized(0.18f, -0.15f, 220);
            }
        } else if (strcmp(emotion, "sad") == 0 || strcmp(emotion, "crying") == 0) {
            companion.setMood(ahl::Mood::Concerned);
        } else if (strcmp(emotion, "doubtful") == 0) {
            companion.setMood(ahl::Mood::Curious);
        } else {
            companion.setMood(ahl::Mood::Calm);
        }
    }
''')
display.write_text(display_source)

# Camera motion sampling uses the real camera without shutter audio or preview.
# It is a movement cue, not facial or person recognition.
camera_header=root/"upstream/firmware/main/hal/board/stackchan_camera.h"
camera_source=camera_header.read_text()
camera_anchor="    bool StreamCaptures();"
if camera_source.count(camera_anchor)!=1:
    raise SystemExit("ERROR: unexpected camera header")
camera_source=camera_source.replace(camera_anchor,camera_anchor+'''
    // Low-rate background sampling, preserving the existing capture lock.
    bool SamplePresenceMotion(float* change) {
        if (!change || !StreamCaptures()) return false;
        auto lock = TryLockFrame();
        if (!lock.owns_lock() || !frame_.data || frame_.len < 512) return false;
        // Compare stable positions in successive raw camera frames.
        // Encoded formats are deliberately excluded to avoid false detection.
        if (frame_.format != V4L2_PIX_FMT_RGB565 &&
            frame_.format != V4L2_PIX_FMT_YUYV) return false;
        constexpr size_t kSamples = 128;
        uint8_t current[kSamples];
        for (size_t i=0;i<kSamples;++i) current[i]=frame_.data[(i*frame_.len/kSamples)&~size_t(1)];
        if (!sample_ready_) {
            memcpy(previous_sample_,current,kSamples);
            sample_ready_=true;
            return false;
        }
        unsigned sum=0;
        for (size_t i=0;i<kSamples;++i) {
            sum += current[i]>previous_sample_[i] ?
                current[i]-previous_sample_[i] : previous_sample_[i]-current[i];
        }
        memcpy(previous_sample_,current,kSamples);
        *change=static_cast<float>(sum)/(kSamples*255.0f);
        return true;
    }
private:
    uint8_t previous_sample_[128] = {};
    bool sample_ready_ = false;
public:
''')
camera_source=camera_source.replace('#include "esp_video.h"','#include "esp_video.h"\n#include <cstring>\n#include <linux/videodev2.h>')
camera_header.write_text(camera_source)
print("AHL companion patch applied to",original,"and AI-on-boot default enabled")
