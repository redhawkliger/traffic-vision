"""THROWAWAY SPIKE — YOLO+ByteTrack over the recorded clip.
Pass 1: stream frames, track, record detections, write the clean clip the
human hand-counts. Never buffers frames (8 GB RAM)."""
import cv2, json, time, warnings
warnings.filterwarnings('ignore')
from ultralytics import YOLO

SRC, N_FRAMES, IMGSZ = 'clip_raw.ts', 1800, 960
VEH = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}

model = YOLO('yolo11n.pt')
cap = cv2.VideoCapture(SRC)
fps = cap.get(cv2.CAP_PROP_FPS)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
clean = cv2.VideoWriter('clip.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

records, t0 = [], time.time()
for i in range(N_FRAMES):
    ok, frame = cap.read()
    if not ok:
        print(f"stream ended at frame {i}"); break
    clean.write(frame)
    r = model.track(frame, persist=True, tracker='bytetrack.yaml', imgsz=IMGSZ,
                    classes=list(VEH), conf=0.25, verbose=False)[0]
    b = r.boxes
    if b is not None and b.id is not None:
        for tid, cls, conf, xyxy in zip(b.id.tolist(), b.cls.tolist(),
                                        b.conf.tolist(), b.xyxy.tolist()):
            x1, y1, x2, y2 = xyxy
            records.append({'f': i, 'id': int(tid), 'cls': VEH[int(cls)],
                            'conf': round(conf, 3),
                            'cx': round((x1 + x2) / 2, 1), 'cy': round((y1 + y2) / 2, 1),
                            'x1': round(x1, 1), 'y1': round(y1, 1),
                            'x2': round(x2, 1), 'y2': round(y2, 1)})
    if i % 150 == 0:
        el = time.time() - t0
        print(f"  frame {i}/{N_FRAMES}  {el:.0f}s elapsed  "
              f"eta {el / max(i, 1) * (N_FRAMES - i) / 60:.1f} min  tracks={len(set(x['id'] for x in records))}",
              flush=True)

cap.release(); clean.release()
json.dump({'fps': fps, 'w': w, 'h': h, 'n_frames': i + 1, 'imgsz': IMGSZ,
           'model': 'yolo11n.pt', 'records': records},
          open('tracks.json', 'w'))
ids = set(x['id'] for x in records)
print(f"DONE {time.time()-t0:.0f}s  frames={i+1}  detections={len(records)}  unique_tracks={len(ids)}")
