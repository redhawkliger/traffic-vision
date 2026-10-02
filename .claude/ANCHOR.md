# ANCHOR
updated: 2026-10-01 (foundation confirmed; storm research done; ADR-0001 proposed)

## GOAL
REFRAMED 2026-10-01 by the user, superseding the monetization framing:
"My goal is to make traffic analysis updated with technology and make it easy,
make it efficient. Traffic engineering is all about reducing congestion and
increasing safety. And that is directly proportional to the abundant data ...
our industry is way backward. And I want to improve it."
"I want to find a way to extract with HIGH DATA QUALITY. That's it."
"monetization in return it's not immediate by December which I said earlier —
that was the wrong approach."
Prior framing (kept for history, no longer the driver): "ship this into a
scalable product and monetize it ... by the end of this year".
"Let's work on finding the right algo for us, which is classifying the vehicles
most as accurately as possible."
True destination is INTERSECTIONS (turning movements feeding DemandIQ); freeway
was only the available starting point.

## LOCKED
- Product = intersection TMCs from free Caltrans arterial cameras (2026-09-27)
- Classes = Car, HV, Motorbike (+ Ped, Bike at intersections "later")
- HV = FHWA 4-13. Pickups, SUVs, Jeeps, light vans are CAR. Visual rule: single
  rear wheels = Car, dual rear wheels = HV (2026-09-27)
- FHWA length boundary ~22 ft; car ~15 ft, semi ~73 ft
- Ground truth method = "I label crops you send me" (2026-09-27; SUPERSEDED
  by the TRUTH METHOD entry below, 2026-10-01)
- Repo = NEW standalone private repo redhawkliger/traffic-vision, separate from
  demandiq. Contents: findings + cleaned tools, spike quarantined (2026-09-27)
- Base case camera = SR-90 @ Harbor Blvd, CAM 506, 1280x720, D12
- Next move chosen = fix tracking in physical units (2026-09-30)
- 60 px vehicle width is the measured usability boundary; above it detection is
  95-99% on all three cameras tested

- SCOPE LOCKED 2026-10-01: VOLUMES + CLASSIFICATION ONLY. Nothing else.
  Sequencing within it: volumes FIRST, classification second.
  User: "I truly believe in the concept of one stone at a time. Let's not
  digress ... When we are able to classify and accurately make sure our backend
  program is perfectly doing what it's meant to do, then we can switch to
  others." Congestion metrics and safety/conflict metrics are OUT for now
  (both are derived from the same detect-track-classify base, so nothing is
  lost by deferring them).
- Accuracy means OBJECTIVE TRUTH, user's own definition: "if 100 vehicles are
  going in a roadway and if we're able to capture those 100 vehicles, that's
  the accuracy. If 50 of them are single vehicles and 20 of them are trucks and
  30 are motorcycles, if we're able to classify that accurately, that's
  accuracy."

