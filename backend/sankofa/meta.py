"""Client de la Meta Model API (compatible OpenAI).

Chaque méthode renvoie None quand l'API n'est pas branchée ou échoue : l'agent bascule
alors sur son moteur local et l'indique dans le journal (champ « engine »).
Les formats exacts de SAM 3.1 et Muse Image sont à confirmer avec la doc officielle :
ils sont isolés ici pour n'avoir qu'un seul endroit à ajuster.
"""
import base64
import json
import mimetypes
import re
from pathlib import Path

from . import config

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


class MetaClient:
    def __init__(self):
        self.live = bool(config.META_API_KEY and OpenAI)
        self.client = OpenAI(api_key=config.META_API_KEY, base_url=config.META_BASE_URL) if self.live else None
        # sans clé Meta, le texte et la vision passent par un modèle Llama hébergé chez Baseten
        self.baseten = (OpenAI(api_key=config.BASETEN_API_KEY, base_url=config.BASETEN_BASE_URL)
                        if config.BASETEN_API_KEY and OpenAI else None)
        self.baseten_model = config.BASETEN_MODEL or None
        self.last_error: str | None = None
        self._day, self._calls = None, 0

    def _allow(self) -> bool:
        """Plafond quotidien d'appels payants : au-delà, l'agent repasse en mode local et le dit."""
        import datetime
        today = datetime.date.today()
        if self._day != today:
            self._day, self._calls = today, 0
        if config.DAILY_PAID_CALL_LIMIT and self._calls >= config.DAILY_PAID_CALL_LIMIT:
            self.last_error = "daily AI budget reached: local mode until tomorrow"
            return False
        self._calls += 1
        return True

    @property
    def budget(self) -> dict:
        return {"limit": config.DAILY_PAID_CALL_LIMIT, "used_today": self._calls}

    @property
    def text_live(self) -> bool:
        return self.live or self.baseten is not None

    def engine_for(self, bulk: bool) -> str:
        if bulk and self.baseten:
            return f"meta:{(self.baseten_model or 'muse-spark-open').split('/')[-1]} (Baseten)"
        return self.text_engine

    @property
    def text_engine(self) -> str:
        if self.live:
            return f"meta:{config.MODEL_TEXT}"
        if self.baseten:
            return f"meta:{(self.baseten_model or 'muse-spark-open').split('/')[-1]} (Baseten)"
        return "local"

    def _baseten_model(self) -> str | None:
        if self.baseten_model:
            return self.baseten_model
        try:
            ids = [m.id for m in self.baseten.models.list().data]
        except Exception as exc:
            return self._fail(exc)
        # priorité aux modèles de Meta : Muse Spark open weights (version la plus récente), puis Llama
        meta_ids = [i for i in ids if i.lower().startswith("meta") or "muse" in i.lower() or "llama" in i.lower()]
        meta_ids.sort(key=lambda i: ("muse" in i.lower(), i), reverse=True)
        self.baseten_model = (meta_ids or ids or [None])[0]
        return self.baseten_model

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _data_url(path: Path) -> str:
        mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode()}"

    def _fail(self, exc: Exception):
        self.last_error = f"{type(exc).__name__}: {exc}"[:300]
        return None

    # ------------------------------------------------------------------ Muse Spark
    def chat(self, system: str, user: str, images: list[Path] = (), json_mode: bool = False,
             max_tokens: int = 1200, bulk: bool = False) -> str | None:
        """bulk=True : génération en série (chroniques) envoyée de préférence à Baseten pour ménager les crédits Meta."""
        if not self.text_live or not self._allow():
            return None
        content = [{"type": "text", "text": user}]
        for p in images:
            content.append({"type": "image_url", "image_url": {"url": self._data_url(p)}})
        use_meta = self.live and not (bulk and self.baseten)
        client, model = (self.client, config.MODEL_TEXT) if use_meta else (self.baseten, self._baseten_model())
        if not model:
            return None
        # Muse Spark (1.3 comme open) raisonne avant de répondre : effort réduit et large marge pour la
        # réponse ; seuls les jetons réellement produits sont facturés
        max_tokens += 4000
        extra = {"reasoning_effort": "low"}
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": content}],
                max_tokens=max_tokens,
                **extra,
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            )
            return r.choices[0].message.content
        except Exception as exc:
            return self._fail(exc)

    def chat_json(self, system: str, user: str, images: list[Path] = (), bulk: bool = False) -> dict | None:
        raw = self.chat(system, user, images, json_mode=True, bulk=bulk)
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            return json.loads(m.group(0) if m else raw)
        except json.JSONDecodeError as exc:
            return self._fail(exc)

    # ------------------------------------------------------------------ SAM 3.1
    def segment(self, image: Path, concepts: list[str], max_side: int = 1024) -> list[dict] | None:
        """Segmentation par concepts via l'API Responses (un concept par requête, d'après la doc Meta).

        Renvoie [{id, label, polygon:[[x,y],...]}] dans les coordonnées de l'image d'origine.
        """
        if not self.live or not self._allow():
            return None
        import cv2
        import numpy as np
        img = cv2.imread(str(image))
        h, w = img.shape[:2]
        scale = min(1.0, max_side / max(h, w))
        small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else img
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
        out = []
        for concept in concepts:
            text = self._sam_stream(concept, data_url)
            if text is None:
                return out or None
            for k, rec in enumerate(_parse_sam(text)):
                x1, y1, x2, y2 = (rec[c] / scale for c in ("x1", "y1", "x2", "y2"))
                poly = None
                if rec.get("mask") is not None:
                    m = cv2.resize(rec["mask"].astype(np.uint8), (max(int(x2 - x1), 1), max(int(y2 - y1), 1)),
                                   interpolation=cv2.INTER_NEAREST)
                    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        c = cv2.approxPolyDP(max(contours, key=cv2.contourArea), 2.5, True).reshape(-1, 2)
                        poly = [[int(px + x1), int(py + y1)] for px, py in c]
                if not poly or len(poly) < 3:  # masque illisible : on garde la boîte, déjà précise
                    poly = [[int(x1), int(y1)], [int(x2), int(y1)], [int(x2), int(y2)], [int(x1), int(y2)]]
                out.append({"id": f"{concept.replace(' ', '-')}-{k}", "label": concept, "polygon": poly})
        return out

    def _sam_stream(self, concept: str, data_url: str) -> str | None:
        import httpx
        body = {"model": config.MODEL_SEGMENT, "stream": True, "metadata": {"mask_encoding": "one_bit"},
                "input": [{"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": concept}, {"type": "input_image", "image_url": data_url}]}]}
        text = []
        try:
            with httpx.stream("POST", f"{config.META_BASE_URL}/responses", json=body, timeout=120,
                              headers={"Authorization": f"Bearer {config.META_API_KEY}",
                                       "Accept": "text/event-stream"}) as r:
                if r.status_code >= 400:
                    r.read()
                    raise RuntimeError(f"HTTP {r.status_code} : {r.text[:200]}")
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    ev = json.loads(payload)
                    if ev.get("type") == "response.output_text.delta":
                        text.append(ev.get("delta", ""))
            raw = "".join(text)
            (config.CACHE_DIR / "sam_last.txt").write_text(raw)  # dernière réponse brute, pour le diagnostic
            return raw
        except Exception as exc:
            return self._fail(exc)

    # ------------------------------------------------------------------ Muse Image
    def reconstruct(self, image: Path, mask: Path, prompt: str, out: Path) -> Path | None:
        """Retouche par Muse Image. L'API n'accepte pas de masque : SANKOFA ne garde ensuite
        que les zones sans preuve (le masque est appliqué localement par l'agent)."""
        if not self.live or not self._allow():
            return None
        import httpx
        try:
            r = httpx.post(f"{config.META_BASE_URL}/images/edits", timeout=180,
                           headers={"Authorization": f"Bearer {config.META_API_KEY}"},
                           json={"model": config.MODEL_IMAGE, "prompt": prompt, "n": 1,
                                 "images": [{"image_url": self._data_url(image)}]})
            r.raise_for_status()
            data = r.json()["data"][0]
            if data.get("b64_json"):
                out.write_bytes(base64.b64decode(data["b64_json"]))
            else:
                out.write_bytes(httpx.get(data["url"], timeout=120).content)
            return out
        except Exception as exc:
            return self._fail(exc)

    # ------------------------------------------------------------------ transcription
    def transcribe(self, audio: Path) -> str | None:
        if not self.live:
            return None
        try:
            with open(audio, "rb") as f:
                r = self.client.audio.transcriptions.create(model=config.MODEL_TRANSCRIBE, file=f)
            return r.text
        except Exception as exc:
            return self._fail(exc)


