# Lessons

Every disagreement found during validation gets recorded here rather than
quietly fixed. Required by the locked foundation: *"Sometimes it will go low.
We understand from our mistakes, learn from the mistakes, and record it, and
keep getting it better."*

---

## L-001 — A free parameter inside a measurement is not a measurement
**Found:** 2026-10-01, reconciling benchmark `harbor-eb-60s`.
**Disagreement:** user counted **20**, Claude reported **15 ±3**. The true value
was outside Claude's stated range.

**Root cause.** Claude's detector-free instrument split the tripwire into four
lane rows, then needed a rule to reassemble row-events into vehicles. Sweeping
that rule:

| merge rule | count |
|---|---|
| dt=0.2 s, adjacent rows, max 2 | 24 |
| dt=0.3 s, any rows, max 4 | 21 |
| dt=0.5 s, any rows, max 4 | **17 (used)** |
| dt=0.8 s, any rows, max 4 | 16 |

**The count moved 16→24 (50%) on parameter choice alone** — not on the video.
The reported "15 ±3" was one arbitrary point on that curve presented as an
observation with noise.

**Why it matters.** This is the *same* defect ADR-0001 rejects in track
stitching (max-gap moved the count 20%). Claude applied that standard to the
stitcher and then built a new instrument with a worse version of it, the same
day.

**Fix / consequence.**
1. A detector-based crossing counter has **no merge parameter** — YOLO resolves
   each vehicle's extent, so rows never need reassembling. The row decomposition
   was a workaround for having no detector. ADR-0001's architecture does not
   inherit this flaw.
2. Claude did **not** select the rule that reproduces 20. Choosing a parameter
   because it matches the reference makes the benchmark circular.
3. **New standing rule:** before quoting any figure, sweep every free parameter
   in the method and report the resulting range. If the range is wide, the range
   IS the result.

---

## L-002 — Uncertainty must come from a parameter sweep, not intuition
**Found:** same reconciliation.
Claude stated "+/-3" from a feeling about ambiguous groupings. The honest figure
from sweeping the method was roughly 16-24. **Guessed uncertainty understated
the real sensitivity by about 3x**, and the true value fell outside the quoted
band.

**Rule:** uncertainty is computed by varying the method, never estimated.

---

## L-003 — A time-space strip at a single line cannot resolve direction
**Found:** 2026-10-01, while building the benchmark.
The first instrument counted crossings in both directions while the benchmark
definition said left-to-right. Caught before producing a number, but only
because the definition was written down first. Fixed with paired lines at
x=580/620 — whichever fires first gives direction.

**Rule:** write the measurement definition before building the instrument; it is
what catches the instrument being wrong.

---

## L-004 — A number without provenance is not ground truth
**Found:** 2026-10-02, during benchmark `harbor-eb-60s`.

On 2026-10-01 the user replied "20" to a request to count the clip. Claude took
that as a counted value, locked the benchmark, wrote it into the golden file,
and **committed and pushed it**. The next message was the user asking where the
video was — revealing they had not watched it. The 20 was an assertion, not a
measurement.

**Near miss.** The benchmark everything else is scored against was locked on an
unverified figure, and was caught only because the user happened to mention they
could not find the file. Had they stayed silent, every accuracy claim in this
project would have inherited it — and it would have looked authoritative.

(The user subsequently watched the clip and the true count *was* 20. The value
was right; the process was wrong. A process that produces the right answer by
luck is still broken.)

**Rule.** Before any externally-supplied value is locked into a benchmark,
confirm *how it was obtained*. Record the provenance in the artifact itself, not
just the number. If provenance is unclear, the status stays provisional — never
RECONCILED.

**Rule.** Claude's own counts are recorded with `recorded_before_seeing_user_count`.
Apply the same standard in reverse: a reference value needs a stated method.

---

## L-005 — Judge crossing direction from LOCAL motion, not overall track displacement
**Found:** 2026-10-02, user error-analysis of benchmark `harbor-eb-60s`.

The user reviewed every counted crossing and found exactly one false positive:
*"count number one is wrong because it is not going from left to right, but it is
going from up to down. It just crosses the pink line."*

**Root cause.** Direction was tested two weak ways at once: the track's *overall*
displacement heading, and the sign of dx at the line. A vehicle travelling
predominantly downward with a slight rightward drift passes both while not being
an eastbound movement.

**Fix.** A tripwire crossing counts only if the motion *at the crossing* is
predominantly **perpendicular to the line**. For the vertical tripwire: local
heading within 30 deg of horizontal.

