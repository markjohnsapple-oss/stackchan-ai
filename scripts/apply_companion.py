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
text=text.replace('    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_V1_ACTIVE");','    static ahl::CompanionCore companion;\n    static ahl::CompanionCore companion_memory;\n    static bool memory_ready = companion_memory.openMemory();\n    if (memory_ready) companion_memory.recordVisit();\n    companion.setState(ahl::State::Listening);\n    mclog::tagInfo(getAppInfo().name, "AHL_COMPANION_V1_ACTIVE");')
original.write_text(text)
hal=root/"upstream/firmware/main/hal/hal.cpp"
if not hal.exists():
    raise SystemExit(f"ERROR: missing HAL: {hal}")
hal_source=hal.read_text()
start_marker='void Hal::startXiaozhi()\n{'
if hal_source.count(start_marker)!=1:
    raise SystemExit("ERROR: unexpected startup function")
hal_source=hal_source.replace('#include "hal.h"', '#include "hal.h"\n#include "companion_core.h"')
hal_source=hal_source.replace(start_marker,start_marker+'\n    static ahl::CompanionCore ahl_memory;\n    const bool ahl_memory_ready = ahl_memory.openMemory();\n    if (ahl_memory_ready) ahl_memory.recordVisit();\n    mclog::tagInfo(_tag, "AHL_COMPANION_BOOT visits={}", ahl_memory.visits());')
hal.write_text(hal_source)
shutil.copyfile(root/"companion/companion_core.h",root/"upstream/firmware/main/hal/companion_core.h")
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
print("AHL companion patch applied to",original,"and AI-on-boot default enabled")
