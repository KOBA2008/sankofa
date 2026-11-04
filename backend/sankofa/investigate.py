"""Étape 1 de l'agent : enquêter dans les archives et constituer le corpus d'un lieu."""
import hashlib
import json
import re
from pathlib import Path

from .config import PLACES_DIR
import cv2
import numpy as np

from .sources import europeana, wikimedia

OPEN_LICENSES = ("public domain", "cc0", "cc by", "no restrictions", "licence ouverte", "pd-", "ogl")
ARCHIVE_MIN_YEAR = 1839  # invention de la photographie
ARCHIVE_MAX_YEAR = 1960
CURRENT_MIN_YEAR = 2008


def is_open(license_name: str) -> bool:
    low = (license_name or "").lower()
    return any(k in low for k in OPEN_LICENSES) and "nc" not in low.split()


def relevance(doc: dict, place: dict, target_year: int) -> float:
    """Score heuristique : le document parle-t-il bien de ce lieu, à la bonne époque ?"""
    text = f"{doc['title']} {doc['description']}".lower()
    hits = sum(text.count(k) for k in place["keywords"])
    # une image géolocalisée à quelques centaines de mètres compte comme une mention du lieu
    if doc.get("geo_dist") is not None:
        hits += 2 if doc["geo_dist"] < 250 else 1
    if hits == 0:
        return 0.0
    if place.get("require") and not any(r in text for r in place["require"]):
        return 0.0
    if any(x in text for x in place.get("exclude", [])):
        return 0.0
    # gravures, peintures et intérieurs ne montrent pas le lieu tel qu'il était
    if re.search(r"peinture|painting|lithograph|gravure|engraving|dîner|interior|intérieur|aquarelle|drawing|dessin|"
                 r"sketch|watercolou?r|tableau|längsschnitt|laengsschnitt|schnitt|lumpenball|schwender|"
                 r"musée des beaux|\bppp\d|livingstone|toverlantaarn|"
                 # peintres repérés parmi les résultats
                 r"maximilien luce|aivazovsky|duvieux|félix ziem|cammarano|raffaëlli|ernest lawson|colin campbell cooper|"
                 r"pennell|romilly fedden", text):
        return 0.0
    score = min(hits, 3) * 2.0
    year = doc.get("year")
    if year:
        score += max(0.0, 3.0 - abs(year - target_year) / 15)
    if (doc.get("width") or 0) >= 1000:
        score += 0.5
    # portraits, documents textuels, cartes, peintures : ce ne sont pas des vues photographiques du lieu
    if re.search(r"portrait|portret|lettre|letter|census|enumeration|plakat|banner|\bmap\b|carte de|chemin de fer|"
                 r"locomotive|voiture de|goliath|avion|record du monde|\bfig\b|beiträge|fauna|flora|identifier:|bookid|"
                 r"internet archive book|journal of|bulletin|annual report|admiralty|\bchart\b|plan du|plano |"
                 r"postal|stamp|timbre|frimärke|médaille|handatlas|google art project|oil on canvas|huile sur toile|"
                 r"\bking\b|\broi\b|deputado|coronel|faculdade|colégio", text):
        return 0.0
    return round(score, 2)


def clean_title(title: str) -> str:
    """Titre lisible : sans cote d'inventaire ni identifiant technique."""
    t = re.sub(r"\s*[-–]\s*(btv\w+|A\d{4,}\w*|\w*\d{6,}\w*)$", "", title)
    t = re.sub(r"\s*\(?\b(LCCN\w+|RP-F-[\w-]+|PH\d+|D\.\d+|CP\d+)\b\)?", "", t)
    t = re.sub(r"\s*\(\d{8,}\)", "", t)
    t = re.sub(r"(\s*--\s*\d+)+$", "", t)
    t = t.replace("_", " ").strip(" -–,")
    return t[:1].upper() + t[1:] if t else title


def _old_year_in_title(title: str) -> bool:
    y = wikimedia.parse_year(title)
    return bool(y and y <= ARCHIVE_MAX_YEAR)


