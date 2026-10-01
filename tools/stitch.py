"""Stitch fragmented tracks back into vehicles - in physical units, no calibration.

THE PROBLEM
    Trackers lose vehicles and re-acquire them under a new id. Measured at
    SR-90 Harbor Blvd: 421 raw tracks, 53% of which are continuations of
    another track, inflating the vehicle count ~2.14x. One tan Jeep produced
    nine separate track ids in 13.7 seconds.

THE APPROACH
    Thresholds in PIXELS do not transfer between cameras - that is per-site
    tuning, not a product. But a pixel->feet homography would mean a
    calibration step before any result.

    Resolution: the detected vehicle's own bounding box IS a known physical
    length (a passenger car is ~15 ft). So express motion in VEHICLE LENGTHS
    per second. That is a physical statement, needs no calibration, and
    self-corrects for perspective - a distant vehicle has a small box, so its
    permitted jump shrinks in proportion.

    Every threshold below is a real-world quantity, identical on every camera.
"""
from __future__ import annotations

import collections
import math
from dataclasses import dataclass

# --- Physical constants -------------------------------------------------------
CAR_LENGTH_FT = 15.0        # typical passenger car; the implicit ruler

# --- Physical thresholds (same on every camera) -------------------------------
MAX_SPEED_LEN_PER_S = 8.0   # 8 car-lengths/s = 120 ft/s = 82 mph. Generous.

# How long to hold a lost vehicle. A red phase is 30-60 s, so 60 looks like the
# physically obvious choice - but it over-merges. Measured on SR-90 Harbor Blvd,
# sweeping this value (chains longer than 45 s are implausible for one vehicle):
#
#     gap  vehicles  links  implausible chains
#       2       173     26         9
#       5       161     38         9
#      20       153     46         9
#      40       150     49        10
#      60       144     55        19   <- cliff
#
# The jump at 60 s is successive vehicles queueing at the same stop bar being
# merged into one. 40 s is the knee: it still spans most red phases.
# THIS IS THE ONE THRESHOLD TRADING TWO ERROR TYPES WITH NO GROUND TRUTH TO
# ARBITRATE - revisit it against a human count.
MAX_GAP_S = 40.0
MAX_STOPPED_DRIFT_LEN = 1.5 # a vehicle "waiting" may drift <=1.5 car-lengths
MAX_SIZE_RATIO = 2.0        # a car does not become a truck mid-crossing
MAX_HEADING_DEG = 75.0      # continuation must roughly follow the old heading


@dataclass
class Frag:
    """One track fragment, reduced to what stitching needs."""
    tid: int
    t0: float      # seconds
    t1: float
    x0: float      # centroid at birth
    y0: float
    x1: float      # centroid at death
    y1: float
    size0: float   # max bbox dimension at birth (px) ~ one vehicle length
    size1: float
    vx: float      # velocity at death, px/s
    vy: float
    n: int         # observations


def fragments_from_tracks(tracks: dict[int, list[dict]], fps: float,
                          tail: int = 3) -> list[Frag]:
    """Reduce per-frame records to fragments.

    Each record needs: f (frame), cx, cy, and either (w,h) or (x1,y1,x2,y2).
    """
    out = []
    for tid, rec in tracks.items():
        if len(rec) < 2:
            continue
        rec = sorted(rec, key=lambda r: r["f"])
        a, b = rec[0], rec[-1]

        def size(r: dict) -> float:
            if "w" in r and "h" in r:
                return max(r["w"], r["h"])
            return max(r["x2"] - r["x1"], r["y2"] - r["y1"])

        k = min(tail, len(rec) - 1)
        p = rec[-1 - k]
        dt = (b["f"] - p["f"]) / fps
        vx = (b["cx"] - p["cx"]) / dt if dt > 0 else 0.0
        vy = (b["cy"] - p["cy"]) / dt if dt > 0 else 0.0

        out.append(Frag(tid, a["f"] / fps, b["f"] / fps,
                        a["cx"], a["cy"], b["cx"], b["cy"],
                        size(a), size(b), vx, vy, len(rec)))
    return out


def _heading_ok(f: Frag, g: Frag) -> bool:
    """Does g lie roughly ahead of f, along f's direction of travel?"""
    speed = math.hypot(f.vx, f.vy)
    if speed < 1e-6:
        return True                      # f was stopped: any direction is fine
    dx, dy = g.x0 - f.x1, g.y0 - f.y1
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return True
    cos = (f.vx * dx + f.vy * dy) / (speed * d)
    return cos >= math.cos(math.radians(MAX_HEADING_DEG))


def link(fragments: list[Frag]) -> dict[int, int]:
    """Return {successor_tid: predecessor_tid} for fragments judged continuations.

    Greedy nearest-in-time matching; each fragment gets at most one successor
    and at most one predecessor.
    """
    frags = sorted(fragments, key=lambda f: f.t0)
    used_pred: set[int] = set()
    used_succ: set[int] = set()
    links: dict[int, int] = {}

    for g in frags:                                    # candidate successor
        best, best_cost = None, None
        for f in frags:                                # candidate predecessor
            if f.tid == g.tid or f.tid in used_pred or g.tid in used_succ:
                continue
            dt = g.t0 - f.t1
            if dt <= 0 or dt > MAX_GAP_S:
                continue

            scale = max(1e-6, (f.size1 + g.size0) / 2.0)   # px per vehicle length
            dist_len = math.hypot(g.x0 - f.x1, g.y0 - f.y1) / scale
            speed_len_s = dist_len / dt

            # a long gap is only credible if the vehicle barely moved (red light)
            if dt > 3.0 and dist_len > MAX_STOPPED_DRIFT_LEN:
                continue
            if speed_len_s > MAX_SPEED_LEN_PER_S:
                continue
            ratio = max(f.size1, g.size0) / max(1e-6, min(f.size1, g.size0))
            if ratio > MAX_SIZE_RATIO:
                continue
            if not _heading_ok(f, g):
                continue

            cost = dist_len + speed_len_s + 2.0 * (ratio - 1.0)
            if best_cost is None or cost < best_cost:
                best, best_cost = f, cost

        if best is not None:
            links[g.tid] = best.tid
            used_pred.add(best.tid)
            used_succ.add(g.tid)
    return links


def vehicles(fragments: list[Frag], links: dict[int, int]) -> list[list[int]]:
    """Collapse fragments into vehicles (chains of linked track ids)."""
    parent = {f.tid: f.tid for f in fragments}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for succ, pred in links.items():
        ra, rb = find(succ), find(pred)
        if ra != rb:
            parent[ra] = rb

    groups: dict[int, list[int]] = collections.defaultdict(list)
    for f in fragments:
        groups[find(f.tid)].append(f.tid)
    return list(groups.values())
