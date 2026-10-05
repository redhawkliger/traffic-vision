"""Stage 1: throw out placeholders, then rank 320x260 thumbnails for
'surface intersection' rather than 'freeway corridor'.

At this resolution crosswalk bars are unresolvable, so the signal is structural:
a freeway view has ONE dominant road axis; an intersection has two or more
crossing axes over a large paved area. Validated against the three SR-90
intersection cameras we already know (Brea 510, Harbor 506, Beach 500).
"""
import cv2, numpy as np, json, os, math, collections
from concurrent.futures import ThreadPoolExecutor

def placeholder(im):
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    if g.mean()>195 and cv2.Canny(g,60,160).mean()<6: return True
    if float(g.std())<18: return True
    return False

def feats(path):
    im=cv2.imread(path)
    if im is None: return None
    H,W=im.shape[:2]
    if placeholder(im): return {'placeholder':True,'score':-1.0}
    r=im[int(H*0.25):,:]                       # drop sky/horizon
    g=cv2.cvtColor(r,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(r,cv2.COLOR_BGR2HSV)
    pave=float(((hsv[...,1]<60)&(g>55)&(g<190)).mean())     # grey, mid-tone = asphalt
    e=cv2.Canny(cv2.GaussianBlur(g,(3,3),0),50,150)
    lines=cv2.HoughLinesP(e,1,np.pi/180,threshold=28,minLineLength=max(18,W//12),maxLineGap=6)
    hist=np.zeros(18)
    if lines is not None:
        for x1,y1,x2,y2 in lines[:,0]:
            a=math.degrees(math.atan2(y2-y1,x2-x1))%180
            L=math.hypot(x2-x1,y2-y1)
            hist[int(a//10)%18]+=L
    tot=hist.sum()
    if tot<1: return {'placeholder':False,'score':0.0,'pave':pave,'axes':0}
    h=hist/tot
    # count orientation peaks that are separated - a corridor has one, a box has 2+
    idx=np.argsort(-h); peaks=[]
    for i in idx:
        if h[i]<0.10: break
        if all(min(abs(i-j),18-abs(i-j))>=3 for j in peaks): peaks.append(int(i))
    axes=len(peaks)
    ent=float(-(h[h>0]*np.log(h[h>0])).sum()/math.log(18))   # spread of orientations
    s=min(axes,3)/3.0*0.45 + min(pave/0.42,1.0)*0.30 + min(ent/0.80,1.0)*0.25
    return {'placeholder':False,'score':round(float(s),4),'pave':round(pave,3),
            'axes':axes,'ent':round(ent,3)}

def main():
    cams=[c for c in json.load(open('data/stills/index.json')) if c.get('have_still')]
    paths=[f"data/stills/{c['uid']}.jpg" for c in cams]
    with ThreadPoolExecutor(6) as p: res=list(p.map(feats,paths))
    rows=[]
    for c,f in zip(cams,res):
        if not f: continue
        rows.append({**{k:c.get(k) for k in ('uid','district','route','name','direction','county','lat','lon','stream')},**f})
    json.dump(rows,open('data/stills/stage1.json','w'),indent=1)
    live=[r for r in rows if not r['placeholder']]
    print(f"total {len(rows)}  placeholders {len(rows)-len(live)}  usable {len(live)}")
    live.sort(key=lambda x:-x['score'])
    # VALIDATION: where do the three known intersection cameras land?
    print("\nVALIDATION - known SR-90 intersection cams:")
    for i,r in enumerate(live):
        n=str(r['name']).lower()
        if r['district']==12 and 'sr-90' in str(r['route']).lower() and any(k in n for k in ('brea','harbor','beach')):
            print(f"  rank {i+1:5d}/{len(live)}  score {r['score']:.3f} axes={r['axes']} pave={r['pave']:.2f}  {r['name'][:52]}")
    print("\nTOP 25 by stage-1 score:")
    for r in live[:25]:
        print(f"  {r['score']:.3f} ax={r['axes']} pave={r['pave']:.2f} D{r['district']:<3}"
              f"{str(r['route'])[:7]:<8}{str(r['name'])[:50]}")

if __name__=='__main__': main()
