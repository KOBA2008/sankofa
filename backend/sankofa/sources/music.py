"""Bibliothèque musicale : enregistrements du domaine public ou sous licence libre (Wikimedia Commons, Musopen).

Chaque morceau garde son titre, son interprète, sa licence et son lien, affichés au générique.
"""
import json
import random
import re

from ..config import DATA
from .wikimedia import API, _cached_json, _clean, _throttled_get

MUSIC_DIR = DATA / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
LIBRARY = MUSIC_DIR / "library.json"

QUERIES = [
    ("Gymnopédie Musopen", "piano"), ("Satie Gnossienne", "piano"), ("Chopin Nocturne Musopen", "piano"),
    ("Debussy Clair de lune piano", "piano"), ("Bach Cello Suite", "violoncelle"), ("Musopen violin sonata", "violon"),
    ("Musopen string quartet", "cordes"), ("Vivaldi Musopen", "cordes"), ("Beethoven Moonlight Sonata Musopen", "piano"),
    ("Schubert Impromptu Musopen", "piano"), ("Bach violin partita", "violon"), ("Grieg Musopen", "piano"),
]
CALM = re.compile(r"nocturne|gymnop|clair de lune|gnossienne|adagio|largo|moonlight|andante|lent|sarabande|air", re.I)
OPEN = ("public domain", "cc0", "cc by")


def build_library(per_query: int = 2, log=print) -> list[dict]:
    tracks = []
    for query, instrument in QUERIES:
        data = _cached_json({
            "action": "query", "format": "json", "generator": "search", "gsrsearch": f"{query} filetype:audio",
            "gsrnamespace": 6, "gsrlimit": 10, "prop": "imageinfo|videoinfo",
            "iiprop": "size|extmetadata|url", "iiextmetadatafilter": "LicenseShortName|Artist",
            "viprop": "derivatives",
        })
        kept = 0
        for page in data.get("query", {}).get("pages", {}).values():
            if kept >= per_query:
                break
            title = page["title"].removeprefix("File:")
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = _clean(meta.get("LicenseShortName", {}).get("value", ""))
            duration = info.get("duration") or 0
            mp3 = next((d["src"] for d in (page.get("videoinfo") or [{}])[0].get("derivatives", [])
                        if d["src"].endswith(".mp3")), None)
            if not mp3 or not any(k in lic.lower() for k in OPEN) or not 100 <= duration <= 420:
                continue
            # pas de voix : on écarte lectures, livres audio et chansons
            if re.search(r"backing track|wikiorchestra|excerpt|ringtone|midi|kafka|lesung|hörbuch|reading|"
                         r"audiobook|lied|song|vocal|chant", title, re.I):
                continue
            tid = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50].strip("-")
            if any(t["id"] == tid for t in tracks):
                continue
            dest = MUSIC_DIR / f"{tid}.mp3"
            log(f"Musique : {title}")
            if not dest.exists():
                dest.write_bytes(_throttled_get(mp3, binary=True))
            tracks.append({
                "id": tid, "title": re.sub(r"\.(ogg|oga|flac|opus|wav|mp3)$", "", title, flags=re.I),
                "instrument": instrument, "mood": "calme" if CALM.search(title) else "lumineux",
                "artist": _clean(meta.get("Artist", {}).get("value", ""))[:120], "license": lic,
                "duration": round(duration), "page_url": info.get("descriptionurl", ""),
                "file": f"/media/music/{dest.name}",
            })
            kept += 1
    LIBRARY.write_text(json.dumps(tracks, ensure_ascii=False, indent=1))
    return tracks


def library() -> list[dict]:
    return json.loads(LIBRARY.read_text()) if LIBRARY.exists() else []


def pick(seed: int | None = None, mood: str | None = None) -> dict | None:
    tracks = library()
    if mood:
        tracks = [t for t in tracks if t["mood"] == mood] or tracks
    return random.Random(seed).choice(tracks) if tracks else None
