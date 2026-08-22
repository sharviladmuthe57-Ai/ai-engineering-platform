# Project V1 — AI-Native Electrical Planning & Quotation Platform

## What this is
Upload a floor plan → AI reads it → places electrical/CCTV components →
routes wiring → generates BOM → engineer verifies → layout PNG output.

## Stack
- **Backend**: Python + FastAPI
- **AI Vision**: Claude claude-sonnet-4-6 (multimodal)
- **Geometry**: Shapely + NetworkX
- **Output**: Matplotlib
- **Frontend**: Vanilla HTML/JS (no build step)

## Setup

```bash
# 1. Clone / copy project-v1 folder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Run
python -m uvicorn app:app --reload --port 8000

# 5. Open browser
http://localhost:8000
```

## Folder structure
```
project-v1/
├── app.py              ← FastAPI backend (all API routes)
├── requirements.txt
├── core/
│   ├── vision.py       ← Layer 1: floor plan → JSON via Claude vision
│   ├── geometry.py     ← Layer 2+3: component placement + wire routing
│   └── renderer.py     ← Layer 4: layout PNG generation
├── static/
│   └── index.html      ← Full frontend (upload + verification screen + results)
├── uploads/            ← Uploaded floor plan images (auto-created)
├── outputs/            ← Generated layout PNGs (auto-created)
└── jobs/               ← Job state files as JSON (auto-created)
```

## API Endpoints
```
POST /upload            Upload floor plan, get vision extraction + job_id
POST /verify/{job_id}   Submit verified room data, get layout + BOM
GET  /layout/{job_id}   Download layout PNG
GET  /bom/{job_id}      Get BOM as JSON
GET  /status/{job_id}   Check job status
```

## Workflow (V1.0 — Manual Assist Mode)
1. User uploads floor plan
2. Claude vision API reads it → extracts rooms, walls, doors, elements
3. Engineer sees verification screen — corrects any AI mistakes
4. Engineer confirms → geometry engine places components + routes wiring
5. BOM generated automatically from routing output
6. Layout PNG downloaded

## What's next (V1.1 → V1.2)
- V1.1: Improve automated component placement (remove need for manual correction on standard plans)
- V1.2: Dijkstra-based optimal multi-room wire routing
- THEN: Go sell. Do not build more until first paying customer.
