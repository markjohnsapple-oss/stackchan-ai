# Arcade Home Labs StackChan AI

This is a customisation project for M5Stack StackChan firmware, compiled with GitHub Actions.

## Current development milestone
The first integration adds a small, bounded companion state machine to the existing AI Agent app, while preserving Xiaozhi voice startup, UI, controls and other upstream firmware features. It does **not** yet implement camera presence detection, spoken proactive greetings, persistent memory or wake-word-free listening. Those require real device/service integration.

Run the **Build StackChan firmware** workflow in GitHub Actions. Its ZIP artifact contains firmware binaries and flash arguments. Do not flash until the build has succeeded and the target hardware and recovery route are confirmed.

No private credentials or conversation data should be committed to this public repository.
