"""Day 4 — blur faces in every frame that leaves the pipeline. Detection only, never recognition; no identities stored."""
from __future__ import annotations

import cv2
import numpy as np

_PAD = 0.25            # grow each blurred box by this share on every side, so hair and chin are covered too
_CELLS = 6             # a box is shrunk to this many pixels across and scaled back: fixed cost at any box size
_FACE_SCORE = 0.6
# YuNet runs at half size: 4× faster (crowd_02 32 → 8 ms). The small faces this loses belong to people whose box head
# band is blurred anyway; what only YuNet catches are large, close faces of people the person detector misses.
_FACE_SCALE = 0.5


class FaceBlur:
    """YuNet finds the faces that are large enough; in high, wide shots most faces are only 5–15 px, so the top
    `head_fraction` of every person box is blurred as well. Where the detector misses most people (zones counted by
    the density model) the frame gets a soft blur of about one head, so faces go but the crowd stays visible."""

    def __init__(self, face_model: str, head_fraction: float):
        self.head_fraction = head_fraction
        self.detector = cv2.FaceDetectorYN.create(face_model, "", (320, 320), _FACE_SCORE)

    def apply(self, image: np.ndarray, person_boxes, soft_zones=()) -> np.ndarray:
        """Blur in place and return `image`. `person_boxes` are (x1, y1, x2, y2) pixel boxes; `soft_zones` are
        (polygon points, sigma px) for zones to soften as a whole."""
        h, w = image.shape[:2]
        # Faces are found on the raw frame, before the soft blur would hide them from the detector.
        small = cv2.resize(image, None, fx=_FACE_SCALE, fy=_FACE_SCALE, interpolation=cv2.INTER_AREA)
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = self.detector.detect(small)
        boxes = faces[:, :4] / _FACE_SCALE if faces is not None else []
        for points, sigma in soft_zones:
            _soft_blur(image, np.int32(points), sigma)
        regions = [(x, y, x + fw, y + fh) for x, y, fw, fh in boxes]
        regions += [(x1, y1, x2, y1 + (y2 - y1) * self.head_fraction) for x1, y1, x2, y2 in person_boxes]
        for x1, y1, x2, y2 in regions:
            px, py = (x2 - x1) * _PAD, (y2 - y1) * _PAD
            x1, y1 = max(int(x1 - px), 0), max(int(y1 - py), 0)
            x2, y2 = min(int(x2 + px) + 1, w), min(int(y2 + py) + 1, h)
            if x2 - x1 < 2 or y2 - y1 < 2:
                continue
            roi = image[y1:y2, x1:x2]
            scale = _CELLS / max(x2 - x1, y2 - y1)
            small = cv2.resize(roi, (max(1, round((x2 - x1) * scale)), max(1, round((y2 - y1) * scale))),
                               interpolation=cv2.INTER_AREA)
            image[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR)
        return image


def _soft_blur(image: np.ndarray, polygon: np.ndarray, sigma: float) -> None:
    x, y, bw, bh = cv2.boundingRect(polygon)
    x, y = max(x, 0), max(y, 0)
    roi = image[y:y + bh, x:x + bw]
    mask = np.zeros(roi.shape[:2], np.uint8)
    cv2.fillPoly(mask, [polygon - (x, y)], 1)
    cv2.copyTo(cv2.GaussianBlur(roi, (0, 0), sigma), mask, roi)


def head_sigma_px(homography, polygon, head_size_m: float) -> float:
    """Gaussian sigma ≈ half a head at the zone's centre, from the homography (pixels per metre there)."""
    pts = np.asarray(polygon, np.float64)
    center = pts.mean(axis=0)
    cx, cy = homography.to_world(tuple(center))
    to_image = np.linalg.inv(homography.H)
    a, b = cv2.perspectiveTransform(np.float64([[(cx, cy), (cx + head_size_m, cy)]]), to_image)[0]
    return max(1.5, float(np.hypot(*(b - a))) / 2)
