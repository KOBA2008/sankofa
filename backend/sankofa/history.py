"""L'histoire d'un lieu : une frise datée tirée de son article Wikipédia, recoupée avec l'article anglais.

Même règle que pour les pays : chaque événement est une citation exacte, reliée à sa section.
"""
import json
import re

from .chronicle import HISTORIOGRAPHY, SKIP, _corroborate, _en_index, _importance, _proper_nouns, _sentences, find_year
from .config import PLACES_DIR
from .sources import wikipedia

# article français, article anglais
WIKI = {
    "porto-novo-marche": ("Porto-Novo", "Porto-Novo"),
    "cotonou-wharf": ("Cotonou", "Cotonou"),
    "dakar-goree": ("Île de Gorée", "Gorée"),
    "paris-parvis-notre-dame": ("Cathédrale Notre-Dame de Paris", "Notre-Dame de Paris"),
    "new-york-flatiron": ("Flatiron Building", "Flatiron Building"),
    "madrid-puerta-del-sol": ("Puerta del Sol", "Puerta del Sol"),
    "giza-pyramides": (["Complexe pyramidal de Gizeh", "Nécropole de Gizeh", "Pyramides de Gizeh"], "Giza pyramid complex"),
    "djenne-mosquee": ("Grande mosquée de Djenné", "Great Mosque of Djenné"),
    "cape-coast-castle": ("Château de Cape Coast", "Cape Coast Castle"),
    "marrakech-jemaa-el-fna": ("Place Jemaa el-Fna", "Jemaa el-Fnaa"),
    "salvador-pelourinho": ("Pelourinho", "Pelourinho"),
    "london-tower-bridge": ("Tower Bridge", "Tower Bridge"),
    "rome-colisee": ("Colisée", "Colosseum"),
    "istanbul-sainte-sophie": (["Sainte-Sophie (Istanbul)", "Basilique Sainte-Sophie", "Sainte-Sophie de Constantinople"], "Hagia Sophia"),
    "agra-taj-mahal": ("Taj Mahal", "Taj Mahal"),
    "cape-town-adderley": ("Le Cap", "Adderley Street"),
}

MAX_EVENTS = 16
# rubriques d'un article de ville qui ne racontent pas son histoire
PLACE_SKIP = re.compile(r"personnalit|jumelage|démograph|population|climat|transport|sport|économie|"
                        r"notable people|twin|demograph|climate|economy|education|enseignement", re.I)
NOT_HISTORY = re.compile(r"^[^.()]{3,60}\(\d{4}\s*[-–]\s*(\d{4})?\)\s*,|habitants|recensement|inhabitants|census",
                         re.I)


def _candidates(article: dict | None) -> list[dict]:
    if not article:
        return []
    cands = []
    for sec in article["sections"]:
        if SKIP.search(sec["title"]) or PLACE_SKIP.search(sec["title"]):
            continue
        for sent in _sentences(sec["text"]):
            fy = find_year(sent)
            if fy and not HISTORIOGRAPHY.search(sent) and not NOT_HISTORY.search(sent):
                cands.append({"year": fy[0], "label": fy[1], "text": sent, "section": sec["title"],
                              "url": sec["url"], "score": _importance(sent), "nouns": _proper_nouns(sent)})
    return cands


def build(place_id: str) -> dict | None:
    titles = WIKI.get(place_id)
    if not titles:
        return None
    fr_titles = titles[0] if isinstance(titles[0], list) else [titles[0]]
    fr = max((a for a in (wikipedia.article(t, "fr") for t in fr_titles) if a),
             key=lambda a: len(_candidates(a)), default=None)
    en = wikipedia.article(titles[1], "en")
    # un article français trop pauvre en dates cède la place à l'article anglais, l'autre sert au recoupement
    if fr and en and len(_candidates(fr)) < 6 and len(_candidates(en)) > len(_candidates(fr)):
        main, other = en, fr
    else:
        main, other = (fr, en) if fr else (en, None)
    if not main:
        return None
    sources = [{"n": 1, "title": main["title"], "url": main["url"], "lang": main["lang"],
                "license": "CC BY-SA 4.0", "source": "Wikipédia" if main["lang"] == "fr" else "Wikipedia"}]
    if other:
        sources.append({"n": 2, "title": other["title"], "url": other["url"], "lang": other["lang"],
                        "license": "CC BY-SA 4.0", "source": "Wikipédia" if other["lang"] == "fr" else "Wikipedia"})
    index = _en_index(other)
    cands = _candidates(main)
    cands.sort(key=lambda e: e["score"], reverse=True)
    events, years = [], set()
    for c in cands:
        if c["score"] <= 0 or c["year"] in years:
            continue
        c["corroborated"] = _corroborate(c["year"], c.pop("nouns"), index)
        c.pop("score")
        events.append(c)
        years.add(c["year"])
        if len(events) >= MAX_EVENTS:
            break
    events.sort(key=lambda e: e["year"])
    intro = next((s["text"] for s in main["sections"] if s["title"] == "Introduction"), "")
    result = {
        "place": place_id, "lang": main["lang"], "sources": sources, "events": events,
        "intro": " ".join(_sentences(intro)[:3])[:600],
        "stats": {"events": len(events), "corroborated": sum(e["corroborated"] for e in events)},
    }
    (PLACES_DIR / place_id / "history.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def get(place_id: str) -> dict | None:
    path = PLACES_DIR / place_id / "history.json"
    if path.exists():
        return json.loads(path.read_text())
    return build(place_id)
