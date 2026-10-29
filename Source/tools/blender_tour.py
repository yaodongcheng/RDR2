"""大陆巡览助手 —— 在已有的 continent.blend 里运行，解决"加载贴图就卡死"。

打开 deliverable/blender/continent/continent.blend 后：
  Scripting → Text Editor → Open 本文件 → Run Script

然后在该文本框里按需调用：

  tour.solid()                 切 Solid 模式（不加载贴图），立刻不卡
  tour.shrink_textures(256)    把已加载的 7065 张贴图内存缩到 256px（显存/内存骤降）
  tour.tileify()               把 ENTITIES 按 2000 m 分成 43 个 collection
  tour.only('wild2000_05_00')  只显示某一块，其余隐藏（推荐：一次只开一块）
  tour.jump(2989.5, 2189.4)    把视口跳到威拉德之息（夏洛蒂的家）
  tour.jump(2989.5, 2189.4, 40)  跳过去并拉近到 40 m
  tour.spot()                  打印当前视点附近的对象/网格统计（核查有没有缺）
  tour.hide_small()            隐藏 < 1.5 m 的小物件（约 8.7 万个），只看建筑

坐标约定：X 东 / Y 北 / Z 上，单位米（与 world_meta.json 一致）。
"""
import bpy
import math
import os
from collections import defaultdict

TILE = 2000.0
X0, Y0, WORLD = -7684.0, -8196.0, 12296.0

GUIDE = {
    '威拉德之息(夏洛蒂的家)': (2989.5, 2189.4, 'wild2000_05_00'),
    '圣丹尼斯': (1286.0, 1060.0, None),
    '瓦伦丁': (-1030.0, 1960.0, None),
    '黑水镇': (-2260.0, 880.0, None),
    '安尼斯堡': (2883.6, 1347.9, None),
}


# ---------------------------------------------------------------- 视口
def _views():
    return [a for a in bpy.context.screen.areas if a.type == 'VIEW_3D']


def _set_views(fn):
    n = 0
    for a in _views():
        try:
            fn(a.spaces.active)
            n += 1
        except Exception:
            pass
    return n


def clip(end=20000.0, start=2.0):
    """把视口裁剪距离拉到能看见整块大陆（默认 1000 m 会把远处切掉，看起来像"地图没了"）。

    默认值 `start=2.0 / end=20000.0` 是用户 2026-10-29 定的口味：每次打开都直接用这组，
    不用手改。想临时换就自己调一次，例如 `clip(start=0.5)` 或 `clip(end=40000)`。
    """
    def f(sp):
        sp.clip_start = start
        sp.clip_end = end
    n = _set_views(f)
    print('clip: %d 个视口 clip_start=%.1f clip_end=%.0f' % (n, start, end))


def flat_colored(colors=''):
    """★ 默认模式：**Solid，不采样贴图**，但每个材质按它贴图的平均色着色。

    比 Solid+贴图 快得多（不绑定/采样贴图），又不会变成一片灰 —— 地面是绿的、水是蓝的、
    沙漠偏黄、城里的木头偏褐。颜色表由 `export/world/mat_avg_color.json` 提供（离线算好的平均色）。
    """
    import json as _json
    path = colors or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'export', 'world', 'mat_avg_color.json')
    table = {}
    try:
        table = _json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print('  (颜色表没读到，退回灰色: %s)' % e)
    n = 0
    for m in bpy.data.materials:
        nm = m.name
        rgb = None
        if nm.startswith('m_'):
            key = nm[2:].split('.')[0]
            v = table.get(key)
            if v:
                rgb = v
        elif nm.startswith('ntex_'):
            parts = nm[5:].split('_')
            if len(parts) >= 3:
                try:
                    rgb = [float(parts[0]), float(parts[1]), float(parts[2])]
                except Exception:
                    rgb = None
        if nm in ('water', 'Water'):
            rgb = [0.16, 0.32, 0.45]
        elif nm == 'terrain_ground':
            rgb = [0.32, 0.38, 0.26]
        if rgb:
            m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
            n += 1

    def f(sp):
        sp.shading.type = 'SOLID'
        sp.shading.color_type = 'MATERIAL'
        sp.shading.light = 'STUDIO'
        sp.shading.show_shadows = False
        sp.shading.show_cavity = False
        sp.clip_start = 2.0
        sp.clip_end = 20000.0
    v = _set_views(f)
    print('flat_colored: %d 个视口 = Solid/MATERIAL（无贴图），已着色 %d 个材质' % (v, n))


