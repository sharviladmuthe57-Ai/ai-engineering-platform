# AI Engineering Platform — Project State

Last verified: 2026-09-03. Current Phase-1 backend state includes the completed Placement V2 checkpoint described below.

This is a durable handoff for developers and coding agents. The repository, tests, and versioned fixtures are the source of truth. Statements labelled **Verified** were checked in this repository on the date above. Statements labelled **Product intent** describe direction, not shipped functionality.

## 1. Product goal

**Product intent.** Build an AI-native engineering workspace that turns architectural drawings into structured, editable engineering output. The current wedge is electrical design: architectural plan → understood spaces/openings → first-draft electrical design → engineer review → BOM/BOQ → future editable 2D and 3D views.

The present system is a Phase-1 prototype, not construction-ready electrical design software. Its architectural understanding and electrical generation are deliberately deterministic; they do not use an LLM in the core path.

## 2. Current phase

**Verified.** Phase 1 now includes the working Editable 2D Electrical Canvas V1: generated electrical design can be reviewed, manually edited, routed incrementally, saved, and reopened. Interactive 3D, plumbing, HVAC, structural design, multi-floor coordination, and broader BIM functions remain future work.

## 3. Current architecture

**Verified.**

- `app.py` is a FastAPI application with local filesystem job persistence. It owns upload, verification, layout, BOM, status, and PNG endpoints.
- `core/cv_analyzer.py` implements raster preprocessing, structural wall masking, room-region detection, best-effort OCR, scale estimation, room construction, detected elements, and opening-candidate dispatch.
- `core/openings.py` implements V1 boundary-gap candidates and `apply_verified_openings_to_rooms`, the compatibility adapter.
- `core/openings_v2.py` implements exterior-wall-aware proposals, clustering, conservative V2 classification, and opt-in V3 symbol-aware classification.
- `core/opening_symbols.py` scores local door-swing/leaf and window-band evidence for V3.
- `core/rules_engine.py` contains deterministic room-type component rules and positional hints.
- `core/placement.py` validates proposed electrical positions against their intended room rectangle and already placed components.
- `core/geometry.py` places components, chooses a DB, delegates routing, and derives the BOM.
- `core/routing.py` implements deterministic Routing V2.1: a room-rectangle connectivity graph, validated door/opening portals where available, conservative geometric transitions otherwise, per-component room-aware paths, and declared V1 fallback metadata.
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
  → Placement V2 room-local validation (inset, collision resolution, stable IDs)
  → Routing V2.1 room-connectivity path (or explicit V1 fallback)
  → BOM + renderer PNG + completed job response
