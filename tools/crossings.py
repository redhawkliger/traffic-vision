"""Directional tripwire-crossing counter (ADR-0001 Option C), camera-agnostic.

Counts crossings of a line by tracked vehicles; does NOT count track identities
and does NOT merge tracks (near-duplicates are reported, never collapsed).

Nothing here knows about any camera. Everything site-specific is an INPUT:
  line              two points [[x0,y0],[x1,y1]] in whatever coordinate space the
                    tracks use (pixels today; ground-plane/homography points later)
  direction         unit vector [dx,dy], or a name: left_to_right, right_to_left,
                    top_to_bottom, bottom_to_top, positive_normal, negative_normal
  heading_tol_deg   max angle between LOCAL motion at the crossing and direction
  along_range       optional [s0,s1]: distance along the line from point 0 within
                    which a crossing counts (the "band"); default = whole segment
  window_frames     optional [lo,hi): applied to the CROSSING frame (L-006)

Rules (lessons.md): direction from local motion at the crossing only (L-005);
window on the crossing frame, not track start (L-006); one event per track;
every count is printed with a parameter sweep (L-001/L-002).

Track file format: tools/track.py output {"records":[{"f","id","cx","cy","w","h"..}],
"true_fps":..}.  Only f,id,cx,cy,w,h and true_fps are read.

CLI:  python tools/crossings.py TRACKS.json --config configs/harbor-eb.json \
          [--window LO HI] [--heading-tol 30] [--out result.json]
"""
import argparse
import collections
import json
import math
import statistics
import sys

NAMED_DIRECTIONS = {
    "left_to_right": (1.0, 0.0),
    "right_to_left": (-1.0, 0.0),
    "top_to_bottom": (0.0, 1.0),
    "bottom_to_top": (0.0, -1.0),
}

DEFAULTS = {
    "heading_tol_deg": 30.0,
    "along_range": None,
    "window_frames": None,
    "local_motion": "pair",
    "anchor": "ground",         # "ground" = box bottom-centre (no height bias); "centroid" = legacy
    "near_duplicate_seconds": 1.0,
    "n_segments": 4,
    "maturity": {"min_obs": 3, "min_travel_widths": 1.0,
                 "max_immature_frac": 0.5, "max_born_past_frac": 0.25},
    "sweep_heading_tols": [20.0, 25.0, 30.0, 35.0],
    # (shift of band start, shift of band end) in line units; shows band sensitivity
    "sweep_band_shifts": [[0, 0], [0, -40], [0, 40], [-40, 0], [40, 0], [40, -40], [-40, 40]],
}


# ------------------------------------------------------------------ geometry
class Geometry:
    def __init__(self, line, direction):
        (x0, y0), (x1, y1) = line
        self.p0 = (float(x0), float(y0))
        L = math.hypot(x1 - x0, y1 - y0)
        if L == 0:
            raise ValueError("line has zero length")
        self.length = L
        self.u = ((x1 - x0) / L, (y1 - y0) / L)             # along the line
        self.d = self._direction(direction)
        n = (-self.u[1], self.u[0])                          # a normal
        dot = n[0] * self.d[0] + n[1] * self.d[1]
        if abs(dot) < 1e-9:
            raise ValueError("direction is parallel to the line; it can never cross")
        # orient the normal so that motion along `direction` goes negative -> positive side
        self.n = n if dot > 0 else (-n[0], -n[1])

    def _direction(self, direction):
        if isinstance(direction, str):
            if direction in NAMED_DIRECTIONS:
                v = NAMED_DIRECTIONS[direction]
            elif direction in ("positive_normal", "negative_normal"):
                v = (-self.u[1], self.u[0])
                if direction == "negative_normal":
                    v = (-v[0], -v[1])
            else:
                raise ValueError(f"unknown direction {direction!r}")
        else:
            v = tuple(float(c) for c in direction)
        m = math.hypot(*v)
        if m == 0:
            raise ValueError("direction has zero length")
        return (v[0] / m, v[1] / m)

    def side(self, x, y):
        return (x - self.p0[0]) * self.n[0] + (y - self.p0[1]) * self.n[1]

    def along(self, x, y):
        return (x - self.p0[0]) * self.u[0] + (y - self.p0[1]) * self.u[1]

    def proj_dir(self, x, y):
        return x * self.d[0] + y * self.d[1]



