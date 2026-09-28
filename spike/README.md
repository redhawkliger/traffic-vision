# THROWAWAY SPIKE CODE — DO NOT BUILD ON THIS

Everything in this directory is research scaffolding from 2026-09-26/27. It
answered questions and is kept only so the answers can be reproduced or
re-checked.

**It is not a foundation.** Known and deliberate problems:

- Hardcoded absolute paths to `~/Desktop/spike_cv/`
- Several scripts were produced by `sed`-patching other scripts
- **Every threshold is in pixels**, which is the exact anti-pattern the project
  rejected: pixel thresholds are per-camera tuning and do not transfer. Anything
  reused must be re-expressed in feet / seconds / mph via calibration.
- No tests, no error handling, no argument validation
- Tracker parameters were hand-tuned for one night-time freeway clip
  (`night_bytetrack.yaml`)

## What each file did

| File | Purpose | Superseded by |
|---|---|---|
| `record.py` | HLS segment recorder | `tools/record.py` |
| `track.py`, `track_night.py` | YOLO + ByteTrack over a clip | — |
| `count.py`, `count_night.py` | Screenline crossing counts | — |
| `analyze.py` | Trajectory structure, flow direction | — |
| `render2.py`, `render_night.py` | Annotated verification video | — |
| `crops.py` | One best crop per track | `tools/measure.py` |
| `uptime_probe.py` | Camera availability over time | — |
| `night_bytetrack.yaml` | Night-tuned tracker config | — |

## What was actually learned

See the root `README.md`. The findings are the durable output; this code is not.

## Reproducing

Needs an isolated venv (~1.2 GB, Intel macOS ceiling is torch 2.2.2):

```bash
python3.12 -m venv .venv-cv
./.venv-cv/bin/pip install "numpy<2" torch==2.2.2 torchvision==0.17.2 opencv-python ultralytics
```
