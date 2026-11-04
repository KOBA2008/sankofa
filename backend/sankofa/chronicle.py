"""La chronique d'un pays : l'agent reconstitue son histoire à partir des sources, et seulement d'elles.

Chaque événement de la frise est une citation exacte d'une source, reliée à sa section.
Il est « recoupé » quand une source rédigée indépendamment (l'article dans l'autre langue)
cite la même année avec le même nom propre. Les siècles que les sources ne couvrent pas
sont signalés comme lacunes, au lieu d'être comblés.
"""
import json
import re
import unicodedata

from . import config
from .countries import BY_ID
from .investigate import is_open, load_manifest, relevance
from .meta import meta
from .sources import wikimedia, wikipedia

COUNTRIES_DIR = config.DATA / "countries"
COUNTRIES_DIR.mkdir(parents=True, exist_ok=True)

SKIP = re.compile(r"note|référence|bibliograph|annexe|connexe|lien|galerie|voir aussi|glossaire|^sources?$|"
                  r"lecture|filmograph|further|reference|see also|external|bibliography", re.I)
# phrases qui parlent du travail des historiens, pas d'un événement de l'histoire
HISTORIOGRAPHY = re.compile(r"\bétude|publiée|cet article|ouvrage|chercheurs?|historiens?|archéolog|"
                            r"selon (?:les|des)|\bstudy\b|published|this article", re.I)
IMPORTANT = re.compile(
    r"indépendan|fond[ée]|royaume|\broi\b|reine|empereur|empire|dynastie|colon|protectorat|traité|guerre|"
    r"conquête|conquis|révolution|coup d.[ée]tat|république|constitution|élu|président|abolition|traite|"
    r"esclav|capitale|invasion|annex|proclam|conférence|exil|déport|bataille|accords?|unification|"
    r"occupation|insurrection|réforme|démocrati|monarchie|sultan|pharaon|califat|apartheid", re.I)
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
CAP_STOP = {"dans", "après", "avant", "sous", "cette", "entre", "pendant", "selon", "depuis", "lors", "with",
            "after", "before", "during", "under", "from", "this", "that", "their", "these", "while", "following",
            "elle", "elles", "leur", "leurs", "pour", "mais", "ainsi", "alors", "cependant", "however", "although"}


def _roman(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN.get(ch, 0)
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


UNITS = re.compile(r"^\s*(?:grammes?|kg|kilos?|km|mètres?|hommes|guerriers|soldats|articles|habitants|morts|"
                   r"personnes|victimes|navires|millions?|milliards?|pages|%|\$|euros?|francs?|men|soldiers|people|"
                   r"km2|tonnes?)\b", re.I)
BC = r"(?:\s*(?:av(?:ant)?\.?\s*(?:J\.?-?C\.?|notre ère)|BC\b|BCE\b))"
# une année à trois chiffres n'est acceptée qu'après un mot qui introduit une date
DATE_CUE = re.compile(r"(?:\ben|\bde|\bà|vers|dès|depuis|jusqu.en|\bin|\bby|from|après|avant|l.an|année|"
                      r"\bau|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|"
                      r"–|-|\()\s*$", re.I)


def find_year(sentence: str) -> tuple[int, str] | None:
    """Première date d'une phrase : année (« en 1894 »), siècle (« XVIe siècle »), avant notre ère."""
    if re.search(r"ISBN|lire en ligne|\bp\.\s*\d", sentence):
        return None
    cands = []
    m = re.search(r"\b(?!L[eè])([IVX]+[IVXL]*|L[IVX]+)(?:e|ème|er)\s+siècle(" + BC + ")?", sentence)
    if m:
        c = _roman(m.group(1))
        year = -(c * 100 - 50) if m.group(2) else (c - 1) * 100 + 50
        cands.append((m.start(), year, f"{m.group(1)}e s." + (" av. J.-C." if m.group(2) else "")))
    for y in re.finditer(r"(?<![\d,.\w-])(-)?(\d{3,4})(?!\d|[.,]\d|\s\d{3}\b)", sentence):
        val = int(y.group(2))
        after = sentence[y.end():y.end() + 40]
        if UNITS.match(after):
            continue
        # « 264-240 av. J.-C. » : la mention avant notre ère peut suivre la seconde borne
        bc = re.match(r"(?:\s*(?:[-–]|à|et|to)\s*\d{2,4})?" + BC, after) is not None
        before = sentence[max(0, y.start() - 14):y.start()]
        if val < 1000 and not bc and not y.group(1) and not DATE_CUE.search(before):
            continue
        if bc or y.group(1):
            cands.append((y.start(), -val, f"{val} av. J.-C."))
        elif 100 <= val <= 2026:
            cands.append((y.start(), val, str(val)))
        break
    en = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)[- ]century(\s+BCE?)?", sentence)
    if en:
        c = int(en.group(1))
        year = -(c * 100 - 50) if en.group(2) else (c - 1) * 100 + 50
        cands.append((en.start(), year, f"{c}e s."))
    if not cands:
        return None
    _, year, label = min(cands)
    return year, label


