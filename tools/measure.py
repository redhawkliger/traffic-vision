"""Site qualification: measure how big vehicles actually appear on a camera.

This is the screening test that decides whether a camera is worth using, and it
needs NO labelled data. Resolution in the stream manifest is not a useful
predictor - framing is. A 1280x720 intersection camera beat a 1920x1080 freeway
camera by 1.85x on median vehicle size, because it points at a confined box
rather than a mile of road.

Empirical thresholds measured on Caltrans imagery:
    < 60 px vehicle width   unclassifiable by model OR human
    >= 60 px                Car/HV distinguishable
    >= 100 px               reliable

CAUTION - `--skip` biases the result. Heavy subsampling loses short tracks and
over-samples large, persistent vehicles, which inflates the apparent median.
Measured on the same clip: skip=3 gave 453 tracks at 61 px median; skip=12 gave
37 tracks at 78 px. Use skip<=3 for any number you intend to act on.

Usage:
    python measure.py clip.ts
    python measure.py clip.ts --crops out/ --skip 3
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import warnings

warnings.filterwarnings("ignore")

# COCO ids -> our scheme. NOTE: this naive mapping OVER-CALLS heavy vehicles,
# because COCO labels pickups, Jeeps and light vans as `truck` while FHWA 1-3
# counts them as Car. Kept here only as a baseline to measure against.
COCO_TO_SCHEME = {0: "ped", 1: "bike", 2: "car", 3: "motorbike", 5: "HV", 7: "HV"}


def probe_video(path: str) -> dict:
    """Frame count, size, and TRUE frame rate.

    Container metadata frequently lies - one Caltrans camera declared 30 fps
    and delivered 10.8. Always derive fps from frames / wall-clock duration.
    """
    import cv2
    cap = cv2.VideoCapture(path)
    meta_fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    return {"frames": n, "width": w, "height": h, "meta_fps": meta_fps}


def best_crop_per_track(path: str, skip: int = 2, imgsz: int = 1280,
                        conf: float = 0.15, crops_dir: str | None = None) -> list[dict]:
    """Track vehicles and keep the single LARGEST observation of each.

    One crop per track, not per frame: a vehicle is seen 30-100 times and the
    largest view is the most informative. This also keeps the output honest as
    a per-vehicle sample rather than a per-frame one.
    """
    import cv2
    from ultralytics import YOLO

    model = YOLO("yolo11n.pt")
    cap = cv2.VideoCapture(path)
    best: dict[int, dict] = {}
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % skip:
            i += 1
            continue
        res = model.track(frame, persist=True, imgsz=imgsz, conf=conf,
                          classes=list(COCO_TO_SCHEME), verbose=False)[0]
        boxes = res.boxes
        if boxes is not None and boxes.id is not None:
            for tid, cls, cf, xyxy in zip(boxes.id.tolist(), boxes.cls.tolist(),
                                          boxes.conf.tolist(), boxes.xyxy.tolist()):
                x1, y1, x2, y2 = (int(v) for v in xyxy)
                area = (x2 - x1) * (y2 - y1)
                tid = int(tid)
                if area <= best.get(tid, {}).get("area", 0):
                    continue
                rec = {"area": area, "w": x2 - x1, "h": y2 - y1, "frame": i,
                       "coco": model.names[int(cls)], "conf": round(cf, 3)}
                if crops_dir:
                    pad = int(0.12 * max(x2 - x1, y2 - y1))
                    H, W = frame.shape[:2]
                    rec["_crop"] = frame[max(0, y1 - pad):min(H, y2 + pad),
                                         max(0, x1 - pad):min(W, x2 + pad)].copy()
                best[tid] = rec
        i += 1
    cap.release()

    out = []
    for tid, rec in sorted(best.items()):
        crop = rec.pop("_crop", None)
        if crops_dir is not None and crop is not None and crop.size:
            os.makedirs(crops_dir, exist_ok=True)
            fn = os.path.join(crops_dir, f"{tid:05d}.jpg")
            cv2.imwrite(fn, crop)
            rec["file"] = fn
        rec["track_id"] = tid
        out.append(rec)
    return out


def report(vid: dict, tracks: list[dict], duration_s: float | None = None) -> dict:
    import numpy as np
    w = np.array([t["w"] for t in tracks]) if tracks else np.array([0])
    pct = {q: int(np.percentile(w, q)) for q in (10, 25, 50, 75, 90)}
    usable = {thr: float((w >= thr).mean()) for thr in (60, 100, 150)}

    print(f"video      : {vid['width']}x{vid['height']}  {vid['frames']} frames")
    if duration_s:
        print(f"frame rate : {vid['frames']/duration_s:.1f} fps TRUE "
              f"(metadata claims {vid['meta_fps']:.0f})")
    print(f"tracks     : {len(tracks)}")
    print("\nvehicle width (px)")
    for q, v in pct.items():
        print(f"   p{q:<3}: {v}")
    print("\nusable share")
    for thr, frac in usable.items():
        print(f"   >= {thr:>3} px : {frac*100:5.1f}%")
    print("\nCOCO label mix:",
          collections.Counter(t["coco"] for t in tracks).most_common())

    verdict = ("GOOD - classification viable" if usable[60] >= 0.45 else
               "MARGINAL - counting only" if usable[60] >= 0.20 else
               "POOR - reject for classification")
    print(f"\nVERDICT: {verdict}  (median {pct[50]} px, {usable[60]*100:.0f}% >= 60 px)")
    return {"percentiles": pct, "usable": usable, "verdict": verdict,
            "n_tracks": len(tracks)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--skip", type=int, default=2, help="process every Nth frame")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--conf", type=float, default=0.15,
                    help="LOW on purpose; 0.25 discards ~80%% of night vehicles")
    ap.add_argument("--crops", help="directory to write one crop per vehicle")
    ap.add_argument("--duration", type=float, help="true clip duration in seconds")
    ap.add_argument("--json", help="write the summary here")
    args = ap.parse_args()

    vid = probe_video(args.video)
    tracks = best_crop_per_track(args.video, args.skip, args.imgsz,
                                 args.conf, args.crops)
    summary = report(vid, tracks, args.duration)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"video": vid, "summary": summary, "tracks": tracks}, fh, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
