"""
cv_analyzer.py  v3  —  LOCAL CV Floor Plan Analyzer
====================================================
Honest architecture:
  - Wall detection: Canny + OTSU + morphological closing (works well)
  - Room regions: connected components on inverted wall mask (works well)
  - OCR: attempted, used when it works, skipped gracefully when it fails
  - Scale: from user-provided dimensions (best) or image proportions (fallback)
  - Room type: from OCR if available, else size heuristics
  - Doors/windows: wall gap detection
  - All sizes/positions in metres
"""

import cv2
import numpy as np
import re
from pathlib import Path

from .openings import extract_opening_candidates

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ── CONSTANTS ────────────────────────────────────────────────────────────────
DIM_RE      = re.compile(r'(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)')
MIN_ROOM_PX = 1800
MAX_FRAC    = 0.87
DEFAULT_W   = 12.0

ROOM_KEYWORDS = {
    "bed":"bedroom","bedroom":"bedroom","sleeping":"bedroom",
    "kitchen":"kitchen","kitch":"kitchen",
    "bath":"bathroom","toilet":"bathroom","wc":"bathroom",
    "w.c":"bathroom","w/c":"bathroom","lavatory":"bathroom",
    "living":"living","hall":"living","lounge":"living","drawing":"living",
    "dining":"dining",
    "varand":"verandah","veranda":"verandah","porch":"verandah",
    "balcon":"balcony","terrace":"balcony",
    "stair":"staircase","staircase":"staircase",
    "store":"store","storage":"store","utility":"store",
    "garage":"garage","parking":"garage",
    "puja":"puja_room","pooja":"puja_room","mandir":"puja_room",
    "office":"office","study":"study",
    "lobby":"lobby","foyer":"lobby","entrance":"lobby",
    "passage":"corridor","corridor":"corridor",
    "servant":"servant_room","maid":"servant_room",
}


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def analyze_floor_plan(image_path: str,
                       known_width_m : float = None,
                       known_height_m: float = None) -> dict:
    warnings = []
    img = cv2.imread(str(image_path))
    if img is None:
        return {"success":False,"error":f"Cannot load: {image_path}"}

    H, W = img.shape[:2]
    print(f"[CV] Image: {W}×{H}px")

    # 1. Preprocess
    gray, binary = preprocess(img)

    # 2. Wall mask with tuned kernel for this plan size
    wall_mask = make_wall_mask(binary, W, H)

    # 3. Find enclosed room regions
    regions = find_room_regions(wall_mask, W, H)
    print(f"[CV] Regions found: {len(regions)}")

    # 4. OCR — attempt, use if successful, skip if not
    ocr_labels = []
    if OCR_AVAILABLE:
        ocr_labels = attempt_ocr(gray, W, H)
        print(f"[OCR] Labels read: {len(ocr_labels)}")

    # 5. Scale: user input > OCR calibration > image proportion
    if known_width_m:
        scale   = known_width_m  / W
        scale_y = (known_height_m / H) if known_height_m else scale
    else:
        scale = _calibrate_scale(ocr_labels, regions, W)
        if scale is None:
            scale = DEFAULT_W / W
            warnings.append(
                f"Width assumed {DEFAULT_W}m — enter actual building width for accurate wire lengths")
        scale_y = scale
    print(f"[Scale] {scale:.5f} m/px")

    # 6. Build room objects
    rooms = build_rooms(regions, ocr_labels, scale, scale_y, H, W, wall_mask, warnings)

    # 7. Elements (CCTV cameras etc.)
    elements = detect_elements(img, gray, scale, H)

    # 8. Opening candidates are additive; legacy room openings remain intact.
    opening_candidates = extract_opening_candidates(
        wall_mask, regions, scale_x_m_per_px=scale, scale_y_m_per_px=scale_y
    )

    # 9. Confidence
    n_ocr = sum(1 for r in rooms if r["name"] != "unknown")
    conf  = min(0.92, 0.45 + 0.07*len(rooms) + 0.05*n_ocr)

    return {
        "success": True,
        "data": {
            "plan_type"        : "local_cv",
            "confidence"       : round(conf, 2),
            "unit"             : "metres",
            "site"             : {
                "total_width" : round(W * scale,   1),
                "total_height": round(H * scale_y, 1),
                "has_compound": False,
            },
            "rooms"            : rooms,
            "detected_elements": elements,
            "opening_candidates": opening_candidates,
            "electrical_hints" : [],
            "warnings"         : warnings,
            "_debug"           : {
                "image_px"     : f"{W}×{H}",
                "scale_mppx"   : round(scale, 5),
                "regions_found": len(regions),
                "ocr_labels"   : len(ocr_labels),
                "rooms_final"  : len(rooms),
                "opening_candidates": len(opening_candidates),
            },
        }
    }