```

The upload API does not select V2 or V3; `analyze_floor_plan` defaults to V1. V2/V3 are implemented opt-in paths used by the benchmark tooling. Routing V2.1 is the default electrical layout path; `routing_version="v1"` remains available only for comparison/fallback auditing.

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

**Verified.** `rules_engine.py` maps room labels to static components and positional hints. `geometry.py` generates each component, applies Placement V2 validation, selects a DB by choosing the room closest to the origin and placing the DB near that room's left wall, and delegates to Routing V2.1 by default. It applies `BUFFER = 1.15` to route length.

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

## Placement V2 implementation and benchmark

**Verified on 2026-09-03.** Placement V2 leaves the room rules, quantities, component categories, CV, routing, and BOQ formulas unchanged. It adds a reusable, deterministic `PlacementValidator` per room:

- each proposed point is clamped to a safe inward room inset using only frozen room geometry;
- wall-mounted components retain an intended wall side and stay wall-adjacent from inside the room;
- accepted opening candidates are preferred over legacy doors for doorway placement; pending/rejected candidates remain inert through the existing adapter;
- the legacy `outside_door` bathroom proposal is retained only for V1 benchmark comparison, then corrected inward by V2 validation;
- occupied positions are resolved through a fixed candidate order, never random jitter; and
- IDs use a room-local, per-component occurrence counter across all rules, preventing repeated rule blocks from restarting at `_0`.

Every V2 component carries additive placement metadata: version, method, original/validated position, adjustment reason, intended wall side, door source, and collision-resolution flag. DB placement remains intentionally unchanged.

The benchmark runner now emits current-proposal Placement V1 and validated Placement V2 overlays alongside the routing V1/V2/V2.1 overlays, and reports placement comparisons without changing the fixture definitions. Component counts are identical before and after for every fixture.

| Plan | Components | Intended-room % V1 → V2 | Outside components V1 → V2 | Wall collisions V1 → V2 | Near-wall % V1 → V2 | Co-locations V1 → V2 | Duplicate IDs V1 → V2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 71 | 92.9 → 100.0 | 0 → 0 | 6 → 5 | 40.4 → 93.0 | 7 → 0 | 1 → 0 |
| 02 | 92 | 93.4 → 100.0 | 1 → 0 | 17 → 10 | 51.4 → 94.6 | 8 → 0 | 2 → 0 |
| 03 | 91 | 92.2 → 100.0 | 0 → 0 | 3 → 2 | 58.0 → 94.2 | 7 → 0 | 5 → 0 |

The V2 switch source counts (accepted / legacy / deterministic fallback) are 0 / 9 / 2, 0 / 8 / 6, and 0 / 14 / 1 for plans 01–03. It performed 55, 77, and 71 coordinate corrections and 14, 23, and 10 collision resolutions. All switches are now in their intended room, including the former routing endpoints `room_8_switch_1way_0` (plan 01), `room_10_switch_1way_0` and `room_8_switch_1way_0` (plan 02), and `room_12_switch_1way_0` (plan 03).

Routing V2.1 was rerun without modification: all three fixtures have 0 outside routes, 0 suspicious routes, and 0 fallback routes. Raw/reported wire lengths are 538.96/619.75 m (plan 01), 667.86/768.03 m (plan 02), and 1033.55/1188.56 m (plan 03). The remaining 17 fixture wall-mask hits are disclosed rather than hidden: production placement receives frozen room geometry but not the raster wall mask, so it cannot safely make pixel-level wall claims. The rectangular inset materially reduces hits (26 → 17 overall) while keeping 93.0–94.6% of wall-mounted points near their intended wall.

## Routing V2.1 implementation and benchmark

**Verified on 2026-09-03.** Routing V2.1 preserves the public `waypoints` and `length_m` route fields, then adds `routing_version`, `architecture_aware`, `fallback_used`, `fallback_reason`, source/target/traversed rooms, and controlled-transition metadata. It builds a deterministic graph from the detected room rectangles:

- overlapping rooms connect through their common area;
- for an otherwise valid shared/near boundary, an accepted opening is preferred, then a legacy door/opening, then a geometric portal; accepted candidates carry their candidate ID and provenance;
- pending, uncertain, and rejected candidates are not adapted into legacy rooms and therefore cannot form portals;
- geometry-only transitions still require a shared span and a gap of at most 0.25 m, and are marked as `geometric_fallback`;
- every intra-room leg is a deterministic Manhattan segment inside the current room rectangle;
- a disconnected graph uses the preserved V1 Manhattan route and declares the fallback; it never silently reports that as architecture-aware.

The transition records disclose `portal_id`, portal type/provenance, trust class, and whether a geometric fallback was used. The graph and Dijkstra tie-breaking are deterministic. A missing room-graph path still uses the explicit declared V1 fallback. Existing placement/rules were not changed.

The benchmark runner now emits V1, V2, and V2.1 overlays and a `routing_comparison` for every plan. `outside_building_routes` evaluates the modeled routing domain (room rectangles plus explicit transitions); `outside_room_union_routes` remains available to disclose any path samples in a transition gap rather than hiding them.

| Plan | Raw route m V1 → V2 | Wire m V1 → V2 | Outside modeled domain V1 → V2 | Suspicious V1 → V2 | Fallbacks | Architecture-aware V2 |
| --- | --- | --- | --- | ---: | ---: |
| 01 | 441.44 → 528.25 | 507.61 → 607.48 | 37 → 1 | 52 → 1 | 0 | 100% |
| 02 | 601.33 → 678.71 | 691.54 → 780.48 | 79 → 3 | 80 → 3 | 0 | 100% |
| 03 | 904.78 → 1006.15 | 1040.47 → 1157.05 | 83 → 1 | 83 → 1 | 0 | 100% |

The V2 overlays remove the exterior-crossing full-plan star lines and show routes travelling through the room graph. Route length increases by roughly 11–20%; this is reported rather than concealed. V2 still records strict room-union excursions (33, 3, and 83 routes) where paths use explicit near-boundary transitions. The remaining modeled-domain failures are five switch routes whose existing placements sit at/outside room boundaries; placement was deliberately not changed.

V2.1 was benchmarked against the same fixtures and V2 output. No fixture had an accepted candidate, so trusted accepted-opening transitions are zero; the run still validates the accepted-opening path with unit tests. Legacy doors replaced a meaningful share of geometric portals, preserving or improving containment without changing CV, placement, 2D/3D, or BOQ formulas.

| Plan | Routes V2 → V2.1 | Raw m V2 → V2.1 | Wire m V2 → V2.1 | Outside / suspicious V2 → V2.1 | Accepted / legacy / geometric / failed transitions (V2.1) |
| --- | ---: | ---: | ---: | ---: |
| 01 | 70 → 70 | 528.25 → 540.81 | 607.48 → 621.92 | 1 / 1 → 1 / 1 | 0 / 69 / 18 / 0 |
| 02 | 91 → 91 | 678.71 → 662.22 | 780.48 → 761.55 | 3 / 3 → 2 / 2 | 0 / 107 / 41 / 0 |
| 03 | 90 → 90 | 1006.15 → 1031.35 | 1157.05 → 1186.00 | 1 / 1 → 1 / 1 | 0 / 87 / 102 / 0 |

The paired overlays were visually inspected. V2.1 preserves room-graph containment, routes through credible legacy doors where geometry permits, and retains geometric portals only where no usable opening supports the same boundary. Plan 02 improves by one modeled-domain/suspicious route; plans 01 and 03 are unchanged. The remaining V2.1 bad route is plan 03 `room_12_switch_1way_0` (route 78, 17.61 m raw / 20.25 m reported), an existing boundary-placement issue rather than a fallback or failed transition.

## 11. DB and routing diagnosis

**Verified.** DB coordinates are (2.64, 4.61) m for plan 01, (2.01, 2.82) m for plan 02, and (1.40, 3.35) m for plan 03. The most distant raw routes are 11.00 m (plan 01 fridge), 12.73 m (plan 02 chimney; duplicated destination route IDs are possible), and 16.52 m (plan 03 AC). Each crosses multiple room regions; the longest routes in plans 01–03 respectively leave the modeled building area in the audit.

The DB heuristic remains simplistic and can worsen total length because it chooses a room only by distance to the coordinate origin; it has no entrance, service, electrical-room, or circuit model. It is not the systemic V1 root cause, and Routing V2 removes the unrestricted direct-L behavior without changing DB placement. DB placement is now a secondary optimization concern, not a reason to change placement/routing scope in this milestone.

## 12. Known failures, ordered by current severity

1. **Electrical rules/BOQ:** static rules and heuristic consumables are not circuit/load/code aware.
2. **Architectural input:** room labels and legacy openings remain heuristic upstream constraints; V3 candidates are intentionally pending/inert.
3. **Raster wall-mask precision:** Placement V2 has room geometry but no production wall-mask input. The remaining 17 benchmark pixel-mask hits should remain visible for a future geometry/product-data decision, not be fixed with fixture-specific coordinates.

## 13. Frozen decisions and current blocker

**Frozen decisions.** Preserve room segmentation V1, opening detector V3, benchmark fixtures, additive opening review, legacy compatibility, Routing V2.1, and Placement V2. Placement V2 is frozen for Phase 1: it is deterministic, keeps quantities unchanged, eliminates duplicate IDs/co-locations/outside components, brings all components into intended rooms, and removes all benchmark suspicious routes. Do not merge `recovered-sunday-tuesday` into `main`.

**Current blocker (verified).** No remaining Phase-1 backend blocker justifies another placement pass. The outstanding non-code-ready limitations are static electrical rules/BOQ heuristics and disclosed raster wall-mask precision; neither warrants reopening frozen placement before editor work.

## 14. One next recommended milestone

Build the **editable 2D engineering canvas** using stable Placement V2 component IDs/coordinates and synchronized BOQ state. Do not start it until separately authorized.

## 15. Future roadmap

**Product intent.** After routing reaches an acceptable benchmarked Phase-1 state: clean severe placement defects, freeze electrical-generation V1, build an editable 2D electrical canvas with BOQ synchronization, add an interactive 3D view of the same project, then expand engineering scope only when justified.

## 16. Tests and benchmark commands

**Verified on 2026-09-03.**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m benchmarks.run_electrical_benchmark fixtures\benchmarks --output-dir <temporary-output-dir>
```

