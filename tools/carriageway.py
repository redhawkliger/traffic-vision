"""Find the CARRIAGEWAY edges from the asphalt, and span the counting line across it.

Why: deriving line extent from traffic density asks "where were vehicles?" - so a
lane that was empty, or where optical flow went incoherent, looks like no lane.
The owner caught exactly that: the leftmost lane fell outside the line.

The road surface is a physical feature that is there whether or not a car is.
Asphalt is dark, low-saturation and smooth; the median barrier and the shoulder
are bright. So walk across the line's own axis on a vehicle-free median
background and take the contiguous asphalt run that the line already sits in.

    python tools/carriageway.py BACKGROUND CONFIG [--out CONFIG] [--inset 6]
"""
from __future__ import annotations
import argparse, json
import cv2, numpy as np

def asphalt_mask(bg):
    hsv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV)
    g = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    # dark-to-mid, unsaturated, and not blown out: road, not barrier/sky/dirt
    m = ((hsv[..., 1] < 70) & (g > 40) & (g < 165)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    return m

def span(bg, line, inset=6.0, hit=0.55):
    """Extend `line` along its own axis to the edges of the asphalt it lies in."""
    H, W = bg.shape[:2]
    m = asphalt_mask(bg)
    A = np.array(line[0], float); B = np.array(line[1], float)
    u = (B - A) / np.linalg.norm(B - A)          # along the line
    n = np.array([-u[1], u[0]])                  # across it = direction of travel
    mid = (A + B) / 2.0
    L = float(np.linalg.norm(B - A))

    def on_road(p):
        """Sample a short span along TRAVEL so one lane stripe cannot read as 'off road'."""
        votes = []
        for d in (-14, -7, 0, 7, 14):
            q = p + n * d
            x, y = int(round(q[0])), int(round(q[1]))
            if 0 <= x < W and 0 <= y < H:
                votes.append(m[y, x] > 0)
        return bool(votes) and (sum(votes) / len(votes)) >= hit

    out = {}
    for name, sign in (("neg", -1.0), ("pos", +1.0)):
        t = 0.0; last_ok = 0.0
        while t < 2200:
            t += 2.0
            p = mid + u * sign * t
            if not (0 <= p[0] < W and 0 <= p[1] < H):
                break
            if on_road(p):
                last_ok = t
            elif t - last_ok > 26:               # 26px of continuous non-road = a real edge
                break
        out[name] = max(0.0, last_ok - inset)
    A2 = mid - u * out["neg"]; B2 = mid + u * out["pos"]
    return [[int(round(A2[0])), int(round(A2[1]))], [int(round(B2[0])), int(round(B2[1]))]], L, m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("background"); ap.add_argument("config")
    ap.add_argument("--out"); ap.add_argument("--inset", type=float, default=6.0)
    ap.add_argument("--viz")
    a = ap.parse_args()
    bg = cv2.imread(a.background)
    cfg = json.load(open(a.config))
    new, old_len, m = span(bg, cfg["line"], a.inset)
    nl = float(np.linalg.norm(np.array(new[1], float) - np.array(new[0], float)))
    print(f"line {cfg['line']} (len {old_len:.0f}px)  ->  {new} (len {nl:.0f}px)")
    if a.viz:
        v = cv2.addWeighted(bg, 0.72, cv2.cvtColor(m, cv2.COLOR_GRAY2BGR), 0.28, 0)
        cv2.line(v, tuple(cfg["line"][0]), tuple(cfg["line"][1]), (0, 0, 255), 5)
        cv2.line(v, tuple(new[0]), tuple(new[1]), (0, 255, 255), 3)
        for p in new:
            cv2.circle(v, tuple(p), 11, (0, 255, 255), -1); cv2.circle(v, tuple(p), 11, (0, 0, 0), 2)
        cv2.putText(v, "RED = old (from traffic density)", (24, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 6)
        cv2.putText(v, "RED = old (from traffic density)", (24, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.putText(v, "YELLOW = new (curb to curb, from asphalt)", (24, 88), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 6)
        cv2.putText(v, "YELLOW = new (curb to curb, from asphalt)", (24, 88), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        cv2.imwrite(a.viz, v); print("wrote", a.viz)
    if a.out:
        cfg["line"] = new
        cfg.setdefault("derivation", {})["extent_from"] = (
            "carriageway edges detected from the asphalt on a vehicle-free median background "
            "(tools/carriageway.py) - NOT from traffic density, which misses empty lanes")
        json.dump(cfg, open(a.out, "w"), indent=1); print("wrote", a.out)

if __name__ == "__main__":
    main()
