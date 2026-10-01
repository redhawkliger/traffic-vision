# ADR-0001: Count tripwire crossings on the ground plane, not track identities

**Status:** Proposed
**Date:** 2026-10-01
**Deciders:** project owner (traffic engineer)
**Supersedes:** the track-stitching approach prototyped in `tools/stitch.py`

---

## Context

### What we are building

Volumes and classification only, volumes first ([ANCHOR](../../.claude/ANCHOR.md)).
Accuracy means objective truth — if 100 vehicles pass, report 100 — measured per
15-minute bin against a human-counted benchmark, on a staged ladder of
**85% → 92.75% → 98%**. The unit of work is one camera, one leg, one minute,
then widening.

### The forces at play

**1. The current architecture is wrong by roughly 2×, and we measured it.**

On SR-90 at Harbor Blvd (311 s, 1280×720, 421 raw tracks, 23,605 detections):

| Measurement | Value |
|---|---|
| Median track lifespan | 2.28 s (a crossing takes 5–15 s) |
| Tracks living < 2 s | 46% |
| Tracks that are continuations of another | 53% |
| **Implied count inflation** | **2.01×** |
| Tracks dying in the far field | 50% |
| Tracks dying while nearly stopped | 27% |

One tan Jeep Wrangler produced **nine separate track IDs in 13.7 seconds**.
Counting track identities therefore counts one vehicle nine times.

**2. Post-hoc stitching reduces but cannot resolve it.**

`tools/stitch.py` links fragments using the vehicle's own bounding box as a
physical ruler (≤ 8 vehicle-lengths/sec). It cut 380 fragments → 189 vehicles
and dropped the re-acquisition signature from 46% → 21%. But it introduced
over-merging: 30 of 189 chains are implausible, the longest spanning 137.8 s.
**The truth lies between 189 and 380 and is not determinable from inside the
method.** The max-gap threshold is a free parameter with no ground truth to set
it — gap=2 s yields 173 vehicles, gap=60 s yields 144.

**3. Research says production systems do not do this at all.**

Storm Research briefing, 2026-10-01 ([report](../../storm-reports/traffic-camera-vehicle-counting-classification-briefing.html)):

> Production systems do not rely on unbroken tracks. They project to the ground
> plane via homography, then count **directional tripwire crossings per approach,
> paired into OD zone pairs**. A stopped car never crosses; detector flicker
> cannot fabricate a crossing.

This reconciles the sharpest contradiction in the research: the academic lens
shows tracking is genuinely weak (best PR-MOTA on UA-DETRAC ~21–24%), while the
practitioner lens reports deployments that work. Both are true, because
**production counting does not depend on the thing that is broken.**

**4. Corroborating constraints from verified sources.**

- NCHRP Web-Only Document 436 (Tsapakis et al., TTI, 2025 — *not* peer-reviewed):
  video-based motorized volume WMAPE **1.4%–33.7%** across vendors and sites.
  Authors state accuracy degrades as volume rises, and **turning-movement counts
  are less accurate than through movements**.
- Caltrans inductive loops in a published head-to-head **overcounted by 24.5%**
  (3,392 vs 2,724 observed), worst "during periods with frequent lane changes and
  queuing near signalized intersections."
- VDOT VTRC 26-R53 (2026) certifies count devices against *"absolute,
  human-verified video ground truth"* with a 5% error threshold — the same method
  this project locked independently.

---

## Decision

**Count directional tripwire crossings projected onto the ground plane. Do not
count track identities.**

Tracking is retained, but demoted: its job is to establish *direction and
continuity across a short transit*, not to maintain identity across stops,
occlusions, or the full field of view.

### Pipeline

```
 1  CAPTURE      HLS -> clip.  Verify CONTINUOUS availability over the window;
                 invalidate periods that fragment. (42% of live cameras flap.)
 2  QUALIFY      Site gate, no labels needed: measure pixels-per-vehicle.
                 >=60 px vehicle width => detection is 95-99%. Below => reject.
 3  CALIBRATE    Homography, once per camera, from painted MUTCD references
                 (12 ft lanes; 10 ft stripe / 30 ft gap). Pixels -> feet.
 4  DETECT       YOLO11n. conf=0.10-0.15 (NOT the 0.25 default). The only AI step.
 5  TRACK        ByteTrack, for short-transit continuity and direction only.
 6  CROSS        Tripwire per approach, on the GROUND PLANE, with direction.
                 <-- THE COUNT HAPPENS HERE
 7  PAIR         [DEFERRED] entry zone -> exit zone = turning movement.
 8  CLASSIFY     [DEFERRED - ADR-0002]
 9  VALIDATE     Signed error per 15-min bin vs human-counted benchmark.
10  MONITOR      View-change and availability drift; invalidate, never silently
                 degrade.
```

Steps 7 and 8 are explicitly out of scope for now — volumes first, one stone at
a time. The architecture must not *preclude* them.

### Why this dissolves the failure mode

| Failure we measured | Effect under crossings |
|---|---|
| One vehicle → 9 track IDs | Still **one** crossing event |
| 46% of tracks live < 2 s | Irrelevant unless they cross |
| Vehicle stops at red, loses ID | A stopped vehicle **never crosses** |
| 50% of deaths in the far field | Tripwire sits in the qualified zone; far field is out of scope |
| Detector flicker | Cannot fabricate a transit across a line |

### Why the deferred pairing step is tractable

Turning movements need entry→exit identity, which reintroduces a tracking
dependency. But the *transit through the intersection box is short (3–10 s) and
the vehicle is moving* — the regime where tracking is strongest. Every
fragmentation mode we measured occurs when a vehicle is **stopped** or **distant**.
We are not re-acquiring the hard problem; we are scoping tracking to its easy case.

