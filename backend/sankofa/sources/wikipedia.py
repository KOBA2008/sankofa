"""Lecture des articles d'histoire de Wikipédia (texte brut, découpé en sections)."""
import hashlib
import json
import re

from ..config import CACHE_DIR
from .wikimedia import _throttled_get


def article(title: str, lang: str = "fr") -> dict | None:
    """Renvoie {title, url, lang, sections: [{title, level, text}]} ou None si l'article n'existe pas."""
    params = {"action": "query", "format": "json", "prop": "extracts", "explaintext": 1,
              "exsectionformat": "wiki", "titles": title, "redirects": 1}
    key = hashlib.sha1(f"{lang}|{json.dumps(params, sort_keys=True)}".encode()).hexdigest()
    path = CACHE_DIR / f"wikipedia_{key}.json"
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = _throttled_get(f"https://{lang}.wikipedia.org/w/api.php", params)
        path.write_text(json.dumps(data))
    page = next(iter(data.get("query", {}).get("pages", {}).values()), {})
    text = page.get("extract")
    if not text:
        return None
    real_title = page["title"]
    base = f"https://{lang}.wikipedia.org/wiki/{real_title.replace(' ', '_')}"
    sections, current = [], {"title": "Introduction", "level": 2, "lines": []}
    for line in text.split("\n"):
        m = re.match(r"^(={2,4})\s*(.+?)\s*\1$", line.strip())
        if m:
            sections.append(current)
            current = {"title": m.group(2), "level": len(m.group(1)), "lines": []}
        elif line.strip():
            current["lines"].append(line.strip())
    sections.append(current)
    out = []
    for s in sections:
        body = " ".join(s["lines"]).strip()
        if body:
            out.append({"title": s["title"], "level": s["level"], "text": body,
                        "url": f"{base}#{s['title'].replace(' ', '_')}" if s["title"] != "Introduction" else base})
    return {"title": real_title, "url": base, "lang": lang, "sections": out}
