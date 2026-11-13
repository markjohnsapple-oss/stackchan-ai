#!/usr/bin/env python3
"""Minimal ESP-IDF 6.1 / LVGL 9.5 compatibility fixes after all ASL overlays.
Run only against the disposable pinned upstream checkout; fail closed on drift.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / 'upstream/firmware/main'
CAMERA = UP / 'hal/board/stackchan_camera.h'
APP = UP / 'apps/app_asl_companion/app_asl_companion.cpp'
LIVE = UP / 'apps/app_asl_companion/asl_live_mode.cpp'

def once(text, old, replacement, name):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'STOP: unexpected {name} occurrence count: {count}')
    return text.replace(old, replacement, 1)

def compile_fixes():
    originals = {p: p.read_text() for p in (CAMERA, APP, LIVE)}
    camera = originals[CAMERA]
    # EspVideo already defines the video pixel formats. Avoid duplicate macros.
    camera = once(camera, '#include <linux/videodev2.h>\n', '', 'camera format duplicate include')
    # The original overlay inserted SamplePresenceMotion before an auto-return
    # TryLockFrame definition. Acquire that same recursive mutex explicitly.
    camera = once(camera,
                  '        auto lock = TryLockFrame();',
                  '        std::unique_lock<std::recursive_mutex> lock(capture_mutex_, std::try_to_lock);',
                  'camera auto-return forward reference')
    # LVGL 9.5 exports image-cache eviction in this dedicated internal header.
    include = '#include <src/misc/cache/instance/lv_image_cache.h>\n'
    app = originals[APP]
    live = originals[LIVE]
    if app.count('lv_image_cache_drop(') != 2 or live.count('lv_image_cache_drop(') != 2:
        raise RuntimeError('STOP: unexpected face cache usage; refusing to patch')
    app = once(app, '#include "app_asl_companion.h"\n',
               '#include "app_asl_companion.h"\n' + include, 'app header anchor')
    live = once(live, '#include "asl_live_mode.h"\n',
                '#include "asl_live_mode.h"\n' + include, 'live header anchor')
    for path, content in ((CAMERA, camera), (APP, app), (LIVE, live)):
        path.write_text(content)
    print('AHL compatibility fixes applied; camera and animation features remain intact.')

if __name__ == '__main__':
    compile_fixes()