# --- ground anchor -----------------------------------------------------------
# A box CENTROID sits higher in the image for a tall vehicle, so on an oblique
# view it is displaced along the line toward the far end - by 32px for a car and
# 88px for a truck, correlation with box height r=1.000 (measured at SR-41
# Bullard, L-022). That is a height-dependent bias inside the measurement, and it
# cost two truck counts. The GROUND CONTACT POINT - bottom-centre of the box - is
# where the vehicle actually meets the road plane and carries no such bias.
def _pt(r, anchor="ground"):
    """Return the (x, y) used for all crossing geometry."""
    if anchor == "centroid":
        return r["cx"], r["cy"]
    return r["cx"], r["cy"] + r["h"] / 2.0


def load_tracks(path_or_dict):
    D = path_or_dict if isinstance(path_or_dict, dict) else json.load(open(path_or_dict))
    tracks = collections.defaultdict(list)
    for r in D["records"]:
        tracks[r["id"]].append(r)
    for t in tracks.values():
        t.sort(key=lambda r: r["f"])
    return dict(tracks), float(D.get("true_fps") or D.get("meta_fps") or 25.0)


def resolve_params(cfg):
    p = json.loads(json.dumps(DEFAULTS))
    for k, v in cfg.items():
        if k == "maturity":
            p["maturity"].update(v)
        else:
            p[k] = v
    return p


# --------------------------------------------------------------- core finder
def find_events(tracks, fps, geo, params, heading_tol=None, band_shift=(0, 0)):
    anchor = params.get("anchor", "ground")
    """One event per track. Returns list of event dicts (counted or rejected)."""
    tol = params["heading_tol_deg"] if heading_tol is None else heading_tol
    rng = params["along_range"] or [0.0, geo.length]
    s0, s1 = rng[0] + band_shift[0], rng[1] + band_shift[1]
    win = params["window_frames"]
    local = params["local_motion"]
    events = []
    for tid, t in tracks.items():
        accepted, first_reject = None, None
        for i in range(len(t) - 1):
            p, q = t[i], t[i + 1]
            px_, py_ = _pt(p, anchor); qx_, qy_ = _pt(q, anchor)
            sp, sq = geo.side(px_, py_), geo.side(qx_, qy_)
            if not (sp < 0 <= sq):
                continue
            fr = -sp / (sq - sp)
            xc = px_ + fr * (qx_ - px_)
            yc = py_ + fr * (qy_ - py_)
            s = geo.along(xc, yc)
            if local == "win2":
                a, b = t[max(0, i - 1)], t[min(len(t) - 1, i + 2)]
            else:
                a, b = p, q
            ax_, ay_ = _pt(a, anchor); bx_, by_ = _pt(b, anchor)
            vx, vy = bx_ - ax_, by_ - ay_
            vm = math.hypot(vx, vy)
            cosang = (vx * geo.d[0] + vy * geo.d[1]) / vm if vm else 0.0
            heading = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
            in_band = s0 <= s <= s1
            reason = "none"
            if not in_band:
                reason = "band"
            elif heading > tol:
                reason = "angle"
            elif win is not None and not (win[0] <= q["f"] < win[1]):
                reason = "window"
            first = t[0]
            ev = {
                "track_id": tid, "frame": q["f"], "t": round(q["f"] / fps, 3),
                "x_cross": round(xc, 2), "y_cross": round(yc, 2),
                "along_line": round(s, 2),
                "heading_deg": round(heading, 2),
                "obs_before": i + 1,
                "travel_before_in_widths": round(
                    (geo.proj_dir(*_pt(q, anchor)) - geo.proj_dir(*_pt(first, anchor)))
                    / max(q["w"], 1e-9), 3),
                "bbox_w_at_cross": q["w"],
                "_box": (q["cx"], q["cy"], q["w"], q["h"]),
                "born_x": first["cx"], "born_y": first["cy"], "born_frame": first["f"],
                "end_x": t[-1]["cx"], "end_y": t[-1]["cy"], "end_frame": t[-1]["f"],
                "counted": reason == "none", "reject_reason": reason,
                "near_duplicate_of": None,
            }
            if reason in ("none", "window") and in_band and heading <= tol:
                # geometry passed: this is the track's event (window decides counted)
                accepted = ev
                break
            if first_reject is None:
                first_reject = ev
        ev = accepted or first_reject
        if ev is not None:
            events.append(ev)
    events.sort(key=lambda e: (e["frame"], e["track_id"]))
    return events


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return abs(ax - bx) < (aw + bw) / 2 and abs(ay - by) < (ah + bh) / 2


