"""Tracker pinning: the default resolves to configs/tracker.yaml and the output header
records the tracker (never an invisible library default).
Run: .venv-cv/bin/python -m unittest tests.test_track_header -v"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import track as T  # noqa: E402

CLIP = os.path.join(ROOT, "data", "clips", "_506__Harbor_Blvd_NW_Corner.ts")


class TrackerPin(unittest.TestCase):
    def test_default_resolves_to_pinned_yaml(self):
        path, cfg = T.resolve_tracker(None)
        self.assertEqual(path, os.path.join(ROOT, "configs", "tracker.yaml"))
        self.assertEqual(cfg["tracker_type"], "tracktrack")
        self.assertEqual((cfg["track_high_thresh"], cfg["new_track_thresh"],
                          cfg["track_low_thresh"]), (0.25, 0.25, 0.1))

    def test_bare_name_resolves_to_installed(self):
        path, cfg = T.resolve_tracker("bytetrack.yaml")
        self.assertTrue(os.path.isabs(path) and os.path.exists(path))
        self.assertEqual(cfg["tracker_type"], "bytetrack")

    def test_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            T.resolve_tracker("nope_not_a_tracker.yaml")

    @unittest.skipUnless(os.path.exists(CLIP), "harbor clip not on disk")
    def test_header_records_tracker(self):
        d = T.track(CLIP, skip=3, imgsz=320, start=0, end=9)
        self.assertEqual(d["tracker_yaml"], os.path.join(ROOT, "configs", "tracker.yaml"))
        self.assertEqual(d["tracker_name"], "tracktrack")
        self.assertEqual(d["tracker_config"]["new_track_thresh"], 0.25)
        self.assertEqual(d["tracker_config"]["track_low_thresh"], 0.1)


if __name__ == "__main__":
    unittest.main()
