"""
ocr_reader.py
-------------
Extracts room labels and dimensions from floor plan images.
Uses Tesseract 5 with aggressive preprocessing.
Returns list of TextBlock(text, x, y, w, h, parsed_name, parsed_dims)
"""

import cv2
import numpy as np
import re
import pytesseract
from dataclasses import dataclass, field
from typing import Optional

# ── Room keyword → canonical type ──────────────────────────────────────────
ROOM_KEYWORDS = {
    "bed"        : "bedroom",
    "bedroom"    : "bedroom",
    "bed room"   : "bedroom",
    "master"     : "bedroom",
    "mbr"        : "bedroom",
    "living"     : "living",
    "living hall": "living",
    "hall"       : "living",
    "drawing"    : "living",
    "lounge"     : "living",
    "dining"     : "dining",
    "kitchen"    : "kitchen",
    "kit"        : "kitchen",
    "kitch"      : "kitchen",
    "bath"       : "bathroom",
    "bathroom"   : "bathroom",
    "toilet"     : "bathroom",
    "wc"         : "bathroom",
    "w.c"        : "bathroom",
    "w/c"        : "bathroom",
    "washroom"   : "bathroom",
    "lavatory"   : "bathroom",
    "store"      : "store",
    "storage"    : "store",
    "utility"    : "store",
    "varandah"   : "varandah",
    "veranda"    : "varandah",
    "verandah"   : "varandah",
    "balcony"    : "balcony",
    "porch"      : "varandah",
    "stair"      : "staircase",
    "stairs"     : "staircase",
    "staircase"  : "staircase",
    "stairway"   : "staircase",
    "passage"    : "corridor",
    "corridor"   : "corridor",
    "lobby"      : "corridor",
    "foyer"      : "corridor",
    "garage"     : "garage",
    "car"        : "garage",
    "pooja"      : "pooja",
    "puja"       : "pooja",
    "prayer"     : "pooja",
    "servant"    : "servant",
    "maid"       : "servant",
    "office"     : "office",
    "study"      : "office",
}

@dataclass
class TextBlock:
    text    : str
    x       : int
    y       : int
    w       : int
    h       : int
    cx      : int = 0
    cy      : int = 0
    room_type: Optional[str] = None
    dim_w   : Optional[float] = None
    dim_h   : Optional[float] = None

    def __post_init__(self):
        self.cx = self.x + self.w // 2
        self.cy = self.y + self.h // 2


# ── DIMENSION PATTERNS ──────────────────────────────────────────────────────
# Matches: 3.65X3.00  3.65x3.00  3.65×3.00  3.65*3.00  3.65 X 3.00
DIM_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*[xX×*]\s*(\d+\.?\d*)"
)


