"""Read the roadway with a model trained for driving scenes, instead of colour rules.

SegFormer fine-tuned on Cityscapes labels every pixel with the classes a driving
dataset cares about - road, sidewalk, car, pole, vegetation, terrain. Class 0 is
`road`: the drivable carriageway, which is exactly the thing a counting line must
span. Runs ONCE per camera on a vehicle-free median background, so CPU is fine.

    python tools/roadseg.py BACKGROUND --out mask.png --viz viz.jpg
"""
from __future__ import annotations
import argparse
import cv2, numpy as np, torch
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

MODEL = "nvidia/segformer-b0-finetuned-cityscapes-1024-1024"
ROAD, SIDEWALK, CAR, TRUCK, BUS = 0, 1, 13, 14, 15

def segment(bgr: np.ndarray):
    proc = SegformerImageProcessor.from_pretrained(MODEL)
    net = SegformerForSemanticSegmentation.from_pretrained(MODEL).eval()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        out = net(**proc(images=rgb, return_tensors="pt")).logits
    up = torch.nn.functional.interpolate(out, size=bgr.shape[:2], mode="bilinear",
                                         align_corners=False)
    return up.argmax(1)[0].cpu().numpy().astype(np.int32)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("background"); ap.add_argument("--out"); ap.add_argument("--viz")
    a = ap.parse_args()
    bg = cv2.imread(a.background)
    lab = segment(bg)
    road = (lab == ROAD).astype(np.uint8) * 255
    road = cv2.morphologyEx(road, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    print(f"road pixels: {100*(road>0).mean():.1f}% of frame")
    for name, idx in (("road", ROAD), ("sidewalk", SIDEWALK), ("car", CAR)):
        print(f"  class {idx:2d} {name:9s} {100*(lab==idx).mean():5.1f}%")
    if a.out: cv2.imwrite(a.out, road); print("wrote", a.out)
    if a.viz:
        v = bg.copy()
        v[road > 0] = (0.45 * v[road > 0] + 0.55 * np.array([0, 230, 255])).astype(np.uint8)
        cv2.putText(v, "SegFormer/Cityscapes class 'road'", (24, 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 6)
        cv2.putText(v, "SegFormer/Cityscapes class 'road'", (24, 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 230, 255), 2)
        cv2.imwrite(a.viz, v); print("wrote", a.viz)

if __name__ == "__main__":
    main()
