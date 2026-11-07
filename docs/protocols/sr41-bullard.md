# SR-41 Bullard Ave benchmark protocol

STATED IN WRITING BEFORE ANY CROSSING COUNT EXISTS. 2026-10-05.

## Site
SR-41 at Bullard Ave, Caltrans D6, CCTV `41_Bullard`. 1920x1080.
Clip: data/clips/sr41_bullard_mon_20261005.ts, Monday 2026-10-05 ~15:22-15:32 PDT.

## Lines - DERIVED, not drawn
configs/bullard-streams-proposed.json, from 18,270 frames of motion:
  stream 1  dir +156.8 deg  tol +-16.1  (measured heading spread p95 = 11.5)
  stream 2  dir  -45.1 deg  tol +-29.4  (measured heading spread p95 = 21.0)
Tolerance rule: p95 * 1.4, capped at (angular separation / 2 - 10). Separation
is 158.1 deg, so neither stream can leak into the other.
Line position rule: 65th percentile along each stream's own travel path, so
vehicles are tracked well before crossing (counters L-011 track-birth).

## VERIFICATION SEGMENT - never a benchmark
frames 15000-15900 (clip t ~500-530 s). Used ONLY to check that the derived
lines cover every lane, that real crossing headings fall inside the tolerance,
and to measure the detector-vs-tracker gap (the mechanism that hid the 8-second
truck at Brea). Anything learned here may change the config. It is therefore
IN-SAMPLE and can never be quoted as an accuracy.

## BENCHMARK WINDOW RULE - fixed now
The benchmark window is the 120 s with the most vehicle DETECTIONS inside the
two line bands, measured from a detection pass sampled every 25 frames, and
EXCLUDING any frame in the verification segment. Never chosen from crossing
output. 120 s because L-008 requires N >= 50 subjects; this site yields far more.

## Order of operations
1. detection-density pass (no tracking, no crossings)
2. track + verify on the verification segment; fix the config if it is wrong
3. FREEZE the config and commit it
4. select the benchmark window by the rule above
5. track it, count, SEAL the prediction in git
6. only then render the review video for the owner

## What must be reported with any number
- the count AND its sweep range across tolerance and band shifts (L-001/L-002)
- maturity per line segment
- detector-vs-tracker gap on the benchmark window
- count_type: reviewed (owner delivery protocol - one numbered video)
