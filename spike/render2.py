"""THROWAWAY SPIKE — two videos:
  handcount.mp4 : clean frames + the count line ONLY (unbiased human count)
  annotated.mp4 : boxes, ids, classes, running tally (see where model fails)"""
import cv2, json, collections
BASE='/Users/Ak47/Desktop/spike_cv'
D=json.load(open(f'{BASE}/tracks.json'))
recs,W,H,FPS,NF=D['records'],D['w'],D['h'],D['fps'],D['n_frames']
cfg=json.load(open(f'{BASE}/lines.json')); events=json.load(open(f'{BASE}/events.json'))
L=cfg['lines'][0]; A,B=tuple(L['a']),tuple(L['b'])
ev=events[L['label']]

byframe=collections.defaultdict(list)
for r in recs: byframe[r['f']].append(r)
tally=[0]*(NF+1)
for e in ev:
    if e['f']<=NF: tally[e['f']]+=1
run=0
for i in range(NF+1):
    run+=tally[i]; tally[i]=run
counted={e['id']:e['f'] for e in ev}
COL={'car':(0,255,0),'truck':(0,140,255),'bus':(255,0,255),'motorcycle':(255,255,0)}

def writer(path):
    for cc in ('avc1','mp4v'):
        w=cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*cc),FPS,(W,H))
        if w.isOpened(): print(f"  {path} codec={cc}"); return w
    raise RuntimeError('no codec')

hc=writer(f'{BASE}/handcount.mp4'); an=writer(f'{BASE}/annotated.mp4')
cap=cv2.VideoCapture(f'{BASE}/clip_raw.ts')
for i in range(NF):
    ok,fr=cap.read()
    if not ok: break
    clean=fr.copy()
    cv2.line(clean,A,B,(0,0,255),3)
    cv2.putText(clean,"COUNT VEHICLES CROSSING THIS LINE (moving away)",(30,470),0,0.75,(0,0,255),2)
    cv2.putText(clean,f"t={i/FPS:5.1f}s",(8,30),0,0.8,(255,255,255),2)
    hc.write(clean)

    cv2.line(fr,A,B,(0,0,255),3)
    for r in byframe.get(i,[]):
        c=COL.get(r['cls'],(200,200,200))
        p1,p2=(int(r['x1']),int(r['y1'])),(int(r['x2']),int(r['y2']))
        flash = r['id'] in counted and 0 <= i-counted[r['id']] < 12
        cv2.rectangle(fr,p1,p2,(255,255,255) if flash else c, 3 if flash else 1)
        cv2.putText(fr,f"{r['id']} {r['cls'][:3]}",(p1[0],p1[1]-4),0,0.42,c,1)
    cv2.rectangle(fr,(0,0),(430,78),(0,0,0),-1)
    cv2.putText(fr,f"t={i/FPS:5.1f}s",(8,28),0,0.7,(255,255,255),2)
    cv2.putText(fr,f"COUNT: {tally[i]}",(8,66),0,0.95,(0,255,255),2)
    an.write(fr)
cap.release(); hc.release(); an.release()
print(f"done. final tally={tally[NF-1]}")