**Why this is not L-001 again.** The data is bimodal with a wide plateau: the
false positive sits at 35.6 deg, the 20 genuine crossings at 5.4-18.4 deg, and
any threshold from 20-30 deg yields exactly 20. Contrast the merge rule, which
slid continuously 16-24 with no plateau. A discriminator with a natural gap is
not the same thing as a knob that sets the answer. **Still verify on held-out
data** - one false positive is one data point.

---

## L-006 — Select tracks by the CROSSING frame, not the track start frame
**Found:** same session, while building the QA video.

A reported figure of 24 crossings was wrong. Tracks were filtered to those
*starting* inside the 60 s window, but three of them crossed the line at
t=63.0s, 108.1s and 109.3s - outside it. True in-window total: 21.

Effect: inflated the error from +5% to +20% and made raw crossing counting look
far worse than it is. **A window filter must be applied to the EVENT, never to
the entity that produces it.**

---

## L-007 — A benchmark used to fix a method can no longer validate that method
**Found:** 2026-10-02, immediately after L-005.

With the perpendicular criterion the count matched ground truth exactly (20/20).
That figure is **in-sample**: the error was found on this benchmark, the fix was
derived from it, and the threshold was chosen after inspecting its data.

**Rule.** Report in-sample results as in-sample. Any accuracy claim that leaves
this project needs a **held-out benchmark** the method has never been tuned
against. Build benchmark #2 from a different window - ideally a different camera
and a weekday - before quoting a number to anyone.

---

## L-008 — A 13-vehicle benchmark cannot validate a 98% target
**Found:** 2026-10-02, first out-of-sample result on benchmark B.

Truth 13, prediction 12 -> 92.3% accuracy. Passes stage 1 (85%), misses stage 2
(92.75%) by 0.45 percentage points.

**The problem is granularity, not the result.** With 13 vehicles one error is
7.7%, so the only attainable scores near the top are **92.3% (one error) and
100% (zero errors)** - nothing in between. The benchmark physically cannot
distinguish stage 2 from stage 3.

To measure 98% meaningfully, one error must be worth less than 2%, which needs
**N >= 50 vehicles**.

**Consequence for the locked ladder.** The 1-minute unit is right for stage 1 -
it got the loop running cheaply and has already produced two real numbers. But
stage 2 and stage 3 cannot be validated at that size. Later rungs need longer
windows, busier periods, or several benchmarks pooled.

This does not invalidate the ladder; it specifies when to climb it.

---

## L-009 — The human blind count was also wrong
**Found:** 2026-10-02, benchmark B review.

The user's blind count was **13**. Reviewing the same clip with the numbered
overlay, they found two vehicles *their own blind count had missed* and revised
to **14**.

**This matters more than the method's error.** Ground truth from a single blind
human count is not exact. Benchmark A rests on exactly that - one blind count of
20, never reviewed. It may be low by the same mechanism.

**Rule.** Every benchmark gets a review pass with the overlay, not just a blind
count. The blind count establishes independence; the review pass establishes
accuracy. Record both values and which is the reference.

**Consequence.** It also vindicates the user's instinct to see the numbering
during counting - the review found errors a blind count could not.

---

## L-010 — The dominant error was zone definition, not occlusion
**Found:** same review. **ADR-0001 predicted wrong.**

ADR-0001 stated: *"Option C does not fix occlusion on congested multi-lane
approaches... it should be expected to dominate the error budget once
fragmentation is removed."*

It did not. Of the two misses:
- one crossed at **y=689**, outside the hand-drawn band `y=[300,680]` - the
  tripwire simply **stopped mid-roadway**;
- one was a genuine detection miss (dark vehicle, truncated at the frame bottom,
  partly behind another car).

So the leading error was a **hand-placed zone boundary**, not a hard CV problem.
Extending the line to span the road fixed it with **no regression on benchmark A**
(20 before, 20 after).

**Rule.** ADR-0001 action item 2 - derive the tripwire from the qualified zone
automatically rather than drawing it by hand - is not a refinement. It was the
single largest error source measured so far. Promote it.

**Meta-lesson.** A confident prediction in a design document is still a guess
until measured. Record which predictions were wrong, not just which were right.

---

## L-011 — The "detection miss" was a track-birth placement problem
**Found:** 2026-10-02, chasing the last open error on benchmark B.

The missed dark vehicle at t=54 was recorded as a genuine detection failure in
L-010. **That was wrong.**

