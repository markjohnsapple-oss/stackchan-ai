#pragma once
// Arcade Home Labs StackChan Brain V1: local, deterministic decision layer.
// No network calls, audio playback, camera capture or hardware ownership.
// Hardware events are supplied by the existing StackChan firmware.
#include <cstdint>
#include <string>
namespace ahl {
enum class BrainAction : uint8_t { None, Greet, CheckIn };
struct BrainInput {
    uint32_t now_ms = 0;
    bool person_present = false;
    bool cloud_ready = false;
    bool robot_idle = false;
    bool quiet_hours = false;
};
class CompanionBrain {
public:
    BrainAction decide(const BrainInput& in) const {
        if (!in.person_present || !in.cloud_ready || !in.robot_idle || in.quiet_hours)
            return BrainAction::None;
        if (arrival_pending_ && elapsed(in.now_ms, arrival_ms_) >= 1500 &&
            (!last_greet_valid_ || elapsed(in.now_ms, last_greet_ms_) >= 60000))
            return BrainAction::Greet;
        if (!arrival_pending_ && elapsed(in.now_ms, last_interaction_ms_) >= 300000 &&
            (!last_checkin_valid_ || elapsed(in.now_ms, last_checkin_ms_) >= 900000))
            return BrainAction::CheckIn;
        return BrainAction::None;
    }
    void presenceChanged(bool present, uint32_t now) {
        if (present == present_) return;
        present_ = present;
        arrival_pending_ = present;
        arrival_ms_ = now;
        if (!present) last_interaction_ms_ = now;
    }
    void interaction(uint32_t now) { last_interaction_ms_ = now; }
    // Call ONLY after a spoken greeting/check-in is successfully initiated.
    void accepted(BrainAction action, uint32_t now) {
        if (action == BrainAction::Greet) {
            arrival_pending_ = false;
            last_greet_valid_ = true;
            last_greet_ms_ = now;
        } else if (action == BrainAction::CheckIn) {
            last_checkin_valid_ = true;
            last_checkin_ms_ = now;
        }
        if (action != BrainAction::None) last_interaction_ms_ = now;
    }
    static const char* instruction(BrainAction action) {
        switch (action) {
            case BrainAction::Greet: return "A person has just arrived. Greet them briefly and naturally; do not claim to recognise their identity.";
            case BrainAction::CheckIn: return "The person is nearby and the conversation has been quiet. Offer one short, friendly check-in without demanding a reply.";
            default: return "";
        }
    }
    static const char* personality() {
        return "You are StackChan, an Arcade Home Labs AI companion. Speak warmly and naturally in British English. Be curious, concise and respectful. Do not invent memories, camera observations or feelings.";
    }
private:
    static uint32_t elapsed(uint32_t now, uint32_t then) { return now - then; }
    bool present_ = false;
    bool arrival_pending_ = false;
    bool last_greet_valid_ = false;
    bool last_checkin_valid_ = false;
    uint32_t arrival_ms_ = 0;
    uint32_t last_greet_ms_ = 0;
    uint32_t last_checkin_ms_ = 0;
    uint32_t last_interaction_ms_ = 0;
};
} // namespace ahl
