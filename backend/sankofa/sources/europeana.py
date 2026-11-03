"""Enquête dans Europeana : musées et archives d'Europe (Rijksmuseum, archives nationales, bibliothèques).

La clé publique de démonstration suffit pour un prototype ; une clé personnelle
(gratuite) se renseigne dans EUROPEANA_KEY.
"""
import hashlib
import json
import os

import httpx

from ..config import CACHE_DIR, USER_AGENT
from .wikimedia import parse_year

API = "https://api.europeana.eu/record/v2/search.json"
KEY = os.getenv("EUROPEANA_KEY", "api2demo")

_LICENSES = {
    "publicdomain/mark": "Public domain",
    "publicdomain/zero": "CC0",
    "licenses/by/": "CC BY",
    "licenses/by-sa/": "CC BY-SA",
    "rightsstatements.org/vocab/NoC": "No restrictions",
}


def _license(url: str) -> str:
    return next((name for k, name in _LICENSES.items() if k in url), "")


def search(query: str, years: tuple[int, int] = (1840, 1960), rows: int = 40) -> list[dict]:
    params = {"wskey": KEY, "query": query, "rows": rows, "media": "true", "reusability": "open",
              "qf": ["TYPE:IMAGE", f"YEAR:[{years[0]} TO {years[1]}]"], "profile": "rich"}
    key = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()
    path = CACHE_DIR / f"europeana_{key}.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        try:
            r = httpx.get(API, params=params, headers={"User-Agent": USER_AGENT}, timeout=40)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return []
        path.write_text(json.dumps(data))

    docs = []
    for it in data.get("items", []):
        first = lambda k: (it.get(k) or [""])[0]
        image = first("edmIsShownBy") or first("edmPreview")
        year = parse_year(" ".join(it.get("year", []) or [])) or parse_year(first("title"))
        lic = _license(first("rights"))
        if not image or not lic:
            continue
        desc = it.get("dcDescriptionLangAware") or {}
        description = next(iter(desc.values()), [""])[0] if desc else first("dcDescription")
        docs.append({
            "source": f"Europeana · {first('dataProvider')}".strip(" ·"),
            "title": first("title")[:200],
            "file": it.get("id", ""),
            "date_raw": " ".join(it.get("year", []) or []),
            "year": year,
            "license": lic,
            "artist": first("dcCreator")[:120],
            "credit": first("dataProvider"),
            "description": (description or "")[:600],
            "page_url": it.get("guid", ""),
            "thumb_url": image,
            "width": None,
            "height": None,
        })
    return docs
