"""THROWAWAY SPIKE — record N seconds of a Caltrans HLS camera to a .ts file."""
import sys, time, json, urllib.request, urllib.parse
UA = {'User-Agent': 'Mozilla/5.0'}

def get(url, timeout=20):
    r = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(r, timeout=timeout) as f:
        return f.read()

def record(playlist_url, out_path, seconds=60):
    base = playlist_url.rsplit('/', 1)[0]
    master = get(playlist_url).decode('utf8', 'ignore')
    chunk_name = next(l.strip() for l in master.splitlines()
                      if l.strip() and not l.startswith('#'))
    chunk_url = f"{base}/{chunk_name}"
    print(f"chunklist: {chunk_url}")

    seen, total_dur, t0 = set(), 0.0, time.time()
    with open(out_path, 'wb') as out:
        while total_dur < seconds:
            if time.time() - t0 > seconds * 3 + 60:
                print("!! wall-clock timeout"); break
            try:
                cl = get(chunk_url, 15).decode('utf8', 'ignore')
            except Exception as e:
                print("chunklist error", e); time.sleep(2); continue
            lines = cl.splitlines()
            new = 0
            for i, line in enumerate(lines):
                if line.startswith('#EXTINF'):
                    seg = lines[i + 1].strip()
                    if seg in seen:
                        continue
                    dur = float(line.split(':')[1].rstrip(','))
                    try:
                        data = get(f"{base}/{seg}", 30)
                    except Exception as e:
                        print("seg fail", seg, e); continue
                    out.write(data); out.flush()
                    seen.add(seg); total_dur += dur; new += 1
                    print(f"  +{dur:.1f}s  total={total_dur:.1f}s  ({len(data)/1e6:.2f} MB)  {seg}")
                    if total_dur >= seconds:
                        break
            if new == 0:
                time.sleep(3)
    print(f"DONE: {total_dur:.1f}s -> {out_path}")
    return total_dur

if __name__ == '__main__':
    record(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 60)
