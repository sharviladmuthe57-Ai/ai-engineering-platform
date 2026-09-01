# Electrical Design Benchmark V1

This is a read-only audit of the current production electrical engine.  It
does not feed, alter, or optimise electrical production rules, placement,
routing, BOM generation, room segmentation, or opening detection.

## Pipeline audited

`app.py` first obtains architectural vision data.  On verification it applies
only explicitly accepted opening candidates through the compatibility adapter,
then calls `core.geometry.generate_layout`, then `core.renderer.render_layout`.
The layout generator assigns the DB using its current origin-proximity
heuristic, applies the static room rules from `core.rules_engine`, places
components from their current positional hints, and creates one Manhattan
DB-to-component route per placement.  BOM entries are derived from placement
labels; wire and several consumables are current heuristic quantities.

## Run

From the repository root, with the project's runtime dependencies installed:

```powershell
python -m benchmarks.run_electrical_benchmark fixtures/benchmarks --output-dir benchmark_reports/electrical
```

The runner processes `plan_01.png` through `plan_03.png`, writes
`electrical_benchmark.json`, and writes one `*_electrical.png` overlay per
plan.  These are audit artifacts, not production renderings.

## Audit semantics

The expectation table is deliberately broad and is used only to flag omitted
component categories for the room types assigned by the existing engine.  It
is not an electrical-code compliance checker and it is not used by production
placement.  Spatial flags use detected rectangular room geometry and the
existing raster wall mask, so they identify candidates for review rather than
certify constructability.

The report records all generated components, routes, direct BOM reconciliation,
heuristic consumables, placement and route flags, and the provenance of each
flag (architectural input, electrical rules, placement, routing, or BOM).