# ═════════════════════════════════════════════════════════════════════════════
#  1. PREPROCESS
# ═════════════════════════════════════════════════════════════════════════════
def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if np.mean(gray) < 100:          # dark background (blueprint)
        gray = cv2.bitwise_not(gray)

    # CLAHE for local contrast
    clahe    = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)

    denoised = cv2.fastNlMeansDenoising(enhanced, h=8)

    # OTSU
    _, otsu = cv2.threshold(denoised, 0, 255,
                             cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Canny edges (catches thin internal walls that OTSU misses)
    canny   = cv2.Canny(denoised, 15, 60)

    binary  = cv2.bitwise_or(otsu, canny)
    return gray, binary


# ═════════════════════════════════════════════════════════════════════════════
#  2. WALL MASK
# ═════════════════════════════════════════════════════════════════════════════
def make_wall_mask(binary, W, H):
    # Structural walls are long, mostly horizontal/vertical strokes. Isolate
    # them before closing gaps so furniture outlines, text and sanitary
    # symbols do not become miniature room boundaries.
    short_side = min(W, H)
    line_len = max(18, int(short_side * 0.035))
    h_lines = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (line_len, 1)))
    v_lines = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_len)))
    structural = cv2.bitwise_or(h_lines, v_lines)

    # Close drawing-scale gaps in supported wall lines, then apply only modest
    # dilation. This closes doorway breaks for component segmentation without
    # erasing thin internal partitions.
    plan_diag = (W * W + H * H) ** 0.5
    kern_sz = max(3, min(9, int(plan_diag / 120)))
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (kern_sz, kern_sz))
    k_dil = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(2, kern_sz // 2), max(2, kern_sz // 2)))
    closed = cv2.morphologyEx(structural, cv2.MORPH_CLOSE, k_close, iterations=2)
    wall = cv2.dilate(closed, k_dil, iterations=1)

    # Remove tiny noise blobs.
    nb, out, stats, _ = cv2.connectedComponentsWithStats(wall, connectivity=8)
    result = np.zeros_like(wall)
    min_sz = H * W * 0.0002
    for i in range(1, nb):
        if stats[i, cv2.CC_STAT_AREA] >= min_sz:
            result[out == i] = 255
    return result

# ═════════════════════════════════════════════════════════════════════════════
#  3. ROOM REGIONS
# ═════════════════════════════════════════════════════════════════════════════
def find_room_regions(wall_mask, W, H):
    floor = cv2.bitwise_not(wall_mask)

    # Strip the drawing/page border. The actual plan is normally inset from it.
    bw = max(3, W // 60)
    bh = max(3, H // 60)
    floor[:bh, :] = 0
    floor[-bh:, :] = 0
    floor[:, :bw] = 0
    floor[:, -bw:] = 0

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(
        floor, connectivity=4)

    total = W * H
    min_room_px = max(MIN_ROOM_PX, int(total * 0.003))
    min_room_span = max(12, int(min(W, H) * 0.045))
    regions = []
    for i in range(1, num):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_room_px:
            continue
        if area / total > MAX_FRAC:
            continue
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        rw = int(stats[i, cv2.CC_STAT_WIDTH])
        rh = int(stats[i, cv2.CC_STAT_HEIGHT])

        # Long closet/furniture slivers are not occupiable rooms. The limit is
        # scale-relative and deliberately permits compact bathrooms/WCs.
        if min(rw, rh) < min_room_span:
            continue
        cx, cy = float(centroids[i][0]), float(centroids[i][1])
        asp = max(rw, rh) / max(min(rw, rh), 1)
        if asp > 12 and area < 10000:
            continue

        # Dimension bands and the page/exterior envelope can survive the
        # border strip. Reject only page-relative edge artifacts; no plan-
        # specific count, coordinate, or physical-dimension assumption is used.
        wf, hf = rw / W, rh / H
        near_left_or_right = min(x, W - (x + rw)) < W * 0.04
        near_top_or_bottom = min(y, H - (y + rh)) < H * 0.04
        if wf > 0.90 and hf > 0.90:
            continue
        if ((wf < 0.08 and hf > 0.70 and near_left_or_right) or
                (hf < 0.08 and wf > 0.70 and near_top_or_bottom)):
            continue

        regions.append({"x": x, "y": y, "w": rw, "h": rh,
                        "area": area, "cx": cx, "cy": cy})

    regions.sort(key=lambda r: r["area"], reverse=True)
    return regions

# ═════════════════════════════════════════════════════════════════════════════
#  4. OCR  (best-effort, graceful failure)
# ═════════════════════════════════════════════════════════════════════════════
def attempt_ocr(gray, W, H):
    """
    Try to read room labels and dimensions.
    Returns empty list on failure — caller handles gracefully.
    Works best on: clean digital plans, large text, high contrast.
    Less reliable on: scanned drawings, small text, lines crossing text.
    """
    labels = []
    try:
        # Upscale for better character recognition
        scale_up = max(1.0, min(4.0, 2400/max(W,H)))
        ups = cv2.resize(gray, None, fx=scale_up, fy=scale_up,
                         interpolation=cv2.INTER_CUBIC)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6,6))
        ups   = clahe.apply(ups)

        _, bin_ = cv2.threshold(ups, 0, 255,
                                cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        cfg  = r'--oem 3 --psm 11'
        data = pytesseract.image_to_data(
            bin_, config=cfg,
            output_type=pytesseract.Output.DICT)

        blocks = []
        for i in range(len(data["text"])):
            txt  = str(data["text"][i]).strip()
            conf = int(data["conf"][i])
            if not txt or conf < 35 or len(txt) < 2: continue
            bx = int(data["left"][i]   / scale_up)
            by = int(data["top"][i]    / scale_up)
            bw = int(data["width"][i]  / scale_up)
            bh = int(data["height"][i] / scale_up)
            blocks.append({"text":txt,"conf":conf,
                            "cx":bx+bw//2,"cy":by+bh//2})

        # Cluster nearby blocks and parse
        labels = _cluster_and_parse(blocks)

    except Exception as e:
        print(f"[OCR] Skipped: {e}")

    return labels


def _cluster_and_parse(blocks):
    """Cluster text blocks → parse room name + dimensions."""
    if not blocks: return []
    CLUSTER_R = 110
    used = [False]*len(blocks)
    clusters = []
    for i,b in enumerate(blocks):
        if used[i]: continue
        cl = [b]; used[i]=True
        for j,b2 in enumerate(blocks):
            if used[j] or i==j: continue
            if abs(b2["cx"]-b["cx"])<CLUSTER_R and abs(b2["cy"]-b["cy"])<CLUSTER_R:
                cl.append(b2); used[j]=True
        clusters.append(cl)

    labels = []
    for cl in clusters:
        text = " ".join(c["text"] for c in cl).strip()
        if len(text) < 2: continue
        name = _classify(text)
        w_m, h_m = _parse_dim(text)
        if name == "unknown" and w_m == 0: continue
        cx = int(np.mean([c["cx"] for c in cl]))
        cy = int(np.mean([c["cy"] for c in cl]))
        labels.append({"name":name,"w_m":w_m,"h_m":h_m,
                        "cx":cx,"cy":cy,"raw":text})
    return labels


def _classify(text):
    t = text.lower()
    for kw, rt in ROOM_KEYWORDS.items():
        if kw in t: return rt
    return "unknown"


def _parse_dim(text):
    m = DIM_RE.search(text)
    if m:
        try:
            a,b = float(m.group(1)), float(m.group(2))
            if 0.3 < a < 50 and 0.3 < b < 50:
                return round(a,2), round(b,2)
        except: pass
    return 0.0, 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  5. SCALE CALIBRATION
# ═════════════════════════════════════════════════════════════════════════════
def _calibrate_scale(labels, regions, W):
    """Use OCR dimensions + region sizes to self-calibrate scale."""
    if not labels or not regions: return None
    scales = []
    for lbl in labels:
        if lbl["w_m"] <= 0: continue
        best = min(regions, key=lambda r: ((r["cx"]-lbl["cx"])**2+(r["cy"]-lbl["cy"])**2)**0.5)
        d    = ((best["cx"]-lbl["cx"])**2+(best["cy"]-lbl["cy"])**2)**0.5
        if d < max(best["w"],best["h"])*1.5 and best["w"] > 10:
            s = lbl["w_m"] / best["w"]
            if 0.001 < s < 0.5: scales.append(s)
    return float(np.median(scales)) if len(scales) >= 2 else (scales[0] if scales else None)


# ═════════════════════════════════════════════════════════════════════════════
#  6. BUILD ROOMS
# ═════════════════════════════════════════════════════════════════════════════
def build_rooms(regions, ocr_labels, scale, scale_y, H, W, wall_mask, warnings):
    rooms = []
    used_labels = set()

    for ri, reg in enumerate(regions):
        # Try to match an OCR label to this region
        name = "unknown"
        w_m  = round(reg["w"] * scale,   2)
        h_m  = round(reg["h"] * scale_y, 2)

        rx1,ry1 = reg["x"], reg["y"]
        rx2,ry2 = rx1+reg["w"], ry1+reg["h"]

        best_lbl = None; best_d = 1e9
        for li, lbl in enumerate(ocr_labels):
            tol = 40
            if (rx1-tol <= lbl["cx"] <= rx2+tol and
                ry1-tol <= lbl["cy"] <= ry2+tol):
                d = ((lbl["cx"]-reg["cx"])**2+(lbl["cy"]-reg["cy"])**2)**0.5
                if d < best_d: best_d=d; best_lbl=(li,lbl)

        if best_lbl:
            li, lbl = best_lbl
            name = lbl["name"] if lbl["name"] != "unknown" else name
            if lbl["w_m"] > 0 and lbl["h_m"] > 0:
                ratio_w = lbl["w_m"] / max(w_m, 0.01)
                ratio_h = lbl["h_m"] / max(h_m, 0.01)
                if 0.2 < ratio_w < 5 and 0.2 < ratio_h < 5:
                    w_m = lbl["w_m"]; h_m = lbl["h_m"]
            used_labels.add(li)

        # Fallback: size-based classification
        if name == "unknown":
            name = _size_type(w_m*h_m, w_m, h_m, ri, len(regions))

        x_m = round(reg["x"] * scale,              2)
        y_m = round((H - reg["y"] - reg["h"]) * scale_y, 2)

        doors   = _detect_doors(wall_mask,   reg, W, H, scale)
        windows = _detect_windows(wall_mask, reg, W, H, scale)

        rooms.append({
            "id"     : f"room_{ri+1}",
            "name"   : name,
            "x"      : max(0.0, x_m),
            "y"      : max(0.0, y_m),
            "width"  : max(0.5, w_m),
            "height" : max(0.5, h_m),
            "area_m2": round(w_m*h_m, 1),
            "shape"  : "rectangle",
            "doors"  : doors,
            "windows": windows,
        })

    return rooms


def _size_type(area, w, h, rank, total):
    """Room type from area + position rank (large→small order)."""
    asp = max(w,h)/max(min(w,h),0.1)
    if asp > 3.5 and area < 8:   return "corridor"
    if rank == 0 and area >= 12: return "living"
    if rank == 1 and area >= 7:  return "bedroom"
    if area < 3.5:               return "bathroom"
    if area < 6:                 return "kitchen"
    return "bedroom"


# ═════════════════════════════════════════════════════════════════════════════
#  DOORS + WINDOWS
# ═════════════════════════════════════════════════════════════════════════════
DOOR_MIN,DOOR_MAX = 12,100
WIN_MIN, WIN_MAX  = 8, 70

def _gap_profile(wall_mask, x1,y1,x2,y2, axis):
    x1=max(0,x1); y1=max(0,y1)
    x2=min(wall_mask.shape[1],x2); y2=min(wall_mask.shape[0],y2)
    if x2<=x1 or y2<=y1: return np.array([])
    return np.min(wall_mask[y1:y2, x1:x2], axis=axis)

def _gaps(profile, gmin, gmax):
    gs=[]; in_g=False; s=0
    for i,v in enumerate(profile):
        if v<50 and not in_g: in_g=True; s=i
        elif v>=50 and in_g:
            in_g=False
            if gmin<=i-s<=gmax: gs.append((s,i))
    if in_g and gmin<=len(profile)-s<=gmax: gs.append((s,len(profile)))
    return gs

def _detect_doors(wm, reg, W,H,scale):
    rx,ry,rw,rh = reg["x"],reg["y"],reg["w"],reg["h"]
    doors=[]
    for wall,x1,y1,x2,y2,ax in [
        ("bottom",rx,ry+rh-5,rx+rw,ry+rh+5,0),
        ("top",   rx,ry-5,   rx+rw,ry+5,   0),
        ("left",  rx-5,ry,   rx+5, ry+rh,  1),
        ("right", rx+rw-5,ry,rx+rw+5,ry+rh,1)]:
        p=_gap_profile(wm,x1,y1,x2,y2,ax)
        if p.size==0: continue
        for gs,ge in _gaps(p,DOOR_MIN,DOOR_MAX)[:1]:
            doors.append({"wall":wall,
                          "position":round((gs+ge)/2*scale,2),
                          "width":max(0.7,round((ge-gs)*scale,2))})
    return doors[:2]

def _detect_windows(wm, reg, W,H,scale):
    rx,ry,rw,rh=reg["x"],reg["y"],reg["w"],reg["h"]
    wins=[]
    for wall,x1,y1,x2,y2,ax in [
        ("top",  rx,ry-3,rx+rw,ry+3,0),
        ("right",rx+rw-3,ry,rx+rw+3,ry+rh,1)]:
        p=_gap_profile(wm,x1,y1,x2,y2,ax)
        if p.size==0: continue
        for gs,ge in _gaps(p,WIN_MIN,WIN_MAX)[:2]:
            wins.append({"wall":wall,
                         "position":round((gs+ge)/2*scale,2),
                         "width":max(0.4,round((ge-gs)*scale,2))})
    return wins[:3]


# ═════════════════════════════════════════════════════════════════════════════
#  ELEMENTS (CCTV etc.)
# ═════════════════════════════════════════════════════════════════════════════
def detect_elements(img, gray, scale, H_px):
    elements=[]
    blurred = cv2.GaussianBlur(gray,(7,7),0)
    circles = cv2.HoughCircles(blurred,cv2.HOUGH_GRADIENT,
                               dp=1.2,minDist=30,
                               param1=60,param2=30,
                               minRadius=8,maxRadius=55)
    if circles is not None:
        for (cx,cy,r) in np.round(circles[0]).astype(int)[:8]:
            elements.append({"type":"camera","label":"",
                             "x":round(cx*scale,2),
                             "y":round((H_px-cy)*scale,2),
                             "width":round(r*2*scale,2),
                             "height":round(r*2*scale,2),
                             "notes":f"r={r}px"})
    return elements


# ══ CLI ══════════════════════════════════════════════════════════════════════
if __name__=="__main__":
    import sys
    if len(sys.argv)<2: print("Usage: python cv_analyzer.py <img> [w_m]"); sys.exit(1)
    w=float(sys.argv[2]) if len(sys.argv)>2 else None
    r=analyze_floor_plan(sys.argv[1],known_width_m=w)
    if r["success"]:
        for rm in r["data"]["rooms"]:
            print(f'  {rm["name"]:14} {rm["width"]:.1f}×{rm["height"]:.1f}m')
    else: print("FAIL:",r["error"])
