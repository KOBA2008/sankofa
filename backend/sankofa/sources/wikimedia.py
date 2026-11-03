"""Enquête dans Wikimedia Commons : recherche, métadonnées, téléchargement.

Commons limite fortement le débit : on espace les appels, on respecte Retry-After
et on met chaque réponse en cache disque pour ne jamais redemander la même chose.
"""
import hashlib
import json
import re
import time
from pathlib import Path

import httpx

from ..config import CACHE_DIR, USER_AGENT

API = "https://commons.wikimedia.org/w/api.php"
_HEADERS = {"User-Agent": USER_AGENT}
_MIN_INTERVAL = 1.5
_last_call = 0.0


def _throttled_get(url: str, params: dict | None = None, binary: bool = False):
    global _last_call
    for attempt in range(6):
        wait = _MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        r = httpx.get(url, params=params, headers=_HEADERS, timeout=60, follow_redirects=True)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("retry-after", 5 * (attempt + 1))))
            continue
        r.raise_for_status()
        return r.content if binary else r.json()
    raise RuntimeError(f"Commons indisponible : {url}")


def _cached_json(params: dict) -> dict:
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()
    path = CACHE_DIR / f"commons_{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = _throttled_get(API, params)
    path.write_text(json.dumps(data))
    return data


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_year(raw: str) -> int | None:
    """Première année plausible trouvée dans un champ date de Commons."""
    m = re.search(r"\b(1[6-9]\d\d|20[0-2]\d)\b", raw or "")
    return int(m.group(1)) if m else None


def search(query: str, limit: int = 40, width: int = 1600) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": width,
        "iiextmetadatafilter": "DateTimeOriginal|LicenseShortName|ImageDescription|Artist|Credit|ObjectName",
    }
    pages = _cached_json(params).get("query", {}).get("pages", {})
    return [d for d in (_page_to_doc(p) for p in pages.values()) if d]


def _page_to_doc(page: dict) -> dict | None:
    if "imageinfo" not in page:
        return None
    info = page["imageinfo"][0]
    meta = info.get("extmetadata", {})
    get = lambda k: _clean(meta.get(k, {}).get("value", ""))
    date_raw = get("DateTimeOriginal")
    title = page["title"].removeprefix("File:")
    return {
        "source": "Wikimedia Commons",
        "title": re.sub(r"\.(jpe?g|png|tiff?|gif)$", "", title, flags=re.I),
        "file": title,
        "date_raw": date_raw[:80],
        "year": parse_year(date_raw) or parse_year(title),
        "license": get("LicenseShortName"),
        "artist": get("Artist")[:120],
        "credit": get("Credit")[:200],
        "description": get("ImageDescription")[:600],
        "page_url": info.get("descriptionurl", ""),
        "thumb_url": info.get("thumburl") or info.get("url", ""),
        "width": info.get("thumbwidth") or info.get("width"),
        "height": info.get("thumbheight") or info.get("height"),
    }


def geosearch(lat: float, lon: float, radius: int = 400, limit: int = 60, width: int = 1600) -> list[dict]:
    """Toutes les images géolocalisées dans un rayon autour d'un lieu, anciennes comme récentes."""
    found = _cached_json({"action": "query", "format": "json", "list": "geosearch", "gscoord": f"{lat}|{lon}",
                          "gsradius": radius, "gsnamespace": 6, "gslimit": limit})
    hits = {g["title"]: g.get("dist") for g in found.get("query", {}).get("geosearch", [])}
    results = []
    titles = list(hits)
    for i in range(0, len(titles), 25):
        params = {
            "action": "query", "format": "json", "titles": "|".join(titles[i:i + 25]),
            "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": width,
            "iiextmetadatafilter": "DateTimeOriginal|LicenseShortName|ImageDescription|Artist|Credit|ObjectName",
        }
        for page in _cached_json(params).get("query", {}).get("pages", {}).values():
            doc = _page_to_doc(page)
            if doc:
                doc["geo_dist"] = hits.get(page["title"])
                results.append(doc)
    return results


def download(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.write_bytes(_throttled_get(url, binary=True))
    return dest
