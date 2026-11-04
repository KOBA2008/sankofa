"""L'agent SANKOFA : enquête, annote, aligne, apprend le style, reconstruit, s'évalue, raconte.

Chaque étape publie des événements que l'interface affiche en direct. Le champ « engine »
dit honnêtement qui a fait le travail : la Meta Model API ou le moteur local.
"""
import hashlib
import json
import re
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from . import vision
from .config import CACHE_DIR, PLACES_DIR, RUNS_DIR
from .investigate import build_corpus, clean_title, load_manifest
from .meta import meta
from .places import BY_ID

# SAM 3.1 traite un concept par requête : deux concepts suffisent, le ciel est détecté localement
CONCEPTS = ["building", "road"]
STEPS = [
    ("enquete", "Enquête dans les archives"),
    ("annotation", "Annotation de la vue actuelle"),
    ("alignement", "Re-photographie : alignement des archives"),
    ("style", "Apprentissage du style de la ville"),
    ("reconstruction", "Reconstruction du passé"),
    ("evaluation", "Auto-évaluation sur archives cachées"),
    ("recit", "Récit sourcé du lieu"),
]


@dataclass
class Run:
    id: str
    place_id: str
    year: int
    current: Path | None
    status: str = "pending"
    events: list = field(default_factory=list)
    result: dict | None = None
    cond: threading.Condition = field(default_factory=threading.Condition)

    @property
    def dir(self) -> Path:
        return RUNS_DIR / self.id

    def emit(self, step: str, status: str, message: str, engine: str = "local", **data):
        ev = {"t": round(time.time(), 2), "step": step, "status": status, "message": message,
              "engine": engine, "data": data}
        with self.cond:
            self.events.append(ev)
            self.cond.notify_all()
        with open(self.dir / "events.jsonl", "a") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


RUNS: dict[str, Run] = {}


def _cached_align(a_path: Path, c_path: Path, a_img: np.ndarray, c_img: np.ndarray) -> vision.Alignment:
    """L'alignement est déterministe : on le mémorise par couple d'images et de tailles."""
    key = f"{a_path}|{a_path.stat().st_mtime}|{c_path}|{c_path.stat().st_mtime}|{a_img.shape}|{c_img.shape}"
    path = CACHE_DIR / f"align_{hashlib.sha1(key.encode()).hexdigest()}.json"
    if path.exists():
        d = json.loads(path.read_text())
        return vision.Alignment(np.array(d["H"]) if d["H"] is not None else None, d["inliers"], d["ratio"])
    al = vision.align(a_img, c_img)
    path.write_text(json.dumps({"H": al.homography.tolist() if al.homography is not None else None,
                                "inliers": al.inliers, "ratio": al.ratio}))
    return al


def start_run(place_id: str, year: int | None = None, current: Path | None = None) -> Run:
    place = BY_ID[place_id]
    manifest = load_manifest(place_id) or {"currents": []}
    if current is None and not manifest["currents"]:
        raise ValueError("Aucune vue actuelle disponible : envoyez une photo.")
    run = Run(uuid.uuid4().hex[:10], place_id, int(year or place["era"]), Path(current) if current else None)
    run.dir.mkdir(parents=True, exist_ok=True)
    RUNS[run.id] = run
    threading.Thread(target=_execute, args=(run,), daemon=True).start()
    return run


def _rel(path: Path) -> str:
    return "/media/" + str(path.relative_to(PLACES_DIR.parent))


def start_task(key: str, pipeline) -> Run:
    """Lance une autre tâche d'agent (ex. la chronique d'un pays) avec le même journal en direct."""
    run = Run(uuid.uuid4().hex[:10], key, 0, None)
    run.dir.mkdir(parents=True, exist_ok=True)
    RUNS[run.id] = run
    threading.Thread(target=_execute, args=(run, pipeline), daemon=True).start()
    return run


