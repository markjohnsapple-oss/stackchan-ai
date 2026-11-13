#!/usr/bin/env python3
"""Add consent-only local vector memories and auto-relisten to ASL v4 after base overlay.
Do not run on a working device tree. Used only in disposable CI checkout.
"""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'upstream/firmware'

# Exact source-side markers from ASL Companion v4. All are validated before any edits.
LIVE=UP/'main/apps/app_asl_companion/asl_live_mode.cpp'
HAL=UP/'main/hal/hal.cpp'
DISPLAY=UP/'main/hal/board/stackchan_display.cc'
BRIDGE=UP/'main/hal/board/hal_bridge.h'
CHANGES={
 BRIDGE:[
  ('bool startAiAgentOnBoot          = true;', 'bool startAiAgentOnBoot          = false;')
 ],
 LIVE:[
  ('#include <string_view>', '#include <string_view>\n#include <application.h>'),
  ('std::atomic<uint32_t> greeting_end_ms{0};', 'std::atomic<uint32_t> greeting_end_ms{0};\nstd::atomic<bool> auto_listen_enabled{true};\nstd::atomic<uint32_t> last_auto_start_ms{0};'),
  ('lv_obj_t* face = nullptr;', 'lv_obj_t* face = nullptr;\nlv_obj_t* auto_button = nullptr;\nlv_obj_t* auto_label = nullptr;'),
  ('void on_touch(lv_event_t*) {', '''void on_auto_toggle(lv_event_t*) {
    const bool enabled = !auto_listen_enabled.load();
    auto_listen_enabled.store(enabled);
    if (auto_label) lv_label_set_text(auto_label, enabled ? "AUTO ON" : "AUTO OFF");
    if (!enabled) Application::GetInstance().StopListening();
}
void on_touch(lv_event_t*) {'''),
  ('''    bool expected = false;
    if (!greeting_started.compare_exchange_strong(expected, true)) return;
    const uint32_t now = static_cast<uint32_t>(esp_timer_get_time() / 1000);
    greeting_end_ms.store(now + GREETING_DURATION_MS);
#ifdef ASL_HOST_TEST
    // The actual encoded sound is validated separately with ffprobe.
    hal_bridge::app_play_sound(std::string_view("OggS", 4));
#else
    hal_bridge::app_play_sound(std::string_view(greeting_begin,
       static_cast<size_t>(greeting_end - greeting_begin)));
#endif''', '''    bool expected = false;
    const uint32_t now = static_cast<uint32_t>(esp_timer_get_time() / 1000);
    if (greeting_started.compare_exchange_strong(expected, true)) {
        greeting_end_ms.store(now + GREETING_DURATION_MS);
#ifdef ASL_HOST_TEST
        hal_bridge::app_play_sound(std::string_view("OggS", 4));
#else
        hal_bridge::app_play_sound(std::string_view(greeting_begin,
           static_cast<size_t>(greeting_end - greeting_begin)));
#endif
        return;
    }
    // The ASL menu selection is an explicit opt-in to continuous conversations.
    // Keep the original factory AI Agent's listening behaviour unchanged.
    if (!auto_listen_enabled.load() || !hal_bridge::is_xiaozhi_ready() ||
        !hal_bridge::is_xiaozhi_idle()) return;
    if (static_cast<int32_t>(now - greeting_end_ms.load()) < 2500) return;
    if (last_auto_start_ms.load() != 0 && now - last_auto_start_ms.load() < 15000) return;
    last_auto_start_ms.store(now);
    hal_bridge::toggle_xiaozhi_chat_state();'''),
  ('    lv_obj_add_event_cb(face, on_touch, LV_EVENT_CLICKED, nullptr);', '''    lv_obj_add_event_cb(face, on_touch, LV_EVENT_CLICKED, nullptr);
    auto_button = lv_button_create(screen);
    lv_obj_set_size(auto_button, 78, 25);
    lv_obj_align(auto_button, LV_ALIGN_TOP_RIGHT, -3, 3);
    lv_obj_add_event_cb(auto_button, on_auto_toggle, LV_EVENT_CLICKED, nullptr);
    auto_label = lv_label_create(auto_button);
    lv_label_set_text(auto_label, "AUTO ON");
    lv_obj_center(auto_label);
    lv_obj_move_foreground(auto_button);'''),
  ('    greeting_end_ms.store(0);\n    current_sequence = asl_face::Sequence::Idle;', '    greeting_end_ms.store(0);\n    auto_listen_enabled.store(true);\n    last_auto_start_ms.store(0);\n    current_sequence = asl_face::Sequence::Idle;'),
  ('void reset() {\n    if (face) {', '''void reset() {
    if (auto_button) { lv_obj_delete(auto_button); auto_button = nullptr; auto_label = nullptr; }
    if (face) {'''),
  ('    greeting_end_ms.store(0);\n    current_frame = 0;', '    greeting_end_ms.store(0);\n    auto_listen_enabled.store(true);\n    last_auto_start_ms.store(0);\n    current_frame = 0;')
 ],
 HAL:[
  ('#include <apps/app_asl_companion/asl_live_mode.h>', '#include <apps/app_asl_companion/asl_live_mode.h>\n#include "ahl_memory_service.h"\n#include <mcp_server.h>'),
  ('    hal_bridge::start_xiaozhi_app();', '''    // AI can query facts the user explicitly instructed ASL Companion to remember.
    // Factory AI Agent receives no access to ASL private memories.
    McpServer::GetInstance().AddTool(
        "ahl.memory.search", "Search locally saved, user-approved ASL Companion notes. "
        "Only use when asked to recall something. Never invent a memory.",
        PropertyList({Property("query", kPropertyTypeString)}),
        [](const PropertyList& p) -> ReturnValue {
            if (!asl_live::requested()) return std::string("ASL Companion mode inactive");
            return ahl::getAslMemory().search(p["query"].value<std::string>());
        });
    hal_bridge::start_xiaozhi_app();'''),
 ],
 DISPLAY:[
  ('#include <apps/app_asl_companion/asl_live_mode.h>', '#include <apps/app_asl_companion/asl_live_mode.h>\n#include <hal/ahl_memory_service.h>'),
  ('void StackChanAvatarDisplay::SetChatMessage(const char* role, const char* content)\n{', '''void StackChanAvatarDisplay::SetChatMessage(const char* role, const char* content)
{
    // Store only an explicit user speech command such as "remember that ...".
    // No automatic transcript, photo or facial data retention.
    if (role && content && strcmp(role, "user") == 0 && asl_live::requested()) {
        (void)ahl::getAslMemory().processExplicitUtterance(content);
    }'''),
 ]
}

def apply():
    staged={}
    for path, patches in CHANGES.items():
        text=path.read_text()
        if not text: raise RuntimeError('Empty source: '+str(path))
        for old,new in patches:
            if text.count(old)!=1:
                raise RuntimeError('Source unexpectedly changed in '+str(path)+' marker='+old[:60])
            text=text.replace(old,new,1)
        staged[path]=text
    headers={
        UP/'main/hal/ahl_vector_index.h': ROOT/'companion/ahl_vector_index.h',
        UP/'main/hal/ahl_memory_service.h': ROOT/'companion/ahl_memory_service.h',
    }
    for target,src in headers.items():
        if not src.is_file() or target.exists(): raise RuntimeError('Source missing or collides: '+str(src))
    for target,content in staged.items(): target.write_text(content)
    for target,src in headers.items(): shutil.copyfile(src,target)
    print('AHL ASL opt-in auto conversation and explicit vector memory integrated.')

if __name__=='__main__': apply()