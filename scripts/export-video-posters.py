"""Extract small local fallback posters from the seven supplied videos."""
from pathlib import Path
import cv2

root = Path(__file__).resolve().parents[1] / "public" / "videos"
for index in range(1, 8):
    capture = cv2.VideoCapture(str(root / f"scene-{index:02}.mp4"))
    capture.set(cv2.CAP_PROP_POS_MSEC, 500)
    ok, frame = capture.read()
    if not ok:
        raise RuntimeError(f"Cannot decode scene {index}")
    height, width = frame.shape[:2]
    resized = cv2.resize(frame, (1280, round(height * 1280 / width)))
    cv2.imwrite(str(root / f"poster-{index}.webp"), resized, [cv2.IMWRITE_WEBP_QUALITY, 72])
    print(f"Scene {index}: {width}x{height}, {capture.get(cv2.CAP_PROP_FPS):g} fps, decoded successfully")
    capture.release()
