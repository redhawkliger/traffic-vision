"""Rank cameras by COUNTABILITY, using the project's own site gate.

Not 'is it an intersection' - the owner accepted a freeway. The question is
whether vehicles are big enough to detect reliably (>=60 px => 95-99% recall,
measured earlier on three cameras) and whether there are enough of them for a
benchmark to have statistical power (L-008 wants N>=50).
"""
import json, os, sys, cv2, numpy as np
from ultralytics import YOLO
VEH={2,3,5,7}
GATE=60.0

def main(min_w=1280, out='data/frames/countability.json'):
    idx={c['uid']:c for c in json.load(open('data/stills/index.json'))}
    files=[f for f in os.listdir('data/frames') if f.endswith('.jpg')]
    todo=[]
    for f in files:
        uid=f[:-4]
        if uid not in idx: continue
        im=cv2.imread('data/frames/'+f)
        if im is None or im.shape[1]<min_w: continue
        todo.append((uid,'data/frames/'+f))
    print(f"frames >= {min_w}px wide: {len(todo)}",flush=True)
    m=YOLO('models/yolo11n.pt'); rows=[]
    for i in range(0,len(todo),16):
        batch=todo[i:i+16]
        for (uid,p),r in zip(batch,m.predict([p for _,p in batch],imgsz=1280,conf=0.25,verbose=False)):
            b=r.boxes
            sz=[]
            if b is not None:
                for xy,c in zip(b.xyxy.cpu().numpy(), b.cls.cpu().numpy().astype(int)):
                    if c in VEH: sz.append(max(xy[2]-xy[0], xy[3]-xy[1]))
            sz=np.array(sz) if sz else np.array([])
            n_ok=int((sz>=GATE).sum()) if len(sz) else 0
            rows.append({**{k:idx[uid].get(k) for k in ('uid','district','route','name','direction','lat','lon','stream')},
                         'n_veh':len(sz),'n_countable':n_ok,
                         'median_px':round(float(np.median(sz)),1) if len(sz) else 0.0,
                         'frac_gate':round(float((sz>=GATE).mean()),3) if len(sz) else 0.0,
                         'wh':[r.orig_shape[1],r.orig_shape[0]]})
        if (i+16)%160==0: print(f"  {min(i+16,len(todo))}/{len(todo)}",flush=True)
    rows.sort(key=lambda x:(-x['n_countable'],-x['median_px']))
    json.dump(rows,open(out,'w'),indent=1)
    print(f"\nscored {len(rows)}\nTOP 25 by countable vehicles in one frame:")
    for i,r in enumerate(rows[:25]):
        print(f" {i+1:3d}. n={r['n_countable']:3d}/{r['n_veh']:<3} med={r['median_px']:6.1f}px "
              f"gate={r['frac_gate']:.2f} {r['wh'][0]}x{r['wh'][1]:<5} D{r['district']:<3}{str(r['name'])[:44]}")

if __name__=='__main__':
    main(int(sys.argv[1]) if len(sys.argv)>1 else 1280)
