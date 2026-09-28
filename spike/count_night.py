"""THROWAWAY SPIKE — count screenline crossings from stored tracks + render overlay."""
import cv2, json, math, collections, sys
import numpy as np

BASE = '/Users/Ak47/Desktop/spike_cv'
D = json.load(open(f'{BASE}/tracks_night.json'))
recs, W, H, FPS = D['records'], D['w'], D['h'], D['fps']
NF = D['n_frames']

tracks = collections.defaultdict(list)
for r in recs:
    tracks[r['id']].append(r)
for t in tracks.values():
    t.sort(key=lambda r: r['f'])

MIN_LEN, MIN_DISP = 3, 10
def disp(t):
    return math.hypot(t[-1]['cx'] - t[0]['cx'], t[-1]['cy'] - t[0]['cy'])
good = {k: v for k, v in tracks.items() if len(v) >= MIN_LEN and disp(v) >= MIN_DISP}

def side(p, a, b):
    return (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])

def within(p, a, b):
    """projection of p onto segment ab falls inside it"""
    vx, vy = b[0]-a[0], b[1]-a[1]
    L2 = vx*vx + vy*vy
    if L2 == 0: return False
    t = ((p[0]-a[0])*vx + (p[1]-a[1])*vy) / L2
    return 0.0 <= t <= 1.0

def count_line(a, b, label):
    events = []
    for tid, t in good.items():
        cls = collections.Counter(r['cls'] for r in t).most_common(1)[0][0]
        for p, q in zip(t, t[1:]):
            P, Q = (p['cx'], p['cy']), (q['cx'], q['cy'])
            sp, sq = side(P, a, b), side(Q, a, b)
            if sp == 0 or sq == 0 or (sp > 0) == (sq > 0):
                continue
            mid = ((P[0]+Q[0])/2, (P[1]+Q[1])/2)
            if not within(mid, a, b):
                continue
            events.append({'id': tid, 'f': q['f'], 'cls': cls,
                           'dir': 'up' if q['cy'] < p['cy'] else 'down'})
            break   # count each track once
    return events

if __name__ == '__main__':
    cfg = json.load(open(f'{BASE}/lines.json'))
    allev = {}
    print(f"frames={NF} ({NF/FPS:.1f}s)  raw_tracks={len(tracks)}  good_tracks={len(good)}\n")
    for L in cfg['lines']:
        a, b = tuple(L['a']), tuple(L['b'])
        ev = count_line(a, b, L['label'])
        allev[L['label']] = ev
        bycls = collections.Counter(e['cls'] for e in ev)
        bydir = collections.Counter(e['dir'] for e in ev)
        rate = len(ev) / (NF / FPS) * 3600
        print(f"--- {L['label']}  {a}->{b}")
        print(f"    crossings: {len(ev)}   => {rate:,.0f} veh/h")
        print(f"    direction: {dict(bydir)}")
        print(f"    classes  : {dict(bycls)}")
        print()
    json.dump({k: v for k, v in allev.items()}, open(f'{BASE}/events_night.json', 'w'), indent=1)
    print("wrote events_night.json")
