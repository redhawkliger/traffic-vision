"""Score a camera still for 'the whole intersection box is in frame'.

Owner's criterion: the area bounded by the crosswalks must be fully visible,
with the frame edge OUTSIDE the crosswalks.

Discriminator that matters: a CROSSWALK is a run of parallel bars whose centres
lie on a line PERPENDICULAR to the bars, evenly spaced. Lane dashes are the
opposite - successive dashes lie ALONG their own axis. That single test throws
out most road paint. A full box then needs those crosswalks arranged AROUND a
centre, not clustered on one side (which is what a 2-approach view looks like).
"""
import cv2, numpy as np, math

def bars(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(3.0, (8, 8)).apply(g)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT,
                          cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)))
    _, bw = cv2.threshold(th, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    H, W = g.shape
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < 60 or a > 0.02 * H * W:
            continue
        pts = np.column_stack(np.where(lab == i))[:, ::-1].astype(np.int32)
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
        L, S = max(rw, rh), min(rw, rh)
        if S < 3 or L < 12 or not (2.0 <= L / max(1e-6, S) <= 25.0):
            continue
        if a / max(1e-6, rw * rh) < 0.55:
            continue
        theta = math.radians(ang + (90 if rh > rw else 0))   # bar LONG axis
        pad = 14
        y0, y1 = max(0, int(cy - h / 2 - pad)), min(H, int(cy + h / 2 + pad))
        x0, x1 = max(0, int(cx - w / 2 - pad)), min(W, int(cx + w / 2 + pad))
        ring = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        if ring.size == 0 or not (45 < float(np.median(ring)) < 190):
            continue
        out.append((float(cx), float(cy), float(L), float(S), float(theta)))
    return out

def _is_crosswalk(mem, bs):
    """Centres collinear PERPENDICULAR to the bars, and evenly spaced."""
    P = np.array([[bs[k][0], bs[k][1]] for k in mem])
    th = np.mean([bs[k][4] for k in mem])
    axis = np.array([math.cos(th), math.sin(th)])        # along the bar
    perp = np.array([-axis[1], axis[0]])                 # across the run
    u = P @ axis                                         # spread ALONG bars
    t = P @ perp                                         # spread ACROSS bars
    Lm = float(np.mean([bs[k][2] for k in mem]))
    if np.std(u) > 0.55 * Lm:                            # not a side-by-side run
        return False
    if np.ptp(t) < 1.2 * Lm:                             # run must be longer than one bar
        return False
    ts = np.sort(t); dif = np.diff(ts)
    if len(dif) < 3 or np.mean(dif) < 1e-6:
        return False
    if np.std(dif) / np.mean(dif) > 0.60:                # spacing must be regular
        return False
    return True

def groups(bs, min_bars=4):
    used = [False] * len(bs); gs = []
    order = sorted(range(len(bs)), key=lambda i: -bs[i][2])
    for i in order:
        if used[i]:
            continue
        cx, cy, L, S, th = bs[i]
        mem = [i]
        for j, o in enumerate(bs):
            if j == i or used[j]:
                continue
            d = abs(math.degrees(th - o[4])) % 180; d = min(d, 180 - d)
            if d > 15: continue
            if max(L, o[2]) / max(1e-6, min(L, o[2])) > 2.0: continue
            if math.hypot(cx - o[0], cy - o[1]) > 3.0 * L: continue
            mem.append(j)
        if len(mem) >= min_bars and _is_crosswalk(mem, bs):
            for k in mem: used[k] = True
            P = np.array([[bs[k][0], bs[k][1]] for k in mem])
            gs.append({"n": len(mem), "cx": float(P[:,0].mean()), "cy": float(P[:,1].mean()),
                       "theta": float(np.mean([bs[k][4] for k in mem]))})
    return gs

def score(path):
    img = cv2.imread(path)
    if img is None: return None
    H, W = img.shape[:2]
    if W < 600: return None
    gs = groups(bars(img))
    r = {"path": path, "n_groups": len(gs), "surround": 0.0, "margin": 0.0,
         "score": 0.0, "groups": gs, "wh": [W, H]}
    if len(gs) < 2: return r
    P = np.array([[g["cx"], g["cy"]] for g in gs])
    c = P.mean(0)
    # do the crosswalks SURROUND a centre, or sit on one side? -> angular coverage
    angs = np.degrees(np.arctan2(P[:,1]-c[1], P[:,0]-c[0])) % 360
    quad = len({int(a // 90) for a in angs})
    # distinct bar ORIENTATIONS: a real box has crosswalks on >=2 axes
    ths = sorted({round(math.degrees(g["theta"]) % 180 / 25) for g in gs})
    r["surround"] = quad / 4.0
    r["n_axes"] = len(ths)
    mx = min(P[:,0].min()/W, 1-P[:,0].max()/W); my = min(P[:,1].min()/H, 1-P[:,1].max()/H)
    r["margin"] = max(0.0, min(mx, my))
    r["score"] = round(float(
        min(len(gs),4)/4.0 * 0.30 +
        r["surround"]      * 0.30 +
        min(r["n_axes"],3)/3.0 * 0.20 +
        min(r["margin"]/0.08, 1.0) * 0.20), 4)
    r["surround"] = round(r["surround"], 3); r["margin"] = round(r["margin"], 4)
    return r

if __name__ == "__main__":
    import sys, json
    for p in sys.argv[1:]:
        r = score(p)
        print(json.dumps({k:v for k,v in r.items() if k!="groups"}) if r else f"{p}: unreadable")