---

## Options considered

### Option A — Count unique track identities *(current, rejected)*

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Correctness | **Fails: 2.01× measured inflation** |
| Calibration needed | None |
| Robustness to stops | None — this is the failure |

**Pros:** simplest; already built; no calibration.
**Cons:** measurably wrong by ~2×; error scales with signal delay, so it is worst
at exactly the congested intersections that matter most.

### Option B — Track identities + post-hoc stitching *(prototyped, rejected)*

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Correctness | Improves, does not resolve — truth stuck between 189 and 380 |
| Calibration needed | None (uses bbox as ruler) |
| Robustness to stops | Partial; trades under-merge for over-merge |

**Pros:** no calibration; physical units; already working; measurable improvement
(re-acquisition 46% → 21%).
**Cons:** introduces a free parameter (max gap) that changes the count by 20% with
no ground truth to set it; 16% of output chains implausible; patches a symptom.

### Option C — Directional tripwire crossings on the ground plane *(recommended)*

| Dimension | Assessment |
|---|---|
| Complexity | Medium — calibration is the new work |
| Correctness | Removes the dominant error class by construction |
| Calibration needed | **Yes — homography, once per camera** |
| Robustness to stops | High — stopped vehicles never cross |
| Industry precedent | Reported as the production approach |

**Pros:** fragmentation becomes largely irrelevant; no free parameter inside the
count; counts are in physical units from the start; extends naturally to OD
pairing and to classification; matches reported production practice.
**Cons:** requires calibration before any count (a real new dependency); tripwire
placement must sit inside the qualified zone; occlusion on multi-lane approaches
remains unsolved and is the named failure mode in NCHRP.

### Option D — Pixel-domain virtual loop, no detector

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Correctness | **Unreliable — measured 79 vs YOLO's 48 on the same clip** |
| Calibration needed | None |
| Classification | **Impossible** |

**Pros:** no model, no GPU, trivially fast.
**Cons:** we measured it disagreeing with the detector by 65% with no way to
adjudicate; cannot classify, so it is a dead end against the locked scope.
Retain only as an independent cross-check.

---

## Trade-off analysis

**The core trade is: accept a per-camera calibration dependency in exchange for
removing a 2× systematic error.**

Option B is tempting because it is already built and needs no calibration. But
its central parameter cannot be set without ground truth, and it moves the count
by 20% across its plausible range. That is a free parameter sitting *inside the
measurement* — unacceptable for a project whose entire thesis is auditable
accuracy. Option C has no equivalent knob: a crossing either happened or it
did not.

Calibration is a genuine cost, but it is the **one** per-camera step the
foundation already permits, and it is required anyway for classification by
physical size and for any future speed work. It is not new debt.

**What we are explicitly not buying:** Option C does not fix occlusion on
congested multi-lane approaches, which NCHRP names as a primary degradation and
which gets worse as volume rises. Nothing in this ADR addresses that, and it
should be expected to dominate the error budget once fragmentation is removed.

---

## Consequences

**Easier**
- Counts become robust to track fragmentation, the dominant measured error.
- Stopped vehicles and signal queues stop corrupting the count.
- Counts are in physical units from the moment of measurement.
- Step 1 of the ladder (one leg, one minute) needs only *one* tripwire — no
  pairing, no classification, no identity across the box.
- Classification decouples cleanly; it can be wrong without making volumes wrong.

**Harder**
- Calibration is now a prerequisite. No calibration, no count.
- Tripwire placement becomes a correctness-relevant decision and must be derived
  from the qualified zone, not hand-drawn per camera.
- A view change (PTZ nudge, mount shift) silently invalidates calibration —
  detection of this becomes mandatory, not a refinement.

**To revisit**
- Occlusion handling on multi-lane approaches — deferred, expected to dominate.
- Entry→exit pairing for turning movements (ADR-0003).
- Classification method (ADR-0002) — note that storm verification *partially
  rehabilitated* geometric features: the primary source dismissing length-based
  classification in fact combines "semantic and geometric" features and extracts
  axle configuration from video.
- Whether `tools/stitch.py` is retired or retained as a diagnostic. It should
  stay as an *instrument* — the re-acquisition signature is a useful tracker
  health metric even when counting does not depend on it.

---

## Action items

1. [ ] **Build the calibration module.** 4-point homography, pixels → feet, from
       MUTCD painted references. Manual point entry first; automatic lane-marking
       derivation later.
2. [ ] **Derive the qualified zone** from the pixels-per-vehicle map, and place
       the tripwire inside it automatically rather than by hand.
3. [ ] **Implement directional crossing counting** on the ground plane with
       per-crossing provenance (track id, frame, ground coordinates) so every
       count is auditable back to pixels.
4. [ ] **Produce the step-1 benchmark**: one leg, one minute, at SR-90 Harbor
       Blvd (footage already on disk). Both parties count independently, reconcile,
       version the result as the permanent yardstick.
5. [ ] **Score against it** and record the first real number on the
       85 / 92.75 / 98 ladder.
6. [ ] **Open `lessons.md`** and record every disagreement found during
       reconciliation — the foundation requires it.
7. [ ] **Demote `tools/stitch.py`** to a diagnostic; keep the re-acquisition
       metric as tracker health.
8. [ ] Defer: pairing (ADR-0003), classification (ADR-0002), occlusion.

---

## Honest uncertainties

- The tripwire+OD architecture rests on **a single research lens**, not a primary
  source. It is coherent and explains the academic/practitioner contradiction,
  but it has not been verified against a published system description.
- We still have **no ground truth**. This ADR argues that Option C removes a known
  error class; it does not prove the resulting count is right.
- All our measurements are from **one camera on one Sunday**. Weekday volumes,
  queues and occlusion will be materially harsher.
