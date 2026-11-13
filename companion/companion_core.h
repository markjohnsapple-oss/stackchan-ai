#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "nvs.h"
#include "nvs_flash.h"

namespace ahl {
enum class State : uint8_t { Idle, Listening, Thinking, Speaking };
enum class Mood : uint8_t { Calm, Curious, Happy, Concerned };

// Seven-feature companion orchestration. Hardware/audio/cloud transports
// are supplied by the firmware's existing services, not simulated here.
class CompanionCore {
public:
    // 1: Conversational turn management, with no wake-word requirement at
    // this layer. The audio service must feed speech events continuously.
    void speechStarted(uint32_t now) { state_=State::Listening; last_interaction_=now; }
    void speechEnded(uint32_t now) { state_=State::Thinking; last_interaction_=now; }
    void responseStarted(uint32_t now) { state_=State::Speaking; last_interaction_=now; }
    void responseEnded(uint32_t now) { state_=State::Idle; last_interaction_=now; ++turns_; }
    State state() const { return state_; }

    // 2: Camera/presence events, with debounce and greeting cooldown.
    void onPresence(bool present, uint32_t now) {
        if (present_ == present) return;
        present_=present; entered_at_=now;
        if (!present) greeted_=false;
    }
    bool shouldGreet(uint32_t now) const {
        return present_ && !greeted_ && state_==State::Idle &&
            (uint32_t)(now-entered_at_)>=1500 &&
            (last_greet_==0 || (uint32_t)(now-last_greet_)>=60000);
    }
    void markGreeted(uint32_t now) { greeted_=true; last_greet_=now; }

    // 3: Persistent bounded text memories. The caller must provide consent
    // before writing personal conversation details.
    bool openMemory() {
        if (handle_) return true;
        if (nvs_open("ahl_companion",NVS_READWRITE,&handle_)!=ESP_OK) return false;
        nvs_get_u32(handle_,"visits",&visits_);
        nvs_get_u32(handle_,"turns",&saved_turns_);
        size_t len=0;
        if (nvs_get_str(handle_,"memory",nullptr,&len)==ESP_OK && len>0 && len<=2048) {
            std::vector<char> buffer(len);
            if (nvs_get_str(handle_,"memory",buffer.data(),&len)==ESP_OK) memory_=buffer.data();
        }
        return true;
    }
    bool saveMemory(const std::string& note) {
        if (!handle_ || note.size()>1800) return false;
        memory_=note;
        return nvs_set_str(handle_,"memory",memory_.c_str())==ESP_OK &&
               nvs_commit(handle_)==ESP_OK;
    }
    const std::string& memory() const { return memory_; }
    bool recordVisit() {
        if (!handle_) return false;
        ++visits_;
        return nvs_set_u32(handle_,"visits",visits_)==ESP_OK &&
               nvs_commit(handle_)==ESP_OK;
    }
    bool saveTurnCount() {
        if (!handle_) return false;
        saved_turns_+=turns_; turns_=0;
        return nvs_set_u32(handle_,"turns",saved_turns_)==ESP_OK &&
               nvs_commit(handle_)==ESP_OK;
    }
    uint32_t visits() const { return visits_; }
    ~CompanionCore() { if (handle_) nvs_close(handle_); }

    // 4: Stable personality with context-dependent mood.
    void setMood(Mood mood) { mood_=mood; }
    Mood mood() const { return mood_; }
    std::string personalityPrompt() const {
        std::string prompt="You are an Arcade Home Labs companion: warm, curious, concise, respectful, and honest. "
            "Speak naturally in British English. Never claim to see or remember anything unless data confirms it. ";
        if (!memory_.empty()) prompt+="Saved user-approved context: "+memory_+". ";
        return prompt;
    }

    // 5: Non-blocking expressive animation cue scheduling.
    bool idlePulseDue(uint32_t now) {
        if (state_!=State::Idle || (uint32_t)(now-last_pulse_)<15000) return false;
        last_pulse_=now; return true;
    }

    // 6: Proactive interaction eligibility with cooldown and quiet-time gate.
    bool proactiveDue(uint32_t now, bool quiet_hours) const {
        return !quiet_hours && present_ && state_==State::Idle &&
            (uint32_t)(now-last_interaction_)>300000 &&
            (uint32_t)(now-last_proactive_)>900000;
    }
    void markProactive(uint32_t now) { last_proactive_=now; }

    // 7: Cloud-AI request context for the existing Wi-Fi transport.
    // Transport and credential handling remain with Xiaozhi.
    std::string cloudContext() const { return personalityPrompt(); }
private:
    nvs_handle_t handle_=0;
    State state_=State::Idle;
    Mood mood_=Mood::Curious;
    bool present_=false, greeted_=false;
    uint32_t entered_at_=0,last_greet_=0,last_pulse_=0;
    uint32_t last_interaction_=0,last_proactive_=0;
    uint32_t visits_=0,turns_=0,saved_turns_=0;
    std::string memory_;
};
CompanionCore& getCompanion();
} // namespace ahl
