import json, math, cv2, collections
from concurrent.futures import ThreadPoolExecutor

cams=[c for c in json.load(open('data/stills/index.json')) if c.get('have_still')]
sig=json.load(open('data/stills/signals.json'))
print(f"cameras {len(cams)}  signals {len(sig)}")

# drop placeholder cards (white-on-blue "Temporarily Unavailable")
def white(c):
    im=cv2.imread(f"data/stills/{c['uid']}.jpg")
    if im is None: return 1.0
    return float((cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)>225).mean())
with ThreadPoolExecutor(8) as p: wf=list(p.map(white,cams))
for c,w in zip(cams,wf): c['white']=round(w,3)
real=[c for c in cams if c['white']<=0.55]
print(f"placeholders dropped: {len(cams)-len(real)}   real images: {len(real)}")

# grid index on signals (0.01 deg ~ 1.1 km)
G=collections.defaultdict(list)
for la,lo in sig: G[(round(float(la),2),round(float(lo),2))].append((float(la),float(lo)))
def near(lat,lon):
    best=1e9
    for dla in (-0.01,0,0.01):
        for dlo in (-0.01,0,0.01):
            for sla,slo in G.get((round(lat+dla,2),round(lon+dlo,2)),()):
                dx=(slo-lon)*111320*math.cos(math.radians(lat)); dy=(sla-lat)*110540
                best=min(best,math.hypot(dx,dy))
    return best
for c in real:
    c['sig_m']=round(near(float(c['lat']),float(c['lon'])),1)

for R in (60,90,120,150):
    print(f"  within {R:3d} m of a signal: {sum(1 for c in real if c['sig_m']<=R)}")

print("\nVALIDATION - the three cams we KNOW are intersections:")
for c in real:
    n=str(c['name']).lower()
    if c['district']==12 and any(k in n for k in ('brea blvd','harbor blvd','beach blvd')) and 'sr-90' in str(c['route']).lower():
        print(f"   {c['sig_m']:7.1f} m   {c['name'][:55]}")

cand=[c for c in real if c['sig_m']<=90]
cand.sort(key=lambda c:c['sig_m'])
json.dump(cand,open('data/stills/candidates.json','w'),indent=1)
print(f"\ncandidates written: {len(cand)}")
print("by district:",dict(sorted(collections.Counter(c['district'] for c in cand).items())))
print("with a stream URL:",sum(1 for c in cand if c.get('stream')))