def _execute(run: Run, pipeline=None):
    run.status = "running"
    try:
        run.result = (pipeline or _pipeline)(run)
        run.status = "done"
        (run.dir / "result.json").write_text(json.dumps(run.result, ensure_ascii=False, indent=2))
        run.emit("done", "done", "Terminé.", result=run.result)
    except Exception as exc:
        run.status = "error"
        traceback.print_exc()
        run.emit("error", "error", f"L'agent s'est arrêté : {exc}")


def _pipeline(run: Run) -> dict:
    place = BY_ID[run.place_id]
    engine_text = meta.text_engine

    # ------------------------------------------------------------------ 1. enquête
    run.emit("enquete", "running", f"Je cherche {place['name']} ({place['city']}) autour de {run.year}.")
    manifest = load_manifest(run.place_id)
    if not manifest or not manifest["archives"]:
        manifest = build_corpus(place, log=lambda m: run.emit("enquete", "log", m))
    archives = [a for a in manifest["archives"] if abs(a["year"] - run.year) <= 45] or manifest["archives"]
    archives.sort(key=lambda a: (abs(a["year"] - run.year) / 10) - a["score"])
    contributions = manifest.get("contributions", [])
    run.emit("enquete", "log", f"{len(manifest['archives'])} documents d'archives retenus, "
             f"{len(archives)} proches de {run.year}, {len(contributions)} contributions de la communauté.",
             sources=[_source_card(a) for a in archives[:12]])

    verdicts = {}
    if meta.text_live:
        for a in archives[:8]:
            v = meta.chat_json(
                "Tu es archiviste. Réponds en JSON {\"relevant\": bool, \"depicts\": str, \"era_ok\": bool}.",
                f"Cette image montre-t-elle {place['name']} à {place['city']} vers {run.year} ? "
                f"Titre d'archive : {a['title']}. Description : {a['description'][:300]}",
                [PLACES_DIR / a["path"]])
            if v:
                verdicts[a["id"]] = v
        if verdicts:
            archives = [a for a in archives if verdicts.get(a["id"], {}).get("relevant", True)]
    run.emit("enquete", "done", f"Corpus validé : {len(archives)} documents.",
             engine=meta.text_engine if verdicts else "local")

    if run.current is None:
        run.emit("enquete", "log", "Je cherche, parmi les vues actuelles, celle qui retrouve le mieux l'angle des archives.")
        best, best_score = manifest["currents"][0], 0
        refs = [(PLACES_DIR / a["path"], vision.load_archive(PLACES_DIR / a["path"])) for a in archives]
        for c in manifest["currents"]:
            c_path = PLACES_DIR / c["path"]
            img = vision.load(c_path)
            score = sum(al.inliers for al in (_cached_align(p, c_path, r, img) for p, r in refs) if al.ok)
            if score > best_score:
                best, best_score = c, score
        if best_score == 0:  # aucun angle commun : on préfère une vue d'ensemble de jour
            detail = re.compile(r"detail|plaque|placa|año|sign|night|nuit|interior|intérieur|neon|close", re.I)
            best = next((c for c in manifest["currents"] if not detail.search(c["title"])), best)
        run.current = PLACES_DIR / best["path"]
        run.emit("enquete", "log", f"Vue retenue : « {best['title'][:70]} ».")

    # ------------------------------------------------------------------ 2. annotation
    run.emit("annotation", "running", "Je découpe la vue actuelle en éléments (bâtiments, rue, ciel).")
    current = vision.load(run.current)
    cur_path = run.dir / "current.jpg"
    cv2.imwrite(str(cur_path), current, [cv2.IMWRITE_JPEG_QUALITY, 92])
    api_segs = meta.segment(cur_path, CONCEPTS) if meta.live else None
    if api_segs:
        segments, seg_engine = vision.masks_from_api(current.shape, api_segs), "meta:sam-3.1"
    else:
        segments, seg_engine = vision.segment_scene(current), "local"
    run.emit("annotation", "done", f"{len(segments)} éléments isolés.", engine=seg_engine,
             segments=[{"id": s.id, "label": s.label, "polygon": s.polygon()} for s in segments],
             size=[current.shape[1], current.shape[0]])

    # ------------------------------------------------------------------ 3. alignement
    run.emit("alignement", "running", "Je cherche d'où chaque photographe d'époque a pris sa vue.")
    aligned, nearest = [], []
    for a in archives:
        img = vision.load_archive(PLACES_DIR / a["path"])
        al = _cached_align(PLACES_DIR / a["path"], run.current, img, current)
        nearest.append({**_source_card(a), "inliers": al.inliers, "aligned": al.ok})
        if al.ok:
            warped, valid = vision.warp(img, al.homography, current.shape)
            aligned.append({"doc": a, "img": img, "warped": warped, "valid": valid, "al": al})
        run.emit("alignement", "log", f"« {clean_title(a['title'])[:60]} » ({a['year']}) : "
                 + (f"superposable, {al.inliers} points communs" if al.ok else "point de vue différent"),
                 archive=a["id"], ok=al.ok, inliers=al.inliers)
    aligned.sort(key=lambda x: x["al"].inliers, reverse=True)
    run.emit("alignement", "done", f"{len(aligned)} archive(s) superposable(s) à la vue actuelle.")

    # ------------------------------------------------------------------ 4. style
    run.emit("style", "running", "J'apprends le rendu photographique de la ville à cette époque.")
    style_imgs = [vision.load_archive(PLACES_DIR / a["path"], 640) for a in archives[:12]]
    profile = vision.style_profile(style_imgs)
    decade = run.year // 10 * 10
    style_path = PLACES_DIR / run.place_id / f"style_{decade}.json"
    style_path.write_text(json.dumps(profile))
    run.emit("style", "done", f"Profil de style {place['city']} {decade}s appris sur {len(style_imgs)} archives.",
             tint=profile["tint"], contrast=round(profile["contrast"], 2), grain=round(profile["grain"], 1))

    # ------------------------------------------------------------------ 5. reconstruction
    run.emit("reconstruction", "running", "Je reconstruis la scène : les archives d'abord, l'imagination ensuite.")
    recon = vision.age(current, profile)
    coverage = np.zeros(current.shape[:2], bool)
    for x in aligned[:3]:
        layer = x["valid"] & ~coverage
        recon = vision.blend(recon, x["warped"], layer)
        coverage |= x["valid"]

    tags = []
    hypothesis_mask = np.zeros(current.shape[:2], np.uint8)
    for s in segments:
        cov = float((s.mask & coverage).sum() / max(s.mask.sum(), 1))
        sources = [x["doc"]["id"] for x in aligned if (s.mask & x["valid"]).sum() > 0.3 * s.mask.sum()]
        if cov > 0.5 and sources:
            best = next(x for x in aligned if x["doc"]["id"] in sources)
            sim = vision.structure_similarity(current, best["warped"], s.mask & best["valid"])
            status = "inchange" if sim > 0.32 else "documente"
            note = ("Même structure qu'en " if status == "inchange" else "Différent aujourd'hui, attesté en ") \
                + str(best["doc"]["year"])
            conf = round(min(0.95, 0.5 + cov * 0.3 + best["al"].ratio * 0.2), 2)
        else:
            status, note, conf = "hypothese", "Aucune archive ne montre cette zone sous cet angle.", round(0.25 + cov * 0.3, 2)
            if s.label in ("bâti", "building", "building facade", "roof", "monument"):
                hypothesis_mask |= s.mask.astype(np.uint8)
        tags.append({"id": s.id, "label": s.label, "status": status, "note": note, "confidence": conf,
                     "coverage": round(cov, 2), "sources": sources, "polygon": s.polygon(), "bbox": s.bbox})

    recon_engine = "local"
    if meta.live and hypothesis_mask.any():
        prompt = _reconstruction_prompt(place, run.year, archives)
        mask_path = run.dir / "mask.png"
        cv2.imwrite(str(mask_path), (1 - hypothesis_mask) * 255)  # zones transparentes = à générer
        base_path = run.dir / "base.png"
        cv2.imwrite(str(base_path), recon)
        gen = meta.reconstruct(base_path, mask_path, prompt, run.dir / "generated.png")
        if gen:
            g = cv2.imread(str(gen))
            # Muse Image peut changer légèrement le cadrage : on recadre au même format avant de redimensionner
            gh, gw = g.shape[:2]
            target = current.shape[1] / current.shape[0]
            if gw / gh > target:
                cw = int(gh * target)
                g = g[:, (gw - cw) // 2:(gw - cw) // 2 + cw]
            else:
                ch = int(gw / target)
                g = g[(gh - ch) // 2:(gh - ch) // 2 + ch]
            g = cv2.resize(g, (current.shape[1], current.shape[0]))
            documented = recon.copy()
            recon = vision.blend(recon, g, hypothesis_mask.astype(bool))
            recon = vision.blend(recon, documented, coverage)  # les zones documentées restent prioritaires
            recon_engine = "meta:muse-image"
    recon_path = run.dir / "reconstruction.jpg"
    cv2.imwrite(str(recon_path), recon, [cv2.IMWRITE_JPEG_QUALITY, 92])
    counts = {k: sum(t["status"] == k for t in tags if t["label"] not in ("ciel", "sky"))
              for k in ("documente", "inchange", "hypothese")}
    run.emit("reconstruction", "done",
             f"{counts['documente']} zone(s) documentée(s), {counts['inchange']} inchangée(s), "
             f"{counts['hypothese']} hypothèse(s).", engine=recon_engine,
             reconstruction=_rel(recon_path), tags=tags)

    # ------------------------------------------------------------------ 6. évaluation
    run.emit("evaluation", "running", "Je me teste : je cache une archive, je reconstruis sans elle, je compare.")
    holdouts = []
    for i, x in enumerate(aligned[:3]):
        others = [y for j, y in enumerate(aligned) if j != i]
        test = vision.age(current, profile)
        cov = np.zeros(current.shape[:2], bool)
        for y in others[:3]:
            test = vision.blend(test, y["warped"], y["valid"] & ~cov)
            cov |= y["valid"]
        region = x["valid"]
        score = vision.fair_similarity(test, x["warped"], region)
        baseline = vision.fair_similarity(current, x["warped"], region)
        holdouts.append({"archive": x["doc"]["id"], "title": clean_title(x["doc"]["title"]), "year": x["doc"]["year"],
                         "ssim": round(score, 3), "baseline": round(baseline, 3), "others": len(others)})
        run.emit("evaluation", "log", f"Archive cachée {x['doc']['year']} : similarité {score:.2f} "
                 f"(vue actuelle brute : {baseline:.2f}, {len(others)} autre(s) archive(s) disponible(s)).")

    built = [t for t in tags if t["label"] not in ("ciel", "sky", "rue / sol", "street", "road")]
    built_area = sum(_poly_area(t["polygon"]) for t in built) or 1
    evidenced = sum(_poly_area(t["polygon"]) for t in built if t["status"] != "hypothese")
    evidence_share = evidenced / built_area
    holdout_score = float(np.mean([h["ssim"] for h in holdouts])) if holdouts else None
    richness = min(len(archives) / 10, 1.0)
    reliability = 0.5 * evidence_share + 0.2 * richness + (0.3 * max(0.0, holdout_score) if holdout_score else 0)
    # sans test à l'aveugle possible, le score plafonne mécaniquement à 70 %
    gaps = [_gap_question(t, current.shape[1], place) for t in tags if t["status"] == "hypothese"
            and t["label"] not in ("ciel", "sky")]
    evaluation = {
        "reliability": round(reliability, 2),
        "evidence_share": round(evidence_share, 2),
        "holdout": holdouts,
        "holdout_score": round(holdout_score, 3) if holdout_score is not None else None,
        "source_richness": round(richness, 2),
        "n_sources": len(archives),
        "gaps": gaps[:4],
    }
    msg = f"Fiabilité estimée : {round(reliability * 100)} %."
    if not holdouts:
        msg += " Aucune archive n'est prise sous le même angle : test à l'aveugle impossible, score plafonné."
    run.emit("evaluation", "done", msg, **evaluation)

    # ------------------------------------------------------------------ 7. récit
    run.emit("recit", "running", "J'écris l'histoire du lieu, chaque phrase reliée à sa source.")
    numbered = archives[:8]
    from . import history
    hist = history.get(run.place_id)
    story = _narrate_live(place, run.year, numbered, counts, hist) if meta.text_live else None
    story_engine = engine_text if story else "local"
    story = story or _narrate_local(place, run.year, numbered, counts, evaluation)
    run.emit("recit", "done", "Récit prêt.", engine=story_engine)

    return {
        "run": run.id, "place": place, "year": run.year,
        "current": _rel(cur_path), "reconstruction": _rel(recon_path),
        "size": [current.shape[1], current.shape[0]],
        "tags": tags, "counts": counts, "evaluation": evaluation, "story": story,
        "sources": [_source_card(a, i + 1) for i, a in enumerate(numbered)] + ([{
            "id": "wikipedia", "n": len(numbered) + 1, "title": hist["sources"][0]["title"], "year": None,
            "license": "CC BY-SA 4.0", "source": "Wikipédia", "page_url": hist["sources"][0]["url"],
            "image": "/favicon.svg", "description": ""}] if hist and hist.get("events") else []),
        "history": hist,
        "aligned": [x["doc"]["id"] for x in aligned],
        "nearest": sorted(nearest, key=lambda n: (n["aligned"], n["inliers"]), reverse=True)[:6],
        "engines": {"segmentation": seg_engine, "reconstruction": recon_engine, "story": story_engine},
        "style": {"decade": decade, "tint": profile["tint"]},
    }


# ---------------------------------------------------------------------- utilitaires

def _source_card(a: dict, n: int | None = None) -> dict:
    card = {k: a.get(k) for k in ("id", "title", "year", "date_raw", "license", "artist", "page_url", "source",
                                  "description")}
    card["title"] = clean_title(card["title"] or "")
    card["image"] = "/media/places/" + a["path"]
    if n:
        card["n"] = n
    return card


def _poly_area(poly) -> float:
    if len(poly) < 3:
        return 0.0
    return float(abs(cv2.contourArea(np.array(poly, np.float32))))


def _gap_question(tag: dict, width: int, place: dict) -> dict:
    x0, _, x1, _ = tag["bbox"]
    cx = (x0 + x1) / 2 / width
    side = "à gauche" if cx < 0.36 else "à droite" if cx > 0.64 else "au centre"
    return {"tag": tag["id"], "side": side,
            "question": f"Avez-vous une photo ancienne ou un souvenir de la partie {side} de "
                        f"{place['name'].lower()} ? Je n'ai aucune preuve pour cette zone."}


def _reconstruction_prompt(place: dict, year: int, archives: list[dict]) -> str:
    refs = "; ".join(f"{a['title']} ({a['year']})" for a in archives[:5])
    plan = meta.chat(
        "Tu es historien de l'architecture. Décris en 80 mots maximum, en anglais, à quoi ressemblaient "
        "les bâtiments et la rue, uniquement d'après les sources fournies. Pas d'invention spectaculaire.",
        f"Lieu : {place['name']}, {place['city']}, vers {year}. Contexte : {place['context']} Sources : {refs}",
        [PLACES_DIR / a["path"] for a in archives[:3]], max_tokens=200)
    return (f"Historical photograph of {place['name']}, {place['city']}, around {year}. "
            f"{plan or ''} Keep the exact street geometry and perspective. Period-accurate, sepia albumen print.")


def _narrate_live(place: dict, year: int, sources: list[dict], counts: dict, hist: dict | None = None) -> dict | None:
    listing = "\n".join(f"[S{i + 1}] {clean_title(a['title'])} ({a['year']}) : {a['description'][:250]}"
                        for i, a in enumerate(sources))
    if hist and hist.get("events"):
        n = len(sources) + 1  # la frise Wikipédia devient une source numérotée de plus
        listing += f"\n[S{n}] Article « {hist['sources'][0]['title']} », événements datés :\n" + "\n".join(
            f"  ({e['label']}) {e['text']}" for e in hist["events"])
    return meta.chat_json(
        "Tu es historien. Écris un récit court (120 à 170 mots) sur un lieu à une date donnée. "
        "Chaque phrase factuelle cite sa source [S1], [S2]… N'invente AUCUN détail absent des sources : "
        "ni heure, ni météo, ni émotion, ni pensée des personnes, ni ambiance sonore. Une information qui ne "
        "vient pas des sources est annoncée comme « contexte général ». Ne commente pas ce que les sources "
        "ne disent pas, et écris un texte fluide plutôt qu'une liste de constats. Réponds en JSON "
        "{\"title\": str, \"fr\": str, \"en\": str}.",
        f"Lieu : {place['name']}, {place['city']} ({place['country']}). Année : {year}.\n"
        f"Contexte connu : {place['context']}\nSources :\n{listing}\n"
        f"Reconstruction : {counts['documente']} zones documentées, {counts['hypothese']} hypothèses.")


def _narrate_local(place: dict, year: int, sources: list[dict], counts: dict, ev: dict) -> dict:
    years = sorted(a["year"] for a in sources) or [year]
    cited = sources[:3]
    fr_refs = " ".join(f"« {clean_title(a['title'])} » ({a['year']}) [S{i + 1}]." for i, a in enumerate(cited))
    en_refs = " ".join(f"“{clean_title(a['title'])}” ({a['year']}) [S{i + 1}]." for i, a in enumerate(cited))
    fr = (f"{place['name']}, {place['city']}, vers {year}. Pour situer le lieu : {place['context']} "
          f"Les archives retrouvées couvrent les années {years[0]} à {years[-1]} : {fr_refs} "
          f"Sur cette vue, {counts['documente'] + counts['inchange']} zone(s) s'appuient sur des preuves "
          f"et {counts['hypothese']} reste(nt) des hypothèses de l'IA, signalées en jaune.")
    en = (f"{place['name']}, {place['city']}, around {year}. Archives found span {years[0]} to {years[-1]}: "
          f"{en_refs} In this view, {counts['documente'] + counts['inchange']} area(s) rest on evidence and "
          f"{counts['hypothese']} remain AI hypotheses, marked in yellow.")
    return {"title": f"{place['city']}, {year}", "fr": fr, "en": en}


def add_contribution(place_id: str, kind: str, file: Path, year: int | None, note: str) -> dict:
    """Une photo ou un témoignage de la communauté rejoint le corpus, marqué « non vérifié »."""
    root = PLACES_DIR / place_id
    (root / "community").mkdir(parents=True, exist_ok=True)
    dest = root / "community" / f"{uuid.uuid4().hex[:8]}{file.suffix.lower()}"
    shutil.copy(file, dest)
    manifest = load_manifest(place_id) or {"place": place_id, "archives": [], "currents": []}
    entry = {"id": f"community-{dest.stem}", "kind": kind, "year": year, "note": note[:1000],
             "path": str(dest.relative_to(PLACES_DIR)), "verified": False, "source": "Communauté SANKOFA",
             "title": note[:80] or "Contribution de la communauté", "license": "CC BY 4.0 (contributeur)",
             "score": 1.0, "description": note, "page_url": "", "artist": "Contributeur"}
    if kind == "audio":
        text = meta.transcribe(dest)
        entry["transcript"] = text or "(transcription disponible quand la Meta Model API est branchée)"
    manifest.setdefault("contributions", []).append(entry)
    if kind == "photo" and year and year <= 1960:
        manifest["archives"].append(entry)
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return entry