The tracked suite passed: **44 tests, 0 failures** with OpenCV 4.10.0.84. The five Placement V2 tests cover deterministic unique IDs/count preservation, inward switch placement, accepted/legacy/fallback door priority, wall/interior containment plus co-location resolution, and Routing V2.1 compatibility. The existing routing tests continue to cover declared V1 fallback. `requirements.txt` pins that version because the previous unbounded OpenCV dependency resolved to OpenCV 5.0.0.93 and produced 7 V3 test errors due to a `HoughLinesP` array-shape assumption. Tesseract was unavailable during benchmark regeneration; the code skipped OCR gracefully and used its existing scale fallback.

## 17. Important files

- `app.py`, `static/index.html`
- `core/cv_analyzer.py`, `core/openings.py`, `core/openings_v2.py`, `core/opening_symbols.py`
- `core/rules_engine.py`, `core/placement.py`, `core/geometry.py`, `core/routing.py`, `core/renderer.py`, `core/symbols.py`
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

- 2026-09-03: Implemented Placement V2: room-local deterministic validation, inward switch correction, accepted/legacy/fallback door provenance, collision resolution, and stable unique IDs. All 44 tests passed. The three fixtures retain component counts, reach 100% intended-room containment, have zero duplicates/co-locations/outside components, reduce wall-mask hits 26 to 17, and reduce routing outside/suspicious/fallback counts to zero. Placement V2 is frozen for Phase 1.
- 2026-09-03: Implemented Routing V2.1 portal validation. The default router now prefers accepted openings, then credible legacy doors, then constrained geometric portals; pending/rejected candidates remain inert. The runner produces V1/V2/V2.1 comparisons and overlays. All 39 tests passed; V2.1 improved plan 02 containment (3 to 2 bad routes) and did not regress plans 01 or 03. Routing V2.1 is frozen for Phase 1.
- 2026-09-03: Implemented Routing V2 with a deterministic room-graph domain, explicit transition/fallback metadata, V1/V2 benchmark comparison, and paired overlays. Pin OpenCV 4.10.0.84 and correct the README fixture statement. Routing is improved but not frozen.
- 2026-09-03: Created this verified continuity checkpoint, added targeted `.gitignore`, regenerated the electrical audit in temporary storage, and confirmed routing as the next milestone. No production algorithm changed.
- 2026-09-01: `5f17abb` clarified the electrical benchmark overlay legend.
- Recent main history: V3 symbol-aware opening classification and tests; V1–V3 comparison; electrical expectations, read-only audit, reproducible runner, invariant tests, and documentation.
- Recovery safety snapshot: `2ee4729` on `recovered-sunday-tuesday`; preserve only, do not merge.

