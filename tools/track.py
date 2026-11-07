"""Detect and track vehicles in a clip; write per-frame records with bboxes.

Output JSON carries everything downstream stages need - crucially the bounding
box, because stitch.py uses the vehicle's own box as its physical ruler.

NOTE on conf: the default is deliberately LOW. Ultralytics defaults to 0.25,
which discarded ~80% of night vehicles in testing (they detect at 0.15-0.24),
and ByteTrack's own new_track_thresh (also 0.25) then prevents weak detections
from ever STARTING a track. Both must be lowered together.

Usage:
    python track.py clip.ts out.json --skip 3
"""
from __future__ import annotations

import argparse
import json
import os
import time
import warnings

warnings.filterwarnings("ignore")

VEHICLE_CLASSES = {0: "ped", 1: "bike", 2: "car", 3: "motorbike", 5: "HV", 7: "HV"}

# The tracker is PINNED (never the invisible ultralytics library default). Its path and
# full resolved contents are written into every output header.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TRACKER = os.path.join(ROOT, "configs", "tracker.yaml")


def resolve_tracker(tracker: str | None = None) -> tuple[str, dict]:
    """Return (absolute yaml path, parsed contents). None -> configs/tracker.yaml.
    A bare name such as 'bytetrack.yaml' resolves to the installed ultralytics cfg."""
    import yaml
    path = tracker or DEFAULT_TRACKER
    if not os.path.exists(path):
        import ultralytics
        alt = os.path.join(os.path.dirname(ultralytics.__file__), "cfg", "trackers",
                           os.path.basename(path))
        if not os.path.exists(alt):
            raise FileNotFoundError(f"tracker yaml not found: {path}")
        path = alt
    path = os.path.abspath(path)
    with open(path, encoding="utf-8") as fh:
        return path, yaml.safe_load(fh)


def track(path: str, skip: int = 3, imgsz: int = 1280, conf: float = 0.15,
          model_name: str = "yolo11n.pt", tracker: str | None = None,
          start: int = 0, end: int | None = None) -> dict:
    import cv2
    from ultralytics import YOLO

    model = YOLO(model_name)
    cap = cv2.VideoCapture(path)
    meta_fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracker_path, tracker_cfg = resolve_tracker(tracker)
    kwargs = dict(persist=True, imgsz=imgsz, conf=conf, tracker=tracker_path,
                  classes=list(VEHICLE_CLASSES), verbose=False)

    records, i, started = [], 0, time.time()
    while True:
        if end is not None and i >= end:
            break
        if i < start:  # sequential grab keeps absolute frame indices exact on .ts
            if not cap.grab():
                break
            i += 1
            continue
        ok, frame = cap.read()
        if not ok:
            break
        if i % skip:
            i += 1
            continue
        res = model.track(frame, **kwargs)[0]
        b = res.boxes
        if b is not None and b.id is not None:
            for tid, cls, cf, xyxy in zip(b.id.tolist(), b.cls.tolist(),
                                          b.conf.tolist(), b.xyxy.tolist()):
                x1, y1, x2, y2 = xyxy
                records.append({
                    "f": i, "id": int(tid), "cls": VEHICLE_CLASSES[int(cls)],
                    "coco": model.names[int(cls)], "conf": round(cf, 3),
                    "cx": round((x1 + x2) / 2, 1), "cy": round((y1 + y2) / 2, 1),
                    "w": round(x2 - x1, 1), "h": round(y2 - y1, 1),
                })
        i += 1
        if i % 600 == 0:
            el = time.time() - started
            print(f"  frame {i}  {el:.0f}s  tracks={len({r['id'] for r in records})}",
                  flush=True)
    cap.release()

    n_frames = i
    true_fps = n_frames / (n_frames / meta_fps) if meta_fps else 0
    return {"source": path, "width": w, "height": h, "n_frames": n_frames,
            "meta_fps": meta_fps, "true_fps": true_fps, "skip": skip,
            "imgsz": imgsz, "conf": conf, "model": model_name,
            "tracker_yaml": tracker_path,
            "tracker_name": tracker_cfg.get("tracker_type"),
            "tracker_config": tracker_cfg,
            "elapsed_s": round(time.time() - started, 1), "records": records}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--skip", type=int, default=3)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--tracker", help="tracker yaml; default configs/tracker.yaml (pinned TrackTrack)")
    ap.add_argument("--start", type=int, default=0, help="first frame to process")
    ap.add_argument("--end", type=int, default=None, help="stop before this frame")
    args = ap.parse_args()

    data = track(args.video, args.skip, args.imgsz, args.conf, args.model, args.tracker,
                 args.start, args.end)
    with open(args.out, "w") as fh:
        json.dump(data, fh)
    ids = {r["id"] for r in data["records"]}
    print(f"DONE {data['elapsed_s']}s  frames={data['n_frames']}  "
          f"detections={len(data['records'])}  tracks={len(ids)} -> {args.out}")


if __name__ == "__main__":
    main()