def solid():
    """纯色 Solid（最快，但没有颜色信息）。"""
    def f(sp):
        sp.shading.type = 'SOLID'
        sp.shading.color_type = 'OBJECT'
        sp.shading.light = 'STUDIO'
    n = _set_views(f)
    print('solid: %d 个 3D 视口已切到 Solid（纯色）' % n)


def textured():
    """★ 开贴图：Solid 模式 + 贴图颜色（第一次调用会先把大图缩到 256，约 30 s）。

    Solid 模式不编译 EEVEE 着色器，但 color_type='TEXTURE' 会显示 albedo 贴图，
    所以"有贴图 + 不卡"能同时成立。这是看地图的正确姿势。
    """
    try:
        shrink_textures(256)      # 无贴图模式下没缩过，这里补一次
    except Exception as e:
        print('  (缩图跳过: %s)' % e)

    def f(sp):
        sp.shading.type = 'SOLID'
        sp.shading.color_type = 'TEXTURE'
        sp.shading.light = 'STUDIO'
        sp.shading.show_shadows = False
        sp.shading.show_cavity = False
        sp.clip_start = 2.0
        sp.clip_end = 20000.0
    n = _set_views(f)
    print('textured: %d 个视口 = Solid + 贴图（推荐，切区后依然流畅）' % n)


def material(only_current_tile=True):
    """切 Material Preview —— 会真正编译 EEVEE 着色器。

    安全做法：只留当前分区 + 关掉光线追踪/阴影/运动模糊。
    依然建议先用 textured()；非要用材质预览再调它。
    """
    ent = bpy.data.collections.get('ENTITIES')
    if only_current_tile and ent:
        cur = None
        for a in _views():
            r = a.spaces.active.region_3d
            if r:
                cur = (r.view_location.x, r.view_location.y)
                break
        if cur:
            only(_tile_of(*cur))
    try:
        ee = bpy.context.scene.eevee
        for attr, val in (('use_raytracing', False), ('use_shadows', False),
                          ('taa_samples', 8), ('use_motion_blur', False)):
            if hasattr(ee, attr):
                setattr(ee, attr, val)
    except Exception as e:
        print('  (eevee 设置跳过: %s)' % e)

    def f(sp):
        sp.shading.type = 'MATERIAL'
        sp.clip_start = 2.0
        sp.clip_end = 20000.0
    n = _set_views(f)
    print('material: %d 个视口已切 Material Preview（只显示当前分区，已关光线追踪/阴影）' % n)


def tiles():
    """列出所有分区与对象数，方便挑一个看。"""
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        print('没有 ENTITIES 集合')
        return
    tidy = defaultdict(int)
    if classified():
        for k, zh, c in cats():
            for sub in c.children:
                tidy[sub.get('tile') or '?'] += len(sub.all_objects)
        rows = sorted(((n, 'T_' + t) for t, n in tidy.items()), reverse=True)
    else:
        rows = sorted(((len(c.all_objects), c.name) for c in ent.children if c.name.startswith('T_')), reverse=True)
    print('分区 %d 个（对象数从多到少）：' % len(rows))
    for n, nm in rows:
        print('  %-22s %6d' % (nm, n))
    print('切区：tour.only("%s")' % (rows[0][1][2:] if rows else 'wild2000_05_00'))


def shrink_textures(max_px=256, protect_over=1024, big_max=4096):
    """把已加载图片在内存里等比缩到 max_px，显存占用可降一个数量级。不写回文件。

    protect_over: 超过这个值的图不按 max_px 缩，而是封顶到 big_max。
    地面彩图 12296×12296（约 605 MB）—— 缩成 256 会糊成一片；完全不缩又太吃显存。
    折中：封顶 4096（约 64 MB，全图 2.6 m/px，够看）。
    """
    done = 0
    saved = 0
    for img in bpy.data.images:
        try:
            w, h = img.size
        except Exception:
            continue
        if not w or not h:
            continue
        m = max(w, h)
        if m <= max_px:
            continue
        if protect_over and m > protect_over:
            if big_max and m > big_max:
                k = big_max / float(m)
                try:
                    img.scale(max(1, int(w * k)), max(1, int(h * k)))
                    done += 1
                except Exception:
                    pass
            continue
        k = max_px / float(m)
        saved += w * h * 4
        try:
            img.scale(max(1, int(w * k)), max(1, int(h * k)))
            done += 1
        except Exception as e:
            print('  跳过', img.name, e)
    print('shrink_textures: 缩放 %d 张，释放约 %.2f GB' % (done, saved / 1073741824.0))


