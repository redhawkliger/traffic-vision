"""Measure what track stitching does to the vehicle count.

Reports both failure directions, because only reporting one is how you fool
yourself:
  UNDER-merging  -> count stays inflated (the original problem)
  OVER-merging   -> distinct vehicles collapse into one, count now too LOW

Over-merge warnings flag chains that are implausible on their face: too many
fragments, or spanning more time than a vehicle plausibly spends in frame.

Usage:
    python eval_stitch.py tracks.json
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stitch import fragments_from_tracks, link, vehicles  # noqa: E402

# A vehicle crossing an intersection takes ~5-15 s. Anything far beyond that
# in a single chain is suspicious rather than impressive.
PLAUSIBLE_SPAN_S = 45.0
PLAUSIBLE_FRAGS = 8


def reacquisition_rate(frags, radius_lengths: float = 2.0,
                       window_s: float = 3.0) -> float:
    """Independent fragmentation estimate, scale-free.

    Counts deaths followed by a birth nearby (in vehicle-lengths) and soon.
    Run before AND after stitching: it should fall sharply if stitching worked.
    """
    linked = 0
    for f in frags:
        for g in frags:
            if g is f:
                continue
            dt = g.t0 - f.t1
            if not (0 < dt <= window_s):
                continue
            scale = max(1e-6, (f.size1 + g.size0) / 2)
            if math.hypot(g.x0 - f.x1, g.y0 - f.y1) / scale <= radius_lengths:
                linked += 1
                break
    return linked / max(1, len(frags))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tracks")
    args = ap.parse_args()

    data = json.load(open(args.tracks))
    fps = data.get("meta_fps") or 25.0
    tracks = collections.defaultdict(list)
    for r in data["records"]:
        tracks[r["id"]].append(r)

    frags = fragments_from_tracks(tracks, fps)
    links = link(frags)
    groups = vehicles(frags, links)
    by_tid = {f.tid: f for f in frags}

    print(f"source      : {os.path.basename(data['source'])}")
    print(f"clip        : {data['n_frames']} frames @ {fps:.1f} fps "
          f"= {data['n_frames']/fps:.0f}s")
    print(f"raw tracks  : {len(tracks)}  (fragments usable: {len(frags)})")
    print(f"links made  : {len(links)}")
    print(f"VEHICLES    : {len(groups)}")
    red = 1 - len(groups) / max(1, len(frags))
    print(f"\ncount reduction: {len(frags)} -> {len(groups)} "
          f"({red*100:.0f}% fewer)   inflation was {len(frags)/max(1,len(groups)):.2f}x")

    before = reacquisition_rate(frags)
    merged = []
    for g in groups:
        fs = [by_tid[t] for t in g]
        fs.sort(key=lambda f: f.t0)
        merged.append(fs)
    # after: treat each vehicle as one fragment spanning its chain
    class M:  # noqa: D401 - tiny shim matching the Frag interface we need
        pass
    after_frags = []
    for fs in merged:
        m = M()
        m.t0, m.t1 = fs[0].t0, fs[-1].t1
        m.x0, m.y0 = fs[0].x0, fs[0].y0
        m.x1, m.y1 = fs[-1].x1, fs[-1].y1
        m.size0, m.size1 = fs[0].size0, fs[-1].size1
        after_frags.append(m)
    after = reacquisition_rate(after_frags)
    print(f"\nre-acquisition signature (independent check)")
    print(f"   before stitching: {before*100:.0f}% of fragments look like continuations")
    print(f"   after  stitching: {after*100:.0f}%")

    sizes = collections.Counter(len(g) for g in groups)
    print("\nfragments per vehicle")
    for k in sorted(sizes):
        print(f"   {k:>2} fragment(s): {sizes[k]:>4} vehicles")

    print("\nOVER-MERGE CHECK (chains that look implausible)")
    bad = []
    for fs in merged:
        span = fs[-1].t1 - fs[0].t0
        if len(fs) > PLAUSIBLE_FRAGS or span > PLAUSIBLE_SPAN_S:
            bad.append((len(fs), round(span, 1), [f.tid for f in fs][:10]))
    if not bad:
        print("   none - no chain exceeds "
              f"{PLAUSIBLE_FRAGS} fragments or {PLAUSIBLE_SPAN_S:.0f}s")
    else:
        bad.sort(reverse=True)
        print(f"   {len(bad)} suspicious chain(s) of {len(groups)}:")
        for n, span, tids in bad[:10]:
            print(f"      {n} fragments over {span}s  ids={tids}")

    print("\nLARGEST CHAINS (expect the 9-id Jeep to appear here if stitching works)")
    for fs in sorted(merged, key=len, reverse=True)[:5]:
        span = fs[-1].t1 - fs[0].t0
        print(f"   {len(fs):>2} fragments  {span:>5.1f}s  "
              f"size {fs[0].size0:.0f}->{fs[-1].size1:.0f}px  "
              f"ids={[f.tid for f in fs][:10]}")


if __name__ == "__main__":
    main()