def mark_near_duplicates(events, fps, seconds):
    """Report-only. Later event gets near_duplicate_of = earlier track id."""
    for j, e in enumerate(events):
        for i in range(j):
            o = events[i]
            if o["reject_reason"] in ("band", "angle") or e["reject_reason"] in ("band", "angle"):
                continue
            if abs(e["frame"] - o["frame"]) <= seconds * fps and _overlap(e["_box"], o["_box"]):
                e["near_duplicate_of"] = o["track_id"]
                break


# ---------------------------------------------------------------- maturity
def maturity_stats(tracks, geo, params, events):
    anchor = params.get("anchor", "ground")
    """Per-segment of the band: are tracks established before the line?"""
    rng = params["along_range"] or [0.0, geo.length]
    n = params["n_segments"]
    m = params["maturity"]
    tol = params["heading_tol_deg"]
    width = (rng[1] - rng[0]) / n
    segs = [{"segment": k, "along_range": [round(rng[0] + k * width, 1), round(rng[0] + (k + 1) * width, 1)],
             "crossings": [], "born_past_line": 0} for k in range(n)]

    def seg_of(s):
        if not (rng[0] <= s <= rng[1]):
            return None
        return min(n - 1, int((s - rng[0]) // width)) if width > 0 else 0

    crossed = {e["track_id"] for e in events if e["reject_reason"] in ("none", "window")}
    for e in events:
        if e["reject_reason"] in ("none", "window"):
            k = seg_of(e["along_line"])
            if k is not None:
                segs[k]["crossings"].append(e)
    # tracks born past the line that move in `direction` for >=1 width: can never cross
    for tid, t in tracks.items():
        if tid in crossed or len(t) < 2:
            continue
        a, b = t[0], t[-1]
        if geo.side(*_pt(a, anchor)) < 0:
            continue
        ax_, ay_ = _pt(a, anchor); bx_, by_ = _pt(b, anchor)
        vx, vy = bx_ - ax_, by_ - ay_
        vm = math.hypot(vx, vy)
        if vm < a["w"]:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (vx * geo.d[0] + vy * geo.d[1]) / vm))))
        if ang > tol:
            continue
        k = seg_of(geo.along(*_pt(a, anchor)))
        if k is not None:
            segs[k]["born_past_line"] += 1
    out = []
    for sg in segs:
        ev = sg.pop("crossings")
        nc = len(ev)
        bp = sg["born_past_line"]
        sg["n_crossings"] = nc
        if nc:
            sg["median_obs_before"] = statistics.median(e["obs_before"] for e in ev)
            sg["median_travel_before_in_widths"] = round(statistics.median(
                e["travel_before_in_widths"] for e in ev), 2)
            sg["immature_frac"] = round(sum(
                1 for e in ev if e["obs_before"] < m["min_obs"]
                or e["travel_before_in_widths"] < m["min_travel_widths"]) / nc, 3)
        if nc + bp == 0:
            sg["verdict"] = "no_data"
        elif nc == 0 or sg["median_travel_before_in_widths"] < m["min_travel_widths"] \
                or sg["immature_frac"] > m["max_immature_frac"] \
                or bp / (nc + bp) > m["max_born_past_frac"]:
            sg["verdict"] = "NO_MATURE_ZONE"
        else:
            sg["verdict"] = "mature"
        out.append(sg)
    return out


