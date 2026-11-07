"""Which cameras actually look at a signalised surface intersection?

Pixel heuristics failed (the three known intersection cams ranked 1142/2226/2449
of 3589). Use authoritative geometry instead: OpenStreetMap traffic_signals
nodes. A camera within ~90 m of a signal is a candidate; a freeway mainline cam
is not near one.
"""
import json, urllib.request, urllib.parse, time, math, sys

EP = "https://overpass-api.de/api/interpreter"
def overpass(q, tries=3):
    for a in range(tries):
        try:
            data = urllib.parse.urlencode({"data": q}).encode()
            req = urllib.request.Request(EP, data=data, headers={"User-Agent": "traffic-vision-research/1.0"})
            with urllib.request.urlopen(req, timeout=600) as fh:
                return json.loads(fh.read())
        except Exception as e:
            print(f"  attempt {a+1} failed: {type(e).__name__} {e}", flush=True)
            time.sleep(20 * (a + 1))
    return None

cams = [c for c in json.load(open('data/stills/index.json')) if c.get('have_still')]
lats = [float(c['lat']) for c in cams if c.get('lat')]
lons = [float(c['lon']) for c in cams if c.get('lon')]
print(f"camera bbox: lat {min(lats):.2f}..{max(lats):.2f}  lon {min(lons):.2f}..{max(lons):.2f}", flush=True)

q = (f"[out:json][timeout:600];node[\"highway\"=\"traffic_signals\"]"
     f"({min(lats)-0.05},{min(lons)-0.05},{max(lats)+0.05},{max(lons)+0.05});out skel;")
print("querying Overpass for every traffic signal in the camera bbox ...", flush=True)
t0 = time.time()
res = overpass(q)
if not res:
    print("FAILED"); sys.exit(1)
sig = [(e['lat'], e['lon']) for e in res.get('elements', []) if e.get('type') == 'node']
print(f"got {len(sig)} traffic signals in {time.time()-t0:.0f}s", flush=True)
json.dump(sig, open('data/stills/signals.json', 'w'))
print("wrote data/stills/signals.json")
