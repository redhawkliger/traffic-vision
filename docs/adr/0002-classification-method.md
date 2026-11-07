# ADR-0002: Classify by measured geometry first; learn from own labels only where geometry fails

**Status:** Proposed
**Date:** 2026-10-02
**Deciders:** project owner (traffic engineer)
**Depends on:** ADR-0001 (crossings counted on the ground plane, calibrated)

---

## Context

Scope is volumes + classification; volumes came first and now have a measured
baseline (benchmark A 20/20 in-sample, benchmark B out-of-sample, see
`lessons.md`). Classification is the second half and is **unsolved**.

**Locked classes:** Car, HV, Motorbike (Ped/Bike at intersections later).
HV = FHWA 4-13. Pickups, SUVs, Jeeps, light vans are CAR. Visual rule: single
rear wheels = Car, dual rear wheels = HV. FHWA length boundary ~22 ft
(car ~15 ft, semi ~73 ft). Full Scheme F (13 classes) is REJECTED: axle classes
5-13 are not observable from this viewpoint.

**Measured so far**
- COCO class labels over-call HV ~2x (Jeeps and light vans come out as `truck`).
- Detection itself is 95-99% above 60 px vehicle width, so the detector is not
  the bottleneck (L-011: three of five defects had nothing to do with model
  capability).
- Every public training dataset is non-commercial (MIO-TCD, UA-DETRAC, AI City,
  BDD100K, VisDrone). Own-labelled data is the only lawful training route.
- Rare classes are sample-starved even with axle sensors (class 7 n=42 of 20,099)
  - a labelling ceiling, which is one reason 13 classes is rejected.

**Tension to resolve.** The *locked rule* (dual rear wheels) is a wheel-count
rule; the *planned method* (length vs 22 ft) is a size rule. They disagree on
real vehicles: a crew-cab pickup is ~19-22 ft and single-rear-wheel (Car by the
rule, borderline by length); a dually or box truck is HV by wheels. Length is a
proxy for the rule, not the rule. The proxy's error rate has never been measured.

**Constraint on any length measurement.** Length from a bounding box on an oblique
camera is NOT vehicle length: the box includes the vehicle's height projection and
perspective. A ground-plane homography is exact only for points on the ground, so
box-derived "feet" is biased. This must be measured, not assumed.

---

## Decision

Classification is decided by **evidence in this order**, and nothing is adopted
until it beats the previous rung on a labelled held-out set:

1. **Truth first.** Extend the golden schema to one class label per counted
   vehicle (`class`, `count_type`, `provenance`). Class labels are produced by the
   locked truth method (independent label, reconcile, log disagreements).
   Rare-class sample size is recorded; a class with too few examples is reported
   as "not measurable yet", never given an accuracy.
2. **Baseline = Option B (calibrated geometry)** using ground-contact length where
   measurable, evaluated against the labels. No labels needed to *run* it, only to
   *score* it.
3. **Escalate to Option C (own-labelled crop classifier) only for the confusion
   cells geometry demonstrably cannot separate** (expected: crew-cab pickups /
   vans vs dually / box trucks).
4. Option A (COCO label mapping) is retained only as a measured comparator.

Per L-001/L-002: every free parameter (the length threshold, the box-to-ground
correction) is swept and the **range is reported**, never a single tuned value.
Per L-007: a threshold tuned on a benchmark is in-sample on that benchmark.

---

## Options considered

### A - Map detector (COCO) class labels *(rejected as method, kept as comparator)*
Measured ~2x HV over-call. Zero effort, known wrong.

### B - Calibrated geometric length vs ~22 ft *(baseline)*
| Dimension | Assessment |
|---|---|
| Labels needed | None to run; some to score |
| GPU | None |
| Principled | Matches FHWA length boundary, physical units |
| Risk | Box != vehicle length on oblique view; length != dual-wheel rule; length threshold is a free parameter in the measurement (L-001) |

### C - Own-labelled crop classifier (fine-tuned small model) *(conditional)*
| Dimension | Assessment |
|---|---|
| Labels needed | Hundreds to thousands of own crops; HV minority class is scarce |
| Legal | Clean (own data), unlike every public dataset |
| Risk | Sample-starved HV; in-sample overfit to ONE camera/one Sunday; GPU/Intel-Mac constraints (no torch past 2.2.2) |
| Upside | Can learn the visual dual-wheel / cab cues geometry cannot |

### D - Ensemble / bigger model *(rejected for now)*
L-011 tested 18 model configs on a failing frame: all detected the vehicle.
Ensembling fixes detection error; classification error here is a rule-definition
and measurement problem. Revisit only if per-class confusion analysis shows it.

### E - Full FHWA Scheme F *(already rejected)*
Axle classes unobservable; inference dressed as measurement.

---

## Consequences

**Easier:** classification can be wrong without corrupting volumes (ADR-0001
decoupling); no labels or GPU to get a first honest number.

**Harder:** needs a labelled class column before any accuracy is quotable; the
box-vs-length bias needs its own measurement; HV will be small-N, so per-class
accuracy will be granular (see L-008) and may be unmeasurable at 1-minute scale.

**Interaction with the accuracy ladder:** stage targets (85 / 92.75 / 98) were
defined on volumes. Per-class targets are NOT yet defined - **open decision for
the owner** (see below). Total-volume accuracy and per-class accuracy must be
reported separately.

---

## Action items
1. [ ] Extend golden-file schema with per-vehicle class + provenance.
2. [ ] Label classes for benchmarks A and B (reviewed pass, per L-009).
3. [ ] Score Option A (COCO) as the comparator.
4. [ ] Measure box-length bias vs. true length on known-length reference vehicles
       (buses/semis/standard cars) via the calibration module.
5. [ ] Score Option B with a threshold sweep; report the range.
6. [ ] Build the confusion matrix; only then decide whether Option C is needed.
7. [ ] Record every class disagreement in `lessons.md`.

## Decisions (owner, 2026-10-02)
1. **Targets apply per class.** The 85 / 92.75 / 98 ladder is used for each class
   (Car, HV, Motorbike) as well as for volumes, on the SAME benchmarks. Exact
   metric (per-class recall vs per-vehicle) is to be pinned when classification
   starts; per-class recall is the interpretation that cannot be gamed by
   calling everything Car.
2. **Rule vs proxy: UNDECIDED, deferred.** Owner notes the dual-rear-wheel rule
   may be unobservable (often only one side/wheel is visible, e.g. vehicle seen
   side-on). That is a real risk to the rule as a TRUTH definition. To be settled
   from evidence when classification starts: check on actual crops how often the
   rear axle is visible, and whether truth is "human's FHWA-type judgment" with
   wheels as one cue.
3. **Ordering: volumes first.** ADR-0002 stays Proposed and PARKED. Fix tripwire
   placement (L-010/L-011), get volumes right, then start classification.

## Honest uncertainties
- Option B's viability rests on an untested assumption (box-derived length is
  usable). It may fail outright on oblique views.
- Only one camera, one Sunday, ~34 labelled vehicles in existence.
- No class ground truth exists today; every class figure so far is a comparison
  to a human impression.