## 22. Editable 2D Electrical Canvas V1

**Verified on 2026-09-03.** The editor is a deliberately lightweight product layer over the existing canonical generated layout. It uses plain HTML/CSS/JavaScript and SVG, with no frontend framework, WebGL, worker stack, database, or new runtime dependency. The background is the job's original uploaded plan; component and route coordinates remain in metres with a bottom-left, y-up project coordinate system. SVG converts to raster coordinates only for drawing, including the required y-axis inversion.

### State and persistence

- `core/editor_state.py` creates a JSON-serialisable `project_state_version: "1.0"` from the immutable generated `layout` retained in each completed job.
- State contains job/plan reference, scale and coordinate metadata, rooms, DB position, stable components, routes, BOQ, wire total, CCTV state where applicable, edit/revision metadata, monotonic `next_component_sequence`, and `last_modified`.
- Jobs continue to persist as small local JSON files under `jobs/`. Existing completed jobs are lazily initialised so no migration command or database is required.
- `POST /project/{jid}/save` records save metadata; opening the editor stores `?editor_job=<jid>` in the URL, so refresh/reopen reloads the same saved state. `POST /project/{jid}/reset` derives a clean editable state from the preserved generated layout.

### Supported operations and safeguards

- Select any existing component to inspect its stable ID, type, room, position, provenance, and placement method.
- Drag a non-DB component. Clicks do not mutate state; a small drag threshold prevents a selection click being misclassified as a manual move. A valid move preserves the ID, stores `position_source: "user_modified"`, and updates only that component's Routing V2.1 route.
- For V1, cross-room movement is intentionally rejected. A component must remain inside its assigned detected room; this safer rule prevents a stale room association while keeping routing/BOQ assumptions stable.
- Add a light, fan, one-way switch, or two-pin socket by choosing the SVG/DOM palette tool and clicking inside a detected room. New IDs are persisted deterministically, for example `user_ceiling_light_0001`, and carry `position_source`/`editor_status`/placement provenance of `user_added`.
- Delete a selected non-DB component after confirmation. Its route is removed. Reset also asks for confirmation.
- The BOM continues to use the existing formula implementation. Every accepted move/add/delete refreshes BOQ and total wire length without rerunning CV or global placement.