- ACCURACY TARGETS LOCKED 2026-10-01, three stages (user's own numbers):
      stage 1: 85%      stage 2: 92.75%     stage 3: 98%
  Claude's interpretation, correctable: measured per 15-MINUTE BIN on volumes,
  so 85% = within +/-15% of true count in every bin, 98% = within +/-2%.
  Per-bin not per-period, because a count can be +6% then -6% and total
  perfectly while being useless for peak hour factor / HCM.
  Companion stricter check: vehicle-level matching (did we count the SAME
  vehicles, not merely the same total) - follows from "capture those 100".
  CURRENT STANDING: unknown but certainly FAILING stage 1 - fragmentation alone
  inflates counts ~2x.

- UNIT OF WORK LADDER LOCKED 2026-10-01 (user's words): iterate, nail one
  thing, lock it, improve it.
      step 1: ONE camera, ONE leg, 1 MINUTE
      step 2: next conflict points
      step 3: one leg, 5 minutes
      step 4: 5 minutes, 2 legs
      step 5+: scale by location, "best case based on the location"
  "Sometimes it will go low. We understand from our mistakes, learn from the
  mistakes, and record it, and keep getting it better." -> a LESSONS LOG is a
  requirement, not optional (same pattern as the DemandIQ harness lessons.md).

- FOUNDATION CONFIRMED by the user 2026-10-01: Claude restated objective /
  scope / accuracy bar / unit of work / truth method in full and the user
  agreed ("yea it does"). The five-question grill is COMPLETE. Next stage is a
  WRITTEN SPEC, which should consume this understanding rather than
  re-interviewing.
- TRUTH METHOD LOCKED 2026-10-01: for the first benchmark, Claude and the user
  count INDEPENDENTLY, then reconcile every disagreement. Later counts may be
  lighter (Claude counts, user spot-checks) once the method is trusted.
  Ground truth is recorded as a VERSIONED FILE in the repo (per vehicle:
  timestamp, leg, class) and becomes the permanent yardstick.
  Every disagreement found goes into the LESSONS LOG, not quietly fixed.
  Rationale: every measurement to date has been relative (model vs model,
  before vs after), which is exactly why nothing ever closed.

## CONSTRAINTS
- FOUNDATION BEFORE SOLUTION. User 2026-10-01: "lets lock in the fundamentals
  and foundation first and then move on to how to figure out a solution."
  Order: objective -> data -> accuracy bar -> unit of work -> truth method,
  THEN camera source, THEN technical solution. Claude has repeatedly jumped to
  implementation early; do not.
- Every threshold in PHYSICAL units (feet, seconds, mph, vehicle-lengths), never
  pixels. Exactly ONE per-camera step allowed: calibration.
  User: "we are creating a specific solution for that camera and that
  intersection. The next intersection will have a different issue."
- Diagnose before fix; present diagnosis and wait for approval
- Use cost-appropriate agents — cheap models for mechanical fan-out, strong
  model for architecture/diagnosis/correctness
- One thing at a time. "Let's not unnecessarily get into the weeds and clutch."
- December 2026 deadline RETIRED by the user 2026-10-01 ("that was the wrong
  approach"). Optimise for data quality, not time-to-revenue.
- Named comparators, all solving this differently: INRIX, Miovision, TransCore
  (tolling/RFID), Replica, StreetLight. User on the cellular-derived ones:
  "I don't think it's very accurate."
- Split commits by concern; commit messages via -F file
- Never quote an accuracy figure until ground truth exists

- ADR-0001 PROPOSED 2026-10-01 (docs/adr/0001-count-crossings-not-tracks.md,
  commit e1e3825): COUNT DIRECTIONAL TRIPWIRE CROSSINGS ON THE GROUND PLANE,
  NOT TRACK IDENTITIES. Tracking demoted to short-transit continuity/direction.
  Accepts a per-camera homography calibration as a prerequisite in exchange for
  removing the ~2x fragmentation error by construction. Awaiting user sign-off.

## REJECTED
- Counting track identities - measured 2.01x inflation; one Jeep = 9 track IDs
- Post-hoc track stitching as the COUNTING method (tools/stitch.py) - improves
  (380->189, re-acq 46%->21%) but leaves truth between 189 and 380 and puts a
  free parameter inside the measurement (gap=2s -> 173 veh, gap=60s -> 144).
  DEMOTED to a diagnostic; the re-acquisition signature stays as tracker health.
- Pixel-domain virtual loop as the counting method - measured 79 vs YOLO's 48 on
  the same clip with no way to adjudicate, and cannot classify. Cross-check only.
- Space mean speed / platoon cross-correlation — "those things we can have for
  later, like platoon and stuff. lets do one at a time" (parked, not dead)
- Phone data for OD matrices — "I don't want to do that now"; user's Replica
  experience: hard to calibrate against real data, "not great"
- Full FHWA Scheme F (13 classes) — axle-based classes 5-13 not observable from
  an overhead camera; would be inference dressed as measurement
- MIO-TCD training dataset — CC BY-NC-ND signals (NonCommercial, NoDerivatives)
  and published by Miovision, a direct competitor
- I-880 as the corridor test bed — only 6 of 13 cameras live, 2-7 mi gaps
- Camera-specific zone/pixel tuning — user killed it as unscalable
- ~30k-instance labelling + GPU training programme for v1 — would fix detection,
  which already works at 95-99%; classification is the broken half
- Super-resolution to recover detail — hallucinates pixels, undefendable

## RESEARCH FINDINGS (storm-research 2026-10-01, 19 citations verified)
- VERIFIED: Caltrans inductive loops OVERCOUNTED 24.5% in a published head-to-head
  (3,392 vs 2,724) - the industry's reference standard is itself badly wrong.
- VERIFIED: VDOT VTRC 26-R53 certifies count devices against "absolute,
  human-verified video ground truth", 5% threshold, 8-step fail-fast protocol.
  OUR LOCKED TRUTH METHOD IS WHAT A STATE DOT USES.
- VERIFIED: NCHRP Web-Only Doc 436 (NOT peer-reviewed) - video volume WMAPE
  1.4-33.7%; loops 4.0-45.5%; authors state TURNING MOVEMENTS ARE LESS ACCURATE
  THAN THROUGH MOVEMENTS and accuracy degrades as volume rises.
- VERIFIED: ALL major public datasets are non-commercial (MIO-TCD CC BY-NC-SA 4.0,
  UA-DETRAC no grant, AI City/CityFlow NVIDIA academic-only with the ban EXTENDING
  TO MODELS TRAINED ON IT, BDD100K data non-commercial w/ BSD-3 covering toolkit
  only, VisDrone research-only). Own-labelled data is the only lawful route.
- VERIFIED: rare FHWA classes are sample-starved even WITH axle sensors
  (class 7 n=42, 11 n=47, 12 n=64 of 20,099) - a labelling ceiling on any model.
- CORRECTED: "manual counts carry 4-5% classification error by FHWA's own
  accounting" is FALSE as attributed (it is Zheng & McDonald 2012, UK) and is
  CONTESTED - Majumder & Wilmot 2023 measured 1.05%/1.08%. This materially
  rescues the objective-truth objective.
- CORRECTED: "axles are unobservable from video" - ALL FIVE lenses asserted it;
  the cited primary source (Chen et al., JCCE 39(3)) EXTRACTS axle configuration
  from video and names INTERCLASS SIMILARITY as the barrier. Partially
  rehabilitates geometric features for classification.
- Vendor "95%+" figures are self-published and uncited for classification;
  Miovision's only third-party numbers are VOLUME accuracy.
- Agency price point: ~$450 per 12-hr TMC (Fort Bend County TX, verified).

## STATE
foundation (locked, confirmed):
  objective = better traffic data to modernise the industry, not monetisation.
  scope = volumes + classification ONLY, volumes first.
  bar = 85% -> 92.75% -> 98%, per 15-min bin, vs objective truth.
  unit = 1 camera / 1 leg / 1 MINUTE, then conflict points, then 1 leg 5 min,
         then 2 legs 5 min, then scale by location.
  truth = Claude and user count independently, reconcile, version the result,
          log every disagreement.

current solution:
  live Caltrans HLS -> record -> YOLO11n detect (the only AI step, 95-99% recall
  above 60 px) -> ByteTrack -> stitch fragments using the vehicle's own bounding
  box as the ruler (max 8 vehicle-lengths/sec, max 40 s gap) -> counts.
  Classification still unsolved: COCO over-calls HV ~2x (calls Jeeps and light
  vans `truck`); plan is geometric length vs the 22 ft threshold, which needs no
  labels and no GPU.

last verified step:
  Matched-config stitching on SR-90 Harbor Blvd (421 raw tracks, 23,605 dets):
  380 fragments -> 189 vehicles, inflation was 2.01x, re-acquisition signature
  46% -> 21%. BUT 30 of 189 chains implausible (longest 137.8 s, 8 fragments),
  so over-merging is now happening alongside under-merging.
  Truth is somewhere between 189 and 380 and CANNOT be resolved without ground
  truth. The 40 s gap threshold is the one judgement call sitting inside the
  count (gap=2 gives 173 vehicles, gap=60 gives 144).

next action:
  AWAIT USER SIGN-OFF ON ADR-0001. Then action items 1-6 in that ADR:
  calibration module -> qualified zone -> directional crossing counting ->
  step-1 benchmark (one leg, one minute, Harbor Blvd, both count independently)
  -> first real number on the 85/92.75/98 ladder -> open lessons.md.
  After the spec: step 1 of the ladder - pick ONE leg at SR-90 Harbor Blvd
  (footage already on disk, 311 s, 1280x720), take ONE MINUTE of it, both
  parties count independently, reconcile, and that becomes benchmark v1.
  NOTE: the camera-source question (Caltrans vs own hardware) is NOT urgent -
  step 1 runs on footage we already have.
  Uncommitted in repo: tools/stitch.py, tools/track.py, tools/eval_stitch.py.

## MODEL TIERING (user plan, 2026-10-02)
User is switching this work to cheaper models where appropriate.
  Sonnet  -> implementing a decided design, running tests, refactoring
  Haiku   -> mechanical fan-out (image classification, citation checks)
  Opus    -> error analysis, architecture, interpreting results,
             "is this number real?" judgements
Rationale: the expensive model's value this project was almost entirely in
CATCHING ITS OWN ERRORS (a window-filter bug that made +5% look like +20%; a
fabricated vendor quote; recognising a 20/20 result was in-sample). Those are
judgement tasks. Implementation against a written ADR is not.

## BENCHMARKS
- harbor-eb-60s   : RECONCILED, reference = 20 (user-counted). SPENT as a
                    validator - it was used to find and fix a defect (L-007).
- harbor-eb-60s-B : HELD OUT, awaiting user count. Sealed prediction = 12.
                    DO NOT tune anything on this window before the user counts;
                    doing so voids it as an out-of-sample test.

## BENCHMARK DELIVERY PROTOCOL (user decision, 2026-10-02)
ONE video per benchmark, WITH the numbering/rings visible. Not two files.
User: "I wouldn't double count. If you find something there, I'll let you know
you missed it. So one time is enough... I'm living and checking, so that is
totally fine."

Claude raised the anchoring concern once; the user overrode it. Decision stands.

CONSEQUENCE TO RECORD ACCURATELY (not to re-argue): a count made while the
method's output is visible is a REVIEW, not a blind test. Label it as such in
the golden file - `count_type: "reviewed"` vs `count_type: "blind"`.
  - benchmark A  : reviewed (count first, then QA review found the false positive)
  - benchmark B  : BLIND - prediction sealed in git before the count. This is
                   the project's only true out-of-sample number so far (92.3%).
  - benchmark C+ : reviewed, per this decision.
Reviews catch error MODES better (the user can say "#4 is wrong because..."),
which is more useful for fixing the method. Blind tests are the only thing that
produces a defensible accuracy figure. If a number ever needs to leave this
project, re-run a blind benchmark for it.
