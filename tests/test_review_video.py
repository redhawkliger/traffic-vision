"""Tests for tools/review_video.py. Run: .venv-cv/bin/python -m unittest tests.test_review_video -v
Synthetic clip, NOT Harbor: 320x240, horizontal tripwire (proves orientation/size independence)."""
import json
import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import crossings as C  # noqa: E402
import review_video as R  # noqa: E402

W, H, FPS, NF = 320, 240, 10, 60
CFG = {"line": [[20, 120], [300, 120]], "direction": "top_to_bottom",
       "heading_tol_deg": 30, "along_range": [0, 200]}   # band: x 20..220


def make_tracks():
    recs = []

    def add(tid, pts):
        for f, (x, y) in pts:
            recs.append({"f": f, "id": tid, "cx": x, "cy": y, "w": 24, "h": 24})
    # 1: down through band at f~20 ; 2: down at f~30 ; 3: down but outside band (x=280) f~35
    add(1, [(f, (100, 120 + (f - 20) * 6)) for f in range(15, 26)])
    add(2, [(f, (150, 120 + (f - 30) * 6)) for f in range(25, 36)])
    add(3, [(f, (280, 120 + (f - 35) * 6)) for f in range(30, 41)])
    # 4: crosses mostly sideways-diagonal (heading ~60 deg) f~45 -> rejected angle
    add(4, [(f, (60 + (f - 45) * 10, 120 + (f - 45) * 6)) for f in range(40, 51)])
    # 5: down at f~50 in band
    add(5, [(f, (200, 120 + (f - 50) * 6)) for f in range(45, 56)])
    return {"records": recs, "true_fps": FPS}


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.clip = os.path.join(cls.tmp, "clip.mp4")
        w = cv2.VideoWriter(cls.clip, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
        for _ in range(NF):
            w.write(np.full((H, W, 3), 60, np.uint8))
        w.release()
        cls.tracks = make_tracks()
        cls.res = C.run(cls.tracks, CFG)
        cls.out = os.path.join(cls.tmp, "review.mp4")
        cls.side = R.render(cls.clip, cls.res, CFG, cls.out, "synthetic", "blind")

    def test_counted_and_rejected(self):
        self.assertEqual(self.res["count"], 3)
        reasons = sorted(e["reject_reason"] for e in self.res["events"] if not e["counted"])
        self.assertEqual(reasons, ["angle", "band"])

    def test_numbering_stable_and_ordered(self):
        counted = [lb for lb in self.side["labels"] if lb["counted"]]
        self.assertEqual([lb["label"] for lb in counted], ["#1", "#2", "#3"])
        self.assertEqual([lb["frame"] for lb in counted], sorted(lb["frame"] for lb in counted))
        self.assertEqual([lb["track_id"] for lb in counted], [1, 2, 5])
        # rerun -> identical labels
        again = R.label_events(self.res["events"])
        self.assertEqual([l["label"] for l in again], [l["label"] for l in self.side["labels"]])

    def test_sidecar_maps_back(self):
        with open(os.path.splitext(self.out)[0] + ".labels.json") as fh:
            sc = json.load(fh)
        by = {lb["label"]: lb for lb in sc["labels"]}
        ev = {e["track_id"]: e for e in self.res["events"]}
        for lab in ("#1", "#2", "#3"):
            e = ev[by[lab]["track_id"]]
            self.assertEqual((by[lab]["frame"], by[lab]["x"], by[lab]["y"], by[lab]["heading_deg"]),
                             (e["frame"], e["x_cross"], e["y_cross"], e["heading_deg"]))
        self.assertEqual(sc["meta"]["count_type"], "blind")
        self.assertEqual((sc["meta"]["width"], sc["meta"]["height"]), (W, H))
        self.assertTrue(os.path.exists(os.path.splitext(self.out)[0] + ".labels.csv"))

    def test_rejected_shown_with_reason(self):
        rej = [lb for lb in self.side["labels"] if not lb["counted"]]
        # sidecar keeps ALL rejects with reason (angle + band) ...
        self.assertEqual(len(rej), 2)
        self.assertEqual(sorted(lb["reject_reason"] for lb in rej), ["angle", "band"])
        # ... but the band reject is not drawn (clutter outside the counting zone)
        self.assertEqual({lb["reject_reason"]: lb["draw"] for lb in rej},
                         {"angle": True, "band": False})
        angle = next(lb for lb in rej if lb["reject_reason"] == "angle")
        t = R.reject_text(angle)
        self.assertTrue(t.startswith("rejected: angle ") and t.endswith("deg"))
        self.assertEqual(self.side["meta"]["counted_drawn"], 3)
        self.assertEqual(self.side["meta"]["rejected_drawn"], 1)
        self.assertEqual(self.side["meta"]["rejected_total"], 2)
        self.assertEqual(self.side["meta"]["rejected_not_drawn_band"], 1)
        with open(os.path.splitext(self.out)[0] + ".labels.csv") as fh:
            self.assertIn("band", fh.read())

    def test_band_reject_not_drawn_in_pixels(self):
        e = next(e for e in self.res["events"] if e["reject_reason"] == "band")
        fr = self._frames()
        f = e["frame"]
        rad = int(max(14 * H / 720, min(60 * H / 720, 24 * 0.6)))
        # top of where the ring would be (off the red tripwire row); background is flat grey 60
        px = fr[f][int(round(e["y_cross"])) - rad, int(round(e["x_cross"]))]
        self.assertTrue(all(abs(int(v) - 60) < 12 for v in px), px)

    def _frames(self):
        cap = cv2.VideoCapture(self.out)
        fr = []
        while True:
            ok, im = cap.read()
            if not ok:
                break
            fr.append(im)
        cap.release()
        return fr

    def test_video_geometry_and_pixels(self):
        fr = self._frames()
        self.assertEqual(len(fr), NF)
        self.assertEqual(fr[0].shape[:2], (H, W))
        # horizontal tripwire drawn: red at (x=100, y=120) on frame 0 (BGR red dominant)
        b, g, r = (int(v) for v in fr[0][120, 100])
        self.assertTrue(r > 150 and g < 80 and b < 80, (b, g, r))
        # ring for counted #1 (track 1 at ~(100,120), f~20): green pixel ~ring radius away
        e = next(e for e in self.res["events"] if e["track_id"] == 1)
        f = e["frame"]
        rad = int(max(14 * H / 720, min(60 * H / 720, 24 * 0.6)))
        px = fr[f][int(round(e["y_cross"])), int(round(e["x_cross"])) + rad]
        self.assertTrue(px[1] > 150 and px[2] < 120, px)
        # ring gone after ~1.5 s (+ margin) at same spot
        far = fr[f + int(1.5 * FPS) + 3][int(round(e["y_cross"])) + 40, int(round(e["x_cross"]))]
        self.assertTrue(abs(int(far[1]) - int(far[2])) < 10)

    def test_vertical_line_other_size(self):
        """Different image size + vertical line, left_to_right: nothing assumes Harbor."""
        w2, h2 = 200, 400
        clip = os.path.join(self.tmp, "v.mp4")
        w = cv2.VideoWriter(clip, cv2.VideoWriter_fourcc(*"mp4v"), 10, (w2, h2))
        for _ in range(30):
            w.write(np.full((h2, w2, 3), 40, np.uint8))
        w.release()
        cfg = {"line": [[100, 50], [100, 350]], "direction": "left_to_right"}
        recs = [{"f": f, "id": 7, "cx": 60 + (f - 10) * 8, "cy": 200, "w": 20, "h": 20}
                for f in range(5, 16)]
        res = C.run({"records": recs, "true_fps": 10}, cfg)
        out = os.path.join(self.tmp, "v_review.mp4")
        side = R.render(clip, res, cfg, out, "vert", "reviewed")
        self.assertEqual((side["meta"]["width"], side["meta"]["height"]), (w2, h2))
        self.assertEqual(side["meta"]["counted_drawn"], 1)
        self.assertEqual(side["meta"]["count_type"], "reviewed")

    def test_window_and_boxes(self):
        out = os.path.join(self.tmp, "w.mp4")
        side = R.render(self.clip, self.res, CFG, out, "w", "blind", tracks=self.tracks,
                        boxes=True, window=[25, 45])
        cap = cv2.VideoCapture(out)
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 20)
        cap.release()
        # HUD running count at window start already includes #1 (f~20)
        self.assertEqual(side["meta"]["window_frames"], [25, 45])


if __name__ == "__main__":
    unittest.main()
