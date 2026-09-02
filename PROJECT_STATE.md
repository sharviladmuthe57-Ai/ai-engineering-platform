# AI Engineering Platform — Project State

Last verified: 2026-09-03 on `main` at `5f17abbb2b5a8c006bbe5a9ebc33aa0817fcba9b`.

This is a durable handoff for developers and coding agents. The repository, tests, and versioned fixtures are the source of truth. Statements labelled **Verified** were checked in this repository on the date above. Statements labelled **Product intent** describe direction, not shipped functionality.

## 1. Product goal

**Product intent.** Build an AI-native engineering workspace that turns architectural drawings into structured, editable engineering output. The current wedge is electrical design: architectural plan → understood spaces/openings → first-draft electrical design → engineer review → BOM/BOQ → future editable 2D and 3D views.

The present system is a Phase-1 prototype, not construction-ready electrical design software. Its architectural understanding and electrical generation are deliberately deterministic; they do not use an LLM in the core path.

## 2. Current phase

**Product intent.** Phase 1 is a strong demonstration of architectural-plan understanding, deterministic electrical generation, PNG output, and BOM generation. Editable CAD-like 2D, interactive 3D, plumbing, HVAC, structural design, multi-floor coordination, and broader BIM functions are future work.

## 3. Current architecture

**Verified.**

- `app.py` is a FastAPI application with local filesystem job persistence. It owns upload, verification, layout, BOM, status, and PNG endpoints.
- `core/cv_analyzer.py` implements raster preprocessing, structural wall masking, room-region detection, best-effort OCR, scale estimation, room construction, detected elements, and opening-candidate dispatch.
- `core/openings.py` implements V1 boundary-gap candidates and `apply_verified_openings_to_rooms`, the compatibility adapter.
- `core/openings_v2.py` implements exterior-wall-aware proposals, clustering, conservative V2 classification, and opt-in V3 symbol-aware classification.
- `core/opening_symbols.py` scores local door-swing/leaf and window-band evidence for V3.
- `core/rules_engine.py` contains deterministic room-type component rules and positional hints.
- `core/geometry.py` places components, chooses a DB, creates direct Manhattan/L-shaped DB-to-component routes, and derives the BOM.
- `core/renderer.py` and `core/symbols.py` render the electrical PNG. `static/index.html` is the upload and verification UI.
- `core/ocr_reader.py` is a standalone Tesseract helper and is not wired into `app.py`'s upload route.

Dependencies in `requirements.txt` are FastAPI, Uvicorn, `python-multipart`, Matplotlib, Pillow, NumPy, OpenCV, and PyTesseract.

## 4. Actual runtime pipeline

**Verified.**

```text
POST /upload
  → save image under uploads/
  → analyze_floor_plan() (V1 openings by default)
  → preprocess + structural wall mask + connected regions
  → optional OCR + scale calculation + rooms/elements
  → additive opening candidates
  → save job as awaiting_verification

Engineer verification in static/index.html
  → optional room and opening-candidate edits
  → only accepted candidates adapted to legacy rooms[].doors/windows
  → generate_layout()
  → deterministic component rules and placement
  → DB-to-each-component L-shaped route
  → BOM + renderer PNG + completed job response
```

The upload API does not select V2 or V3; `analyze_floor_plan` defaults to V1. V2/V3 are implemented opt-in paths used by the benchmark tooling. This is important when describing current product behavior.

## 5. Data model and compatibility rule

**Verified.** The production pipeline uses dictionaries, not `core/schema.py`. Rooms retain the legacy `rooms[].doors` and `rooms[].windows` shape used by electrical placement. Opening candidates are additive dictionaries containing stable ID, type, room ID, pixel position, wall side, offset/width, approximate metric width, confidence, provenance/detection method, and `verification_status`.

Only `accepted` candidates are adapted into the corresponding legacy room opening type. `pending` and `rejected` candidates are inert. The UI exposes wall side, pixel width, pixel offset, and pending/accept/reject controls.