_PROTECT = [("av. J.-C.", "av§J§C"), ("apr. J.-C.", "apr§J§C"), ("J.-C.", "J§C"), ("av. notre ère", "av§notre§ère")]


def _sentences(text: str) -> list[str]:
    text = re.sub(r"av\.\s*J\.?\s*-?\s*C\.", "av. J.-C.", text)
    for a, b in _PROTECT:
        text = text.replace(a, b)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÝÉÈ«\"(])", text)
    out = []
    for p in parts:
        for a, b in _PROTECT:
            p = p.replace(b, a)
        p = p.strip()
        if not 40 <= len(p) <= 420:
            continue
        words = p.split()
        caps = sum(w[:1].isupper() for w in words)
        # listes de liens (« Histoire de l'Anatolie, Préhistoire de… ») : trop de majuscules, aucune phrase
        if p.count(",") > 6 or (len(words) > 6 and caps / len(words) > 0.45):
            continue
        out.append(p)
    return out


def _norm(w: str) -> str:
    return unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode().lower()


def _proper_nouns(sentence: str) -> set[str]:
    words = re.findall(r"(?<![.!?]\s)(?<!^)\b([A-ZÀ-Ý][\w'’-]{3,})", sentence)
    return {_norm(w).split("'")[-1] for w in words
            if _norm(w) not in CAP_STOP and not re.fullmatch(r"[ivxl]+(e|eme|er)", _norm(w))}


def _importance(sentence: str) -> float:
    score = 1.0 + 2.0 * len(IMPORTANT.findall(sentence))
    digits = len(re.findall(r"\d", sentence))
    if digits > 14:  # les phrases de statistiques ne sont pas des événements
        score -= 2
    if len(sentence) > 300:
        score -= 0.5
    return score


def _chapters(art: dict) -> list[dict]:
    chapters = []
    for s in art["sections"]:
        if SKIP.search(s["title"]):
            continue
        if s["level"] == 2 or not chapters:
            chapters.append({"title": s["title"], "url": s["url"], "parts": [s]})
        else:
            chapters[-1]["parts"].append(s)
    return chapters


def _en_index(art: dict | None) -> list[tuple[int, set[str]]]:
    if not art:
        return []
    out = []
    for s in art["sections"]:
        if SKIP.search(s["title"]):
            continue
        for sent in _sentences(s["text"]):
            fy = find_year(sent)
            if fy:
                out.append((fy[0], _proper_nouns(sent)))
    return out


def _corroborate(year: int, nouns: set[str], index) -> bool:
    tol = 1 if year > 0 else 50
    return any(abs(y - year) <= tol and nouns & ns for y, ns in index)


