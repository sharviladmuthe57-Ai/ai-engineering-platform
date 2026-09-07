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
pnpm dev --webpack --hostname 127.0.0.1 --port 3001
pnpm build
pnpm start --hostname 127.0.0.1 --port 3001
```

Open [the website](http://127.0.0.1:3001/) while its server is running.
These are two separate applications: Next.js serves the marketing site, and
FastAPI serves the interactive electrical prototype. A localhost link only
works on the computer running that server, and must be restarted after closing
its process or restarting the computer. The production `start` command requires
a successful `build` first. No hosting or paid services are required.

It uses the real local product artifacts in `public/product/`: an architectural
input plan, vision/geometry analysis, a structured plan state, and a generated
electrical routing/BOQ output. The editable 2D electrical canvas is available
from the local application after a plan is processed.

The website's editor frame is a clearly labeled, read-only export of the actual
editor, not a second editing implementation. `static/editor.js` and
`static/editor.css` provide the working editor in FastAPI. Process a plan there,
then open its editable canvas; its `?editor_job=...` URL preserves the project
on reload. The three images in `public/vision/` are supplied BIM references for
the **Vision / Next** chapter, not generated outputs. Interactive 3D remains
unimplemented.

Asset maintenance (only needed when refreshing the evidence):

```bash
node scripts/export-website-proof.mjs <completed-local-job-id>
python scripts/export-video-posters.py
node scripts/prepare-vision-assets.mjs <reference-1.png> <reference-2.png> <reference-3.png>
```

The proof exporter requires an existing completed editable job and its original
PNG in the local ignored runtime folders. The committed, sanitized exports and
assets are sufficient for a website build on another computer. Original local
jobs, uploads, temporary screenshots, and caches must not be committed.

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
