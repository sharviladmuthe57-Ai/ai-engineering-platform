"""
app.py  —  Project V1  (Local CV Architecture)
===============================================
NO external API for core analysis.
Claude API used ONLY if user asks for report/explanation (optional, future).
"""

import os, json, uuid, shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import sys
sys.path.insert(0, str(Path(__file__).parent))

from core.cv_analyzer import analyze_floor_plan   # ← local CV, no API
from core.geometry    import generate_layout
from core.renderer    import render_layout

# ── APP ──────────────────────────────────────────────────────
app = FastAPI(title="Project V1", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

BASE    = Path(__file__).parent
UPLOADS = BASE / "uploads";  UPLOADS.mkdir(exist_ok=True)
OUTPUTS = BASE / "outputs";  OUTPUTS.mkdir(exist_ok=True)
JOBS    = BASE / "jobs";     JOBS.mkdir(exist_ok=True)

app.mount("/static",  StaticFiles(directory=str(BASE/"static")),  name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS)),        name="outputs")


# ── JOB STORE ────────────────────────────────────────────────
def save_job(jid, data):
    (JOBS / f"{jid}.json").write_text(json.dumps(data, indent=2))

def load_job(jid):
    p = JOBS / f"{jid}.json"
    if not p.exists():
        raise HTTPException(404, f"Job {jid} not found")
    return json.loads(p.read_text())


# ── ROUTES ───────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse(str(BASE / "static" / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "mode": "local_cv", "api_required": False}


@app.post("/upload")
async def upload(
    file:         UploadFile = File(...),
    project_type: str        = Form("electrical"),
    known_width:  str        = Form(""),
    known_height: str        = Form(""),
):
    """
    Upload floor plan → local CV analysis → return extracted rooms for verification.
    No external API call. Typically completes in < 2 seconds.
    """
    jid = str(uuid.uuid4())[:8]
    ext = Path(file.filename).suffix or ".jpg"
    img_path = UPLOADS / f"{jid}{ext}"

    with open(img_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print(f"\n[Job {jid}] {file.filename}  type={project_type}")

    # Parse optional known dimensions
    w_m = float(known_width)  if known_width  else None
    h_m = float(known_height) if known_height else None

    # ── LOCAL CV ANALYSIS ─────────────────────────────────────
    result = analyze_floor_plan(str(img_path),
                                known_width_m=w_m,
                                known_height_m=h_m)

    if not result["success"]:
        return JSONResponse({
            "job_id": jid,
            "status": "failed",
            "error" : result.get("error"),
        }, status_code=200)

    vision_data = result["data"]

    save_job(jid, {
        "status"       : "awaiting_verification",
        "project_type" : project_type,
        "img_path"     : str(img_path),
        "vision_data"  : vision_data,
        "created_at"   : datetime.now().isoformat(),
    })

    return JSONResponse({
        "job_id"      : jid,
        "status"      : "awaiting_verification",
        "vision_data" : vision_data,
        "message"     : (
            f"Detected {len(vision_data.get('rooms',[]))} rooms "
            f"and {len(vision_data.get('detected_elements',[]))} elements. "
            f"Confidence: {vision_data.get('confidence',0):.0%}. "
            f"Please verify."
        ),
    })


@app.post("/verify/{jid}")
async def verify(jid: str, verified_data: dict):
    """Engineer submits verified room data → generate full layout + BOM."""
    job = load_job(jid)

    vision_data  = verified_data if verified_data.get("rooms") else job["vision_data"]
    project_type = job["project_type"]

    layout = generate_layout(vision_data, project_type)

    out_png = OUTPUTS / f"{jid}_layout.png"
    render_layout(layout, str(out_png), original_image_path=job.get("img_path"))

    job.update({
        "status"      : "completed",
        "layout"      : layout,
        "output_img"  : str(out_png),
        "completed_at": datetime.now().isoformat(),
    })
    save_job(jid, job)

    return JSONResponse({
        "job_id"     : jid,
        "status"     : "completed",
        "layout_url" : f"/outputs/{jid}_layout.png",
        "bom"        : layout["bom"],
        "summary"    : {
            "rooms"        : len(layout["rooms"]),
            "components"   : len(layout["placed_components"]),
            "total_wire_m" : layout["total_wire_m"],
            "cameras"      : len(layout["cctv_components"]),
            "total_cat6_m" : layout["total_cat6_m"],
            "warnings"     : layout["warnings"],
        },
    })


@app.get("/layout/{jid}")
def get_layout(jid: str):
    job = load_job(jid)
    if job["status"] != "completed":
        raise HTTPException(400, "Not completed yet")
    return FileResponse(job["output_img"], media_type="image/png")


@app.get("/bom/{jid}")
def get_bom(jid: str):
    job = load_job(jid)
    if job["status"] != "completed":
        raise HTTPException(400, "Not completed yet")
    return JSONResponse({"job_id": jid, "bom": job["layout"]["bom"]})


@app.get("/status/{jid}")
def get_status(jid: str):
    job = load_job(jid)
    return {"job_id": jid, "status": job["status"], "created_at": job["created_at"]}
