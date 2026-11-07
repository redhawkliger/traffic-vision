# ADR-0003: Intersection zone-gate model (mouth gates, entries and exits)

**Status:** Proposed
**Date:** 2026-10-02
**Deciders:** project owner (traffic engineer)
**Builds on:** ADR-0001 (directional line crossings); amends how lines are placed
**Motivated by:** L-012 (a line inside the box cannot isolate a movement), owner's
octagon idea (2026-10-02)

---

## Context

Volumes and classification only, volumes first. The destination is intersections:
turning movements feeding DemandIQ. ADR-0001 counts directed line crossings and
deferred entry-exit pairing. Brea (L-012) showed that a single line inside the
intersection box mixes movements that no band or angle can separate.

Owner's proposal: treat the intersection as a polygon whose edges are the leg
**mouths** (crosswalk or stop bar of each approach) joined by diagonal **corner
cuts** (an octagon on a four-leg intersection). A vehicle crossing a mouth inward is
an ENTRY for that approach; outward is an EXIT. Entry mouth + exit mouth = movement.

## Decision

Model each intersection as a set of **gates**, one per leg mouth, each a directed
line (the existing `crossings.py` line + direction, applied twice: inward and
outward). Corner cuts are not gates.

1. **Volumes first:** entries per approach are counted at each mouth with the existing
   counter. No pairing needed.
2. **Sanity check (free, no human count):** over a long window, total entries should
   approximately equal total exits for the box. Report it; do not use it to tune.
3. **Movements later:** entry mouth to exit mouth pairing through the box
   (3-10 s, vehicle moving). Weak where vehicles stop inside the box.
4. **Placement:** gates sit on the approach at the mouth, outside the conflict area,
   perpendicular to the lane direction. Each gate is **confirmed by the owner on a
   still frame before any count** (L-012 rule), with the movement stated in words.
5. **Per-camera visibility report:** for each mouth, state vehicle size
   (>=60 px), frame truncation, and maturity (tracks mature at the gate, L-011).
   A mouth that fails is reported as unmeasurable, never guessed.
6. **Auto-derivation (later):** cluster many tracks; entry and exit points concentrate
   at the mouths; propose the polygon; owner confirms.

## Brea (CCTV 510) application

Daylight frames show three clear mouths (west, north, east) and a south leg mostly
cut off at the frame bottom. Start with the visible mouths; treat south as
unmeasurable until shown otherwise. Search of 202 live D12 cameras found no camera
that clearly shows all four legs (stills were dusk and low resolution; re-screen on
daylight video).

## Consequences

**Easier:** each approach is its own gate (no overlapping movements); in = out
check; existing tools reused (`crossings.py`, `review_video.py`, site config).
**Harder:** multiple gates per intersection mean multiple reviews; pairing remains
the hardest step and depends on tracks surviving the box; near and far mouths on a
single oblique camera differ greatly in detectability.
**Needs:** a polyline/polygon site config format (today a config holds one line);
per-gate review videos.

## Action items
1. [ ] Weekday daylight Brea recording (scheduled 2026-10-05 07:45).
2. [ ] Daylight re-screen of Brea and Palm St (507) on real video frames.
3. [ ] Draw and confirm gates on a still, one mouth at a time.
4. [ ] Entries at one mouth: ladder step 1 (one leg, one minute), blind-sealed, reviewed.
5. [ ] Add in-equals-out reporting.
6. [ ] Defer: pairing, auto-derivation, classification (ADR-0002).

## Honest uncertainties
- No tested camera shows all four mouths cleanly; the model may have to run on partial
  intersections.
- In = out is a sanity check, not accuracy; errors can cancel.
- Everything so far is one Sunday and one Friday dusk; weekday daylight is untested.