def preprocess_for_ocr(img: np.ndarray) -> list:
    """
    Generate multiple preprocessed versions for best OCR coverage.
    Returns list of processed images to try.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

    H, W = gray.shape
    # Scale up for better OCR (tesseract works best at ~200 DPI)
    scale = max(1.0, 1800 / max(H, W))
    if scale > 1.1:
        gray = cv2.resize(gray, (int(W*scale), int(H*scale)), interpolation=cv2.INTER_CUBIC)

    variants = []

    # 1. OTSU binarize
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu", otsu))

    # 2. Adaptive (for uneven lighting)
    adapt = cv2.adaptiveThreshold(gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8)
    variants.append(("adaptive", adapt))

    # 3. Denoised + OTSU
    denoised = cv2.fastNlMeansDenoising(gray, h=12)
    _, d_otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("denoised", d_otsu))

    return variants, scale


def extract_text_blocks(img: np.ndarray) -> list:
    """
    Run Tesseract on multiple preprocessed variants.
    Returns merged list of TextBlock with highest-confidence text.
    """
    variants, scale = preprocess_for_ocr(img)

    # TSV config: get bounding boxes with confidence
    cfg = r"--oem 3 --psm 11 -l eng"

    all_blocks = []

    for name, processed in variants:
        try:
            data = pytesseract.image_to_data(
                processed, config=cfg,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            print(f"[OCR] Tesseract failed on variant {name}: {e}")
            continue

        n = len(data["text"])
        for i in range(n):
            conf = int(data["conf"][i])
            txt  = str(data["text"][i]).strip()
            if conf < 30 or not txt:
                continue

            # Scale back to original image coordinates
            bx = int(data["left"][i]   / scale)
            by = int(data["top"][i]    / scale)
            bw = int(data["width"][i]  / scale)
            bh = int(data["height"][i] / scale)

            if bw < 2 or bh < 2:
                continue

            blk = TextBlock(text=txt, x=bx, y=by, w=bw, h=bh)
            _parse_block(blk)
            all_blocks.append(blk)

    # Deduplicate overlapping blocks (keep highest priority)
    merged = _merge_blocks(all_blocks, img.shape[0])
    print(f"[OCR] Extracted {len(merged)} text blocks "
          f"({sum(1 for b in merged if b.room_type)} rooms, "
          f"{sum(1 for b in merged if b.dim_w)} dims)")
    return merged


def _parse_block(blk: TextBlock):
    """Parse room type and/or dimensions from a text block."""
    txt_lower = blk.text.lower().strip()

    # Try dimension pattern
    m = DIM_PATTERN.search(blk.text)
    if m:
        try:
            blk.dim_w = float(m.group(1))
            blk.dim_h = float(m.group(2))
        except ValueError:
            pass

    # Try room keyword
    for kw, rtype in ROOM_KEYWORDS.items():
        if kw in txt_lower:
            blk.room_type = rtype
            break


def _merge_blocks(blocks: list, H: int) -> list:
    """Remove near-duplicate blocks (same position, different OCR run)."""
    if not blocks:
        return []

    seen   = []
    result = []

    for blk in blocks:
        is_dup = False
        for s in seen:
            if abs(blk.cx - s.cx) < 15 and abs(blk.cy - s.cy) < 15:
                is_dup = True
                # Keep the one with more info
                if (blk.room_type and not s.room_type) or \
                   (blk.dim_w and not s.dim_w):
                    seen.remove(s)
                    result.remove(s)
                    seen.append(blk)
                    result.append(blk)
                break
        if not is_dup:
            seen.append(blk)
            result.append(blk)

    return result


def group_text_into_labels(blocks: list) -> list:
    """
    Cluster nearby text blocks into multi-line labels.
    e.g. ["BED ROOM", "3.65X3.00"] → one label with room_type + dims
    """
    if not blocks:
        return []

    # Sort by Y then X
    blocks = sorted(blocks, key=lambda b: (b.cy, b.cx))
    used   = [False] * len(blocks)
    labels = []

    for i, b in enumerate(blocks):
        if used[i]:
            continue

        group = [b]
        used[i] = True

        for j, b2 in enumerate(blocks):
            if used[j] or j == i:
                continue
            # Same column, close vertically
            if abs(b2.cx - b.cx) < b.w * 1.5 and abs(b2.cy - b.cy) < b.h * 3:
                group.append(b2)
                used[j] = True

        # Merge group into one label
        merged_text  = " ".join(g.text for g in group)
        merged_rtype = next((g.room_type for g in group if g.room_type), None)
        merged_dimw  = next((g.dim_w for g in group if g.dim_w), None)
        merged_dimh  = next((g.dim_h for g in group if g.dim_h), None)

        # Re-parse merged text in case split label
        if not merged_rtype:
            tmp = TextBlock(merged_text, group[0].x, group[0].y,
                            group[0].w, group[0].h)
            _parse_block(tmp)
            merged_rtype = tmp.room_type

        if not merged_dimw:
            tmp = TextBlock(merged_text, group[0].x, group[0].y,
                            group[0].w, group[0].h)
            _parse_block(tmp)
            merged_dimw = tmp.dim_w
            merged_dimh = tmp.dim_h

        avg_cx = sum(g.cx for g in group) // len(group)
        avg_cy = sum(g.cy for g in group) // len(group)
        max_w  = max(g.w for g in group)
        total_h = sum(g.h for g in group)

        lbl = TextBlock(merged_text,
                        avg_cx - max_w//2, avg_cy - total_h//2,
                        max_w, total_h)
        lbl.room_type = merged_rtype
        lbl.dim_w     = merged_dimw
        lbl.dim_h     = merged_dimh
        labels.append(lbl)

    useful = [l for l in labels if l.room_type or l.dim_w]
    print(f"[OCR] Grouped into {len(useful)} useful labels")
    return useful


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
        blocks = extract_text_blocks(img)
        labels = group_text_into_labels(blocks)
        for lbl in labels:
            print(f"  [{lbl.room_type or '?':12}] {lbl.text!r:30} "
                  f"dim={lbl.dim_w}x{lbl.dim_h}  pos=({lbl.cx},{lbl.cy})")
