"""Le documentaire : l'histoire racontée en images d'archives, en texte à l'écran et en musique.

Un « storyboard » décrit les plans (titre, chapitre, événement, avant/après, lacunes, générique).
L'interface le joue en direct ; render_mp4() le transforme en vidéo avec ffmpeg.
Aucune image n'est inventée : seulement des archives et des photos actuelles, toutes créditées.
"""
import hashlib
import json
import random
import subprocess
import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import chronicle, config
from .countries import BY_ID as COUNTRIES
from .investigate import clean_title, load_manifest
from .places import BY_ID as PLACES
from .sources import music
from .sources.wikimedia import _throttled_get

VIDEOS_DIR = config.DATA / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
FONTS = config.ROOT / "backend" / "assets" / "fonts"
W, H, FPS = 1280, 720, 25


def _trim(text: str, limit: int = 230) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def _duration(text: str) -> float:
    return round(min(9.5, max(4.5, 3.0 + len(text) / 38)), 1)


# ---------------------------------------------------------------------- storyboards

def country_storyboard(country_id: str, seed: int | None = None) -> dict:
    chron = chronicle.cached(country_id)
    if not chron:
        raise ValueError("This country's chronicle has not been built yet.")
    country = COUNTRIES[country_id]
    photos = [p for c in chron["chapters"] for p in c["photos"]]
    # réserves d'images pour les chapitres sans photo d'époque : archives et vues actuelles des lieux du pays
    old_pool, new_pool = [], []
    for pid in country["places"]:
        m = load_manifest(pid) or {"archives": [], "currents": []}
        old_pool += [{"image": "/media/places/" + a["path"], "year": a["year"], "title": a["title"],
                      "license": a["license"], "where": PLACES[pid]["city"]} for a in m["archives"][:6]]
        new_pool += [{"image": "/media/places/" + c["path"], "year": c["year"], "title": c["title"],
                      "license": c["license"], "where": PLACES[pid]["city"]} for c in m["currents"][:6]]
    scenes = [{"type": "title", "image": photos[0]["image"] if photos else None, "title": country["name"],
               "subtitle": "A history told only by its sources",
               "eyebrow": " · ".join(country["old_names"][:2]), "duration": 5.5}]
    for c in chron["chapters"]:
        if not c["events"]:
            continue
        span = f"{c['events'][0]['label']} – {c['events'][-1]['label']}" if len(c["events"]) > 1 else c["events"][0]["label"]
        pics = c["photos"] or (new_pool if (c["start"] or 0) >= 1960 else old_pool)[len(scenes) % 3::3][:4]
        imgs = [p["image"] for p in pics]
        caps = [f"Photo {p['year']}" + (f" · {p['where']}" if p.get("where") else "") for p in pics]
        scenes.append({"type": "chapter", "image": imgs[0] if imgs else None, "title": c["title"],
                       "year": span, "caption": caps[0] if caps else None, "duration": 4.0})
        # les événements recoupés passent en premier, puis on garde l'ordre chronologique
        chosen = sorted(sorted(c["events"], key=lambda e: not e["corroborated"])[:3], key=lambda e: e["year"])
        for i, e in enumerate(chosen):
            text = _trim(e["text"])
            j = (i + 1) % len(imgs) if imgs else 0
            scenes.append({"type": "event", "image": imgs[j] if imgs else None, "year": e["label"],
                           "caption": caps[j] if caps else None,
                           "text": text, "badge": "corroborated" if e["corroborated"] else "single source",
                           "source": f"S{e['source']}", "duration": _duration(text)})
    if chron["gaps"]:
        scenes.append({"type": "gap", "image": None, "title": "What the sources leave out",
                       "text": _trim(chron["gaps"][0]["text"], 200), "duration": 6.0})
    credits = [f"S{s['n']} · {s['title']} ({s['license']})" for s in chron["sources"]]
    credits += [f"Photo {p['year']} · {clean_title(p['title'])[:70]} ({p['license']})" for p in photos + old_pool[:4] + new_pool[:4]]
    return _finish({"kind": "country", "id": country_id, "title": country["name"], "scenes": scenes}, credits, seed)