### Additive API surface

- `GET /plan/{jid}` serves only that job's original architectural raster.
- `GET /project/{jid}` returns the editable structured state.
- `PATCH /project/{jid}/components/{component_id}` validates and moves one component.
- `POST /project/{jid}/components` adds a supported manual component.
- `DELETE /project/{jid}/components/{component_id}` removes one non-DB component.
- `POST /project/{jid}/save` and `POST /project/{jid}/reset` persist metadata or restore generated state.

Existing upload, verification, generation, status, PNG, and BOM endpoints remain available. `/bom/{jid}` now reports the active editable-state BOQ once a project state exists.

### Verification and limitations

- Added `tests/test_editor_state.py` for stable-ID moves, targeted route updates, BOQ changes, deterministic add/delete IDs, invalid state rejection, JSON persistence, and reset recovery.
- Added `tests/test_editor_api.py` for safe invalid IDs, all editor API operations, save/reload, and reset. The full tracked test suite passed: **49 tests, 0 failures**.
- Manual local-browser evidence used `fixtures/benchmarks/plan_01.png`: upload/generate (10 rooms, 71 components), open editor, select, move a light, confirm route/wire change (595.39 m → 595.67 m in that generated job), add a light (12 lights; 602.10 m), delete it (11 lights; 595.67 m), save, refresh/reopen, and confirm the moved light remains `room_1_ceiling_light_0` at 5.63, 2.82 m with `user_modified` provenance. The workspace visually presents an aligned plan, routes, component glyphs, dark technical sidebars, and live BOQ.
- Browser screenshots were inspected during that local run but are deliberately not committed as runtime/build artefacts.
- Known V1 limits: rectangular detected-room validation only; no cross-room reassignment, undo/redo, circuit/load editing, code validation, CAD drafting, or mobile optimisation. These are deliberately outside the milestone.

**Freeze decision.** Editable 2D Electrical Canvas V1 is sufficient to freeze: the generate → review → edit → route/BOQ update → save/reopen loop is working with a low-spec-friendly implementation. Do not reopen frozen CV, placement, or routing work for ordinary editor changes.

**One next milestone.** Build an interactive 3D electrical/building view from the same stable structured project state and component IDs. Do not start it without approval.

## 23. Permanent zero-cost implementation policy

**Verified policy on 2026-09-03.** The Phase-1 demo must run locally without paid APIs, paid cloud infrastructure, metered services, API keys, or a payment method. The authorized budget is ₹0 / $0 unless the owner explicitly approves a named service, its purpose, billing model, and a cost limit in advance.

- Prefer existing code, deterministic local algorithms, open-source libraries, browser-native functionality, and local JSON/file persistence (or a local lightweight database only when needed).
- Do not add or enable paid/usage-metered AI, OCR, vision, mapping, database, authentication, storage, email, analytics, hosting, compute, CI/CD, or deployment services. Do not provision cloud resources, trials, credits, subscriptions, domains, billing, or automatic upgrades.
- Never require an API key for core functionality or commit secrets, tokens, credentials, or billing information.
- Before adding an external service, verify that it is genuinely free for the intended operation and cannot create an unexpected charge. If cost behaviour is uncertain, do not use it.
- If a future feature would benefit from paid infrastructure, preserve a local/free core path where practical and label the alternative **FUTURE / OPTIONAL / REQUIRES COST APPROVAL**. Do not activate it without explicit approval.

