"""Tests for tools/crossings.py. Run: .venv-cv/bin/python -m unittest tests.test_crossings -v
(also collectable by pytest). Harbor values appear ONLY here and in configs/harbor-eb.json."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import crossings as C  # noqa: E402

TRACKS = os.path.join(ROOT, "data", "tracks", "harbor_tracks_lowthresh.json")
HARBOR = json.load(open(os.path.join(ROOT, "configs", "harbor-eb.json")))
WIN_A, WIN_B = [0, 1500], [3000, 4500]


def harbor(window, along_range=None, tol=None):
    cfg = copy.deepcopy(HARBOR)
    cfg["window_frames"] = window
    if along_range:
        cfg["along_range"] = along_range
    if tol is not None:
        cfg["heading_tol_deg"] = tol
    return cfg


@unittest.skipUnless(os.path.exists(TRACKS), "harbor tracks file not on disk")
class HarborReproduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.load(open(TRACKS, encoding="utf-8"))

    def test_A_is_20_with_zone_fixed_band(self):
        self.assertEqual(C.run(self.data, harbor(WIN_A))["count"], 20)

    def test_B_is_13_with_zone_fixed_band(self):
        self.assertEqual(C.run(self.data, harbor(WIN_B))["count"], 13)

    def test_B_is_12_with_old_band_y300_680(self):
        # along_range [0,380] on a line starting at y=300 == y in [300,680]
        self.assertEqual(C.run(self.data, harbor(WIN_B, [0, 380]))["count"], 12)

    def test_A_old_band_still_20(self):
        self.assertEqual(C.run(self.data, harbor(WIN_A, [0, 380]))["count"], 20)

    def test_sweep_present_and_range_reported(self):
        res = C.run(self.data, harbor(WIN_B))
        sw = res["summary"]["sweep"]
        self.assertEqual({s["heading_tol_deg"] for s in sw}, {20, 25, 30, 35})
        lo, hi = res["summary"]["sweep_range"]
        self.assertLessEqual(lo, res["count"])
        self.assertGreaterEqual(hi, res["count"])
        self.assertIn("sweep range", C.format_report(res))

    def test_event_fields(self):
        e = C.run(self.data, harbor(WIN_A))["events"][0]
        for k in ("track_id", "frame", "t", "x_cross", "y_cross", "heading_deg", "obs_before",
                  "travel_before_in_widths", "bbox_w_at_cross", "born_x", "born_y", "born_frame",
                  "end_x", "end_y", "end_frame", "counted", "reject_reason", "near_duplicate_of"):
            self.assertIn(k, e)

    def test_one_event_per_track(self):
        ids = [e["track_id"] for e in C.run(self.data, harbor(WIN_A))["events"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_maturity_reported(self):
        m = C.run(self.data, harbor(WIN_B))["summary"]["maturity_by_segment"]
        self.assertEqual(len(m), 4)
        self.assertTrue(all("verdict" in s for s in m))


# ------------------------------------------------------------ synthetic tracks
def trk(tid, pts, w=40, h=40, f0=0, step=3):
    return [{"f": f0 + i * step, "id": tid, "cx": x, "cy": y, "w": w, "h": h}
            for i, (x, y) in enumerate(pts)]


def data_of(*tracks):
    return {"true_fps": 25.0, "records": [r for t in tracks for r in t]}


class SyntheticOtherOrientation(unittest.TestCase):
    """Horizontal line y=100, direction top_to_bottom, in a made-up 500x500 space."""
    CFG = {"line": [[50, 100], [450, 100]], "direction": "top_to_bottom", "heading_tol_deg": 30}

    def vertical_down(self, tid, x, f0=0):
        return trk(tid, [(x, 40 + 20 * i) for i in range(10)], f0=f0)  # crosses y=100

    def test_counts_top_to_bottom_only(self):
        up = trk(2, [(200, 160 - 20 * i) for i in range(10)])           # bottom_to_top
        res = C.run(data_of(self.vertical_down(1, 200), up), self.CFG)
        self.assertEqual(res["count"], 1)
        self.assertEqual(res["events"][0]["track_id"], 1)
        self.assertAlmostEqual(res["events"][0]["y_cross"], 100.0, places=1)
        self.assertAlmostEqual(res["events"][0]["x_cross"], 200.0, places=1)

    def test_left_to_right_motion_not_counted_by_horizontal_line_config(self):
        lr = trk(3, [(20 + 30 * i, 100) for i in range(10)])           # parallel, never crosses
        self.assertEqual(C.run(data_of(lr), self.CFG)["count"], 0)

    def test_angle_reject(self):
        # crosses y=100 but travelling mostly sideways (~72 deg off direction)
        shallow = trk(4, [(100 + 60 * i, 90 + 5 * i) for i in range(6)])
        res = C.run(data_of(shallow), self.CFG)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["events"][0]["reject_reason"], "angle")
        self.assertGreater(res["events"][0]["heading_deg"], 60)
        # but a generous tolerance accepts it: the tolerance is an input
        cfg = dict(self.CFG, heading_tol_deg=88)
        self.assertEqual(C.run(data_of(shallow), cfg)["count"], 1)

    def test_band_reject_along_line(self):
        t = self.vertical_down(5, 460)                                  # beyond segment end x=450
        res = C.run(data_of(t), self.CFG)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["events"][0]["reject_reason"], "band")
        cfg = dict(self.CFG, along_range=[0, 100])                       # only x in [50,150]
        self.assertEqual(C.run(data_of(self.vertical_down(6, 100)), cfg)["count"], 1)
        self.assertEqual(C.run(data_of(self.vertical_down(7, 300)), cfg)["events"][0]["reject_reason"], "band")

    def test_window_applies_to_crossing_frame_not_track_start(self):
        # starts at frame 0 (inside window) but crosses y=100 at frame ~12 (outside [0,6))
        t = self.vertical_down(8, 200)
        cfg = dict(self.CFG, window_frames=[0, 6])
        res = C.run(data_of(t), cfg)
        self.assertEqual(res["count"], 0)
        self.assertEqual(res["events"][0]["reject_reason"], "window")
        # starts BEFORE the window, crosses inside it -> counted
        t2 = self.vertical_down(9, 200, f0=-6)
        cfg2 = dict(self.CFG, window_frames=[0, 100])
        self.assertEqual(t2[0]["f"], -6)
        self.assertEqual(C.run(data_of(t2), cfg2)["count"], 1)

    def test_one_event_per_track_even_if_recrossing(self):
        pts = [(200, 40 + 20 * i) for i in range(6)] + [(200, 140 - 20 * i) for i in range(6)] \
            + [(200, 40 + 20 * i) for i in range(6)]                    # down, up, down again
        res = C.run(data_of(trk(10, pts)), self.CFG)
        self.assertEqual(res["count"], 1)
        self.assertEqual(len(res["events"]), 1)

    def test_no_merging_near_duplicates_reported(self):
        a = self.vertical_down(11, 200)
        b = self.vertical_down(12, 205, f0=3)                            # same vehicle, new id
        res = C.run(data_of(a, b), self.CFG)
        self.assertEqual(res["count"], 2)                                # NOT collapsed
        dup = {e["track_id"]: e["near_duplicate_of"] for e in res["events"]}
        self.assertEqual(dup[12], 11)
        self.assertIsNone(dup[11])

    def test_far_apart_not_flagged_duplicate(self):
        a = self.vertical_down(13, 100)
        b = self.vertical_down(14, 400, f0=3)
        res = C.run(data_of(a, b), self.CFG)
        self.assertTrue(all(e["near_duplicate_of"] is None for e in res["events"]))

    def test_tilted_line_and_vector_direction(self):
        # 45-degree line, direction given as a vector
        cfg = {"line": [[0, 0], [200, 200]], "direction": [1, -1], "heading_tol_deg": 30}
        t = trk(15, [(40 + 20 * i, 160 - 20 * i) for i in range(8)])    # moves (+1,-1), crosses x=y
        self.assertEqual(C.run(data_of(t), cfg)["count"], 1)
        back = trk(16, [(160 - 20 * i, 40 + 20 * i) for i in range(8)])
        self.assertEqual(C.run(data_of(back), cfg)["count"], 0)

    def test_maturity_flags_zone_with_only_born_past_tracks(self):
        # vehicles born just downstream of the line (y 110) can never cross it
        late = [trk(20 + i, [(100 + 80 * i, 110 + 25 * k) for k in range(8)]) for i in range(3)]
        res = C.run(data_of(*late), dict(self.CFG, n_segments=2))
        segs = res["summary"]["maturity_by_segment"]
        self.assertEqual(res["count"], 0)
        self.assertEqual(sum(s["born_past_line"] for s in segs), 3)
        self.assertIn("NO_MATURE_ZONE", [s["verdict"] for s in segs])

    def test_sweep_present(self):
        res = C.run(data_of(self.vertical_down(1, 200)), self.CFG)
        self.assertEqual(len(res["summary"]["sweep"]), 4 * 7)

    def test_bad_direction_parallel_to_line(self):
        with self.assertRaises(ValueError):
            C.Geometry([[0, 0], [10, 0]], "left_to_right")


if __name__ == "__main__":
    unittest.main()
