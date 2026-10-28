# -*- coding: utf-8 -*-
"""探针：同一过场的多个 .yad 分页里，相机段是否首尾相接（能否跨页拼成完整轨迹）"""
import sys, glob, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cutscene_camera as C


def probe(pack, cutscene):
    files = sorted(glob.glob(f'work/story/cutscene_all/extracted/{pack}/{cutscene}-*.yad'),
                   key=lambda p: int(p.rsplit('-', 1)[1].split('.')[0]))
    print('==', cutscene, '页数', len(files))
    for f in files:
        cands = [c for c in C.scan_block(f) if c['bones'] <= 45 and C.camera_signature(c)[0] >= 1]
        if not cands:
            print('  ', os.path.basename(f), '无相机候选')
            continue
        for c in sorted(cands, key=lambda x: -x['dur'])[:2]:
            tk = [k for k in c['tracks'] if len(c['tracks'][k]) == 3][:1]
            if not tk:
                continue
            t = c['tracks'][tk[0]]
            print('  %-22s dur=%6.2f bones=%2d  首X=%8.2f 末X=%8.2f 首Y=%8.2f 末Y=%8.2f' % (
                os.path.basename(f), c['dur'], c['bones'],
                t[0][0], t[0][-1], t[1][0], t[1][-1]))


if __name__ == '__main__':
    probe(sys.argv[1], sys.argv[2])