## 6. Benchmark fixtures

**Verified.** `fixtures/benchmarks/` contains three versioned PNG plans, their annotation JSON, and checked-in detected-result JSON:

- `plan_01.png`: annotation says 50' × 40'; fixture is 824×582 px.
- `plan_02.png`: annotation says 50' × 40'; fixture is 1190×891 px.
- `plan_03.png`: annotation says 60' × 60'; fixture is 1217×1175 px.

The annotations preserve geometric pixel polygons and distinguish confirmed from uncertain observations. An open geometric space can have several semantic zones; geometry is the right basis for routing/boundaries/3D, while semantic zones can inform electrical rules.

Do not casually replace or delete these fixtures.

## 7. Room segmentation status

**Verified.** The frozen room segmentation uses long horizontal/vertical structural strokes, drawing-relative morphology, page-edge/dimension-band filtering, and additive space candidates. Its geometric benchmark (`benchmarks/geometric.py`, IoU threshold 0.35) reproduced:

| Plan | Detected | Matched | Precision | Recall | Mean IoU | Median IoU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 10 | 8 | 0.800 | 0.889 | 0.714 | 0.795 |
| 02 | 13 | 10 | 0.769 | 1.000 | 0.779 | 0.827 |
| 03 | 14 | 13 | 0.929 | 0.929 | 0.779 | 0.809 |

**Frozen decision.** Do not optimize room segmentation for Phase 1 unless benchmark evidence shows a severe downstream demo blocker.

## 8. Opening detection status

**Verified.**

- V1 (`core/openings.py`) is wall-boundary gap extraction.
- V2 adds exterior-side reasoning, gap proposals, deduplication, width/parallel-line/support evidence, and fixture-noise suppression.
- V3 retains V2 proposals and adds local raster evidence for hinge-anchored swing arcs, door leaves, and parallel exterior window bands. Weak/conflicting evidence can remain `uncertain` and pending.

On confirmed annotations across all three fixtures, the reproduced aggregate metrics are:

| Detector | Doors: GT / detected / TP | Door P/R/F1 | Windows: GT / detected / TP | Window P/R/F1 |
| --- | --- | --- | --- | --- |
| V1 | 26 / 102 / 14 | 0.137 / 0.538 / 0.219 | 29 / 27 / 1 | 0.037 / 0.034 / 0.036 |
| V2 | 26 / 70 / 17 | 0.243 / 0.654 / 0.354 | 29 / 24 / 11 | 0.458 / 0.379 / 0.415 |
| V3 | 26 / 70 / 18 | 0.257 / 0.692 / 0.375 | 29 / 23 / 11 | 0.478 / 0.379 / 0.423 |

V3 emitted 52 uncertain pending proposals (17, 18, and 17 by plan). None was accepted in the electrical benchmark. V3 therefore improves the measured detector while preserving human review and does not silently alter electrical input.

**Frozen decision.** Do not restart opening-detector optimization in this phase without evidence of a material product blocker.

## 9. Electrical engine status

**Verified.** `rules_engine.py` maps room labels to static components and positional hints. `geometry.py` generates each component, selects a DB by choosing the room closest to the origin and placing the DB near that room's left wall, then routes every component directly from the DB using the shorter of two L-shaped Manhattan paths. It applies `BUFFER = 1.15` to route length.

The engine supports lights, fans, one-/two-way switches, sockets, AC and appliance points, DB, and optional CCTV/NVR output depending on project type. It is a deterministic first-draft generator, not code-compliant circuit/load engineering.

The BOM directly counts placed components. Wire is derived from the buffered route total; conduit, clips, gang boxes, earthing wire, and screws are heuristic consumables. It is not circuit- or load-aware.

## 10. Electrical Benchmark V1

