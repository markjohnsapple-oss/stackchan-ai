#!/usr/bin/env python3
"""Add approved ASL v4 visual/voice mode AFTER the owner's existing brain patch.

Pinned base source: m5stack/StackChan @ 28b9f0c8bd6acd81cb3c70f1a93c3e373b39d400.
Existing scripts/apply_companion.py runs first and is intentionally untouched.
Only run in the disposable GitHub Actions upstream checkout; never flash automatically.
"""
from pathlib import Path
import hashlib
import tarfile

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/firmware"
PACKAGE = ROOT / "assets/ASL_Companion_v4_overlay.tar.xz"
EXPECTED_SHA256 = "634e2c195f37ddca2dc4f208df24c1c3f7eb33429c31866cc00cb6473c03f54a"
if not PACKAGE.is_file() or hashlib.sha256(PACKAGE.read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise SystemExit("STOP: Approved ASL v4 media archive is missing or altered.")
version = (UP / "CMakeLists.txt").read_text()
if 'set(PROJECT_VER "1.6.2")' not in version:
    raise SystemExit("STOP: This is not the approved 1.6.2 firmware source.")

# Check the installed AHL brain first; no regressions to the existing master.
agent = (UP / "main/apps/app_ai_agent/app_ai_agent.cpp").read_text()
hal_path = UP / "main/hal/hal.cpp"
hal = hal_path.read_text()
if "AHL_COMPANION_V1_ACTIVE" not in agent or "AHL_COMPANION_BOOT" not in hal:
    raise SystemExit("STOP: Existing AHL companion brain must be installed first.")

# Validate the entire archived overlay before writing anything.
expected = {
    "app_asl_companion.cpp", "app_asl_companion.h", "asl_face_assets.cpp",
    "asl_face_assets.h", "asl_face_data.inc", "asl_icon_pixels.inc",
    "asl_live_mode.cpp", "asl_live_mode.h",
}
archive_files = {}
with tarfile.open(PACKAGE, "r:xz") as tf:
    for item in tf.getmembers():
        if not item.isfile():
            continue
        name = item.name
        start = "overlay/firmware/main/apps/app_asl_companion/"
        if name.startswith(start) and name[len(start):] in expected:
            rel = "main/apps/app_asl_companion/" + name[len(start):]
        elif name == "overlay/firmware/main/assets/sfx/asl_companion_greeting.ogg":
            rel = "main/assets/sfx/asl_companion_greeting.ogg"
        else:
            raise SystemExit("STOP: unexpected archive file " + name)
        if rel in archive_files:
            raise SystemExit("STOP: duplicate archived file " + rel)
        archive_files[rel] = tf.extractfile(item).read()
if len(archive_files) != len(expected) + 1:
    raise SystemExit("STOP: incomplete ASL v4 source archive")

main_path = UP / "main/main.cpp"
apps_path = UP / "main/apps/apps.h"
display_path = UP / "main/hal/board/stackchan_display.cc"
changes = {
    main_path: [
        ('        GetMooncake().installApp(std::make_unique<AppSetup>());',
         '        GetMooncake().installApp(std::make_unique<AppSetup>());\n'
         '        GetMooncake().installApp(std::make_unique<AppAslCompanion>());')
    ],
    apps_path: [
        ('#include "app_dance/app_dance.h"',
         '#include "app_dance/app_dance.h"\n#include "app_asl_companion/app_asl_companion.h"')
    ],
    hal_path: [
        ('#include <assets/assets.h>',
         '#include <assets/assets.h>\n#include <apps/app_asl_companion/asl_live_mode.h>'),
        ('        tools::update_reminders();',
         '        tools::update_reminders();\n        asl_live::service_audio();'),
        ('        GetStackChan().update();',
         '        GetStackChan().update();\n        asl_live::tick(GetHAL().millis());')
    ],
    display_path: [
        ('#include <hal/hal.h>',
         '#include <hal/hal.h>\n#include <apps/app_asl_companion/asl_live_mode.h>'),
        ('    stackchan.attachAvatar(std::move(avatar));',
         '    stackchan.attachAvatar(std::move(avatar));\n    asl_live::mount(lv_screen_active());'),
        ('    bool is_idle      = false;\n    bool is_listening = false;',
         '    bool is_idle      = false;\n    bool is_listening = false;\n'
         '    if (status && strcmp(status, Lang::Strings::STANDBY) == 0) asl_live::agent_standby();\n'
         '    asl_live::set_talking(status && strcmp(status, Lang::Strings::SPEAKING) == 0);')
    ]
}
staged = {}
for path, replacements in changes.items():
    original = path.read_text()
    modified = original
    for old, new in replacements:
        if modified.count(old) != 1:
            raise SystemExit("STOP: source marker missing or duplicated: " + str(path) + " / " + old)
        modified = modified.replace(old, new, 1)
    staged[path] = modified
for rel, content in archive_files.items():
    target = UP / rel
    if target.exists() and target.read_bytes() != content:
        raise SystemExit("STOP: existing resource differs: " + str(target))

# Commit into the disposable upstream checkout only after all validations.
for path, txt in staged.items():
    path.write_text(txt)
for rel, content in archive_files.items():
    target = UP / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
print("AHL ASL v4 media installed after existing brain; factory apps retained.")
print("New ASL Companion app: wake-up, idle/talking GIF-derived frames, greeting via original Opus service.")
print("No claim of active face recognition, voice cloning, internet learning, or always-on listening.")
