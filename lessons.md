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