The current application complies: FastAPI, OpenCV, NumPy, local geometry/rules, SVG/DOM UI, and local JSON job persistence provide the complete current demo without external paid services.

## 24. Product website and editor UX refinement

**2026-09-07.** Frontend-only refinement preserves the frozen engineering
pipeline and all 49 tracked backend tests. No backend algorithms, job schema,
engineering rules, dependencies, paid services, or cloud resources changed.

- Removed the small hero prototype card. Kept the cinematic imagery, large
  headline, rounded navigation, cyan accent, and visible contact email.
- Repaired sticky-section ancestry and replaced the cinematic playback logic:
  only the current video plays, adjacent videos use metadata preloading, distant
  videos are unmounted, and off-screen/hidden-tab playback pauses. Local WebP
  posters cover unavailable playback and reduced-motion presentation.
- Kept the aligned 2D input/understanding/structured-plan story; added an actual
  structured electrical placement/routes/BOQ chapter and a read-only export of
  the real editor. Export data is allowlisted and contains no local paths.
- Added three optimized supplied references in a single pinned Vision / Next
  frame: reversible opacity, clip-path, and 2.5% scale transitions. No Three.js,
  WebGL, or new rendering engine. All three references total about 846 KB.
  Each frame says they are supplied visual references, not product output.
- Touch and reduced-motion modes use native image styles with stage buttons,
  avoiding scroll MotionValue ownership of manually selected image styles.
- The actual editor now uses the same paper/graphite/teal visual language, a
  large fitted paper canvas, compact four-tool Add palette, one-line usage hint,
  clear selection/drag halos, and valid/invalid placement feedback. Internal
  IDs and provenance remain in state and are available in Advanced details.
- BOQ leads with live light/fan/switch/socket counts and wire length, with the
  full table under View full BOQ. Save is primary and reports Saved; Reset is
  secondary and retains confirmation. Existing API operations are unchanged.

### Verification evidence

- In the real browser, a disposable copy of the existing plan-01 job was used;
  the original job was not edited. Moving `room_1_ceiling_light_0` to 5.70,
  2.94 m changed its route and wire total from 595.39 to 595.61 m. Save reported
  success; reload retained that ID and translated position.
- Added one light, fan, switch, and socket through the visible toolbar/canvas:
  71 to 75 components; summary 11/2/11/17 to 12/3/12/18; wire 610.53 m.
  Deleting the added socket returned 74 components and 605.72 m. Reset restored
  71 components and 595.39 m. Fit restored the identity camera transform;
  View toggled 10 room boundaries; full BOQ expansion worked. No editor console
  errors were observed.
- Desktop 1440x900 and laptop 1366x768: hero, real aligned 2D frames, editor
  export, all three 3D images and backward stage 3 to 2 to 1 inspected. Sticky
  frame top stayed at 0; no horizontal overflow. Only one cinematic video
  played; zero played in the vision chapter. Mobile 390x844 QA caught and fixed
  a missing headline line break and stale manually selected image styles.
  The final production version was retested: mobile 3D opacities select only
  the requested image and 2D clip masks reverse correctly. The readable mobile
  editor export uses a 1100px frame to include the whole BOQ, without scaling
  the desktop UI into tiny text.
- Existing tracked backend suite: 49 tests passed, unchanged coverage.
  Production build passed, including TypeScript checking and static prerendering.

### Limits and continuity

The marketing export is not interactive. The working editor is the separate
local FastAPI app; instructions and URLs are in README. Local previews require
their server process to remain running and are not a public deployment.
No formal CPU-throttled i3/4 GB benchmark or OS reduced-motion emulation was
available; video lifecycle and lightweight rendering were checked directly.
Room labels still reflect the existing detector's state, not new semantic
corrections. Interactive 3D is still the next unimplemented milestone.
