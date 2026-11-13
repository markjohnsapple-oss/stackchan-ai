#pragma once
#include <cstdint>
namespace ahl {
enum class State : uint8_t { Idle, Listening, Thinking, Speaking };
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
private:
  bool present_ = false, greeted_ = false;
  uint32_t entered_at_ = 0, last_greet_ = 0;
  State state_ = State::Idle;
};
} // namespace ahl