**Verified.** `benchmarks/run_electrical_benchmark.py` regenerated a read-only report and one overlay per plan during this audit. The generated report was inspected in a temporary directory because `benchmark_reports/electrical/electrical_benchmark.json` is not currently tracked in the repository.

| Plan | Rooms | Components | Routes | Raw route m | Reported wire m | Outside routes | Suspicious routes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 10 | 71 | 70 | 441.44 | 507.61 | 37 | 52 |
| 02 | 13 | 92 | 91 | 601.33 | 691.54 | 79 | 80 |
| 03 | 14 | 91 | 90 | 904.78 | 1040.47 | 83 | 83 |

Placement audit results:

| Plan | Intended-room % | Wall-mounted near wall % | Usable-door switches | Wall collisions | Outside components | Co-locations | Duplicate IDs |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 01 | 92.9 | 40.4 | 9/9 | 6 | 0 | 7 | 1 |
| 02 | 93.4 | 51.4 | 8/8 | 17 | 1 | 8 | 2 |
| 03 | 92.2 | 58.0 | 14/14 | 3 | 0 | 7 | 5 |

Switch-near-door measurements describe legacy room doors only. All benchmark V3 candidates were pending and zero were accepted.

## 11. DB and routing diagnosis

**Verified.** DB coordinates are (2.64, 4.61) m for plan 01, (2.01, 2.82) m for plan 02, and (1.40, 3.35) m for plan 03. The most distant raw routes are 11.00 m (plan 01 fridge), 12.73 m (plan 02 chimney; duplicated destination route IDs are possible), and 16.52 m (plan 03 AC). Each crosses multiple room regions; the longest routes in plans 01–03 respectively leave the modeled building area in the audit.

The DB heuristic is simplistic and can worsen paths because it chooses a room only by distance to the coordinate origin; it has no entrance, service, electrical-room, circulation, or topology model. It is not, however, the principal explanation: even a better single DB point would still produce a star of direct, architecture-blind L paths. The audit reports 37/70, 79/91, and 83/90 routes outside the union of detected room rectangles. `geometry.py` has no wall graph, room connectivity, accepted-opening traversal, circuit topology, or building-footprint routing.

## 12. Known failures, ordered by current severity

1. **Routing:** direct DB-to-every-component Manhattan paths cross unrelated spaces, walls, and modeled exterior. This is the dominant visual and product failure.
2. **Placement:** co-located components, wall-mask collisions, duplicate IDs, and one outside-building component on plan 02 remain.
3. **Electrical rules/BOQ:** static rules and heuristic consumables are not circuit/load/code aware.
4. **Architectural input:** room labels and legacy openings remain heuristic upstream constraints; V3 candidates are intentionally pending/inert.
5. **Reproducibility:** `opencv-python>=4.8.0` currently resolves to OpenCV 5, whose Hough line output breaks V3 `_leaf_score`; the test suite passes with OpenCV 4.10.0.84. No dependency/code change was made in this handoff.

## 13. Frozen decisions and current blocker

**Frozen decisions.** Preserve room segmentation V1, opening detector V3, benchmark fixtures, additive opening review, and legacy compatibility. Do not merge `recovered-sunday-tuesday` into `main`.

**Current blocker (verified).** Electrical routing is the immediate Phase-1 blocker. The overlays and route audit show visually implausible architecture-crossing grids on all benchmark plans. The root design is one direct L path per component, not a lack of accepted openings.

## 14. One next recommended milestone

Implement and benchmark **topology-aware electrical routing V2**: model a building/room connectivity graph from the frozen detected geometry and engineer-accepted openings, route along legal room/corridor/wall paths, keep routes inside the modeled footprint, and preserve the benchmark audit. Do not change room segmentation, opening detection, or placement rules as part of that milestone.

## 15. Future roadmap

**Product intent.** After routing reaches an acceptable benchmarked Phase-1 state: clean severe placement defects, freeze electrical-generation V1, build an editable 2D electrical canvas with BOQ synchronization, add an interactive 3D view of the same project, then expand engineering scope only when justified.

