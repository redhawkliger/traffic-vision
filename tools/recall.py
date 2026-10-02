"""Relative detection recall vs vehicle pixel size, across cameras.

production = yolo11n @1280  (what we'd actually run on CPU)
reference  = yolo11s @1536  (stronger + higher res; finds more small objects)

For every REFERENCE detection we ask whether PRODUCTION found it (IoU>=0.45),
bucketed by reference box width. NOT absolute recall - the reference misses
things too. Read it as: what does the cheap model give up vs a stronger one.
"""
import sys, json, warnings, collections
warnings.filterwarnings("ignore")
import cv2, numpy as np
from ultralytics import YOLO

VEH=[2,3,5,7]
BUCKETS=[(0,40),(40,60),(60,80),(80,120),(120,200),(200,10**6)]

def iou(a,b):
    x1=max(a[0],b[0]); y1=max(a[1],b[1]); x2=min(a[2],b[2]); y2=min(a[3],b[3])
    w=max(0,x2-x1); h=max(0,y2-y1); inter=w*h
    ua=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/ua if ua>0 else 0.0

def run(path,label,nframes,dump_prefix=None):
    prod=YOLO('yolo11n.pt'); ref=YOLO('yolo11s.pt')
    cap=cv2.VideoCapture(path)
    total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    idxs=np.linspace(int(total*0.05), int(total*0.95), nframes).astype(int)
    hit=collections.Counter(); tot=collections.Counter()
    dumped=0
    for k,fi in enumerate(idxs):
        cap.set(cv2.CAP_PROP_POS_FRAMES,int(fi))
        ok,fr=cap.read()
        if not ok: continue
        R=ref.predict(fr,imgsz=1536,conf=0.10,classes=VEH,verbose=False)[0]
        P=prod.predict(fr,imgsz=1280,conf=0.15,classes=VEH,verbose=False)[0]
        rb=[[int(v) for v in b] for b in R.boxes.xyxy.tolist()]
        pb=[[int(v) for v in b] for b in P.boxes.xyxy.tolist()]
        miss=[]
        for r in rb:
            w=r[2]-r[0]
            bk=next(b for b in BUCKETS if b[0]<=w<b[1])
            tot[bk]+=1
            if any(iou(r,p)>=0.45 for p in pb): hit[bk]+=1
            else: miss.append(r)
        if dump_prefix and dumped<3 and len(miss)>=2:
            im=fr.copy()
            for p in pb: cv2.rectangle(im,(p[0],p[1]),(p[2],p[3]),(0,255,0),2)
            for m in miss:
                cv2.rectangle(im,(m[0],m[1]),(m[2],m[3]),(0,0,255),2)
                cv2.putText(im,f"MISS {m[2]-m[0]}px",(m[0],m[1]-4),0,0.5,(0,0,255),2)
            cv2.putText(im,"green=found by yolo11n   red=only reference found it",
                        (10,28),0,0.8,(255,255,255),2)
            cv2.imwrite(f"{dump_prefix}_{dumped}.jpg",im); dumped+=1
        if k%25==0: print(f"  {label} {k}/{len(idxs)}",flush=True)
    cap.release()
    print(f"\n=== {label} ===")
    print(f"{'width px':>12} {'ref dets':>9} {'found':>7} {'recall':>8}")
    out={}
    for b in BUCKETS:
        if tot[b]==0: continue
        r=hit[b]/tot[b]
        nm=f"{b[0]}-{b[1] if b[1]<10**6 else '+'}"
        print(f"{nm:>12} {tot[b]:>9} {hit[b]:>7} {r*100:>7.1f}%")
        out[nm]={'ref':tot[b],'found':hit[b],'recall':round(r,4)}
    T=sum(tot.values()); H=sum(hit.values())
    print(f"{'ALL':>12} {T:>9} {H:>7} {H/max(1,T)*100:>7.1f}%")
    out['ALL']={'ref':T,'found':H,'recall':round(H/max(1,T),4)}
    return out

if __name__=='__main__':
    cams=[("Beach Blvd (500)","/Users/Ak47/Desktop/traffic-vision/data/clips/_500__Beach_Blvd_NW_Corner.ts"),
          ("Harbor Blvd (506)","/Users/Ak47/Desktop/traffic-vision/data/clips/_506__Harbor_Blvd_NW_Corner.ts"),
          ("Brea Blvd (510)","/Users/Ak47/Desktop/traffic-vision/data/clips/_510__Brea_Blvd_NW_Corner.ts")]
    res={}
    for name,path in cams:
        res[name]=run(path,name,90,dump_prefix=f"/Users/Ak47/Desktop/traffic-vision/data/recall/{name.split()[0]}")
    json.dump(res,open('/Users/Ak47/Desktop/traffic-vision/data/recall/recall.json','w'),indent=1)
    print("\n\n===== CROSS-CAMERA COMPARISON (recall by size bucket) =====")
    keys=[k for k in ['0-40','40-60','60-80','80-120','120-200','200-+','ALL']]
    print(f"{'bucket':>10} " + " ".join(f"{n.split()[0]:>12}" for n in res))
    for k in keys:
        row=[res[n].get(k) for n in res]
        if not any(row): continue
        print(f"{k:>10} " + " ".join(f"{(v['recall']*100):>11.1f}%" if v else f"{'-':>12}" for v in row))
