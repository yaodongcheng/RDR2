# -*- coding: utf-8 -*-
"""闸门：MLO 实例查找的**唯一口径**（2026-11-06 用户实机教训）。

    python tools/_check_mlo_lookup.py

判据（任一 FAIL 退出码 1）：
  1. 纯函数优先级：精确 > `_main` > `_lod`（LOD 只作兜底）；
  2. 真实数据：`val_bank_int` 必须取到 `*_main`（yaw ≈ 0°），不能是 `*_lod`（yaw −100°）；
     另一例 `roc_house_int`（历史上同样撞过 `_lod`）也不能取到 `_lod`；
  3. 反向测试：模拟旧写法「遍历 tiles、先撞到谁算谁」必须取到 `_lod` ——
     证明这条闸门对旧实现有分辨力（否则 PASS 无意义）。

背景：构建侧（scene_interiors）旧写法拿到 `val_bank_int_lod`（yaw −100°），
体检侧（_check_interior_align）用优先级拿到 `_main`（yaw 0°）⇒ 体检 PASS、画面歪。
现在三处都调 `parse_interior_mlo.find_mlo_instance()`。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_interior_mlo as PM  # noqa: E402


def yaw(e):
    qx, qy, qz, qw = e[4:8]
    return math.degrees(math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz)))


def main():
    bad = []

    # 1) 纯函数优先级
    def fake(name, yawdeg):
        a = math.radians(yawdeg) * 0.5
        return [1, 0, 0, 0, 0.0, 0.0, math.sin(a), math.cos(a)]
    idx = {
        'p_exact': fake('p_exact', 10),
        'p_main': fake('p_main', 20),
        'p_lod': fake('p_lod', 30),
        'q_main': fake('q_main', 20),
        'q_lod': fake('q_lod', 30),
        'r_lod': fake('r_lod', 30),
    }
    cases = [
        ('p_exact', 10, '精确优先'),
        ('q_main', 20, '无精确 → _main'),
        ('r_lod', 30, '只有 _lod → 兜底'),
    ]
    for pkg, want, note in cases:
        e = PM.pick_instance(idx, pkg)
        if e is None or abs(yaw(e) - want) > 1e-3:
            bad.append('优先级用例 %s（%s）：期望 yaw %.1f，实际 %s' % (pkg, note, want, e))
    if PM.pick_instance(idx, 'nope') is not None:
        bad.append('优先级用例：不存在的包应返回 None')
    print('[mlo] 优先级用例 3 条 + 空包 1 条')

    # 2) 真实数据回归
    nm = PM.load_names()
    tl = PM.tiles()
    inst = PM.find_mlo_instance('val_bank_int', names=nm, tile_list=tl)
    if inst is None:
        bad.append('真实数据：val_bank_int 找不到实例')
    else:
        got_yaw = yaw(inst)
        if abs(got_yaw) > 1.0:
            bad.append('真实数据：val_bank_int 拿到 yaw %.1f°（应为 0°，说明取到了 _lod）' % got_yaw)
        print('[mlo] val_bank_int -> yaw %.2f°' % got_yaw)

    inst = PM.find_mlo_instance('roc_house_int', names=nm, tile_list=tl)
    if inst is None:
        bad.append('真实数据：roc_house_int 找不到实例')
    else:
        print('[mlo] roc_house_int -> yaw %.2f°' % yaw(inst))

    # 只有 _lod 的包：LOD 朝向不可信，必须用同词干外壳的朝向（rho_fenceshop_int）
    inst = PM.find_mlo_instance('rho_fenceshop_int', names=nm, tile_list=tl)
    if inst is None:
        bad.append('真实数据：rho_fenceshop_int 找不到实例')
    else:
        fy = yaw(inst)
        print('[mlo] rho_fenceshop_int -> yaw %.2f°（外壳 0°；原始 _lod 是 20°）' % fy)
        if abs(fy) > 2.0:
            bad.append('只有 _lod 的包没有改用外壳朝向：rho_fenceshop_int yaw %.2f°（应≈0°）' % fy)

    # 3) 反向测试：旧写法（tiles 顺序第一个名字命中）必须取到 _lod —— 否则闸门没有分辨力
    want = ('val_bank_int', 'val_bank_int_main', 'val_bank_int_lod')
    old = None
    for e in tl:
        n = nm.get(e[0])
        if not n:
            continue
        if n.split('/')[-1].lower() in want:
            old = e
            break
    if old is None:
        bad.append('反向测试：val_bank_int 在 tiles 里一个实例都没有')
    else:
        oy = yaw(old)
        print('[mlo] 旧写法（先撞到谁算谁）-> yaw %.2f°（必须 ≠ 0，才证明闸门有分辨力）' % oy)
        if abs(oy) < 1.0:
            bad.append('反向测试失效：旧写法也拿到了 yaw 0°（val_bank_int 的 lod 顺序变了？请重核对）')

    if bad:
        print('[mlo] FAIL')
        for x in bad:
            print('   ', x)
        return 1
    print('[mlo] PASS —— 实例查找唯一口径有效')
    return 0


if __name__ == '__main__':
    sys.exit(main())