def place_storyboard(place_id: str, run_id: str | None = None, seed: int | None = None) -> dict:
    place = PLACES[place_id]
    m = load_manifest(place_id) or {"archives": [], "currents": []}
    result = None
    if run_id:
        path = config.RUNS_DIR / run_id / "result.json"
        result = json.loads(path.read_text()) if path.exists() else None
    current = result["current"] if result else ("/media/places/" + m["currents"][0]["path"] if m["currents"] else None)
    scenes = [{"type": "title", "image": current, "title": place["city"], "subtitle": place["name"],
               "eyebrow": f"{place['country']} · today", "duration": 5.0}]
    if result:
        scenes.append({"type": "compare", "image": result["current"], "image_b": result["reconstruction"],
                       "year": f"around {result['year']}", "title": "Today's view dissolves into the past",
                       "duration": 6.5})
    archives = sorted(m["archives"][:12], key=lambda a: a["year"])
    from . import history
    hist = history.get(place_id) or {"events": []}
    events = hist["events"]
    if len(events) > 9:  # on garde un échantillon réparti sur toute la frise
        events = [events[round(i * (len(events) - 1) / 8)] for i in range(9)]
    if events:
        scenes.append({"type": "chapter", "image": "/media/places/" + archives[0]["path"] if archives else None,
                       "title": "Its history", "year": f"{events[0]['label']} – {events[-1]['label']}",
                       "caption": f"Photo {archives[0]['year']}" if archives else None, "duration": 4.0})
        for i, e in enumerate(events):
            a = archives[(i + 1) % len(archives)] if archives else None
            text = _trim(e["text"])
            scenes.append({"type": "event", "image": "/media/places/" + a["path"] if a else None, "year": e["label"],
                           "caption": f"Photo {a['year']}" if a else None, "text": text,
                           "badge": "corroborated" if e["corroborated"] else "single source", "source": "Wikipedia",
                           "duration": _duration(text)})
        scenes.append({"type": "chapter", "image": "/media/places/" + archives[-1]["path"] if archives else None,
                       "title": "The archives", "year": f"{archives[0]['year']} – {archives[-1]['year']}" if archives else "",
                       "duration": 3.5})
    for a in archives:
        text = _trim(clean_title(a["title"]), 140)
        scenes.append({"type": "event", "image": "/media/places/" + a["path"], "year": str(a["year"]),
                       "text": text, "badge": a["license"], "source": a.get("source", ""), "duration": 5.0})
    scenes.append({"type": "gap", "image": None, "title": "The place", "text": _trim(place["context"], 220), "duration": 7.0})
    credits = [f"{a['year']} · {clean_title(a['title'])[:70]} ({a['license']}, {a.get('source', '')})" for a in archives]
    credits = [f"{s['title']} · Wikipedia ({s['license']})" for s in hist.get("sources", [])] + credits
    return _finish({"kind": "place", "id": place_id, "title": place["city"], "scenes": scenes}, credits, seed)


def _finish(board: dict, credits: list[str], seed: int | None) -> dict:
    seed = seed if seed is not None else random.randrange(1_000_000)
    track = music.pick(seed)
    if track:
        credits.append(f"Music · {track['title']} · {track['artist'] or 'performer not credited'} ({track['license']})")
    board["scenes"].append({"type": "credits", "image": None, "title": "Sources", "lines": credits[:18],
                            "duration": min(14.0, 5.0 + len(credits) * 0.45)})
    board["music"] = track
    board["seed"] = seed
    board["total"] = round(sum(s["duration"] for s in board["scenes"]), 1)
    return board


# ---------------------------------------------------------------------- rendu MP4

def _local_image(url: str | None) -> np.ndarray | None:
    if not url:
        return None
    if url.startswith("/media/"):
        path = config.DATA / url.removeprefix("/media/")
    else:
        path = config.CACHE_DIR / f"img_{hashlib.sha1(url.encode()).hexdigest()}.jpg"
        if not path.exists():
            try:
                path.write_bytes(_throttled_get(url, binary=True))
            except Exception:
                return None
    return cv2.imread(str(path))


def _cover(img: np.ndarray, scale: float = 1.18) -> np.ndarray:
    """Recadre l'image pour couvrir le cadre 16:9 avec une marge pour le mouvement de caméra."""
    tw, th = int(W * scale), int(H * scale)
    h, w = img.shape[:2]
    s = max(tw / w, th / h)
    img = cv2.resize(img, (int(w * s) + 1, int(h * s) + 1), interpolation=cv2.INTER_AREA)
    y0, x0 = (img.shape[0] - th) // 2, (img.shape[1] - tw) // 2
    return img[y0:y0 + th, x0:x0 + tw]


