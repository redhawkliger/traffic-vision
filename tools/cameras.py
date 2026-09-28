"""Caltrans CCTV camera discovery and liveness checking.

The status JSON URL pattern is easy to get wrong: the directory is UNPADDED
and the filename is ZERO-PADDED.

    https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD03.json      correct
    https://cwwp2.dot.ca.gov/data/d03/cctv/cctvStatusD03.json     500
    https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD3.json       500

Usage:
    python cameras.py inventory --districts 7 12
    python cameras.py live --district 12 --route SR-90
    python cameras.py live --district 7 --route I-110 --json out.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0"}
DISTRICTS = range(1, 13)
DISTRICT_NAMES = {
    1: "Eureka/N Coast", 2: "Redding", 3: "Sacramento", 4: "Bay Area",
    5: "SLO/Santa Barbara", 6: "Fresno/Bakersfield", 7: "Los Angeles/Ventura",
    8: "San Bernardino/Riverside", 9: "Bishop", 10: "Stockton/Modesto",
    11: "San Diego", 12: "Orange County",
}


def status_url(district: int) -> str:
    """Directory unpadded, filename zero-padded. Getting this wrong returns 500."""
    return f"https://cwwp2.dot.ca.gov/data/d{district}/cctv/cctvStatusD{district:02d}.json"


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return fh.read()


def fetch_district(district: int) -> list[dict]:
    """Return flattened camera records for one district. [] on failure."""
    try:
        data = json.loads(_get(status_url(district)))
    except Exception as exc:  # noqa: BLE001 - network failures are expected
        print(f"  D{district}: fetch failed ({type(exc).__name__})", file=sys.stderr)
        return []

    out = []
    for entry in data.get("data", []):
        cam = entry["cctv"]
        loc = cam["location"]
        img = cam.get("imageData", {})
        try:
            postmile = float(loc.get("postmile", ""))
        except (TypeError, ValueError):
            postmile = None
        out.append({
            "district": district,
            "route": loc.get("route", ""),
            "name": loc.get("locationName", ""),
            "direction": loc.get("direction", ""),
            "county": loc.get("county", ""),
            "postmile": postmile,
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
            "stream": img.get("streamingVideoURL") or None,
            "still": (img.get("static") or {}).get("currentImageURL") or None,
            "record_date": cam.get("recordTimestamp", {}).get("recordDate"),
        })
    return out


def probe_stream(url: str, timeout: int = 12) -> str | None:
    """Fetch the HLS master playlist. Returns 'WxH', 'live' or None if dead.

    A working still image does NOT imply a working stream - always probe this.
    """
    if not url:
        return None
    try:
        body = _get(url, timeout).decode("utf8", "ignore")
    except Exception:  # noqa: BLE001
        return None
    for line in body.splitlines():
        if "RESOLUTION=" in line:
            return line.split("RESOLUTION=")[1].split(",")[0].strip()
    return "live" if body.strip() else None


def check_liveness(cams: list[dict], workers: int = 12) -> list[dict]:
    """Annotate each camera with a 'resolution' key (None == dead)."""
    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(lambda c: probe_stream(c["stream"]), cams))
    for cam, res in zip(cams, results):
        cam["resolution"] = res
    return cams


def cmd_inventory(args: argparse.Namespace) -> None:
    districts = args.districts or list(DISTRICTS)
    total = collections.Counter()
    print(f"{'D':>3} {'district':<26} {'cams':>6} {'w/stream':>9}")
    print("-" * 50)
    for d in districts:
        cams = fetch_district(d)
        streams = sum(1 for c in cams if c["stream"])
        total["cams"] += len(cams)
        total["streams"] += streams
        print(f"{d:>3} {DISTRICT_NAMES.get(d, '?'):<26} {len(cams):>6} {streams:>9}")
    print("-" * 50)
    print(f"{'':>3} {'TOTAL':<26} {total['cams']:>6} {total['streams']:>9}")


def cmd_live(args: argparse.Namespace) -> None:
    cams = fetch_district(args.district)
    if args.route:
        cams = [c for c in cams if c["route"] == args.route]
    cams = [c for c in cams if c["stream"]]
    cams.sort(key=lambda c: (c["postmile"] is None, c["postmile"]))

    print(f"probing {len(cams)} streams ...", file=sys.stderr)
    check_liveness(cams)
    live = [c for c in cams if c["resolution"]]

    print(f"\n{'postmile':>9} {'dir':<7} {'resolution':<12} name")
    for c in live:
        pm = f"{c['postmile']:.2f}" if c["postmile"] is not None else "-"
        print(f"{pm:>9} {c['direction'][:6]:<7} {c['resolution']:<12} {c['name'][:52]}")
    print(f"\nlive: {len(live)}/{len(cams)}", file=sys.stderr)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(live, fh, indent=1)
        print(f"wrote {args.json}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    inv = sub.add_parser("inventory", help="camera counts per district")
    inv.add_argument("--districts", type=int, nargs="*")
    inv.set_defaults(func=cmd_inventory)

    lv = sub.add_parser("live", help="probe streams in one district")
    lv.add_argument("--district", type=int, required=True)
    lv.add_argument("--route", help="e.g. SR-90, I-110")
    lv.add_argument("--json", help="write live cameras to this file")
    lv.set_defaults(func=cmd_live)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
