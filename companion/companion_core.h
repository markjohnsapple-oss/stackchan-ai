#pragma once
#include <cstdint>
#include <cstdio>
#include <string>
#include "nvs.h"
#include "nvs_flash.h"

namespace ahl {
enum class State : uint8_t { Idle, Listening, Thinking, Speaking };

// Persistent companion identity and interaction counters, stored in flash NVS.
// No credentials or conversation recordings are stored here.
class CompanionMemory {
public:
    bool load() {
        esp_err_t e = nvs_open("ahl_companion", NVS_READWRITE, &handle_);
        if (e != ESP_OK) return false;
        uint32_t count = 0;
        if (nvs_get_u32(handle_, "visits", &count) == ESP_OK) visits_ = count;
        uint32_t greetings = 0;
        if (nvs_get_u32(handle_, "greetings", &greetings) == ESP_OK) greetings_ = greetings;
        return true;
    }
    ~CompanionMemory() { if (handle_) nvs_close(handle_); }
    bool recordVisit() {
        if (!handle_) return false;
        ++visits_;
        return nvs_set_u32(handle_, "visits", visits_) == ESP_OK &&
               nvs_commit(handle_) == ESP_OK;
    }
    bool recordGreeting() {
        if (!handle_) return false;
        ++greetings_;
        return nvs_set_u32(handle_, "greetings", greetings_) == ESP_OK &&
               nvs_commit(handle_) == ESP_OK;
    }
    uint32_t visits() const { return visits_; }
    uint32_t greetings() const { return greetings_; }
private:
    nvs_handle_t handle_ = 0;
    uint32_t visits_ = 0, greetings_ = 0;
};

class CompanionCore {
public:
    void onPresence(bool present, uint32_t now) {
        if (present_ == present) return;
        present_ = present;
        if (!present) greeted_ = false;
        entered_at_ = now;
    }
    bool shouldGreet(uint32_t now) const {
        return present_ && !greeted_ && state_ == State::Idle &&
            (uint32_t)(now - entered_at_) >= 1500 &&
            (last_greet_ == 0 || (uint32_t)(now - last_greet_) >= 60000);
    }
    void markGreeted(uint32_t now) { greeted_ = true; last_greet_ = now; }
    void setState(State state) { state_ = state; }
    State state() const { return state_; }
    // Gentle idle animation scheduler; caller decides how to animate.
    bool idlePulseDue(uint32_t now) {
        if (state_ != State::Idle || (uint32_t)(now - last_pulse_) < 15000) return false;
        last_pulse_ = now;
        return true;
    }
private:
    bool present_ = false, greeted_ = false;
    uint32_t entered_at_ = 0, last_greet_ = 0, last_pulse_ = 0;
    State state_ = State::Idle;
};
} // namespace ahl