# ------------------------------------------------------------------- driver
def run(tracks_src, config):
    tracks, fps = load_tracks(tracks_src)
    params = resolve_params(config)
    geo = Geometry(config["line"], config["direction"])
    events = find_events(tracks, fps, geo, params)
    mark_near_duplicates(events, fps, params["near_duplicate_seconds"])
    count = sum(e["counted"] for e in events)

    sweep = []
    for tol in params["sweep_heading_tols"]:
        for sh in params["sweep_band_shifts"]:
            ev = find_events(tracks, fps, geo, params, heading_tol=tol, band_shift=sh)
            sweep.append({"heading_tol_deg": tol, "band_shift": list(sh),
                          "count": sum(e["counted"] for e in ev)})
    counts = [s["count"] for s in sweep]
    for e in events:
        e.pop("_box")
    # _box is needed during marking only
    return {
        "count": count,
        "config": {k: config[k] for k in ("line", "direction") if k in config} | {
            "heading_tol_deg": params["heading_tol_deg"], "along_range": params["along_range"],
            "window_frames": params["window_frames"], "fps": fps},
        "events": events,
        "summary": {
            "n_events": len(events),
            "rejected": dict(collections.Counter(e["reject_reason"] for e in events if not e["counted"])),
            "near_duplicate_pairs": [[e["near_duplicate_of"], e["track_id"]]
                                     for e in events if e["near_duplicate_of"] is not None],
            "sweep": sweep,
            "sweep_range": [min(counts), max(counts)],
            "maturity_by_segment": maturity_stats(tracks, geo, params, events),
        },
    }


def format_report(res):
    s = res["summary"]
    lines = [f"COUNT = {res['count']}   (sweep range {s['sweep_range'][0]}-{s['sweep_range'][1]}; "
             f"quote the range, L-001/L-002)"]
    lines.append(f"events={s['n_events']} rejected={s['rejected']} near_duplicates={s['near_duplicate_pairs']}")
    lines.append("sweep (heading tol deg x band shift [start,end]):")
    tols = sorted({x["heading_tol_deg"] for x in s["sweep"]})
    shifts = []
    for x in s["sweep"]:
        if x["band_shift"] not in shifts:
            shifts.append(x["band_shift"])
    lines.append("  shift".ljust(14) + "".join(f"{t:>6g}" for t in tols))
    for sh in shifts:
        row = {x["heading_tol_deg"]: x["count"] for x in s["sweep"] if x["band_shift"] == sh}
        lines.append(f"  {str(sh):<12}" + "".join(f"{row[t]:>6d}" for t in tols))
    lines.append("maturity by line segment:")
    for sg in s["maturity_by_segment"]:
        lines.append(f"  {sg['along_range']} n={sg['n_crossings']} born_past={sg['born_past_line']} "
                     f"med_travel_w={sg.get('median_travel_before_in_widths', '-')} "
                     f"immature={sg.get('immature_frac', '-')} -> {sg['verdict']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tracks")
    ap.add_argument("--config", required=True, help="site config JSON (line, direction, ...)")
    ap.add_argument("--window", nargs=2, type=int, metavar=("LO", "HI"), help="crossing-frame window [LO,HI)")
    ap.add_argument("--heading-tol", type=float)
    ap.add_argument("--along-range", nargs=2, type=float, metavar=("S0", "S1"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config))
    if a.window:
        cfg["window_frames"] = a.window
    if a.heading_tol is not None:
        cfg["heading_tol_deg"] = a.heading_tol
    if a.along_range:
        cfg["along_range"] = a.along_range
    res = run(a.tracks, cfg)
    print(format_report(res))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
