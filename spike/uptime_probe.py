"""THROWAWAY — poll a fixed camera panel and log stream availability over time.
Answers: 'how reliable are Caltrans feeds, really?'"""
import json, time, urllib.request, csv, os, random
from concurrent.futures import ThreadPoolExecutor
UA={'User-Agent':'Mozilla/5.0'}
PANEL='/Users/Ak47/Desktop/traffic-vision/data/uptime_panel.json'
CSV='/Users/Ak47/Desktop/traffic-vision/data/uptime_log.csv'

def get(u,t=25):
    r=urllib.request.Request(u,headers=UA)
    with urllib.request.urlopen(r,timeout=t) as f: return f.read()

def build_panel():
    cams=[]
    for d in [3,4,7,8,11,12]:
        try: data=json.loads(get(f"https://cwwp2.dot.ca.gov/data/d{d}/cctv/cctvStatusD{d:02d}.json",40))
        except Exception: continue
        rows=[c['cctv'] for c in data['data'] if c['cctv']['imageData'].get('streamingVideoURL')]
        random.seed(100+d)
        for c in random.sample(rows, min(10,len(rows))):
            cams.append({'d':d,'route':c['location']['route'],
                         'name':c['location']['locationName'][:40],
                         'url':c['imageData']['streamingVideoURL']})
    json.dump(cams,open(PANEL,'w'),indent=1); return cams

def alive(c):
    try:
        b=get(c['url'],10)
        return 1 if b else 0
    except Exception: return 0

panel = json.load(open(PANEL)) if os.path.exists(PANEL) else build_panel()
new = not os.path.exists(CSV)
with open(CSV,'a',newline='') as f:
    w=csv.writer(f)
    if new: w.writerow(['ts','n_up','n_total']+[f"D{c['d']}:{c['route']}:{c['name']}" for c in panel])
    for _ in range(90):                      # 90 polls x 2 min = 3 hours
        with ThreadPoolExecutor(15) as ex: st=list(ex.map(alive,panel))
        w.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), sum(st), len(st)]+st)
        f.flush()
        print(f"{time.strftime('%H:%M:%S')}  up={sum(st)}/{len(st)}", flush=True)
        time.sleep(120)
print("UPTIME PROBE DONE")