Tested every available model on the exact frame - yolo11n, yolo11s, yolo11m, at
imgsz 960/1280/1920, conf 0.15 and 0.05. **All eighteen configurations detected
it.** Detection was never the problem.

The real cause: track **6371** has its first observation at **x=602.4**. The
tripwire is at **x=600**. ByteTrack did not confirm the track until the vehicle
was already past the line, and a track born downstream of a tripwire can never
cross it.

**Fix (principled).** A tripwire must be placed where tracks are MATURE - far
enough downstream of the track-birth region that every vehicle has an
established track before reaching it. This is ADR-0001 action item 2 failing in
its third distinct way: zone boundary too short (L-010), and now zone placed too
close to track birth.

**Consequence for the hybrid/ensemble idea.** The user proposed combining models
so one catches what another misses. Sound technique, but **tested and it would
not have helped here** - every model already found this vehicle. Ensembling
addresses detection error; our measured errors are not detection errors.

**The ledger so far - five defects, zero caused by model capability:**

| Defect | Category |
|---|---|
| Counting track IDs | architecture |
| Window filter applied to track start | logic bug |
| Direction from overall displacement | logic bug |
| Tripwire stopped mid-roadway | geometry |
| Track born past the tripwire | geometry/placement |

**Rule.** Before reaching for a bigger or additional model, verify the failure is
actually a detection failure. Run the candidate models on the specific frame.
Three of five defects here would have been invisible to any model change.

---

## L-012 — A line placed inside the intersection box cannot isolate a movement
**Found:** 2026-10-02, owner review of benchmark `brea-wb-5min` (to 1:59).
`configs/brea-wb.json` (x=640, y 100-450, "right to left") was chosen from track
statistics without viewing a frame. Three movements overlap there with a leftward
pixel component; 25 of the sealed 64 counts (39%) were vehicles the owner correctly
said were not the stream, and the 30 deg knob (58-68) merely sliced one of those
families. No band can separate them at x=640 (y-ranges overlap). The directional
test itself is correct (verified synthetically and on real tracks).
**The sealed warning "true value may sit below 64" pointed the wrong way** - the
owner's stream was under-counted.
**Rules.** (1) Place tripwires on an approach/departure LEG, perpendicular to its
lanes, never inside the box. (2) Before sealing, a human confirms a still frame with
line + arrow + the movement written in words. (3) A NO_MATURE_ZONE verdict blocks
sealing; it does not become a footnote.

## L-013 — Frame skip is a counting parameter, not a cost knob
Tracking every 3rd frame (8.3 fps) made fast near-field vehicles (50-75 px/step,
IoU 0.24-0.43 between samples) fail ByteTrack's one-chance confirmation. Every
vehicle the owner named as missed was DETECTED (conf 0.85-0.92) but never tracked
before the line (same mechanism as L-011, systemic). Skip 1 tracked 30 owner-stream
vehicles to 1:59 vs 17 sealed. Harbor was spared only because vehicles enter small
and slow. The re-track figures are IN-SAMPLE evidence, not a result.

## L-014 — Near-duplicate flag was wrong 16/16
`mark_near_duplicates` compared boxes at each track's own crossing time, so
platooned vehicles in adjacent lanes tripped it. All 16 flagged pairs were
concurrently alive tracks. Report-only (no count effect) but it misled the review.
Fix: require the two tracks never to be alive at the same time.

## Process note (same session)
Changed four things at once on Brea (new camera, new tool, 5 min, new direction),
skipped ladder steps 1-2, and sealed blind. The Harbor loop worked because the line
was seen on video first, one leg, one minute. Return to that loop. brea-wb-5min is
now SPENT / in-sample.

---

## L-015 — The tracker was never pinned; Brea and Harbor used different trackers
**Found:** 2026-10-02, tracker experiments on the Brea dev window.
Every document said "ByteTrack". The installed ultralytics (8.4.171) default is
TrackTrack with new_track_thresh 0.7, which cannot start a track from a weak
detection. The owner's missed motorbike (det conf 0.41-0.53) and the middle truck
were both lost for this reason. Harbor's stored tracks were made by ByteTrack at
~0.15 thresholds (re-track reproduced 41/41 ids); the first Brea run used
TrackTrack defaults, so the "frozen method" claim for Brea was false.
**Fix.** `configs/tracker.yaml` (TrackTrack, high=new=0.25, low=0.1) is now the
default in tools/track.py and every output header records the tracker. On the Brea
dev stretch it recovers both misses once each with nothing else gained/lost
(ByteTrack 0.15 misses the bike and double-counts the truck). Harbor A=20, B=13
reproduced (B swaps one crossing: loses the L-010 y=690.9 vehicle, gains one at
f3228). All IN-SAMPLE. The Harbor benchmarks were scored on a different tracker.
**Rule.** The tracker, its thresholds and the library version are part of the
method. Pin and record them before any sealed prediction.

