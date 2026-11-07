import json, os, urllib.request, collections, cv2
from concurrent.futures import ThreadPoolExecutor
UA={"User-Agent":"Mozilla/5.0"}
d=json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://webcams.nyctmc.org/api/cameras/",headers=UA),timeout=40).read())
cams=[c for c in d if str(c.get('isOnline')).lower()=='true']
print(f"{len(d)} cameras, {len(cams)} online",flush=True)
def grab(c):
    p=f"data/nyc/{c['id']}.jpg"
    if os.path.exists(p) and os.path.getsize(p)>4000: return 'cached'
    try:
        r=urllib.request.Request(c['imageUrl'],headers=UA)
        with urllib.request.urlopen(r,timeout=25) as fh: b=fh.read()
        if len(b)<4000: return 'tiny'
        open(p,'wb').write(b); return 'ok'
    except Exception: return 'fail'
with ThreadPoolExecutor(10) as p: res=list(p.map(grab,cams))
print(collections.Counter(res))
got=[c for c in cams if os.path.exists(f"data/nyc/{c['id']}.jpg")]
dims=collections.Counter()
for c in got:
    im=cv2.imread(f"data/nyc/{c['id']}.jpg")
    if im is not None: dims[(im.shape[1],im.shape[0])]+=1
print("resolutions:",dims.most_common(6))
json.dump(got,open('data/nyc/index.json','w'),indent=1)
print("saved",len(got))
