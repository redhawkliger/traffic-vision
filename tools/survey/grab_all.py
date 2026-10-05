import json, os, subprocess, sys, collections
from concurrent.futures import ThreadPoolExecutor
cand=[c for c in json.load(open('data/stills/candidates.json')) if c.get('stream')]
print(f"pulling full-res frames for {len(cand)} candidate cameras",flush=True)
PY_=sys.executable
def grab(c):
    out=f"data/frames/{c['uid']}.jpg"
    if os.path.exists(out) and os.path.getsize(out)>8000: return 'cached'
    try:
        r=subprocess.run([PY_,'scratch_diag/grab_one.py',c['stream'],out],
                         capture_output=True,timeout=30,text=True)
        return 'ok' if r.returncode==0 else f'rc{r.returncode}'
    except subprocess.TimeoutExpired: return 'timeout'
    except Exception: return 'err'
res=[]
with ThreadPoolExecutor(8) as p:
    for i,r in enumerate(p.map(grab,cand)):
        res.append(r)
        if (i+1)%50==0: print(f"  {i+1}/{len(cand)}  {collections.Counter(res)}",flush=True)
print(collections.Counter(res))
got=[c for c in cand if os.path.exists(f"data/frames/{c['uid']}.jpg")]
print(f"frames on disk: {len(got)}")
json.dump(got,open('data/frames/index.json','w'),indent=1)