def _parse_sam(text: str) -> list[dict]:
    """Lit la sortie texte de SAM 3.1 : <0f>id<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..|><|mask;...;data=H,W,!payload|>"""
    import numpy as np
    records = []
    for m in re.finditer(r"<\|box;([^|]*)\|><\|mask;([^|]*)\|>", text):
        box = dict(kv.split("=", 1) for kv in m.group(1).split(";") if "=" in kv)
        rec = {k: int(float(box[k])) for k in ("x1", "y1", "x2", "y2")}
        rec["mask"] = None
        data = re.search(r"data=(\d+),(\d+),(.)(.*)$", m.group(2))
        if data:  # décodage par le parseur officiel de Meta (meta_sam_parser), « ~ » sans perte ou « ! » un bit
            hh, ww, enc = int(data.group(1)), int(data.group(2)), data.group(3)
            try:
                from meta_sam_parser import SegmentationMask, decode_mask_to_raster
                raster = decode_mask_to_raster(SegmentationMask("one_bit" if enc == "!" else "lossless",
                                                                enc + data.group(4), ww, hh))
                rec["mask"] = np.frombuffer(raster, np.uint8).reshape(hh, ww).astype(bool)
            except Exception:
                pass  # masque illisible : la boîte reste utilisable
        records.append(rec)
    return records


meta = MetaClient()
