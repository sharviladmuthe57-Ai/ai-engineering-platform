"""Render reproducible room-segmentation overlays for benchmark plans."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from core.cv_analyzer import find_room_regions, make_wall_mask, preprocess


def render_segmentation(image_path: Path, output_path: Path) -> int:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to read benchmark image: {image_path}")
    height, width = image.shape[:2]
    _, binary = preprocess(image)
    regions = find_room_regions(make_wall_mask(binary, width, height), width, height)

    overlay = image.copy()
    for index, region in enumerate(regions, start=1):
        x, y, rw, rh = (region[key] for key in ("x", "y", "w", "h"))
        color = ((37 * index) % 255, (91 * index) % 255, (173 * index) % 255)
        cv2.rectangle(overlay, (x, y), (x + rw, y + rh), color, 2)
        cv2.putText(overlay, str(index), (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), overlay)
    return len(regions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(f"Rendered {render_segmentation(args.image, args.output)} room regions")


if __name__ == "__main__":
    main()
