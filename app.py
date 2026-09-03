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
from core.openings    import apply_verified_openings_to_rooms
from core.editor_state import (
    EditorStateError, add_component, create_project_state, delete_component,
    move_component, reset_project_state,
)

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


def project_state_for(jid, job):
    """Lazily add editor state for completed jobs created before Editor V1."""
    if job.get("status") != "completed" or "layout" not in job:
        raise HTTPException(400, "Project layout is not ready yet")
    if "project_state" not in job:
        scale = job.get("vision_data", {}).get("_debug", {}).get("scale_mppx")
        job["project_state"] = create_project_state(jid, job["layout"], scale, job.get("project_name"))
        save_job(jid, job)
    return job["project_state"]


def editor_response(jid, state):
    """Expose structured state without leaking local filesystem paths."""
    return {"job_id": jid, "architecture_image_url": f"/plan/{jid}", **state}


def request_position(payload):
    value = payload.get("position")
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y")]
    return value


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
    project_name: str        = Form(""),
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
        "project_name" : project_name.strip(),
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

    # Candidate openings are inert until the verifier accepts them. The adapter
    # writes accepted openings into the established rooms[].doors/windows shape
    # immediately before the unchanged electrical pipeline is called.
    opening_candidates = vision_data.get(
        "opening_candidates", job["vision_data"].get("opening_candidates", [])
    )
    vision_data = dict(vision_data)
    vision_data["rooms"] = apply_verified_openings_to_rooms(
        vision_data.get("rooms", []), opening_candidates
    )

    layout = generate_layout(vision_data, project_type)

    out_png = OUTPUTS / f"{jid}_layout.png"
    render_layout(layout, str(out_png), original_image_path=job.get("img_path"))

    job.update({
        "status"      : "completed",
        "layout"      : layout,
        "output_img"  : str(out_png),
        "completed_at": datetime.now().isoformat(),
    })
    job["project_state"] = create_project_state(
        jid, layout, vision_data.get("_debug", {}).get("scale_mppx"), job.get("project_name")
    )
    save_job(jid, job)

    return JSONResponse({
        "job_id"     : jid,
        "status"     : "completed",
        "layout_url" : f"/outputs/{jid}_layout.png",
        "editor_url" : f"/?editor_job={jid}",
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


@app.get("/openings/{jid}")
def get_openings(jid: str):
    """Return additive opening candidates for the verification UI."""
    job = load_job(jid)
    return {
        "job_id": jid,
        "opening_candidates": job["vision_data"].get("opening_candidates", []),
    }


@app.get("/layout/{jid}")
def get_layout(jid: str):
    job = load_job(jid)
    if job["status"] != "completed":
        raise HTTPException(400, "Not completed yet")
    return FileResponse(job["output_img"], media_type="image/png")


@app.get("/plan/{jid}")
def get_plan(jid: str):
    """Serve the architectural raster only for the requested job."""
    job = load_job(jid)
    image_path = Path(job.get("img_path", ""))
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(404, "Architectural plan image is unavailable")
    return FileResponse(str(image_path))


@app.get("/bom/{jid}")
def get_bom(jid: str):
    job = load_job(jid)
    if job["status"] != "completed":
        raise HTTPException(400, "Not completed yet")
    state = project_state_for(jid, job)
    return JSONResponse({"job_id": jid, "bom": state["bom"], "total_wire_m": state["total_wire_m"]})


@app.get("/status/{jid}")
def get_status(jid: str):
    job = load_job(jid)
    return {"job_id": jid, "status": job["status"], "created_at": job["created_at"]}


# ── EDITABLE 2D PROJECT API ────────────────────────────────────────────────
@app.get("/project/{jid}")
def get_project(jid: str):
    job = load_job(jid)
    return JSONResponse(editor_response(jid, project_state_for(jid, job)))


@app.patch("/project/{jid}/components/{component_id}")
def patch_project_component(jid: str, component_id: str, payload: dict):
    job = load_job(jid)
    state = project_state_for(jid, job)
    try:
        move_component(state, component_id, request_position(payload))
    except EditorStateError as error:
        raise HTTPException(400, str(error)) from error
    save_job(jid, job)
    return JSONResponse(editor_response(jid, state))


@app.post("/project/{jid}/components")
def post_project_component(jid: str, payload: dict):
    job = load_job(jid)
    state = project_state_for(jid, job)
    try:
        add_component(state, payload.get("component_type", ""), payload.get("room_id", ""), request_position(payload))
    except EditorStateError as error:
        raise HTTPException(400, str(error)) from error
    save_job(jid, job)
    return JSONResponse(editor_response(jid, state), status_code=201)


@app.delete("/project/{jid}/components/{component_id}")
def delete_project_component(jid: str, component_id: str):
    job = load_job(jid)
    state = project_state_for(jid, job)
    try:
        delete_component(state, component_id)
    except EditorStateError as error:
        raise HTTPException(400, str(error)) from error
    save_job(jid, job)
    return JSONResponse(editor_response(jid, state))


@app.post("/project/{jid}/save")
def save_project(jid: str):
    job = load_job(jid)
    state = project_state_for(jid, job)
    state["last_saved"] = datetime.now().isoformat()
    save_job(jid, job)
    return JSONResponse(editor_response(jid, state))


@app.post("/project/{jid}/reset")
def reset_project(jid: str):
    job = load_job(jid)
    prior = project_state_for(jid, job)
    scale = job.get("vision_data", {}).get("_debug", {}).get("scale_mppx")
    job["project_state"] = reset_project_state(jid, job["layout"], scale, prior.get("revision_number", 0), job.get("project_name"))
    save_job(jid, job)
    return JSONResponse(editor_response(jid, job["project_state"]))
