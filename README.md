# AI Engineering Platform — V1

A local, manual-assist prototype for electrical-plan generation from floor-plan images.

## Implemented workflow

```text
Image upload
→ local OpenCV room-region extraction
→ additive door/window candidates
→ engineer verification
→ accepted candidates adapted to legacy room openings
→ deterministic electrical placement and architecture-aware routing
→ PNG electrical layout and BOM
```

The electrical engine still consumes the established legacy room format:
`rooms[].doors` and `rooms[].windows`. Opening candidates are intentionally
separate and do not influence electrical placement until an engineer accepts
them in the verification screen.

## Current architecture

- `app.py` — FastAPI upload, job persistence, verification, layout/BOM APIs.
- `core/cv_analyzer.py` — OpenCV preprocessing, wall-mask and room-region
  extraction, best-effort OCR, legacy openings, and additive candidates.
- `core/openings.py` — wall-mask boundary-gap candidate extraction and the
  verified-candidate-to-legacy adapter.
- `core/rules_engine.py` — deterministic per-room component rules.
- `core/geometry.py` and `core/routing.py` — component placement,
  architecture-aware room-graph routing, and BOM.
- `core/renderer.py` and `core/symbols.py` — Matplotlib PNG rendering.
- `core/ocr_reader.py` — standalone multi-variant Tesseract helper; it is
  not currently wired into the upload route.
- `static/index.html` — upload and verification UI.

## Opening candidates

Each candidate records its id, type, room id, image-pixel position, wall side,
pixel width, approximate metric width, transparent heuristic confidence,
detection method/provenance, and verification status.

The current detector finds boundary gaps in the existing morphological wall
mask. It is a candidate generator, not a final architectural-opening detector:
it does not infer door swings or distinguish all interior/exterior opening
semantics. Pending/rejected candidates never modify the electrical pipeline.

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

Open http://localhost:8000.

The UI accepts raster image files. PDF ingestion, precise polygons/walls,
editable CAD geometry, and 3D visualization are not implemented yet.

## Product website

The marketing site is the Next.js application at the repository root.

```bash
pnpm dev
pnpm build
```

It uses the real local product artifacts in `public/product/`: an architectural
input plan, vision/geometry analysis, a structured plan state, and a generated
electrical routing/BOQ output. The editable 2D electrical canvas is available
from the local application after a plan is processed.

## APIs

- `POST /upload` — store an image and return rooms, legacy openings, and
  pending opening candidates.
- `GET /openings/{job_id}` — return candidates for a stored job.
- `POST /verify/{job_id}` — apply verifier edits; accepted candidates are
  adapted immediately before the unchanged electrical pipeline runs.
- `GET /layout/{job_id}`, `GET /bom/{job_id}`, `GET /status/{job_id}`.
- `GET /health`.

## Tests and fixtures

Run `python -m unittest discover -s tests -v`.

`fixtures/benchmarks/` contains three versioned, consented real-plan PNG
fixtures with expected annotations and detected benchmark evidence. They are
stable benchmark inputs and must not be casually replaced.
