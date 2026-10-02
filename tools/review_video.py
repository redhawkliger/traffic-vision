"""Review video: ONE mp4 per benchmark for a human to audit counts, camera-agnostic.

Draws, over the source clip:
  * the tripwire line (from the site config, any orientation) + direction arrow,
    and the along_range band if the config has one
  * each COUNTED crossing as a numbered ring "#N" at the crossing point for ~1.5 s.
    N = running count order = order among counted events in the crossings JSON
    (sorted by frame, track_id, exactly as tools/crossings.py emits them).
  * each REJECTED candidate as an orange ring "R<k> rejected: <reason>" (own numbering)
  * HUD: timestamp, running count, benchmark label, count type (blind|reviewed)
  * optional (--boxes) track boxes + ids behind the rings (needs --tracks)
Sidecar <out>.labels.json (+ .csv): label -> track_id, frame, t, x, y, heading, ...
so any "#N" the owner mentions maps back to pixels.

Nothing is hardcoded: image size comes from the clip, geometry from the config,
fonts/rings scale with image height.

CLI:
  python tools/review_video.py CLIP.ts --crossings result.json --config configs/X.json \
      --label "Harbor EB B" --count-type blind [--tracks tracks.json --boxes] \
      [--window LO HI] [--out review.mp4]
"""
import argparse
import collections
import csv
import json
import math
import os
import sys

import cv2

COUNTED_COL = (0, 230, 0)       # BGR green
REJECT_COL = (0, 140, 255)      # orange
LINE_COL = (0, 0, 255)          # red
RING_SECONDS = 1.5


def label_events(events):
    """Assign stable labels. Counted -> number 1..N in the order given (the event list
    order); rejected -> 'R1'.. in order. Returns list of label dicts."""
    out, nc, nr = [], 0, 0
    for e in events:
        if e["reject_reason"] == "window":   # crossing outside the counting window: not a candidate
            continue
        if e["counted"]:
            nc += 1
            lab, num = f"#{nc}", nc
        else:
            nr += 1
            lab, num = f"R{nr}", nr
        out.append({
            "label": lab, "number": num, "counted": bool(e["counted"]),
            "reject_reason": e["reject_reason"], "track_id": e["track_id"],
            "frame": e["frame"], "t": e["t"], "x": e["x_cross"], "y": e["y_cross"],
            "heading_deg": e["heading_deg"], "along_line": e.get("along_line"),
            "bbox_w_at_cross": e.get("bbox_w_at_cross"),
            "near_duplicate_of": e.get("near_duplicate_of"),
        })
    return out


def reject_text(lb):
    r = lb["reject_reason"]
    if r == "angle":
        return f"rejected: angle {lb['heading_deg']:.0f} deg"
    if r == "band":
        return "rejected: band"
    return f"rejected: {r}"


def build_track_index(tracks_src, hold=3):
    """frame -> list of (id, cx, cy, w, h). Tracks may be subsampled (skip N): each
    record is held for `hold` frames (default = skip-ish) so boxes don't flicker."""
    D = tracks_src if isinstance(tracks_src, dict) else json.load(open(tracks_src))
    hold = max(1, int(D.get("skip", hold)))
    by = collections.defaultdict(list)
    for r in D["records"]:
        for k in range(hold):
            by[r["f"] + k].append((r["id"], r["cx"], r["cy"], r["w"], r["h"]))
    return by


def open_writer(path, fps, size):
    for cc in ("avc1", "mp4v"):
        w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*cc), fps, size)
        if w.isOpened():
            return w, cc
    raise RuntimeError("no usable mp4 codec")


def _text(img, s, org, scale, col, thick, W, H):
    (tw, th), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    x = int(min(max(org[0], 2), max(2, W - tw - 2)))
    y = int(min(max(org[1], th + 2), H - 2))
    cv2.rectangle(img, (x - 2, y - th - 3), (x + tw + 2, y + 4), (0, 0, 0), -1)
    cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, col, thick, cv2.LINE_AA)