def _photos(country: dict, start: int, end: int) -> list[dict]:
    lo, hi = max(start, 1839), min(end, 1960)
    if hi < 1839 or lo > hi:
        return []
    mid = (lo + hi) // 2
    pseudo = {"keywords": [n.lower() for n in country["old_names"] + [country["name"]]]}
    picked = []
    for pid in country["places"]:  # d'abord les archives déjà vérifiées des lieux du pays
        m = load_manifest(pid) or {"archives": []}
        for a in m["archives"]:
            if lo - 3 <= a["year"] <= hi + 3:
                picked.append({"title": a["title"], "year": a["year"], "license": a["license"],
                               "image": "/media/places/" + a["path"], "page_url": a.get("page_url", ""),
                               "source": a.get("source", "")})
    decades = sorted({max(1850, min(1950, y // 10 * 10)) for y in (lo, mid, hi)})
    for name, decade in [(n, d) for n in country["old_names"][:3] for d in decades]:
        if len(picked) >= 12:
            break
        for d in wikimedia.search(f"{name} {decade}", limit=30, width=900):
            if not d["year"] or not (lo - 5 <= d["year"] <= hi + 5) or not is_open(d["license"]):
                continue
            if relevance(d, pseudo, mid) <= 0 or any(p["title"] == d["title"] for p in picked):
                continue
            picked.append({"title": d["title"], "year": d["year"], "license": d["license"], "image": d["thumb_url"],
                           "page_url": d["page_url"], "source": d["source"]})
    picked.sort(key=lambda p: abs(p["year"] - mid))
    return picked[:8]


def run_chronicle(country_id: str):
    country = BY_ID[country_id]

    def pipeline(run):
        # ---------------------------------------------------------------- lecture
        run.emit("lecture", "running", f"Je lis l'histoire du {country['name']} dans les sources.")
        fr = wikipedia.article(country["fr"], "fr")
        if not fr:
            raise ValueError(f"Article introuvable : {country['fr']}")
        en = wikipedia.article(country["en"], "en")
        run.emit("lecture", "done", f"Deux sources rédigées indépendamment : « {fr['title']} » "
                 f"({sum(len(s['text']) for s in fr['sections']) // 1000} k caractères) et « {en['title'] if en else 'aucune'} ».")

        # ---------------------------------------------------------------- extraction
        run.emit("extraction", "running", "J'extrais les événements datés, mot pour mot, avec leur section d'origine.")
        chapters, sources = [], []
        for ch in _chapters(fr):
            sources.append({"n": len(sources) + 1, "title": f"{fr['title']} › {ch['title']}", "url": ch["url"],
                            "lang": "fr", "license": "CC BY-SA 4.0", "source": "Wikipédia"})
            n = len(sources)
            cands = []
            for part in ch["parts"]:
                for sent in _sentences(part["text"]):
                    fy = find_year(sent)
                    if fy and not HISTORIOGRAPHY.search(sent):
                        cands.append({"year": fy[0], "label": fy[1], "text": sent, "source": n,
                                      "score": _importance(sent), "nouns": _proper_nouns(sent)})
            cands.sort(key=lambda e: e["score"], reverse=True)
            keep, seen_years = [], set()
            for c in cands:
                if c["score"] <= 0 or c["year"] in seen_years:
                    continue
                keep.append(c)
                seen_years.add(c["year"])
                if len(keep) >= 10:
                    break
            keep.sort(key=lambda e: e["year"])
            body = " ".join(p["text"] for p in ch["parts"])
            summary = " ".join(_sentences(body)[:2])[:520]
            if not keep and not summary:
                continue
            years = [e["year"] for e in keep]
            chapters.append({"title": ch["title"], "url": ch["url"], "source": n, "summary": summary,
                             "events": keep, "start": min(years) if years else None,
                             "end": max(years) if years else None})
            run.emit("extraction", "log", f"« {ch['title']} » : {len(keep)} événement(s) daté(s).")
        n_events = sum(len(c["events"]) for c in chapters)
        run.emit("extraction", "done", f"{len(chapters)} chapitres, {n_events} événements extraits.")

        # ---------------------------------------------------------------- recoupement
        run.emit("recoupement", "running", "Je recoupe chaque événement avec l'article anglais, écrit par d'autres auteurs.")
        index = _en_index(en)
        if en:
            sources.append({"n": len(sources) + 1, "title": en["title"], "url": en["url"], "lang": "en",
                            "license": "CC BY-SA 4.0", "source": "Wikipedia"})
        corroborated = 0
        for c in chapters:
            for e in c["events"]:
                e["corroborated"] = _corroborate(e["year"], e.pop("nouns"), index)
                corroborated += e["corroborated"]
                e.pop("score", None)
        share = corroborated / n_events if n_events else 0
        run.emit("recoupement", "done", f"{corroborated} événement(s) sur {n_events} recoupé(s) ({round(share * 100)} %).")

        # ---------------------------------------------------------------- lacunes
        run.emit("lacunes", "running", "Je cherche les périodes que les sources laissent dans l'ombre.")
        dated = sorted((c for c in chapters if c["start"] is not None), key=lambda c: c["start"])
        gaps = []
        for a, b in zip(dated, dated[1:]):
            if b["start"] - a["end"] > 80:
                gaps.append({"from": a["end"], "to": b["start"],
                             "text": f"Entre {a['end']} et {b['start']}, les sources consultées ne donnent aucune date précise."})
        if dated and dated[0]["start"] > -1000:
            gaps.insert(0, {"from": None, "to": dated[0]["start"],
                            "text": f"Avant {_fmt(dated[0]['start'])}, l'histoire n'est pas datée dans ces sources : "
                                    "traditions orales, archéologie et sources locales restent à intégrer."})
        thin = [c["title"] for c in chapters if len(c["events"]) < 2 and c["title"] != "Introduction"]
        if thin:
            gaps.append({"from": None, "to": None,
                         "text": "Chapitres peu datés : " + ", ".join(thin[:4]) + "."})
        run.emit("lacunes", "done", f"{len(gaps)} lacune(s) signalée(s).")

        # ---------------------------------------------------------------- illustrations
        run.emit("illustration", "running", "Je cherche des photos d'archives pour chaque période (sous les anciens noms du pays).")
        for c in chapters:
            try:
                c["photos"] = _photos(country, c["start"], c["end"]) if c["start"] is not None else []
            except Exception as exc:  # une recherche de photos qui échoue ne doit pas arrêter la chronique
                c["photos"] = []
                run.emit("illustration", "log", f"« {c['title']} » : photos indisponibles ({type(exc).__name__}).")
            if c["photos"]:
                run.emit("illustration", "log", f"« {c['title']} » : {len(c['photos'])} photo(s).")
        run.emit("illustration", "done", f"{sum(len(c['photos']) for c in chapters)} photos d'époque associées.")

        # ---------------------------------------------------------------- récit
        run.emit("recit", "running", "J'écris le récit, chapitre par chapitre, sans rien ajouter aux sources.")
        engine = "local"
        for c in chapters:
            quotes = "\n".join(f"- ({e['label']}) {e['text']}" for e in c["events"])
            text = meta.chat(
                "Tu es historien. Écris un paragraphe de 90 à 130 mots en français à partir UNIQUEMENT des extraits "
                "fournis. Cite la source à la fin des phrases sous la forme [S{n}]. N'ajoute aucun fait absent "
                "des extraits, ni détail inventé (heure, météo, émotions, pensées). Si les extraits ne reflètent "
                "qu'un point de vue (par exemple colonial), dis-le.",
                f"Chapitre : {c['title']}. Source [S{c['source']}].\nRésumé : {c['summary']}\nÉvénements :\n{quotes}",
                max_tokens=450, bulk=True) if meta.text_live else None
            if text:
                engine = meta.engine_for(bulk=True)
            c["narrative"] = text or (f"{c['summary']} [S{c['source']}]" if c["summary"] else "")
        run.emit("recit", "done", "Chronique prête." if engine != "local" else
                 "Chronique prête (mode local : le récit est fait d'extraits des sources).", engine=engine)

        result = {
            "country": country, "chapters": chapters, "sources": sources, "gaps": gaps,
            "stats": {"chapters": len(chapters), "events": n_events, "corroborated": corroborated,
                      "share": round(share, 2),
                      "span": [_fmt(dated[0]["start"]), _fmt(max(c["end"] for c in dated))] if dated else None},
            "engines": {"narrative": engine},
            "run": run.id,
        }
        (COUNTRIES_DIR / f"{country_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
        return result

    return pipeline


def _fmt(year: int) -> str:
    return f"{-year} av. J.-C." if year < 0 else str(year)


def cached(country_id: str) -> dict | None:
    path = COUNTRIES_DIR / f"{country_id}.json"
    return json.loads(path.read_text()) if path.exists() else None
