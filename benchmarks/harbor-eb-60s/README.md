# Benchmark: harbor-eb-60s

Reference footage for `tests/golden/harbor-eb-60s.json`.

**These files are NOT throwaway.** The golden case is meaningless without them —
every future accuracy figure is measured against this exact 60 seconds.

| File | What it is |
|---|---|
| `GT_count_clip.mp4` | The 60 s to be counted, with the tripwire drawn. **Count this.** |
| `GT_strip_0.png` / `GT_strip_1.png` | Time-space strips, 0-30 s / 30-60 s. Pixel-domain, no detector. |
| source clip | The full 311 s original lives at `data/clips/_506__Harbor_Blvd_NW_Corner.ts` (single copy, shared with benchmark B). |

## What to count

Vehicles whose body crosses the vertical line **x=600** within **y=[300,680]**,
travelling **left to right**, in frames **0-1500** (0.0-60.0 s at 25 fps true).

Excluded: right-to-left crossings; vehicles that stop short without crossing;
anything outside the y band.

## Why video is gitignored but these are kept

`.gitignore` excludes `*.mp4`, `*.ts` and `*.png` precisely so recorded Caltrans
video is never committed — partly size, partly the unresolved commercial terms of
use. These files therefore live on disk only and are **not backed up by git**.
If you clear the working tree, re-cut the window from `source_clip.ts` using the
window definition in the golden JSON.