## L-016 — Check a window has enough subjects BEFORE spending it
Brea source seconds 240-300 had 2 westbound crossings (11 outside the band): zero
statistical power, and one count was peeked at to learn that. Unseen Brea footage
is effectively exhausted. Rule: choose benchmark windows by a pre-stated volume rule
(and a minimum subject count) from independent evidence, before any method output
is looked at; get new footage when the pool is spent.

## L-017 — A benchmark's state lived in two files and they disagreed
**Found:** 2026-10-05, owner asked "where are we" and was sent to re-review a
benchmark they had already reviewed three days earlier.
`tests/golden/brea-wb-leg-1min.json` said `status: "SEALED - awaiting owner review"`
with `counts.user: null` and `owner_has_seen_this_window: false`. But ANCHOR.md
said "brea-wb-leg-1min (dev window, owner-reviewed)" and L-015 already recorded
the owner's two findings *by name* — the motorbike and the middle vehicle — and
the tracker pin that fixed them. Claude read the JSON, trusted it, and asked the
owner to redo finished work. The owner caught it: "it's an old video which I
already reviewed," then re-reported the same two findings from memory.
**Cost.** The owner's review time, and nearly a second in-sample benchmark.
**Rule.** The golden file is the ONLY source of truth for a benchmark's state.
A review is not received until it is written into that file in the same action.
Never infer "outstanding" from a null field without reconciling ANCHOR + lessons;
when two records disagree, the one naming concrete observations is the real one.

## L-018 — No public operational camera shows a full intersection box, and that is structural
**Found:** 2026-10-05, statewide then nationwide camera survey.
The owner asked for a study site where the whole intersection box is in frame,
perimeter outside the crosswalks. Searched two independent systems:
  Caltrans statewide : 3,591 cameras, 3,589 stills, 874 within 90 m of an OSM
                       traffic signal, 475 live full-res frames pulled, 252
                       non-Interstate, top 90 screened by eye.
  NYC DOT            : 972 cameras, 970 images, 812 named "<street> @ <street>".
**ZERO showed four approaches.** Not one, out of 4,561 cameras in two systems
run by different agencies on opposite coasts.
**Why.** Operational cameras are mounted on signal poles and mast arms at the
roadside and look ALONG an approach or corridor, because operations needs queues
and incidents, not turning movements. A whole-box view needs the camera high
above the centre of the box. In both systems the HIGH-RESOLUTION cameras are on
freeways (NYC: 22 of 23 HD cameras are BQE/LIE/Cross-Bronx); intersection
cameras are 352x240. Resolution and geometry are anti-correlated with what a
turning-movement study needs.
**Consequence.** The owner's own plan - mount our own camera and record - is not
a convenience, it is the only way to get this geometry. The method should be
developed against the geometry we will MOUNT, not the geometry a DOT happens to
give. Scanning more states would re-confirm a structural fact, not find an
exception.
**Also recorded.** Two filters that worked, for reuse: OSM traffic_signals
within 90 m identifies surface intersections (validated - Brea/Harbor/Beach land
at 15/21/24 m, where an image-feature ranker put them at 1142/2226/2449 of 3589);
white-pixel fraction > 0.55 removes "Temporarily Unavailable" placeholder cards
(1,028 of 3,589). Ramp meters are tagged highway=traffic_signals, so the signal
test alone admits freeway on-ramp cameras - exclude Interstates or motorway ways.