## 16. Tests and benchmark commands

**Verified on 2026-09-03.**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.run_electrical_benchmark fixtures\benchmarks --output-dir <temporary-output-dir>
```

The tracked suite passed: **31 tests, 0 failures** with OpenCV 4.10.0.84. The first run with the unconstrained latest OpenCV 5.0.0.93 produced 7 V3 test errors due to a `HoughLinesP` array-shape assumption. Tesseract was unavailable during benchmark regeneration; the code skipped OCR gracefully and used its existing scale fallback.

## 17. Important files

- `app.py`, `static/index.html`
- `core/cv_analyzer.py`, `core/openings.py`, `core/openings_v2.py`, `core/opening_symbols.py`
- `core/rules_engine.py`, `core/geometry.py`, `core/renderer.py`, `core/symbols.py`
- `benchmarks/runner.py`, `benchmarks/geometric.py`, `benchmarks/opening_metrics.py`
- `benchmarks/electrical_benchmark.py`, `benchmarks/run_electrical_benchmark.py`, `benchmarks/ELECTRICAL_BENCHMARK_V1.md`
- `fixtures/benchmarks/plan_*.png` and `fixtures/benchmarks/plan_*.annotation.json`
- `tests/`

## 18. Git and branch state

**Verified.** Canonical branch: `main`, tracking `origin/main`. At audit start it was `5f17abb` (`Clarify electrical benchmark overlay legend`). `recovered-sunday-tuesday` is retained at `2ee4729` (`Recover Sunday-Tuesday CV opening and electrical benchmark work`) and must not be merged into main.

The local Git identity is `Srushti Admuthe <srushtiadmuthe1001@gmail.com>`, not the GitHub owner named in the handoff. Do not rewrite history. Confirm or correct identity with the project owner before future commits if needed.

## 19. Handoff discrepancies

**Verified discrepancies from the supplied handoff narrative.**

- `core/schema.py` and the described typed canonical schema are absent; production uses additive dictionaries and legacy room shapes.
- `benchmark_reports/electrical/electrical_benchmark.json` and committed electrical overlays are absent. The runner does reproduce the report/overlays.
- `README.md` incorrectly says no real plans are committed, although all three benchmark plans and annotations are tracked.
- V3 is benchmark-opt-in; the application upload path defaults to V1 openings.
- The local Git identity differs from the expected repository owner identity.

## 20. Development rules and checkpoint protocol

1. Preserve data and public history: never force-push, rewrite shared history, delete benchmark fixtures, delete the recovery branch, or merge that recovery branch into main without explicit authorization.
2. Keep uncertain CV output reviewable. Pending/rejected openings must remain inert.
3. Use benchmark-driven development: implement one material change, test on the three fixtures, inspect measured output/overlays, then freeze acceptable subsystems.
4. Do not casually reopen frozen room segmentation or opening detection.
5. Do not blindly add the working tree. Runtime directories, caches, virtual environments, secrets, and local artifacts must stay out of commits. `.gitignore` now excludes the common local runtime/cache/secret paths while leaving benchmark fixtures and reports unignored for deliberate review.
6. Every meaningful task ends with: relevant tests; `git diff`/`git status`; this document updated; a descriptive commit; non-force push; and verification of branch, commit, tests, benchmark impact, and worktree state.

## 21. Change log / milestones

- 2026-09-03: Created this verified continuity checkpoint, added targeted `.gitignore`, regenerated the electrical audit in temporary storage, and confirmed routing as the next milestone. No production algorithm changed.
- 2026-09-01: `5f17abb` clarified the electrical benchmark overlay legend.
- Recent main history: V3 symbol-aware opening classification and tests; V1–V3 comparison; electrical expectations, read-only audit, reproducible runner, invariant tests, and documentation.
- Recovery safety snapshot: `2ee4729` on `recovered-sunday-tuesday`; preserve only, do not merge.
