#!/usr/bin/env python3
"""AHL v6, narrowly scoped changes on a disposable verified-v5 source checkout.
Executed after existing brain, v4 media, v5 memory and LVGL compatibility patches.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / 'upstream' / 'firmware' / 'main'
LIVE = UP / 'apps' / 'app_asl_companion' / 'asl_live_mode.cpp'
HAL = UP / 'hal' / 'hal.cpp'

def replace_exact(text, old, new, label):
    hits = text.count(old)
    if hits != 1:
        raise RuntimeError(f'Unexpected code for {label}: expected 1 occurrence, found {hits}')
    return text.replace(old, new, 1)

def main():
    before = {p: p.read_text(encoding='utf-8') for p in (LIVE, HAL)}
    live, hal = before[LIVE], before[HAL]
    # Reduce the maximum retry silence, while retaining rate limiting.
    live = replace_exact(live,
        'now - last_auto_start_ms.load() < 15000',
        'now - last_auto_start_ms.load() < 6000',
        'auto listen retry delay')
    live = replace_exact(live,
        'now - greeting_end_ms.load()) < 2500',
        'now - greeting_end_ms.load()) < 1000',
        'greeting listening delay')
    # Do not start a new conversation while speech remains in output queue.
    live = replace_exact(live,
        '    if (last_auto_start_ms.load() != 0 && now - last_auto_start_ms.load() < 6000) return;\n',
        '    if (last_auto_start_ms.load() != 0 && now - last_auto_start_ms.load() < 6000) return;\n'
        '    if (!Application::GetInstance().GetAudioService().IsPlaybackIdle()) return;\n',
        'audio playback guard')
    # Protect factory AI Agent, and avoid camera contention while voice is active.
    hal = replace_exact(hal,
        '        if (!hal_bridge::is_xiaozhi_ready()) continue;',
        '        if (!asl_live::requested() || !hal_bridge::is_xiaozhi_ready() ||\n'
        '            !hal_bridge::is_xiaozhi_idle()) continue;',
        'ASL-only camera motion gate')
    required = {
        'auto-listen': ('auto_listen_enabled', live),
        'camera observation': ('SamplePresenceMotion', hal),
        'memory search': ('ahl.memory.search', hal),
        'approved greeting': ('greeting_begin', live),
        'face animation': ('asl_face::Sequence::Talking', live),
    }
    for label,(marker,source) in required.items():
        if marker not in source:
            raise RuntimeError('Missing protected v5 feature: ' + label)
    for path, content in ((LIVE,live),(HAL,hal)):
        path.write_text(content,encoding='utf-8')
    print('ASL v6 listening and camera-isolation changes applied safely.')

if __name__=='__main__':
    main()
