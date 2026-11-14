#!/usr/bin/env python3
"""Create a minimal original-StackChan/XiaoZhi build from the pinned official source.

Runs ONLY against the temporary GitHub Actions 'upstream' checkout.
Does not change AHL's v5-v9 release branches, approved face files, or NVS.
This first pass strips duplicate ASL Companion integration and unused launcher
apps while retaining native AI Agent, setup, ESP-NOW remote, camera and motors.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "upstream/firmware/main"
MAIN = BASE / "main.cpp"
APPS = BASE / "apps/apps.h"
CMAKE = BASE / "CMakeLists.txt"

def once(src: str, before: str, after: str, label: str) -> str:
    n = src.count(before)
    if n != 1:
        raise RuntimeError(f"STOP: unexpected official {label}: {n} matches")
    return src.replace(before, after, 1)

def main():
    texts = {path: path.read_text(encoding="utf-8") for path in (MAIN, APPS, CMAKE)}
    entry, headers, cmake = texts[MAIN], texts[APPS], texts[CMAKE]

    # Ordinary power-on goes straight to the EXISTING XiaoZhi AI.
    # The factory Home button's warm-reboot target still opens the reduced
    # launcher, giving access to Setup and ESP-NOW Remote for recovery.
    entry = once(
        entry,
        "const bool skip_mooncake = GetHAL().getXiaozhiConfig().startAiAgentOnBoot && GetHAL().getWarmRebootTarget() < 0;",
        "const bool skip_mooncake = GetHAL().getWarmRebootTarget() < 0;",
        "auto-start control")
    # These are standalone menu apps, not the underlying camera/avatar/servo
    # and ESP-NOW implementations used by the native AI.
    unused = [
        ('App::Avatar', '''        hal_toggles::register_app_id(hal_toggles::App::Avatar, GetMooncake().installApp(std::make_unique<AppAvatar>()));
'''),
        ('App::AppCenter', '''        hal_toggles::register_app_id(hal_toggles::App::AppCenter,
                                     GetMooncake().installApp(std::make_unique<AppAppCenter>()));
'''),
        ('App::Ezdata', '''        hal_toggles::register_app_id(hal_toggles::App::Ezdata, GetMooncake().installApp(std::make_unique<AppEzdata>()));
'''),
        ('App::Dance', '''        hal_toggles::register_app_id(hal_toggles::App::Dance, GetMooncake().installApp(std::make_unique<AppDance>()));
''')
    ]
    for label, line in unused:
        entry = once(entry, line, "", "remove " + label)

    for app in ("app_avatar", "app_app_center", "app_ezdata", "app_dance"):
        header = f'#include "{app}/{app}.h"\n'
        headers = once(headers, header, "", "remove header " + app)

    cmake = once(
        cmake,
        "list(APPEND STACK_CHAN_SOURCES main.cpp)",
        '''# AHL slim v1: EXCLUDE unused standalone apps from the compiled binary.
# Never exclude stackchan/ avatar engine, audio, camera, servo, ESP-NOW or Setup.
list(FILTER STACK_CHAN_SOURCES EXCLUDE REGEX "apps/(app_avatar|app_app_center|app_ezdata|app_dance|app_template)/")
list(APPEND STACK_CHAN_SOURCES main.cpp)''',
        "compiled-source filtering")

    required = {
        "original XiaoZhi start": "GetHAL().startXiaozhi();",
        "factory AI Agent in recovery launcher": "std::make_unique<AppAiAgent>()",
        "factory settings/recovery": "std::make_unique<AppSetup>()",
        "physical ESP-NOW remote receiver": "std::make_unique<AppEspnowControl>()",
        "recovery reboot guard": "GetHAL().getWarmRebootTarget() < 0",
    }
    for label, marker in required.items():
        if marker not in entry:
            raise RuntimeError("STOP: protected " + label + " disappeared")

    if "AppAslCompanion" in entry or "AppAslCompanion" in headers:
        raise RuntimeError("STOP: duplicate Companion app unexpectedly present")
    if '#include "app_espnow_ctrl/app_espnow_ctrl.h"' not in headers:
        raise RuntimeError("STOP: hardware remote app header lost")
    for path, contents in ((MAIN, entry), (APPS, headers), (CMAKE, cmake)):
        path.write_text(contents, encoding="utf-8")
    print("AHL SLIM V1 VERIFIED: native AI boots directly; reduced recovery menu")
    print("Included: original XiaoZhi, microphone, speaker, camera, motors, ESP-NOW Remote, Setup.")
    print("Excluded from compiled app: Avatar demo, App Centre, EZData, Dance, Template.")
    print("Skipped entirely: all custom ASL Companion overlays, memories, watcher and face.")
    print("Unchanged: original wake word, factory AI face, voice and saved settings.")

if __name__ == "__main__":
    main()
