"""把「RDR2 原生骨架 · 动作预览」用到的 10 个 clip 用**修好的解码器**重产一遍。

为什么要重产：`export/skeleton_runtime/rdr2_actions.html` 是从
`骑砍2动画重定向/input/source/rdr2/*.gltf` 读数据的，而这批 gltf 是 2026-10-17 上午
用**旧解码器**（缓存四元数按 quat_index 摆放）产出的 ⇒ 页面里骨架是畸形的。

用法: uv run python tools/rebuild_rdr2_clips.py
"""
import os
import subprocess
import sys

PROJ = r'D:/BrainMaker/大镖客2解包分析'
UV = r'C:/Users/yaodongcheng/AppData/Roaming/com.brainmaker.client/cowork-updates/uv-binary/uv.exe'
AN = os.path.join(PROJ, 'export/animations')
OUT = r'D:/BrainMaker/骑砍2动画重定向/input/source/rdr2'
TMP = os.path.join(PROJ, 'work/npc/anim/rebuild')

# (输出 gltf 名, ycd 相对路径, 额外参数)
CLIPS = [
    # ★ 2026-10-17 晚：改用 arthur 的 walk_interior（q5，带真膝弯；block1 = 398 帧 / 13.2 s）
    #   旧的 walk_slow「move」是 q7 低细节版，小腿只弯 3~6°，视觉上像"在大腿根折"。
    ('rdr2_walk',          'mech_loco_m/mech_loco_m@character@arthur@normal@unarmed@walk_interior.ycd',
     ['--anim', '1', '--debias', '--fix-thigh-axis', '--repair-ramps',
      '--mirror-left-leg', '--keep-arm-bias', '--clamp-arms', '22', '--drop-root']),
    ('rdr2_carried_human', 'mech_carry_ped/mech_carry_ped@dead@carried@human.ycd',          ['--auto', '--drop-root']),
    ('rdr2_carried_mount', 'mech_carry_ped/mech_carry_ped@dead@carried@mount.ycd',          ['--auto', '--drop-root']),
    ('rdr2_drop_body',     'mech_carry_ped/mech_carry_ped@dead@drop_body.ycd',              ['--auto', '--drop-root']),
    ('rdr2_injured_idle',  'mech_carry_ped/mech_carry_ped@injured@idle.ycd',                ['--auto', '--drop-root']),
    ('rdr2_pickup_body',   'mech_carry_ped/mech_carry_ped@dead@pickup_body.ycd',            ['--auto', '--drop-root']),
    ('rdr2_putdown_body',  'mech_carry_ped/mech_carry_ped@dead@putdown_body.ycd',           ['--auto', '--drop-root']),
    ('rdr2_remove_lt',     'mech_carry_ped/mech_carry_ped@dead@mount@remove@lt.ycd',        ['--auto', '--drop-root']),
    ('rdr2_stow_lt',       'mech_carry_ped/mech_carry_ped@dead@mount@stow@lt.ycd',          ['--auto', '--drop-root']),
    ('rdr2_throw_body',    'mech_carry_ped/mech_carry_ped@dead@throw_body.ycd',             ['--auto', '--drop-root']),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    os.makedirs(TMP, exist_ok=True)
    ok = 0
    for name, rel, extra in CLIPS:
        ycd = os.path.join(AN, rel)
        if not os.path.exists(ycd):
            print('[skip] 缺 %s' % rel)
            continue
        js = os.path.join(TMP, name + '.json')
        rc, out = run([UV, 'run', 'python', os.path.join(PROJ, 'tools/rdr2_walk_fix.py'),
                       ycd, js] + extra)
        if rc != 0:
            print('[FAIL json] %s\n%s' % (name, out[-800:]))
            continue
        gl = os.path.join(OUT, name + '.gltf')
        extra_gltf = ['--arms-down', '45'] if name == 'rdr2_walk' else []
        rc, out = run([UV, 'run', 'python', os.path.join(PROJ, 'tools/export_gltf_source.py'),
                       js, gl, '--skel', 'yft', '--name', name, '--anim', '0'] + extra_gltf)
        if rc != 0:
            print('[FAIL gltf] %s\n%s' % (name, out[-800:]))
            continue
        line = [l for l in out.splitlines() if 'bones=' in l]
        print('[ok] %-20s %s' % (name, line[0].strip() if line else ''))
        ok += 1
    print('完成 %d/%d' % (ok, len(CLIPS)))


if __name__ == '__main__':
    main()
