"""Exporte une version vitrine statique de SANKOFA (hébergement sans serveur, ex. Vercel).

Chaque réponse de l'API est enregistrée telle quelle dans static-api/*.json, et chaque fichier
/media qu'elle cite est copié (images réduites pour tenir dans les limites d'hébergement).
Usage : python export_static.py <dossier de sortie>
"""
import json
import re
import shutil
import sys
from pathlib import Path

import cv2
from fastapi.testclient import TestClient

from sankofa import config
from sankofa.countries import COUNTRIES
from sankofa.places import PLACES
from sankofa.sources import music

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "../frontend/dist-static").resolve()
MAX_SIDE, TRACKS = 820, 5

# une petite sélection de morceaux calmes suffit pour la vitrine
_all = music.library()
_subset = [t for t in _all if t["mood"] == "calme"][:TRACKS] or _all[:TRACKS]
music.library = lambda: _subset

from sankofa.api import app  # noqa: E402  (après la restriction de la bibliothèque musicale)

client = TestClient(app)
media: set[str] = set()


def save(api_path: str, data):
    dest = OUT / "static-api" / f"{api_path.removeprefix('/api/')}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False)
    dest.write_text(text)
    media.update(re.findall(r'"(/media/[^"]+)"', text))
    return data


def get(api_path: str):
    r = client.get(api_path)
    r.raise_for_status()
    return save(api_path, r.json())


health = get("/api/health")
save("/api/health", {**health, "static": True, "meta_live": False, "text_live": False, "last_error": None})
get("/api/music")
showcase = get("/api/showcase")
get("/api/places")
for p in PLACES:
    get(f"/api/places/{p['id']}")
    get(f"/api/places/{p['id']}/history")
    run = showcase.get(p["id"])
    get(f"/api/documentary/place/{p['id']}" + (f"?run={run}" if run else ""))
    # le lecteur demande /api/documentary/place/<id>?run=… : le fichier statique ignore la requête
for run in showcase.values():
    get(f"/api/runs/{run}")
get("/api/countries")
for c in COUNTRIES:
    get(f"/api/countries/{c['id']}")
    get(f"/api/documentary/country/{c['id']}")

copied, size = 0, 0
for m in sorted(media):
    src = config.DATA / m.removeprefix("/media/")
    dest = OUT / m.lstrip("/")
    if not src.is_file():
        continue
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in (".jpg", ".jpeg", ".png"):
        img = cv2.imread(str(src))
        if img is None:
            continue
        scale = min(1.0, MAX_SIDE / max(img.shape[:2]))
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        params = [cv2.IMWRITE_PNG_COMPRESSION, 9] if src.suffix.lower() == ".png" else [cv2.IMWRITE_JPEG_QUALITY, 76]
        cv2.imwrite(str(dest), img, params)
    elif src.suffix.lower() == ".mp3":  # musique de fond : 96 kb/s suffisent
        import subprocess
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-b:a", "96k", str(dest)], check=True)
    else:
        shutil.copy(src, dest)
    copied += 1
    size += dest.stat().st_size

print(f"{len(media)} fichiers média cités, {copied} copiés, {size / 1e6:.0f} Mo")
