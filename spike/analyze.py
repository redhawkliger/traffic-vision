"""THROWAWAY SPIKE — derive flow structure from stored tracks, then count."""
import cv2, json, math, collections
import numpy as np

D = json.load(open('/Users/Ak47/Desktop/traffic-vision/data/tracks.json'))
recs = D['records']; W, H, FPS = D['w'], D['h'], D['fps']
print(f"frames={D['n_frames']} fps={FPS} dets={len(recs)}")

tracks = collections.defaultdict(list)
for r in recs:
    tracks[r['id']].append(r)
for t in tracks.values():
    t.sort(key=lambda r: r['f'])
print(f"raw tracks: {len(tracks)}")

def traj_stats(t):
    x0, y0 = t[0]['cx'], t[0]['cy']; x1, y1 = t[-1]['cx'], t[-1]['cy']
    disp = math.hypot(x1 - x0, y1 - y0)
    return dict(n=len(t), dx=x1 - x0, dy=y1 - y0, disp=disp,
                frames=t[-1]['f'] - t[0]['f'] + 1,
                cls=collections.Counter(r['cls'] for r in t).most_common(1)[0][0],
                conf=float(np.mean([r['conf'] for r in t])))

S = {tid: traj_stats(t) for tid, t in tracks.items()}
MIN_LEN, MIN_DISP = 6, 25
good = {k: v for k, v in S.items() if v['n'] >= MIN_LEN and v['disp'] >= MIN_DISP}
print(f"after filter (len>={MIN_LEN}, disp>={MIN_DISP}px): {len(good)}")

print("\nlength distribution (frames observed):")
ls = sorted(v['n'] for v in S.values())
for q in [10, 25, 50, 75, 90, 99]:
    print(f"  p{q}: {ls[int(len(ls)*q/100)-1]}")
print("\ndisplacement distribution (px):")
ds = sorted(v['disp'] for v in S.values())
for q in [10, 25, 50, 75, 90, 99]:
    print(f"  p{q}: {ds[int(len(ds)*q/100)-1]:.0f}")

up = sum(1 for v in good.values() if v['dy'] < 0)
dn = sum(1 for v in good.values() if v['dy'] > 0)
print(f"\ndirection of good tracks: dy<0 (receding/up-image)={up}   dy>0 (approaching/down)={dn}")
print("class mix of good tracks:", collections.Counter(v['cls'] for v in good.values()).most_common())

# draw trajectories over the reference frame
base = cv2.imread('/Users/Ak47/Desktop/traffic-vision/data/frame_plain.jpg')
canvas = (base * 0.35).astype('uint8')
for tid, v in good.items():
    pts = np.array([[r['cx'], r['cy']] for r in tracks[tid]], np.int32)
    col = (0, 200, 255) if v['dy'] < 0 else (255, 120, 0)   # amber=up, blue=down
    cv2.polylines(canvas, [pts], False, col, 2)
    cv2.circle(canvas, tuple(pts[0]), 4, (0, 255, 0), -1)    # green = start
    cv2.circle(canvas, tuple(pts[-1]), 4, (0, 0, 255), -1)   # red = end
for x in range(0, W, 100):
    cv2.line(canvas, (x, 0), (x, H), (60, 60, 60), 1)
    cv2.putText(canvas, str(x), (x + 3, 16), 0, 0.45, (150, 150, 150), 1)
for y in range(0, H, 100):
    cv2.line(canvas, (0, y), (W, y), (60, 60, 60), 1)
    cv2.putText(canvas, str(y), (3, y - 4), 0, 0.45, (150, 150, 150), 1)
cv2.imwrite('/Users/Ak47/Desktop/traffic-vision/data/trajectories.jpg', canvas)
print("\nwrote trajectories.jpg  (amber=receding, blue=approaching, green=start, red=end)")
