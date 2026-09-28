"""Record N seconds from a Caltrans HLS camera to a .ts file.

The feed is LIVE ONLY - roughly a 30 s rolling window (3 x 10 s segments) with
no archive. Recording therefore happens in real wall-clock time: a 10 minute
clip takes 10 minutes. There is no way to fetch the past.

Usage:
    python record.py <playlist_url> <out.ts> [seconds]
    python record.py --many cams.json outdir/ [seconds]

`--many` records several cameras concurrently, which is how you capture a
corridor simultaneously. Note that each camera's live edge differs, so clips
are NOT frame-synchronised - do not assume a common t=0.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def record(playlist_url: str, out_path: str, seconds: float = 60.0,
           verbose: bool = True) -> float:
    """Append HLS segments to out_path until `seconds` of media is collected.

    Returns the media duration actually written (may slightly exceed `seconds`
    because segments are atomic - typically 10 s each).
    """
    base = playlist_url.rsplit("/", 1)[0]
    master = _get(playlist_url).decode("utf8", "ignore")
    try:
        chunk_name = next(l.strip() for l in master.splitlines()
                          if l.strip() and not l.startswith("#"))
    except StopIteration:
        raise RuntimeError(f"no variant in master playlist: {playlist_url}")
    chunk_url = f"{base}/{chunk_name}"

    seen: set[str] = set()
    total = 0.0
    started = time.time()
    deadline = seconds * 3 + 60  # generous: guards against a stalled feed

    with open(out_path, "wb") as out:
        while total < seconds:
            if time.time() - started > deadline:
                print(f"!! wall-clock timeout on {out_path}", file=sys.stderr)
                break
            try:
                chunklist = _get(chunk_url, 15).decode("utf8", "ignore")
            except Exception as exc:  # noqa: BLE001
                print(f"   chunklist error ({type(exc).__name__}), retrying",
                      file=sys.stderr)
                time.sleep(2)
                continue

            lines = chunklist.splitlines()
            fresh = 0
            for i, line in enumerate(lines):
                if not line.startswith("#EXTINF"):
                    continue
                seg = lines[i + 1].strip()
                if seg in seen:
                    continue
                try:
                    dur = float(line.split(":")[1].rstrip(","))
                    data = _get(f"{base}/{seg}", 30)
                except Exception as exc:  # noqa: BLE001
                    print(f"   segment failed ({type(exc).__name__})", file=sys.stderr)
                    continue
                out.write(data)
                out.flush()
                seen.add(seg)
                total += dur
                fresh += 1
                if verbose:
                    print(f"   +{dur:.1f}s  total={total:.1f}s  ({len(data)/1e6:.2f} MB)")
                if total >= seconds:
                    break
            if fresh == 0:
                time.sleep(3)  # nothing new published yet

    print(f"DONE {total:.1f}s -> {out_path}")
    return total


def record_many(targets: dict[str, str], outdir: str, seconds: float) -> None:
    """Record several cameras at once. targets = {name: playlist_url}."""
    def worker(name: str, url: str) -> None:
        safe = "".join(c if c.isalnum() else "_" for c in name)[:60]
        try:
            record(url, f"{outdir.rstrip('/')}/{safe}.ts", seconds, verbose=False)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {name}: {exc}", file=sys.stderr)

    threads = [threading.Thread(target=worker, args=(n, u)) for n, u in targets.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("ALL DONE")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url_or_json")
    ap.add_argument("out")
    ap.add_argument("seconds", nargs="?", type=float, default=60.0)
    ap.add_argument("--many", action="store_true",
                    help="first arg is a JSON file of {name: playlist_url} "
                         "or a cameras.py --json output list")
    args = ap.parse_args()

    if args.many:
        raw = json.load(open(args.url_or_json))
        if isinstance(raw, list):  # cameras.py --json output
            raw = {c["name"]: c["stream"] for c in raw if c.get("stream")}
        record_many(raw, args.out, args.seconds)
    else:
        record(args.url_or_json, args.out, args.seconds)


if __name__ == "__main__":
    main()