def draw_line(img, cfg, S):
    (x0, y0), (x1, y1) = cfg["line"]
    p0, p1 = (int(round(x0)), int(round(y0))), (int(round(x1)), int(round(y1)))
    cv2.line(img, p0, p1, LINE_COL, max(1, int(2 * S)), cv2.LINE_AA)
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0:
        return
    u = ((x1 - x0) / L, (y1 - y0) / L)
    rng = cfg.get("along_range")
    if rng:  # thicker segment marks the counting band
        a = (int(x0 + u[0] * rng[0]), int(y0 + u[1] * rng[0]))
        b = (int(x0 + u[0] * rng[1]), int(y0 + u[1] * rng[1]))
        cv2.line(img, a, b, LINE_COL, max(2, int(5 * S)), cv2.LINE_AA)
    # direction arrow from line midpoint
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from crossings import Geometry
        d = Geometry(cfg["line"], cfg["direction"]).d
    except Exception:
        return
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    ln = 50 * S
    cv2.arrowedLine(img, (int(mx), int(my)), (int(mx + d[0] * ln), int(my + d[1] * ln)),
                    LINE_COL, max(1, int(2 * S)), cv2.LINE_AA, tipLength=0.35)


def render(clip, crossings, cfg, out, label="", count_type="blind", tracks=None,
           boxes=False, window=None, ring_seconds=RING_SECONDS):
    cap = cv2.VideoCapture(clip)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {clip}")
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(crossings.get("config", {}).get("fps") or cap.get(cv2.CAP_PROP_FPS) or 25.0)
    S = H / 720.0
    cfg = dict(cfg)   # the crossings run is authoritative for the band it actually used
    if not cfg.get("along_range"):
        cfg["along_range"] = crossings.get("config", {}).get("along_range")
    if window is None:
        window = crossings.get("config", {}).get("window_frames")
    lo, hi = (int(window[0]), int(window[1])) if window else (0, n_total)
    hi = min(hi, n_total) if n_total > 0 else hi

    # rejected candidates outside the rendered window are not shown; counted ones keep
    # their running-count numbers regardless (numbering must match the event list)
    labels = label_events([e for e in crossings["events"] if e["counted"] or lo <= e["frame"] < hi])
    life = int(round(ring_seconds * fps))
    drawn_c = drawn_r = 0
    tidx = build_track_index(tracks) if (boxes and tracks is not None) else None

    # running count at each frame = counted events with frame <= f (full event list)
    counted_frames = sorted(lb["frame"] for lb in labels if lb["counted"])
    drawn_labels = set()

    writer, codec = open_writer(out, fps, (W, H))
    for _ in range(lo):               # sequential skip: exact frame indexing on .ts
        if not cap.grab():
            break
    f = lo
    ci = 0
    while f < hi:
        ok, img = cap.read()
        if not ok:
            break
        if tidx is not None:
            for (tid, cx, cy, w, h) in tidx.get(f, []):
                p1 = (int(cx - w / 2), int(cy - h / 2))
                p2 = (int(cx + w / 2), int(cy + h / 2))
                cv2.rectangle(img, p1, p2, (200, 200, 200), 1)
                cv2.putText(img, str(tid), (p1[0], max(10, p1[1] - 3)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.4 * S, (200, 200, 200), 1, cv2.LINE_AA)
        draw_line(img, cfg, S)

        overlay = None
        active = [lb for lb in labels if 0 <= f - lb["frame"] < life]
        for lb in active:
            col = COUNTED_COL if lb["counted"] else REJECT_COL
            age = f - lb["frame"]
            alpha = 1.0 - 0.6 * age / max(1, life)
            r = int(max(14 * S, min(60 * S, (lb["bbox_w_at_cross"] or 30) * 0.6)))
            if overlay is None:
                overlay = img.copy()
            c = (int(round(lb["x"])), int(round(lb["y"])))
            cv2.circle(overlay, c, r, col, max(2, int(4 * S)), cv2.LINE_AA)
            cv2.circle(overlay, c, max(2, int(3 * S)), col, -1, cv2.LINE_AA)
            lb["_alpha"] = alpha
            if lb["label"] not in drawn_labels:
                drawn_labels.add(lb["label"])
                if lb["counted"]:
                    drawn_c += 1
                else:
                    drawn_r += 1
        if overlay is not None:
            a = max(lb["_alpha"] for lb in active)
            img = cv2.addWeighted(overlay, a, img, 1 - a, 0)
            for lb in active:
                col = COUNTED_COL if lb["counted"] else REJECT_COL
                r = int(max(14 * S, min(60 * S, (lb["bbox_w_at_cross"] or 30) * 0.6)))
                txt = lb["label"] if lb["counted"] else f"{lb['label']} {reject_text(lb)}"
                if lb["counted"] and lb["near_duplicate_of"] is not None:
                    txt += f" (dup of {lb['near_duplicate_of']})"
                _text(img, txt, (lb["x"] + r + 4 * S, lb["y"] - r), 0.7 * S if lb["counted"] else 0.5 * S,
                      col, max(1, int(2 * S)), W, H)

        running = sum(1 for cf in counted_frames if cf <= f)
        hud = [f"{label}  [{count_type} count]" if label else f"[{count_type} count]",
               f"t={f / fps:7.2f}s  f={f}   COUNT: {running}"]
        for k, s in enumerate(hud):
            _text(img, s, (6, int((26 + 30 * k) * S)), 0.7 * S, (255, 255, 255) if k == 0 else (0, 255, 255),
                  max(1, int(2 * S)), W, H)
        writer.write(img)
        f += 1
    cap.release()
    writer.release()

    side = {
        "meta": {"label": label, "count_type": count_type, "clip": clip, "width": W, "height": H,
                 "fps": fps, "window_frames": [lo, hi], "codec": codec,
                 "counted_total": sum(1 for lb in labels if lb["counted"]),
                 "rejected_total": sum(1 for lb in labels if not lb["counted"]),
                 "counted_drawn": drawn_c, "rejected_drawn": drawn_r,
                 "line": cfg["line"], "direction": cfg["direction"]},
        "labels": [{k: v for k, v in lb.items() if not k.startswith("_")} for lb in labels],
    }
    base = os.path.splitext(out)[0]
    with open(base + ".labels.json", "w") as jf:
        json.dump(side, jf, indent=1)
    with open(base + ".labels.csv", "w", newline="") as fh:
        cols = ["label", "counted", "reject_reason", "track_id", "frame", "t", "x", "y",
                "heading_deg", "along_line", "bbox_w_at_cross", "near_duplicate_of"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(side["labels"])
    return side


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--crossings", required=True, help="output JSON of tools/crossings.py")
    ap.add_argument("--config", required=True, help="site config JSON (line, direction, ...)")
    ap.add_argument("--tracks", help="tracks JSON (only needed for --boxes)")
    ap.add_argument("--boxes", action="store_true", help="draw track boxes + ids")
    ap.add_argument("--label", default="", help="benchmark label for the HUD")
    ap.add_argument("--count-type", choices=["blind", "reviewed"], default="blind")
    ap.add_argument("--window", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--out", default="review.mp4")
    a = ap.parse_args(argv)
    if a.boxes and not a.tracks:
        ap.error("--boxes requires --tracks")
    cfg = json.load(open(a.config))
    cr = json.load(open(a.crossings))
    side = render(a.clip, cr, cfg, a.out, a.label, a.count_type, a.tracks, a.boxes, a.window)
    m = side["meta"]
    print(f"wrote {a.out}: counted drawn {m['counted_drawn']}/{m['counted_total']}, "
          f"rejected drawn {m['rejected_drawn']}/{m['rejected_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