def _background(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:int(H * 1.18), 0:int(W * 1.18)].astype(np.float32)
    glow = np.exp(-(((xx - W * 0.4) / (W * 0.7)) ** 2 + ((yy - H * 0.3) / (H * 0.8)) ** 2))
    base = np.stack([12 + 20 * glow, 14 + 26 * glow, 18 + 34 * glow], -1)
    base += rng.normal(0, 3, base.shape[:2])[..., None]
    return np.clip(base, 0, 255).astype(np.uint8)


def _font(name: str, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    if weight:
        try:
            f.set_variation_by_axes([14, weight] if "Inter" in name else [weight])
        except Exception:
            pass
    return f


def _wrap(draw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


GOLD, WHITE, MUTED = (244, 222, 160), (243, 241, 236), (190, 186, 178)
GREEN, AMBER = (52, 211, 153), (251, 191, 36)


def _shadowed(d, xy, text, font, fill):
    """Texte avec une ombre douce : lisible sur n'importe quelle photo."""
    x, y = xy
    for dx, dy in ((0, 2), (1, 3), (2, 2)):
        d.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 110))
    d.text((x, y), text, font=font, fill=fill)


def _overlay(scene: dict) -> np.ndarray:
    """Calque RGBA du plan : dégradé de lisibilité + typographie."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = np.zeros((H, W, 4), np.uint8)
    t = scene["type"]
    ramp = np.linspace(0, 1, H)[:, None] ** (1.6 if t in ("event", "compare") else 1.0)
    grad[..., 3] = (np.clip(ramp * (235 if t in ("event", "compare") else 170) + (60 if t != "event" else 0), 0, 255)).astype(np.uint8)
    img = Image.alpha_composite(img, Image.fromarray(grad, "RGBA"))
    d = ImageDraw.Draw(img)
    x = 90
    if t == "title":
        d.text((x, 250), scene.get("eyebrow", "").upper(), font=_font("JetBrainsMono-Variable.ttf", 20), fill=GOLD)
        d.text((x, 285), scene["title"], font=_font("InstrumentSerif-Regular.ttf", 132), fill=WHITE)
        d.text((x, 440), scene.get("subtitle", ""), font=_font("InstrumentSerif-Italic.ttf", 44), fill=GOLD)
    elif t == "chapter":
        d.text((x, 470), scene.get("year", ""), font=_font("JetBrainsMono-Variable.ttf", 26), fill=GOLD)
        f = _font("InstrumentSerif-Regular.ttf", 76)
        for i, line in enumerate(_wrap(d, scene["title"], f, W - 2 * x)[:2]):
            d.text((x, 510 + i * 80), line, font=f, fill=WHITE)
    elif t in ("event", "compare"):
        f = _font("Inter-Variable.ttf", 30, 500)
        lines = _wrap(d, f"“{scene['text']}”" if t == "event" else "", f, W - 2 * x)[:5]
        y = H - 80 - len(lines) * 42 - (40 if t == "compare" else 0)
        _shadowed(d, (x, y - 92), scene.get("year", ""), _font("InstrumentSerif-Regular.ttf", 72), GOLD)
        if t == "compare":
            d.text((x, H - 80), scene.get("title", ""), font=_font("InstrumentSerif-Italic.ttf", 40), fill=WHITE)
        for i, line in enumerate(lines):
            _shadowed(d, (x, y + i * 43), line, f, WHITE)
        if scene.get("badge"):
            color = GREEN if scene["badge"] == "corroborated" else AMBER if scene["badge"] == "single source" else MUTED
            bf = _font("Inter-Variable.ttf", 20, 500)
            label = f"● {scene['badge']}" + (f"   {scene['source']}" if scene.get("source") else "")
            d.text((W - x - d.textlength(label, font=bf), y - 60), label, font=bf, fill=color)
    elif t == "gap":
        d.text((x, 230), scene["title"], font=_font("InstrumentSerif-Regular.ttf", 64), fill=AMBER)
        f = _font("Inter-Variable.ttf", 32, 500)
        for i, line in enumerate(_wrap(d, scene["text"], f, W - 2 * x)[:6]):
            _shadowed(d, (x, 330 + i * 47), line, f, WHITE)
    if scene.get("caption"):
        cf = _font("JetBrainsMono-Variable.ttf", 16)
        _shadowed(d, (W - 90 - d.textlength(scene["caption"], font=cf), 40), scene["caption"], cf, (225, 222, 214))
    if t == "credits":
        d.text((x, 70), scene["title"], font=_font("InstrumentSerif-Regular.ttf", 60), fill=GOLD)
        f = _font("Inter-Variable.ttf", 18, 400)
        for i, line in enumerate(scene["lines"][:18]):
            d.text((x, 160 + i * 28), textwrap.shorten(line, 120, placeholder="…"), font=f, fill=MUTED)
        d.text((x, H - 60), "SANKOFA · no image was invented", font=_font("JetBrainsMono-Variable.ttf", 18), fill=GOLD)
    return np.array(img)


def render_mp4(board: dict, out: Path, log=lambda *_: None) -> Path:
    total = board["total"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    track = board.get("music")
    if track:
        cmd += ["-stream_loop", "-1", "-i", str(config.DATA / track["file"].removeprefix("/media/"))]
    cmd += ["-t", str(total), "-map", "0:v"]
    if track:
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "160k",
                "-af", f"afade=t=in:st=0:d=2.5,afade=t=out:st={max(0, total - 4)}:d=4"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    fade = int(0.6 * FPS)
    try:
        for k, scene in enumerate(board["scenes"]):
            log(k, scene)
            n = max(1, int(scene["duration"] * FPS))
            src = _local_image(scene.get("image"))
            a = _cover(src) if src is not None else _background(k)
            b = _cover(_local_image(scene.get("image_b"))) if scene.get("image_b") else None
            if src is not None and scene["type"] in ("chapter", "gap", "credits"):
                a = cv2.GaussianBlur(a, (0, 0), 6) if scene["type"] != "chapter" else a
            ov = _overlay(scene)
            ov_rgb = ov[..., :3][..., ::-1].astype(np.float32)
            alpha = ov[..., 3:4].astype(np.float32) / 255
            zoom_in = k % 2 == 0
            for i in range(n):
                p = i / max(n - 1, 1)
                # lent zoom avant ou arrière (effet « Ken Burns ») dans l'image agrandie de 18 %
                z = 1.0 + 0.15 * (p if zoom_in else 1 - p)
                cw = int(a.shape[1] / z)
                ch = int(cw * H / W)
                dx = int((a.shape[1] - cw) * (0.3 + 0.4 * (p if k % 3 else 1 - p)))
                dy = (a.shape[0] - ch) // 2
                frame = cv2.resize(a[dy:dy + ch, dx:dx + cw], (W, H), interpolation=cv2.INTER_LINEAR)
                if b is not None:  # avant / après : la vue actuelle se dissout dans le passé
                    fb = cv2.resize(b[dy:dy + ch, dx:dx + cw], (W, H), interpolation=cv2.INTER_LINEAR)
                    mix = np.clip((p - 0.25) / 0.4, 0, 1)
                    frame = cv2.addWeighted(frame, 1 - mix, fb, mix, 0)
                frame = (frame.astype(np.float32) * (1 - alpha) + ov_rgb * alpha)
                edge = min(i, n - 1 - i)
                if edge < fade:  # fondu au noir entre les plans
                    frame *= edge / fade
                proc.stdin.write(frame.astype(np.uint8).tobytes())
        proc.stdin.close()
    finally:
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    return out


def make_video(kind: str, key: str, seed: int | None, run_id: str | None):
    def pipeline(run):
        run.emit("storyboard", "running", "I cut the story into shots.")
        board = country_storyboard(key, seed) if kind == "country" else place_storyboard(key, run_id, seed)
        run.emit("storyboard", "done", f"{len(board['scenes'])} plans, {board['total']} s, musique : "
                 f"{board['music']['title'] if board['music'] else 'aucune'}.")
        run.emit("rendu", "running", "I assemble the video frame by frame.")
        out = VIDEOS_DIR / f"{kind}-{key}-{board['seed']}.mp4"
        total = len(board["scenes"])
        render_mp4(board, out, log=lambda k, s: run.emit("rendu", "log", f"Plan {k + 1}/{total} : {s['type']}",
                                                         progress=round(k / total, 2)))
        run.emit("rendu", "done", f"Video ready ({out.stat().st_size // 1_000_000} MB).")
        return {"video": f"/media/videos/{out.name}", "board": board}
    return pipeline
