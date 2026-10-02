"""THROWAWAY — track vehicles, keep ONE best (largest) crop per track."""
import cv2, json, os, warnings, sys
warnings.filterwarnings('ignore')
from ultralytics import YOLO
SRC=sys.argv[1]; OUT=sys.argv[2]; SKIP=2; IMGSZ=1280
COCO={0:'ped',1:'bike',2:'car',3:'motorbike',5:'HV',7:'HV'}   # -> user scheme
os.makedirs(OUT,exist_ok=True)
m=YOLO('/Users/Ak47/Desktop/traffic-vision/data/yolo11n.pt')
cap=cv2.VideoCapture(SRC)
best={}
i=0
while True:
    ok,fr=cap.read()
    if not ok: break
    if i%SKIP: i+=1; continue
    r=m.track(fr,persist=True,tracker='/Users/Ak47/Desktop/traffic-vision/data/night_bytetrack.yaml',
              imgsz=IMGSZ,classes=list(COCO),conf=0.15,verbose=False)[0]
    b=r.boxes
    if b is not None and b.id is not None:
        for tid,cls,cf,xy in zip(b.id.tolist(),b.cls.tolist(),b.conf.tolist(),b.xyxy.tolist()):
            x1,y1,x2,y2=[int(v) for v in xy]
            area=(x2-x1)*(y2-y1)
            tid=int(tid)
            if area>best.get(tid,{}).get('area',0):
                pad=int(0.12*max(x2-x1,y2-y1))
                H,W=fr.shape[:2]
                crop=fr[max(0,y1-pad):min(H,y2+pad), max(0,x1-pad):min(W,x2+pad)]
                best[tid]={'area':area,'crop':crop.copy(),'cls':COCO[int(cls)],
                           'raw':m.names[int(cls)],'conf':round(cf,3),'f':i,
                           'w':x2-x1,'h':y2-y1}
    i+=1
    if i%600==0: print(f"  {i} frames, {len(best)} tracks",flush=True)
cap.release()
meta=[]
for tid,d in sorted(best.items()):
    fn=f"{OUT}/{tid:04d}.jpg"
    cv2.imwrite(fn,d['crop'])
    meta.append({'id':tid,'file':fn,'yolo':d['cls'],'coco':d['raw'],
                 'conf':d['conf'],'w':d['w'],'h':d['h'],'frame':d['f']})
json.dump(meta,open(f"{OUT}/meta.json",'w'),indent=1)
import collections
print("tracks:",len(meta))
print("YOLO class mix:",collections.Counter(x['yolo'] for x in meta).most_common())
print("bbox width percentiles:", sorted(x['w'] for x in meta)[::max(1,len(meta)//10)])