def stats():
    sc = bpy.context.scene
    objs = len(bpy.data.objects)
    meshes = len(bpy.data.meshes)
    imgs = len(bpy.data.images)
    tris = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print('对象 %d / 唯一网格 %d / 贴图 %d / 面 %d' % (objs, meshes, imgs, tris))


# ---------------------------------------------------------------- 分区
def _tile_of(x, y):
    i = int((x - X0) // TILE)
    j = int((Y0 + WORLD - y) // TILE)
    return 'wild2000_%02d_%02d' % (i, j)


def cats():
    """返回 [(key, 中文名, collection)] —— 读 ENTITIES 下的 C_<key>_<中文名>。"""
    ent = bpy.data.collections.get('ENTITIES')
    out = []
    if ent is None:
        return out
    for c in ent.children:
        if not c.name.startswith('C_'):
            continue
        parts = c.name.split('_', 2)
        out.append((parts[1] if len(parts) > 1 else c.name,
                    parts[2] if len(parts) > 2 else c.name, c))
    return out


def classified():
    return bool(cats())


def cat_show(key, on):
    """开关某一类（支持中文名或 key）。"""
    for k, zh, c in cats():
        if key == k or key == zh or key == c.name or key in zh or key in k:
            c.hide_viewport = not on
            c.hide_render = not on
            # 同步右侧面板的勾选状态（否则面板会显示"开"但实际是隐藏）
            try:
                pg = getattr(bpy.context.scene, 'rdr2_cats', None)
                if pg is not None and hasattr(pg, 'cat_' + k):
                    setattr(pg, 'cat_' + k, bool(on))
            except Exception:
                pass
            print('cat %s(%s) -> %s' % (zh, k, '显示' if on else '隐藏'))
            return True
    print('没找到分类:', key)
    return False


def tileify():
    """旧结构（按地块）。若文件已跑过 classify_entities.py，直接沿用分类结构。"""
    if classified():
        return len({sub.get('tile') for k, zh, c in cats() for sub in c.children})
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        return 0
    for c in list(ent.children):
        bpy.data.collections.remove(c)
    buckets = {}
    for o in list(ent.all_objects):
        buckets.setdefault(_tile_of(o.location.x, o.location.y), []).append(o)
    for tid, objs in sorted(buckets.items()):
        parent = bpy.data.collections.new('T_' + tid)
        ent.children.link(parent)
        for o in objs:
            parent.objects.link(o)
    for o in list(ent.objects):
        ent.objects.unlink(o)
    return len(buckets)


def only(tid):
    """只显示某个地块（跨所有分类）。只切集合，常数级开销。"""
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        return 0
    key = tid[2:] if tid.startswith('T_') else tid
    hit = 0
    if classified():
        subs = [sub for k, zh, c in cats() for sub in c.children]
        # 保护：目标地块没有任何对象时不要清空场景（视点常落在海面/天空）
        if not any(sub.get('tile') == key for sub in subs):
            print('only(%s): 该地块没有对象，保持当前显示不变' % tid)
            return -1
        # 只在可见性真变化时才赋值，避免无谓的依赖图刷新
        for sub in subs:
            on = (sub.get('tile') == key)
            h = not on
            if sub.hide_viewport != h:
                sub.hide_viewport = h
            if sub.hide_render != h:
                sub.hide_render = h
            if on:
                hit += len(sub.all_objects)
    else:
        target = 'T_' + key
        for c in ent.children:
            on = (c.name == target)
            c.hide_viewport = not on
            c.hide_render = not on
            if on:
                hit = len(c.all_objects)
    print('only(%s): %d 个对象可见' % (tid, hit))
    return hit


def show_all():
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None:
        return
    for c in ent.children:
        c.hide_viewport = False
        c.hide_render = False
        for sub in c.children:
            sub.hide_viewport = False
            sub.hide_render = False
    print('show_all: 全部分区/分类恢复显示')


def show_only(tid):
    return only(tid)


def auto_detail(tid, level=None, max_objects=12000):
    """保留旧接口（新结构下由「分类开关」取代），不再逐个物体 hide。"""
    return 0


def hide_small(threshold=1.5):
    """旧接口：新结构下用分类开关（道具/杂物/贴花）代替。"""
    print('提示：现在用分类开关更快 —— tour.cat_show("道具", False) / tour.cat_show("贴花", False)')


# ---------------------------------------------------------------- 定位
def jump(x, y, dist=0.0, z=None):
    """把 3D 视口对准世界坐标 (x, y)。dist>0 时拉近。"""
    z = z if z is not None else _ground_z(x, y)
    for a in _views():
        sp = a.spaces.active
        r3d = sp.region_3d
        if r3d is None:
            continue
        cur = r3d.view_location.copy()
        r3d.view_location = (x, y, z + 6.0)
        if dist > 0:
            r3d.view_distance = dist
        else:
            r3d.view_distance = max(60.0, r3d.view_distance)
        # 俯视 45°
        r3d.view_rotation = _look_rotation(math.radians(55), math.radians(0))
    print('jump -> (%.1f, %.1f, %.1f)%s' % (x, y, z, '' if not dist else '  dist=%.0fm' % dist))
    # 自动显示目标所在地块（否则跳过去看到的是"空的"，因为别的分区被隐藏）
    ent = bpy.data.collections.get('ENTITIES')
    if ent is not None and ent.children:
        only(_tile_of(x, y))
    spot(x, y, 120.0)


def _look_rotation(pitch, yaw):
    from mathutils import Euler
    return Euler((pitch, 0.0, yaw), 'XYZ').to_quaternion()


def _ground_z(x, y):
    """在 Terrain 网格上按 XY 找最近顶点高度；找不到退化为 0。"""
    t = bpy.data.objects.get('Terrain')
    if t is None or t.type != 'MESH':
        return 0.0
    me = t.data
    if len(me.vertices) < 1000:
        return 0.0
    # 地形是大网格，用步进采样近似（够用）
    best, bz = 1e18, 0.0
    step = max(1, len(me.vertices) // 20000)
    for i in range(0, len(me.vertices), step):
        v = me.vertices[i].co
        d = (v.x - x) ** 2 + (v.y - y) ** 2
        if d < best:
            best, bz = d, v.z
    return float(bz)


def spot(x=None, y=None, radius=150.0):
    """打印指定位置附近的对象统计，用于核查"这里有没有缺"。"""
    if x is None:
        for a in _views():
            r3d = a.spaces.active.region_3d
            if r3d:
                x, y = r3d.view_location.x, r3d.view_location.y
                break
    if x is None:
        x, y = 0.0, 0.0
    near = [o for o in bpy.data.objects
            if o.type == 'MESH' and (o.location.x - x) ** 2 + (o.location.y - y) ** 2 <= radius * radius]
    tris = sum(len(o.data.polygons) for o in near)
    print('spot (%.0f, %.0f) r=%.0fm: %d 个对象 / %d 面' % (x, y, radius, len(near), tris))
    return len(near)


def guide():
    print('\n常用坐标（直接 tour.jump(x, y)）：')
    for k, (x, y, tid) in GUIDE.items():
        print('  %-22s (%8.1f, %8.1f)  tile=%s' % (k, x, y, tid or _tile_of(x, y)))


def help():
    print(__doc__)
    guide()


# ---------------------------------------------------------------- 自动跟随
_FOLLOW = {'on': False, 'state': None, 'timer': None}


def _decide():
    """按视距分三档，带滞回（避免在阈值上来回抖）：

    > 9000 m  → ('terrain', None)  只留地形/水面（全图浏览最快）
    > 3200 m  → ('all', None)      全部地块
    <= 3200 m → ('tile', tid)      当前地块 + 密集时自动降载
    """
    a = None
    for v in _views():
        if v.spaces.active.region_3d is not None:
            a = v
            break
    if a is None:
        return None
    r = a.spaces.active.region_3d
    d = r.view_distance
    prev = _FOLLOW.get('state')
    # 滞回：已经处于某档时，退出该档需要多走出 20%
    if prev:
        k = prev[0]
        if k == 'terrain' and d > 7200:
            return prev
        if k == 'all' and 2600 < d <= 10800:
            return prev
        if k == 'tile' and d <= 3900:
            return ('tile', _tile_of(r.view_location.x, r.view_location.y))
    if d > 9000:
        return ('terrain', None)
    if d > 3200:
        return ('all', None)
    return ('tile', _tile_of(r.view_location.x, r.view_location.y))


def _apply(state):
    kind, tid = state
    ent = bpy.data.collections.get('ENTITIES')
    if ent is None or not ent.children:
        return
    if kind == 'terrain':
        for c in ent.children:
            c.hide_viewport = True
            c.hide_render = True
        print('[follow] 视距很远 → 只显示地形/水面（快）')
        return
    if kind == 'all':
        for c in ent.children:
            c.hide_viewport = False
            c.hide_render = False
            _set_sub(c, 0)
    else:
        only(tid)


def _tick():
    if not _FOLLOW['on']:
        return 0.5
    try:
        st = _decide()
        if st and st != _FOLLOW['state'] and bpy.context.scene.get('_tour_manual') != 1:
            _FOLLOW['state'] = st
            _apply(st)
    except Exception as e:
        print('[tour.follow] 跳过:', e)
    return 0.5


def follow(on=True):
    """自动跟随视点：拉远→全图，拉近→只显示当前地块。"""
    _FOLLOW['on'] = bool(on)
    try:
        bpy.context.scene['_tour_manual'] = 0 if on else 1
    except Exception:
        pass
    if on:
        st = _decide()
        if st:
            _FOLLOW['state'] = st
            _apply(st)
        if _FOLLOW['timer'] is None:
            _FOLLOW['timer'] = bpy.app.timers.register(_tick, first_interval=0.5, persistent=True)
        print('follow: 已开启（>3000 m 全图 / 更近只显示当前地块）')
    else:
        print('follow: 已关闭（手动用 tour.only/show_all 控制）')


def manual():
    """关掉自动跟随，改回手动控制（之后 only()/show_all() 说啥是啥）。"""
    follow(False)
    print('manual: 手动模式（only/show_all 不再被自动覆盖）')


def water_color(rgb=(0.16, 0.32, 0.45)):
    """水面材质在 Solid+TEXTURE 下没有贴图 → 会显示成白色，看着像"地图是空的"。
    给个蓝色视口颜色兜底（只影响显示，不影响 EEVEE 渲染）。"""
    n = 0
    for nm in ('water', 'Water'):
        m = bpy.data.materials.get(nm)
        if m is None:
            continue
        m.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
        try:
            m.roughness = 0.25
        except Exception:
            pass
        n += 1
    print('water_color: %d 个水面材质已上色 %s' % (n, rgb))
    return n


# ---------------------------------------------------------------- 一键档位
def decimate(ratio=0.3, targets=('Terrain', 'Water')):
    """给地形/水面挂**视口用**的减面修改器（非破坏性，删掉 modifier 就恢复）。

    Terrain 946 万顶点 + Water 419 万顶点，两者合计 ~27 M 三角面，是"转视角一顿一顿"的来源之一。
    ratio=0.3 → 地形约 2.8 M 顶点。只影响视口显示，不改网格数据、不影响渲染出图（可 tour.undecimate()）。
    """
    n = 0
    for nm in targets:
        o = bpy.data.objects.get(nm)
        if o is None or o.type != 'MESH':
            continue
        m = o.modifiers.get('preview_decimate')
        if m is None:
            m = o.modifiers.new('preview_decimate', 'DECIMATE')
        m.ratio = float(ratio)
        m.show_viewport = True
        m.show_render = False
        n += 1
    print('decimate: %d 个对象已减面到 %.0f%%（视口有效，渲染不受影响）' % (n, ratio * 100))
    return n


def undecimate(targets=('Terrain', 'Water')):
    n = 0
    for nm in targets:
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        m = o.modifiers.get('preview_decimate')
        if m is not None:
            o.modifiers.remove(m)
            n += 1
    print('undecimate: %d 个对象已恢复原始网格' % n)
    return n


def map_view():
    """只看地图本身：**开地面贴图**，但把所有建筑/道具隐藏 —— 只有 2 个对象，既好看又快。"""
    ent = bpy.data.collections.get('ENTITIES')
    if ent:
        for c in ent.children:
            c.hide_viewport = True
            c.hide_render = True
    def f(sp):
        sp.shading.type = 'SOLID'
        sp.shading.color_type = 'TEXTURE'
        sp.clip_start = 2.0
        sp.clip_end = 20000.0
    n = _set_views(f)
    print('map_view: %d 个视口 = 地面贴图 + 无建筑（快，且能看到地形/水系）' % n)


def boost():
    """一键"我要最快"：纯色 Solid + 关跟随 + 当前地块只留主体建筑。"""
    follow(False)
    solid()
    a = None
    for v in _views():
        if v.spaces.active.region_3d is not None:
            a = v
            break
    if a is not None:
        r = a.spaces.active.region_3d
        tid = _tile_of(r.view_location.x, r.view_location.y)
        only(tid)
        auto_detail(tid, level=2)
    decimate(0.3)
    print('boost: 已完成（纯色 + 单地块 + 只留主体 + 地形减面 30%）')


def full():
    """恢复"看整体"：贴图 + 自动跟随 + 全部小件显示。"""
    ent = bpy.data.collections.get('ENTITIES')
    if ent:
        for c in ent.children:
            c.hide_viewport = False
            c.hide_render = False
            _set_sub(c, 0)
    textured()
    follow(True)
    print('full: 已恢复（贴图 + 跟随，小件全部显示）')


def perf():
    """打印当前可见规模，卡的时候先跑它。"""
    ent = bpy.data.collections.get('ENTITIES')
    vis_c = [c for c in ent.children if not c.hide_viewport] if ent else []
    n_obj = sum(len(c.all_objects) for c in vis_c)
    n_v = 0
    for c in vis_c:
        for o in c.all_objects:
            if o.type == 'MESH' and not o.hide_viewport:
                n_v += len(o.data.vertices)
    imgs = [(i.name, tuple(i.size)) for i in bpy.data.images if i.size[0] > 1024]
    a = next((v for v in _views() if v.spaces.active.region_3d), None)
    print('perf: 可见地块 %d / 对象 %d / 顶点 %.1f M / 大图 %s' % (
        len(vis_c), n_obj, n_v / 1e6, imgs if imgs else '无'))
    if a:
        sh = a.spaces.active.shading.type
        print('      视口 shading=%s  视距=%.0f m' % (sh, a.spaces.active.region_3d.view_distance))
        if sh == 'MATERIAL':
            print('      ⚠ 你正在 Material Preview —— 这是最卡的档位，想要流畅请 tour.textured() 或 tour.boost()')
    dec = [nm for nm in ('Terrain', 'Water')
           if bpy.data.objects.get(nm) and bpy.data.objects[nm].modifiers.get('preview_decimate')]
    print('      地形减面: %s' % ('已启用 ' + str(dec) if dec else '未启用（tour.decimate(0.3) 可提速）'))


# ---------------------------------------------------------------- 流式加载（跟相机）
_STREAM = {'on': False, 'shown': set(), 'timer': None}


def all_tiles():
    out = set()
    for k, zh, c in cats():
        for sub in c.children:
            t = sub.get('tile')
            if t:
                out.add(t)
    return sorted(out)


def tile_center(tid):
    """'wild2000_05_02' → 该地块的世界中心 (x, y)。"""
    try:
        i = int(tid.split('_')[1]); j = int(tid.split('_')[2])
    except Exception:
        return (0.0, 0.0)
    x = X0 + (i + 0.5) * TILE
    y = (Y0 + WORLD) - (j + 0.5) * TILE
    return (x, y)


def tiles_near(x, y, radius):
    """返回与 (x,y) 距离 <= radius 的地块集合。"""
    out = set()
    for t in all_tiles():
        cx, cy = tile_center(t)
        if (cx - x) ** 2 + (cy - y) ** 2 <= radius * radius:
            out.add(t)
    return out


def _apply_tiles(keep):
    """只切换有变化的地块子集合（分类层面的隐藏优先，不受影响）。"""
    changed = 0
    for k, zh, c in cats():
        for sub in c.children:
            t = sub.get('tile')
            want = t in keep
            hide = not want
            if bool(sub.hide_viewport) != hide:
                sub.hide_viewport = hide
                sub.hide_render = hide
                changed += 1
    if changed:
        print('[stream] 换入换出 %d 个集合，当前地块 %d 个' % (changed, len(keep)))


_TILEF = {'on': False, 'timer': None, 'last': None}


def _tilef_tick():
    """只显示相机当前所在的那一块；跨块才切换（比流式加载轻得多）。"""
    if not _TILEF['on']:
        return None
    try:
        a = None
        for v in _views():
            if v.spaces.active.region_3d:
                a = v
                break
        if a is None:
            return 1.0
        r = a.spaces.active.region_3d
        tid = _tile_of(r.view_location.x, r.view_location.y)
        if tid != _TILEF['last']:
            _TILEF['last'] = tid
            n = only(tid)
            print('[tile-follow] 切到 %s（%d 对象）' % (tid, n))
    except Exception as e:
        print('[tile-follow] 异常:', e)
    return 1.0


def follow_tile(on=True):
    """自动跟随单块：只显示相机当前地块，跨块自动切换。"""
    _TILEF['on'] = bool(on)
    if on:
        if _TILEF['timer'] is None:
            _TILEF['timer'] = bpy.app.timers.register(_tilef_tick, first_interval=1.0, persistent=True)
        _tilef_tick()
        print('[tile-follow] 已开启（只显示当前地块，1s 检查，跨块才切）')
    else:
        t = _TILEF['timer']
        if t is not None:
            try:
                bpy.app.timers.unregister(t)
            except Exception:
                pass
            _TILEF['timer'] = None
        _TILEF['last'] = None
        print('[tile-follow] 已关闭（timer 已注销，当前显示保持不动）')


def stream(on=True, radius_m=None, far_hide=9000.0):
    """相机驱动的流式加载：只显示视点附近的地块，移动时自动更新。

    - 半径默认 = max(1200, 视距 × 1.3)，最大 6000 m
    - 视距 > far_hide（默认 9000 m）→ 只留地形/水面（对象全藏）
    - 每 0.5 s 检查一次，**只在集合集合变化时才动**，避免每帧重建
    """
    _STREAM['on'] = bool(on)
    if not on:
        # 2026-10-28：只置标志位时 timer 还在每 0.5s 唤醒，必须真注销
        t = _STREAM.get('timer')
        if t is not None:
            try:
                import bpy as _b
                _b.app.timers.unregister(t)
            except Exception:
                pass
            _STREAM['timer'] = None
        # 跟随相机那一套也一起停
        try:
            ft = _FOLLOW.get('timer')
            if ft is not None:
                import bpy as _b2
                _b2.app.timers.unregister(ft)
                _FOLLOW['timer'] = None
                _FOLLOW['on'] = False
        except Exception:
            pass
        print('stream: 已关闭，timer 已注销（不再跟随相机）')
        return
    if _STREAM['timer'] is None:
        _STREAM['timer'] = bpy.app.timers.register(_stream_tick, first_interval=0.5, persistent=True)
    _stream_tick(radius_m=radius_m, far_hide=far_hide, force=True)
    print('stream: 已开启（半径跟随视距，视距>%.0fm 只留地形）' % far_hide)


def _stream_tick(radius_m=None, far_hide=9000.0, force=False):
    if not _STREAM['on']:
        return 0.5
    try:
        a = None
        for v in _views():
            if v.spaces.active.region_3d is not None:
                a = v
                break
        if a is None:
            return 0.5
        r = a.spaces.active.region_3d
        d = float(r.view_distance)
        loc = r.view_location
        if d > far_hide:
            keep = set()
            if force or _STREAM['shown'] != keep:
                _apply_tiles(keep)
                _STREAM['shown'] = keep
                print('[stream] 视距 %.0f m → 只显示地形（对象全藏）' % d)
            return 0.5
        rad = radius_m if radius_m else max(1200.0, min(6000.0, d * 1.3))
        keep = tiles_near(loc.x, loc.y, rad)
        if force or keep != _STREAM['shown']:
            _apply_tiles(keep)
            _STREAM['shown'] = keep
    except Exception as e:
        print('[stream] 跳过:', e)
    return 0.5


def stream_off():
    _STREAM['on'] = False
    print('stream: 已关闭')