def _dedupe_key(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\b(lccn\w+|btv\w+|rp-f-[\w-]+|\(\d{8,}\)|crop|edit)\b", " ", t)
    t = re.sub(r"[\s_\-–()\"'.,]+\d{0,2}$", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()[:60]


def collect(place: dict, target_year: int | None = None, log=lambda *_: None) -> dict:
    target_year = target_year or place["era"]
    seen, keys, archives, currents = set(), set(), [], []
    def batches():
        # recherches par décennie, avec le nom le plus caractéristique du lieu
        by_decade = [f"{place['keywords'][0]} {d}" for d in (1880, 1900, 1920, 1940)]
        for q in place["archive_queries"] + by_decade + place["current_queries"]:
            log(f"Wikimedia Commons: “{q}”")
            yield wikimedia.search(q)
        radius = int(place.get("radius", 350) * 1.5)
        log(f"Wikimedia Commons: geotagged images within {radius} m")
        yield wikimedia.geosearch(place["lat"], place["lon"], radius, limit=120)
        for q in place.get("europeana_queries", place["archive_queries"][:2]):
            log(f"Europeana: “{q}”")
            yield europeana.search(q)

    for batch in batches():
        for doc in batch:
            if doc["file"] in seen or not is_open(doc["license"]) or not doc["year"]:
                continue
            seen.add(doc["file"])
            key = _dedupe_key(doc["title"])
            if key in keys:
                continue
            keys.add(key)
            if ARCHIVE_MIN_YEAR <= doc["year"] <= ARCHIVE_MAX_YEAR:
                doc["score"] = relevance(doc, place, target_year)
                if doc["score"] > 0:
                    archives.append(doc)
            elif doc["year"] >= CURRENT_MIN_YEAR and not _old_year_in_title(doc["title"]):
                doc["score"] = relevance(doc, place, 2024)
                if doc["score"] > 0:
                    currents.append(doc)
    archives.sort(key=lambda d: d["score"], reverse=True)
    currents.sort(key=lambda d: d["score"], reverse=True)
    return {"archives": archives, "currents": currents}


def build_corpus(place: dict, n_archives: int = 30, n_currents: int = 12, log=print) -> dict:
    """Télécharge le corpus d'un lieu dans data/places/<id>/ et écrit manifest.json."""
    root = PLACES_DIR / place["id"]
    (root / "archive").mkdir(parents=True, exist_ok=True)
    (root / "current").mkdir(parents=True, exist_ok=True)
    found = collect(place, log=log)
    manifest = {"place": place["id"], "archives": [], "currents": []}
    for kind, docs, limit in (("archive", found["archives"], n_archives), ("current", found["currents"], n_currents)):
        for i, doc in enumerate(docs[:limit]):
            if not doc["thumb_url"]:
                continue
            ext = Path(doc["thumb_url"].split("?")[0]).suffix.lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png"):
                ext = ".jpg"
            local = root / kind / f"{hashlib.sha1(doc['thumb_url'].encode()).hexdigest()[:12]}{ext}"
            log(f"Downloading {kind} {i + 1}/{min(limit, len(docs))}: {doc['title'][:70]}")
            try:
                wikimedia.download(doc["thumb_url"], local)
                if not _valid_image(local):
                    raise ValueError("unreadable or too small file")
                if kind == "current" and not _is_color_photo(local):
                    raise ValueError("black-and-white or sepia “current” view: probably a misdated archive")
            except Exception as exc:  # une image manquante ne bloque pas le corpus
                log(f"  failed: {exc}")
                local.unlink(missing_ok=True)
                continue
            doc = {**doc, "id": f"{kind}-{i:02d}", "path": str(local.relative_to(PLACES_DIR))}
            manifest["archives" if kind == "archive" else "currents"].append(doc)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def _valid_image(path: Path) -> bool:
    """Europeana renvoie parfois une page HTML ou une vignette minuscule au lieu de l'image."""
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_REDUCED_GRAYSCALE_2)
    if img is None or min(img.shape[:2]) < 150:
        return False
    if max(img.shape[:2]) > 1800:  # on garde une taille raisonnable sur disque
        full = cv2.imread(str(path))
        scale = 1600 / max(full.shape[:2])
        cv2.imwrite(str(path), cv2.resize(full, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
    return True


def _is_color_photo(path: Path) -> bool:
    """Une vue « actuelle » doit être en couleur : en noir et blanc ou en sépia, la variation de
    chrominance (canaux a et b de l'espace Lab) reste presque nulle."""
    img = cv2.imread(str(path), cv2.IMREAD_REDUCED_COLOR_4)
    if img is None:
        return False
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    return float(lab[..., 1].std() + lab[..., 2].std()) >= 4.0


def load_manifest(place_id: str) -> dict | None:
    path = PLACES_DIR / place_id / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else None
