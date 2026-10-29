"""打开 continent.blend 时自动做的优化（A+ 方案）。

用法（推荐）：双击 打开大陆_流畅.bat
  它会执行：blender <continent.blend> --python tools/blender_autoload.py

也可手动在命令行跑：
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" \
    "deliverable/blender/continent/continent.blend" \
    --python tools/blender_autoload.py

做了什么：
  1. 所有 3D 视口切 Solid（不采样贴图）→ 打开即流畅
  2. 已加载贴图在内存里缩到 256px（2.4 GB → ~0.3 GB，不写回文件）
  3. 按 2000 m 分好 43 个 collection，默认只显示当前视点所在那一块
  4. 打印一段操作提示到 Console

注意：shrink 是内存操作，关掉不保存就恢复原样，不会破坏 tex/*.png。
"""
import bpy
import math
import os
import time


TILE = 2000.0
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0
MAX_PX = 256


def _views():
    try:
        return [a for a in bpy.context.screen.areas if a.type == 'VIEW_3D']
    except Exception:
        return []


def solid(color='TEXTURE'):
    """Solid 模式。color='TEXTURE' = 带贴图（推荐，不编译着色器）；'OBJECT' = 纯色最快。"""
    n = 0
    for a in _views():
        try:
            sh = a.spaces.active.shading
            sh.type = 'SOLID'
            sh.color_type = color
            sh.light = 'STUDIO'
            sh.show_shadows = False
            sh.show_cavity = False
            a.spaces.active.clip_start = 2.0
            a.spaces.active.clip_end = 20000.0
            n += 1
        except Exception:
            pass
    return n


def shrink_textures(max_px=MAX_PX):
    done = 0
    for img in list(bpy.data.images):
        try:
            w, h = img.size
        except Exception:
            continue
        if not w or not h:
            continue
        m = max(w, h)
        if m <= max_px:
            continue
        k = max_px / float(m)
        try:
            img.scale(max(1, int(w * k)), max(1, int(h * k)))
            done += 1
        except Exception:
            pass
    return done


