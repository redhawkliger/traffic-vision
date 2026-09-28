# traffic-vision

Vehicle counting and classification from traffic camera video — starting with
public Caltrans CCTV, aimed at intersection turning-movement counts.

Feeds [DemandIQ](https://github.com/redhawkliger/demandiq) later via API or file
exchange. Deliberately a **separate repo**: the CV stack is ~1.2 GB of
torch/opencv and has no business near DemandIQ's lean production image.

> **Status: research.** Nothing here is a product yet. The `spike/` directory is
> throwaway code kept only for reference — see the warning in `spike/README.md`.

---

## The single most important thing on this page

**Manifest resolution does not mean image quality, and image quality is not the
binding constraint — framing is.**

| Camera | Stream says | Bitrate | Median vehicle | Usable (≥60 px) |
|---|---|---:|---:|---:|
| I-710 @ Long Beach Blvd (freeway) | 1920×1080 | 113 kbps | **33 px** | **13%** |
| SR-90 @ Harbor Blvd (intersection) | 1280×720 | — | **61 px** | **51%** |

The *lower-resolution* camera produces vehicles **1.85× larger** and four times
the usable share, because it points at a confined intersection box instead of a
mile of freeway. Select cameras by **pixels-per-vehicle**, never by resolution.

---

## Design principles (learned the hard way)

1. **Every threshold in physical units — feet, seconds, mph — never pixels.**
   A pixel means something different on every camera. Physical units transfer;
   pixel thresholds are per-site tuning, which is a consulting engagement rather
   than a product. Per camera there should be exactly ONE site-specific step:
   calibration (pixels → feet), which is automatable from painted lane markings
   (MUTCD: 10 ft stripe, 30 ft gap; 12 ft lanes).

2. **AI finds *where* a vehicle is. Deterministic code measures *what* it is.**
   The measurement is what an engineer has to defend. "A neural network said so"
   is not defensible; "measured at 23 ft, over the FHWA 22 ft threshold" is.

3. **Classify the track, not the frame.** A vehicle is seen 30–100 times.
   Aggregate; don't trust any single frame.

4. **Site qualification is a gate, not a tuning knob.** Some cameras are simply
   unusable (tree across the view, mounted too low). Screen and reject them
   automatically; do not tune around them.

---

## Measured facts about the Caltrans CCTV feed

Status JSON URL pattern — directory unpadded, filename zero-padded:

```
https://cwwp2.dot.ca.gov/data/d{n}/cctv/cctvStatusD{n:02d}.json
```

- **3,591 cameras** statewide; **2,305** publish an HLS stream.
- **Live-only.** ~30 s rolling window (3 × 10 s segments). **No archive** — a
  peak-hour count must be recorded in real wall-clock time.
- Resolutions vary 320×240 → 1920×1080; **1280×720 is the most common** among
  live cameras.
- **Uptime is worse than a snapshot suggests.** Over 4 h 21 m polling 60 cameras
  every 2 min: **26 always up, 15 always down, 19 flapping**, mean 42.4/60 (71%).
  **42% of ever-live cameras drop out and return.** A count period must verify
  continuous availability and invalidate periods that fragment.
- **A working still image does NOT imply a working stream.** All five District 6
  intersection cameras served a fresh JPEG but returned **404 on the HLS
  stream**. Always verify the stream.
- Reported frame rate in container metadata is often **wrong** (one camera
  declared 30 fps and delivered 10.8). Always compute `frames / duration`.

### Intersections do exist on Caltrans cameras

State highways include surface arterials with signalised intersections. Sweeping
all 3,591 cameras by name and classifying the stills gave **A=20, B=14, C=77,
D=23** of 136 candidates — and the usable set is essentially **one corridor**:

**SR-90 (Imperial Hwy), District 12 / Orange County** — 23 cameras, 20 with
streams, all live, all 1280×720, at consecutive signalised intersections
(500) Beach Blvd → (520) Rose Dr. Cameras sit at a named corner looking across
the intersection box. Stream URL form:
`wzmedia.dot.ca.gov/D12/EB90HarborBlvd.stream/playlist.m3u8`

This is a free, public, fully-instrumented arterial corridor — and it maps
directly onto DemandIQ's corridor model.

---

## Traps found (each cost real time)

| Trap | Detail |
|---|---|
| **Confidence threshold dominates at night** | Default `conf=0.25` discarded ~80% of night vehicles (detected at 0.15–0.24). Raw detections on one frame: 3 → 32 by lowering to 0.10. Model *size* bought almost nothing (yolo11s at 3× compute: 12.4 vs 12.2 det/frame). |
| **ByteTrack `new_track_thresh` also defaults to 0.25** | So a vehicle never scoring above 0.25 can never *start* a track. Fixing only `conf` half-fixes it and looks like partial improvement. |
| **Track fragmentation inflates counts ~2.14×** | At SR-90 Harbor Blvd: 421 tracks, but **53% look like continuations** of another track. One tan Jeep produced **nine separate track IDs in 13.7 s**. 46% of tracks live < 2 s where a crossing takes 5–15 s. |
| **50% of track deaths are far-field** | Vehicles shrink below detection range. Only 27% die while stopped. |
| **COCO over-calls heavy vehicles** | Under FHWA 4–13, pickups/Jeeps/light vans are **Car**, but COCO labels them `truck`. The same Jeep was called `truck` 6× and `car` 3× within 14 s — frame-level instability, not a hard case. |
| **The Caltrans logo watermark detects as a `truck`** | Burned into every frame of every camera statewide. Mask overlay regions before counting. |
| **Frame-edge tests mislead** | The far approach sits in the image *interior*, so edge-based entry/exit logic scores legitimate movements as broken. Cluster track endpoints instead. |
| **MIO-TCD is likely unusable commercially** | Associated materials reference **CC BY-NC-ND 4.0** (NonCommercial, NoDerivatives), and it is published by **Miovision** — a direct competitor. Verify before it is load-bearing. |

---

## Classification scheme

Body-type based, because **FHWA Scheme F is not recoverable** from an overhead
camera — classes 5–13 are defined by axle count and trailer configuration, which
the imagery does not contain.

| Class | Definition | Typical length |
|---|---|---|
| **Car** | FHWA 1–3: sedan, SUV, **pickup**, minivan, light van (single rear wheels) | 15–20 ft |
| **HV** | FHWA 4–13: box/straight truck, dump, bus, semi (dual rear wheels) | 30–73 ft |
| **Motorbike** | motorcycle, scooter | — |
| Ped / Bike | intersections only — absent on freeways | — |

Visual test: **single rear wheels = Car, dual rear wheels = HV.**

The Car/HV boundary lands in a natural gap at **~22 ft** — nothing normally lives
between 20 and 25 ft. A car is 15 ft and a semi is 73 ft, nearly 5× apart, so
length survives low resolution: it is a *position* measurement, not a *texture*
measurement.

### Class prevalence (measured, SR-90 Harbor Blvd)

~86% Car, ~6.5% HV, ~0.4% Motorbike. To collect 2,000 training instances:

| Class | Vehicles needed | Footage |
|---|---:|---:|
| Car | 2,300 | ~1 hour |
| HV | 31,000 | ~12 hours |
| Motorbike | 500,000 | **~200 hours** |

Rare classes set the entire data-collection budget. Collect where the rare class
lives (HV → I-710 port corridor on a **weekday**), don't sample uniformly.

---

## Hardware notes

- Development machine is **Intel** macOS: **torch 2.2.2 is the last available
  wheel**. `ultralytics` pins only `torch>=1.8.0`, so current versions work.
- No CUDA and no Apple MPS on Intel — **CPU-only is the ceiling** locally.
- Measured: yolo11n @ 960 px ≈ **215 ms/frame**; @ 640 px ≈ 133 ms/frame.
  Processing ran at **5.5 fps against a 30 fps stream** — continuous
  multi-camera monitoring is a **GPU problem, not an algorithm problem**.
- Inference is fine on CPU. Training is not: ~5 days locally vs ~1.5 h on a
  rented GPU (~$1–3 for a full fine-tune).

---

## Open questions

- [ ] **Caltrans CCTV terms of use for commercial products** — the risk that
      could void the whole approach. Unresolved.
- [ ] **Detection recall vs pixels-per-vehicle curve** — measure across the three
      recorded SR-90 cameras. If it holds across sites it is a property of the
      model, and any new camera can then be screened with no labelling at all.
- [ ] **Ground truth.** No human count has been completed. No accuracy figure
      here is validated; none should be quoted until one is.
- [ ] Whether one corner camera resolves all 12 turning movements.
- [ ] PTZ re-aim detection (invalidates calibration silently).

---

## Layout

```
tools/   reusable: camera discovery, HLS recorder, measurement
spike/   THROWAWAY research code — see spike/README.md
docs/    findings and figures
```
