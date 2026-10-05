import os, sys
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS','rw_timeout;8000000|timeout;8000000')
import cv2
url,out=sys.argv[1],sys.argv[2]
cap=cv2.VideoCapture(url)
if not cap.isOpened(): sys.exit(2)
ok=False
for _ in range(12):            # skip the first frames; HLS often starts with a stale/grey one
    r,f=cap.read()
    if r and f is not None and f.std()>12: ok=True
cap.release()
if not ok: sys.exit(3)
cv2.imwrite(out,f); print(f"{f.shape[1]}x{f.shape[0]}")