def _tile_of(x, y):
    i = int((x - X0) // TILE)
    j = int((Y0 + WORLD - y) // TILE)
    return 'wild2000_%02d_%02d' % (i, j)


def tileify():
    """按 2000 m 网格把 ENTITIES 分到子 collection。"""
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        return 0
    for c in list(ent.children):
        if c.name.startswith('T_'):
            for o in list(c.objects):
                c.objects.unlink(o)
            bpy.data.collections.remove(c)
    buckets = {}
    for o in list(ent.objects):
        buckets.setdefault(_tile_of(o.location.x, o.location.y), []).append(o)
    for tid, objs in sorted(buckets.items()):
        c = bpy.data.collections.new('T_' + tid)
        ent.children.link(c)
        for o in objs:
            c.objects.link(o)
    for c in ent.children:
        for o in list(c.objects):
            try:
                ent.objects.unlink(o)
            except Exception:
                pass
    return len(buckets)


def show_only(tid):
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        return 0
    key = 'T_' + tid
    shown = 0
    for c in ent.children:
        on = (c.name == key)
        c.hide_viewport = not on
        c.hide_render = not on
        if on:
            shown = len(c.objects)
    return shown


def main():
    # 幂等：--python 与启动钩子可能各跑一次，避免重复 tileify（每次 ~20s）
    sc = bpy.context.scene
    if sc and sc.get('_cowork_autoload_done'):
        print('[autoload] 已执行过，跳过（避免重复分区）')
        return
    if sc:
        sc['_cowork_autoload_done'] = 1
    t0 = time.time()
    print('=' * 60)
    print('[autoload] 开始优化 continent.blend')
    fp = (bpy.data.filepath or '').replace('\\', '/')
    print('[autoload] 文件:', fp or '(未命名)')

    # 默认无贴图（用户要求：卡就关贴图）。颜色由离线平均色表提供，不会变成一片灰。
    try:
        import sys as _sf, os as _of
        _sf.path.insert(0, _of.path.dirname(_of.path.abspath(__file__)))
        import blender_tour as _tf
        _tf.flat_colored()
    except Exception as e:
        n = solid('TEXTURE')
        print('[autoload] flat_colored 失败(%s)，退回 Solid+贴图 视口: %d' % (e, n))
    try:
        import sys as _s, os as _o
        _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
        import blender_tour as _t
        _t.water_color()      # 水面没贴图，不给颜色会显示成白色（像"空的"）
    except Exception as e:
        print('[autoload] 水面上色失败:', e)

    # 默认无贴图 ⇒ 不做缩图（省 30~40 s 和 ~2.4 GB 内存）。
    # 之后调用 tour.textured() 时会自动缩一次。
    print('[autoload] 跳过贴图缩放（默认无贴图模式；开贴图时 tour.textured() 会自动缩）')

    # 分区 + 按尺寸分子集合（切换集合是常数级；逐个物体 hide 要 2.6 ms/个，绝不能用）
    import sys as _s3, os as _o3
    _s3.path.insert(0, _o3.path.dirname(_o3.path.abspath(__file__)))
    import blender_tour as tour
    nt = tour.tileify()
    print('[autoload] 分区:', nt, ' 分类:', len(tour.cats()))

    # 分类面板（3D 视图按 N → 「RDR2」页签，每类一个开关）
    try:
        import rdr2_cat_ui as cui
        cui.register()
    except Exception as e:
        print('[autoload] 分类面板注册失败:', e)

    # 地形 946 万顶点 + 水面 419 万顶点是剩下的主要负担：视口减面到 50%（不动网格数据）
    try:
        tour.decimate(0.5)
    except Exception as e:
        print('[autoload] 减面跳过:', e)

    cur = None
    for a in _views():
        r = a.spaces.active.region_3d
        if r:
            cur = (r.view_location.x, r.view_location.y)
            break
    if cur and nt:
        tid = _tile_of(*cur)
        # 2026-10-28 用户要求：默认「全图」，不要流式（进入进出反而更卡）
        tour.stream(False)      # 同时注销 timer，彻底不跟随相机
        tour.show_all()
        print('[autoload] 默认「全图」：流式加载已关闭（timer 已注销，不再跟随相机）')
        # 顺序很重要：先 show_all 再关分类（否则会被 show_all 重新打开）
        for _k in ('贴花', '植被'):
            tour.cat_show(_k, False)
        print('[autoload] 默认隐藏分类：贴花 / 植被')
    else:
        print('[autoload] 无可用视口，保持全显')

    print('[autoload] 提示：默认全图；需要时可在面板点「★ 流式加载」开销更小')

    print('[autoload] 总计 %.1fs' % (time.time() - t0))
    print('-' * 60)
    print('现在可以直接用鼠标平移旋转了 —— 视口是 **Solid 无贴图**（按贴图平均色着色）：最快。')
    print('想换区 / 看细节：Python Console 里跑')
    print('    import sys; sys.path.append(r"' + fp.rsplit('/deliverable', 1)[0].replace('/', '\\') + r'\tools"); import blender_tour as tour')
    print('    tour.tiles()                     # 列出 43 个分区（带对象数）')
    print('    tour.only("wild2000_05_00")      # 只显示某一片')
    print('    tour.jump(2989.5, 2189.4, 40)    # 飞到夏洛蒂的家')
    print('    tour.show_all()                  # 全图（Solid 下也不卡）')
    print('    tour.stream(True)                # 流式加载（默认【关闭】，需要时手动开）')
    print('    tour.manual()                    # 关掉跟随，自己控制显示哪些块')
    print('    tour.textured()                  # 想开贴图（更慢，但更真实）')
    print('    tour.material()                  # 材质预览：自动只留当前区 + 关光追/阴影（仍偏重，慎用）')
    print('想看不缩小的原贴图：不保存直接关掉，重新打开即可（tex 文件没被改）')
    print('=' * 60)


if __name__ == '__main__':
    main()