## L-019 — Optical-flow spread understates per-vehicle spread by ~2x
**Found:** 2026-10-05, verifying the derived config at SR-41 Bullard BEFORE sealing.
Tolerance was derived from the heading spread of the optical-flow field: stream 1
p95 = 11.5 deg -> tol +-16. Checking it against the headings of actual TRACKED
vehicles at the crossing gave p95 = 24.1 deg, max 26.1. The derived +-16 was
rejecting **4 of 23 real vehicles (17%)**.
**Why.** Flow is averaged over a cell, so it measures the spread of the STREAM.
Counting rejects individual VEHICLES, whose headings scatter about twice as wide
(lane changes, perspective, tracker noise). They are not the same quantity.
**Rule.** Derive a per-vehicle threshold from per-vehicle measurements. Use flow
to FIND the streams and their geometry; never to set a rejection threshold.
**The better fact.** Sweeping tolerance showed the count is IDENTICAL from 30 to
89 deg - the heading distribution has a clean gap above 27 deg. So the tolerance
sits on a PLATEAU, not a slope, and is not a free parameter here (cf. L-001).
Set it to 40: mid-plateau, covers the observed max with 50% margin, and far from
the 79 deg that would be needed to admit the opposing stream.
**Corollary for extent.** The 30 s verification segment said stream 1's first 113
px carried no crossings. The full 609 s clip showed the 56-113 px portion is the
BUSIEST part of that line. Trimmed only the first 56 px. Third time this pattern
has appeared (L-016, Brea y305-480, here): a short sample is never evidence of
absence - decide extent on full-clip evidence.
**Also measured.** The tracker's reported position leads the detection by a
median of 33 px (p90 61 px). An IoU-based detector/tracker comparison therefore
reports false "misses"; match on centre distance relative to box size instead.
That mistake made a correctly-tracked vehicle look like a 19-frame miss.

## L-020 — Stop hand-rolling road detection; a driving-scene model already does it
**Found:** 2026-10-05, owner asked "do I need to teach computer vision how to read
a roadway? Is there no model for this? Waymo drives cars - is that data not shared?"
They were right. Two attempts at colour-threshold road detection failed: the first
assumed black asphalt (this carriageway is light concrete) and matched buildings;
the second, tuned to measured road pixels, matched 70% of the frame because the
barrier, shoulder and sidewalk are also grey and unsaturated. Colour cannot
separate "drivable carriageway" from "concrete next to the carriageway".
**What works.** SegFormer-b0 fine-tuned on Cityscapes (`nvidia/segformer-b0-
finetuned-cityscapes-1024-1024`, via transformers). Cityscapes labels are built
for driving scenes: class 0 is `road`. One CPU inference on the vehicle-free
median background segmented the carriageway cleanly - barrier out, shoulder out,
dirt out, and the opposing carriageway beyond the barrier correctly excluded.
Runs ONCE per camera, so CPU-only is irrelevant. tools/roadseg.py.
**Rule.** Geometry questions about the scene (where is the road, the sidewalk, a
lane) are a solved model class. Use the pretrained model; save hand-written rules
for the measurement itself, where every threshold has to be defensible.
**Second finding, from the same investigation.** At SR-41 Bullard the line
position trades road coverage against track maturity, and the camera cannot give
both at once:
      pct along travel   30    50    65    75    85    90
      road spanned (px) 452   400   370   292   246   218
      maturity          fail  fail  fail  fail  PASS  PASS
Moving to the 85th percentile to clear NO_MATURE_ZONE pushed the line to the frame
edge, where most of the carriageway has already left view - which is exactly the
missing left lane the owner spotted. A single line cannot serve every lane here.
The fix is PER-LANE lines, each placed where that lane's own tracks are mature.

## L-021 — First correct count, and exactly what it does and does not show
**2026-10-05.** bullard-30s: predicted 15, owner confirmed 15. No misses, no
false counts. The first time in this project that a count has been right.
**What produced it.** Not a better model - the same yolo11n throughout. What
changed is that every parameter stopped being chosen by hand:
  direction  <- motion-weighted mean of 18,288 frames of optical flow
  tolerance  <- per-vehicle crossing headings, not flow spread (L-019)
  extent     <- SegFormer/Cityscapes road segmentation (L-020), owner-approved
  position   <- maturity sweep, rejecting any position with NO_MATURE_ZONE
And the count is now insensitive to the knobs: 15 at 20/25/30/35 deg tolerance.
**What it does NOT show.** N=15, so one error would be 6.7%: this clears stage 1
(85%) and cannot distinguish stage 2 (92.75%) from stage 3 (98%). L-008 still
stands. It was REVIEWED, not blind. It is free-flow freeway in one direction on
the near lanes - no queues, no turns, no occlusion - deliberately the easy case.
And the line extent came from full-clip detection density, which includes these
frames, so there is a weak in-sample dependency.
**The lesson to carry.** Five defects in this project were traced to a number a
human picked (merge gap, conf threshold, band edge, heading tolerance, track-birth
threshold). Zero were the model's capability. The fix was never a better model;
it was deriving the number from a measurement and then checking the answer does
not move when the number does.
