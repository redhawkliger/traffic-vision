"""Grab one still from every Caltrans CCTV camera in the state.

Purpose: pick a STUDY INTERSECTION on geometry, not convenience. The owner's
criterion: the whole intersection box - the area bounded by the crosswalks -
must be inside the frame, with the frame edge OUTSIDE the crosswalks.
"""
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, 'tools')
from cameras import fetch_district, DISTRICTS, DISTRICT_NAMES

UA = {"User-Agent": "Mozilla/5.0"}
OUT = 'data/stills'

cams = []
for d in DISTRICTS:
    got = fetch_district(d)
    cams += [c for c in got if c.get('still')]
    print(f"  D{d:<3}{DISTRICT_NAMES[d]:<26} {len(got):>5} cams, {sum(1 for c in got if c.get('still')):>5} with a still", flush=True)
print(f"\ntotal with stills: {len(cams)}")

for i, c in enumerate(cams):
    c['uid'] = f"d{c['district']:02d}_{i:05d}"

def grab(c):
    path = os.path.join(OUT, c['uid'] + '.jpg')
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        return True
    try:
        req = urllib.request.Request(c['still'], headers=UA)
        with urllib.request.urlopen(req, timeout=20) as fh:
            b = fh.read()
        if len(b) < 5000:
            return False
        open(path, 'wb').write(b)
        return True
    except Exception:
        return False

with ThreadPoolExecutor(24) as pool:
    ok = list(pool.map(grab, cams))
print(f"downloaded {sum(ok)}/{len(cams)}")
for c, good in zip(cams, ok):
    c['have_still'] = bool(good)
json.dump(cams, open('data/stills/index.json', 'w'), indent=1)
print("wrote data/stills/index.json")
