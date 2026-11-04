"""API HTTP de SANKOFA."""
import asyncio
import json
import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import agent, chronicle, config, documentary, history
from .sources import music
from .countries import BY_ID as COUNTRY_BY_ID, COUNTRIES
from .investigate import clean_title, load_manifest
from .meta import meta
from .places import BY_ID, PLACES

app = FastAPI(title="SANKOFA", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=config.DATA), name="media")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "meta_live": meta.live,
        "text_live": meta.text_live,
        "text_engine": meta.text_engine,
        "last_error": meta.last_error,
        "budget": meta.budget,
        "models": {"text": config.MODEL_TEXT, "image": config.MODEL_IMAGE,
                   "segment": config.MODEL_SEGMENT, "transcribe": config.MODEL_TRANSCRIBE},
    }


def _summary(place: dict) -> dict:
    m = load_manifest(place["id"]) or {"archives": [], "currents": []}
    years = [a["year"] for a in m["archives"]]
    return {
        **place,
        "n_archives": len(m["archives"]),
        "n_currents": len(m["currents"]),
        "n_contributions": len(m.get("contributions", [])),
        "span": [min(years), max(years)] if years else None,
        "cover": "/media/places/" + m["archives"][0]["path"] if m["archives"] else None,
        "current_cover": "/media/places/" + m["currents"][0]["path"] if m["currents"] else None,
    }


@app.get("/api/places")
def places():
    return [_summary(p) for p in PLACES]


@app.get("/api/places/{place_id}")
def place(place_id: str):
    if place_id not in BY_ID:
        raise HTTPException(404, "Unknown place")
    m = load_manifest(place_id) or {"archives": [], "currents": []}
    card = lambda a: {**{k: a.get(k) for k in ("id", "title", "year", "date_raw", "license", "artist",
                                               "page_url", "source", "description", "verified", "kind",
                                               "transcript", "note")},
                      "image": "/media/places/" + a["path"], "title": clean_title(a.get("title") or "")}
    return {**_summary(BY_ID[place_id]),
            "archives": [card(a) for a in m["archives"]],
            "currents": sorted((card(a) for a in m["currents"]),
                               key=lambda c: bool(re.search(r"detail|plaque|placa|año|sign|night|nuit|interior|neon|close",
                                                            c["title"], re.I))),
            "contributions": [card(a) for a in m.get("contributions", [])]}


@app.get("/api/showcase")
def showcase():
    """Reconstructions de démonstration, précalculées : visibles sans dépenser de crédits."""
    path = config.DATA / "showcase.json"
    return json.loads(path.read_text()) if path.exists() else {}


@app.get("/api/places/{place_id}/history")
def place_history(place_id: str):
    if place_id not in BY_ID:
        raise HTTPException(404, "Unknown place")
    return history.get(place_id) or {"events": [], "sources": [], "intro": "", "stats": {"events": 0, "corroborated": 0}}


@app.post("/api/places/{place_id}/runs")
async def create_run(place_id: str, year: int | None = Form(None), current_id: str | None = Form(None),
                     photo: UploadFile | None = File(None)):
    if place_id not in BY_ID:
        raise HTTPException(404, "Unknown place")
    current = None
    if photo is not None and photo.filename:
        dest = config.UPLOADS_DIR / f"{uuid.uuid4().hex[:10]}{Path(photo.filename).suffix.lower() or '.jpg'}"
        with dest.open("wb") as f:
            shutil.copyfileobj(photo.file, f)
        current = dest
    elif current_id:
        m = load_manifest(place_id) or {"currents": []}
        match = next((c for c in m["currents"] if c["id"] == current_id), None)
        if match:
            current = config.PLACES_DIR / match["path"]
    try:
        run = agent.start_run(place_id, year, current)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"run_id": run.id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = agent.RUNS.get(run_id)
    if run:
        return {"status": run.status, "events": run.events, "result": run.result}
    path = config.RUNS_DIR / run_id / "result.json"
    if path.exists():
        return {"status": "done", "events": [], "result": json.loads(path.read_text())}
    raise HTTPException(404, "Unknown run")


@app.get("/api/runs/{run_id}/stream")
async def stream(run_id: str):
    run = agent.RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run")

    async def gen():
        sent = 0
        while True:
            while sent < len(run.events):
                yield f"data: {json.dumps(run.events[sent], ensure_ascii=False)}\n\n"
                sent += 1
            if run.status in ("done", "error") and sent >= len(run.events):
                break
            await asyncio.sleep(0.15)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/places/{place_id}/contributions")
async def contribute(place_id: str, kind: str = Form("photo"), year: int | None = Form(None),
                     note: str = Form(""), file: UploadFile = File(...)):
    if place_id not in BY_ID:
        raise HTTPException(404, "Unknown place")
    if kind not in ("photo", "audio"):
        raise HTTPException(400, "Invalid contribution type")
    tmp = config.UPLOADS_DIR / f"tmp_{uuid.uuid4().hex[:8]}{Path(file.filename or 'x.jpg').suffix.lower()}"
    with tmp.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    entry = agent.add_contribution(place_id, kind, tmp, year, note)
    tmp.unlink(missing_ok=True)
    return entry


@app.get("/api/countries")
def countries():
    out = []
    for c in COUNTRIES:
        done = chronicle.cached(c["id"])
        out.append({**c, "stats": done["stats"] if done else None,
                    "cover": next((p["image"] for ch in (done or {}).get("chapters", []) for p in ch.get("photos", [])), None)})
    return out


@app.get("/api/countries/{country_id}")
def country(country_id: str):
    if country_id not in COUNTRY_BY_ID:
        raise HTTPException(404, "Unknown country")
    return {"country": COUNTRY_BY_ID[country_id], "chronicle": chronicle.cached(country_id)}


@app.post("/api/countries/{country_id}/chronicle")
def make_chronicle(country_id: str):
    if country_id not in COUNTRY_BY_ID:
        raise HTTPException(404, "Unknown country")
    run = agent.start_task(f"pays:{country_id}", chronicle.run_chronicle(country_id))
    return {"run_id": run.id}


@app.get("/api/music")
def music_library():
    return music.library()


@app.get("/api/documentary/{kind}/{key}")
def storyboard(kind: str, key: str, seed: int | None = None, run: str | None = None):
    try:
        if kind == "country" and key in COUNTRY_BY_ID:
            return documentary.country_storyboard(key, seed)
        if kind == "place" and key in BY_ID:
            return documentary.place_storyboard(key, run, seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    raise HTTPException(404, "Unknown")


@app.post("/api/documentary/{kind}/{key}/video")
def documentary_video(kind: str, key: str, seed: int | None = Form(None), run: str | None = Form(None)):
    known = key in COUNTRY_BY_ID if kind == "country" else key in BY_ID if kind == "place" else False
    if not known:
        raise HTTPException(404, "Unknown")
    task = agent.start_task(f"video:{kind}:{key}", documentary.make_video(kind, key, seed, run))
    return {"run_id": task.id}


# l'interface compilée est servie par le même serveur en production
_dist = config.ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = _dist / path
        return FileResponse(target if target.is_file() else _dist / "index.html")
