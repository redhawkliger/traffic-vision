"""Where does traffic actually run, and which way? Evidence for line placement.

Replaces drawing a line by eye. Accumulates inter-frame motion over a whole clip
and a coarse optical-flow field, then reports, per image row, the dominant
direction AND its coherence. Coherence matters: optical flow on large, fast,
near-field vehicles can average to noise, and a near-zero mean flow has a
direction that means nothing (L-018 session: a 0.04-coherence reading was
misread as 'opposing lanes').

    python tools/motionmap.py CLIP OUTPREFIX [--step 10]
"""
from __future__ import annotations
import argparse, math
import cv2, numpy as np

def build(src: str, step: int = 10, cols: int = 64):
    cap = cv2.VideoCapture(src)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cell = max(1, W // cols); rows = H // cell
    fx = np.zeros((rows, cols), np.float32); fy = np.zeros_like(fx)
    fw = np.zeros_like(fx); fa = np.zeros_like(fx)          # fa = sum of |flow|
    accum = None; prev = None; prev_small = None; i = used = 0
    sw, sh = 320, max(1, int(320 * H / W))
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % step == 0:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                d = cv2.absdiff(g, prev).astype(np.float32)
                accum = d if accum is None else accum + d
                small = cv2.resize(g, (sw, sh))
                fl = cv2.calcOpticalFlowFarneback(prev_small, small, None, .5, 3, 21, 3, 5, 1.2, 0)
                mag = np.hypot(fl[..., 0], fl[..., 1]); m = mag > 0.6
                ry, rx = sh / rows, sw / cols
                for cy in range(rows):
                    y0, y1 = int(cy * ry), int((cy + 1) * ry)
                    for cx in range(cols):
                        x0, x1 = int(cx * rx), int((cx + 1) * rx)
                        sel = m[y0:y1, x0:x1]
                        if not sel.any(): continue
                        fx[cy, cx] += fl[..., 0][y0:y1, x0:x1][sel].sum()
                        fy[cy, cx] += fl[..., 1][y0:y1, x0:x1][sel].sum()
                        w = mag[y0:y1, x0:x1][sel]
                        fw[cy, cx] += w.sum(); fa[cy, cx] += w.sum()
                prev_small = small
            else:
                prev_small = cv2.resize(g, (sw, sh))
            prev = g; used += 1
        i += 1
    cap.release()
    return dict(accum=accum, fx=fx, fy=fy, fw=fw, fa=fa, W=W, H=H, cell=cell,
                rows=rows, cols=cols, used=used, frames=i)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("outprefix")
    ap.add_argument("--step", type=int, default=10)
    a = ap.parse_args()
    d = build(a.clip, a.step)
    np.savez(a.outprefix + ".npz", **{k: v for k, v in d.items() if isinstance(v, np.ndarray)},
             meta=np.array([d['W'], d['H'], d['cell'], d['rows'], d['cols'], d['used'], d['frames']]))
    print(f"frames {d['frames']} sampled {d['used']}  {d['W']}x{d['H']}  cell {d['cell']}px"
          f"  grid {d['cols']}x{d['rows']}")
    print(f"wrote {a.outprefix}.npz")

if __name__ == "__main__":
    main()
