"""Vision locale : segmentation de secours, alignement photo ancienne / actuelle,
vieillissement photographique et mesure de similarité.

Ces fonctions tournent sans aucune API. Quand la Meta Model API est branchée,
SAM 3.1 remplace segment_scene() et Muse Image remplace le rendu de secours.
"""
from dataclasses import dataclass

import cv2
import numpy as np

MAX_SIDE = 1280


def load(path, max_side: int = MAX_SIDE) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Image illisible : {path}")
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def trim_borders(img: np.ndarray, max_frac: float = 0.18) -> np.ndarray:
    """Retire le carton, le cadre noir ou la marge blanche autour d'un tirage ancien."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = g.shape

    def cut(lines, limit):
        n = 0
        while n < limit and lines(n).std() < 14:
            n += 1
        return n

    top = cut(lambda i: g[i, :], int(h * max_frac))
    bottom = cut(lambda i: g[h - 1 - i, :], int(h * max_frac))
    left = cut(lambda i: g[:, i], int(w * max_frac))
    right = cut(lambda i: g[:, w - 1 - i], int(w * max_frac))
    pad = 4  # le liseré du tirage déborde souvent de quelques pixels
    y0, y1 = min(top + pad, h // 3), max(h - bottom - pad, 2 * h // 3)
    x0, x1 = min(left + pad, w // 3), max(w - right - pad, 2 * w // 3)
    return img[y0:y1, x0:x1]


def load_archive(path, max_side: int = MAX_SIDE) -> np.ndarray:
    return trim_borders(load(path, max_side))


# --------------------------------------------------------------------------- segmentation

@dataclass
class Segment:
    id: str
    label: str
    mask: np.ndarray  # bool, taille de l'image
    bbox: tuple[int, int, int, int]

    def polygon(self, epsilon: float = 2.5) -> list[list[int]]:
        contours, _ = cv2.findContours(self.mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        c = max(contours, key=cv2.contourArea)
        c = cv2.approxPolyDP(c, epsilon, True)
        return c.reshape(-1, 2).tolist()


def _edge_density(gray: np.ndarray) -> np.ndarray:
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 160).astype(np.float32) / 255
    return cv2.blur(edges, (31, 31))


def segment_scene(img: np.ndarray) -> list[Segment]:
    """Découpe heuristique : ciel, sol, puis blocs de façades séparés par les verticales fortes."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    density = _edge_density(gray)

    # ciel : zone lisse et claire (ou bleue) connectée au bord supérieur
    bright = (hsv[..., 2] > 140) & ((hsv[..., 1] < 70) | ((hsv[..., 0] > 90) & (hsv[..., 0] < 130)))
    smooth = density < 0.06
    cand = (bright & smooth).astype(np.uint8)
    n, labels = cv2.connectedComponents(cand)
    top_labels = set(np.unique(labels[0, :])) - {0}
    sky = np.isin(labels, list(top_labels)) if top_labels else np.zeros((h, w), bool)
    sky = cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)).astype(bool)

    # sol : bande basse, en partant de la ligne où la densité de contours chute
    ground = np.zeros((h, w), bool)
    rows = density.mean(axis=1)
    start = int(h * 0.62)
    lower = rows[start:]
    cut = start + int(np.argmax(lower < np.median(rows) * 0.85)) if (lower < np.median(rows) * 0.85).any() else int(h * 0.82)
    ground[max(cut, int(h * 0.6)):, :] = True
    ground &= ~sky

    # bâti : le reste, découpé en colonnes aux fortes verticales
    built = ~(sky | ground)
    sobel_x = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    profile = (sobel_x * built).sum(axis=0)
    profile = cv2.GaussianBlur(profile.reshape(1, -1), (1, 0), sigmaX=w / 60).ravel() if w > 60 else profile
    min_gap = max(w // 7, 40)
    cuts = [0]
    for x in np.argsort(profile)[::-1]:
        if len(cuts) >= 5:
            break
        if all(abs(x - c) > min_gap for c in cuts) and min_gap < x < w - min_gap:
            cuts.append(int(x))
    cuts = sorted(cuts) + [w]

    segments = []
    if sky.sum() > 0.02 * h * w:
        segments.append(Segment("sky", "ciel", sky, _bbox(sky)))
    for i in range(len(cuts) - 1):
        m = np.zeros((h, w), bool)
        m[:, cuts[i]:cuts[i + 1]] = True
        m &= built
        if m.sum() > 0.02 * h * w:
            segments.append(Segment(f"building-{i + 1}", "bâti", m, _bbox(m)))
    if ground.sum() > 0.02 * h * w:
        segments.append(Segment("ground", "rue / sol", ground, _bbox(ground)))
    return segments


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def masks_from_api(img_shape, api_segments: list[dict]) -> list[Segment]:
    """Convertit les polygones renvoyés par SAM 3.1 en Segment."""
    h, w = img_shape[:2]
    out = []
    for i, s in enumerate(api_segments):
        m = np.zeros((h, w), np.uint8)
        pts = np.array(s["polygon"], np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(m, [pts], 1)
        if m.sum() > 0.005 * h * w:
            out.append(Segment(s.get("id", f"seg-{i}"), s.get("label", "objet"), m.astype(bool), _bbox(m.astype(bool))))
    return out


# --------------------------------------------------------------------------- alignement

@dataclass
class Alignment:
    homography: np.ndarray | None
    inliers: int
    ratio: float

    @property
    def ok(self) -> bool:
        return self.homography is not None and self.inliers >= 18 and self.ratio >= 0.3


def align(archive: np.ndarray, current: np.ndarray) -> Alignment:
    """Re-photographie : cherche la transformation qui superpose l'archive à la vue actuelle."""
    sift = cv2.SIFT_create(nfeatures=4000)
    ga = cv2.equalizeHist(cv2.cvtColor(archive, cv2.COLOR_BGR2GRAY))
    gc = cv2.equalizeHist(cv2.cvtColor(current, cv2.COLOR_BGR2GRAY))
    ka, da = sift.detectAndCompute(ga, None)
    kc, dc = sift.detectAndCompute(gc, None)
    if da is None or dc is None or len(ka) < 10 or len(kc) < 10:
        return Alignment(None, 0, 0.0)
    matches = cv2.BFMatcher().knnMatch(da, dc, k=2)
    good = [m for m, n in (p for p in matches if len(p) == 2) if m.distance < 0.72 * n.distance]
    if len(good) < 12:
        return Alignment(None, len(good), 0.0)
    src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kc[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    if H is None:
        return Alignment(None, 0, 0.0)
    inliers = int(mask.sum())
    # une homographie dégénérée (miroir, écrasement, quadrilatère croisé) est rejetée
    det = np.linalg.det(H[:2, :2])
    if det <= 0.01 or det > 100:
        return Alignment(None, inliers, inliers / len(good))
    # des points communs groupés dans un coin (texte, ciel, texture) ne prouvent rien
    pin = mask.ravel().astype(bool)
    for pts, img in ((src[pin], archive), (dst[pin], current)):
        p = pts.reshape(-1, 2)
        spread = float(np.ptp(p[:, 0]) * np.ptp(p[:, 1])) if len(p) else 0.0
        if spread < 0.08 * img.shape[0] * img.shape[1]:
            return Alignment(None, inliers, inliers / len(good))
    h, w = archive.shape[:2]
    quad = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2), H)
    if not cv2.isContourConvex(quad.astype(np.float32)):
        return Alignment(None, inliers, inliers / len(good))
    return Alignment(H, inliers, inliers / len(good))


def warp(archive: np.ndarray, H: np.ndarray, shape) -> tuple[np.ndarray, np.ndarray]:
    h, w = shape[:2]
    warped = cv2.warpPerspective(archive, H, (w, h))
    valid = cv2.warpPerspective(np.ones(archive.shape[:2], np.uint8), H, (w, h)).astype(bool)
    return warped, valid


# --------------------------------------------------------------------------- style d'époque

def style_profile(archives: list[np.ndarray]) -> dict:
    """Profil photographique d'une ville à une époque : teinte, contraste, grain, courbe tonale."""
    if not archives:
        return {"tint": [0.44, 0.40, 0.33], "contrast": 0.8, "grain": 6.0, "curve": list(np.linspace(0, 255, 256))}
    tints, contrasts, grains, hists = [], [], [], []
    for a in archives:
        f = a.astype(np.float32)
        mean = f.reshape(-1, 3).mean(axis=0)
        tints.append(mean / mean.sum())
        g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        contrasts.append(g.std() / 64)
        grains.append(float(np.std(g - cv2.GaussianBlur(g, (5, 5), 0))))
        hists.append(np.histogram(g, 256, (0, 256))[0])
    cdf = np.cumsum(np.mean(hists, axis=0))
    cdf = cdf / cdf[-1]
    return {
        "tint": np.mean(tints, axis=0).round(4).tolist(),
        "contrast": float(np.clip(np.mean(contrasts), 0.4, 1.4)),
        "grain": float(np.clip(np.mean(grains), 2, 14)),
        "cdf": cdf.round(5).tolist(),
    }


def age(img: np.ndarray, profile: dict, seed: int = 7) -> np.ndarray:
    """Rendu « photo d'époque » de la vue actuelle selon le profil appris sur les archives."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if "cdf" in profile:  # spécification d'histogramme vers la courbe tonale des archives
        src_cdf = np.cumsum(np.histogram(g, 256, (0, 256))[0]).astype(np.float64)
        src_cdf /= src_cdf[-1]
        lut = np.interp(src_cdf, np.array(profile["cdf"]), np.arange(256)).astype(np.uint8)
        g = lut[g]
    g = cv2.GaussianBlur(g, (3, 3), 0.8).astype(np.float32)
    tint = np.array(profile["tint"], np.float32) * 3
    out = np.stack([g * tint[0], g * tint[1], g * tint[2]], axis=-1)
    rng = np.random.default_rng(seed)
    out += rng.normal(0, profile.get("grain", 6), g.shape)[..., None]
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w]
    vignette = 1 - 0.45 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 2
    out *= vignette[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def blend(base: np.ndarray, layer: np.ndarray, mask: np.ndarray, feather: int = 21) -> np.ndarray:
    soft = cv2.GaussianBlur(mask.astype(np.float32), (feather | 1, feather | 1), 0)[..., None]
    return (layer * soft + base * (1 - soft)).astype(np.uint8)


# --------------------------------------------------------------------------- mesures

def ssim(a: np.ndarray, b: np.ndarray, mask: np.ndarray | None = None) -> float:
    """SSIM sur niveaux de gris, moyenné sur le masque."""
    x = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    y = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    k = (11, 11)
    mx, my = cv2.GaussianBlur(x, k, 1.5), cv2.GaussianBlur(y, k, 1.5)
    sxx = cv2.GaussianBlur(x * x, k, 1.5) - mx * mx
    syy = cv2.GaussianBlur(y * y, k, 1.5) - my * my
    sxy = cv2.GaussianBlur(x * y, k, 1.5) - mx * my
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    s = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    if mask is not None and mask.any():
        return float(s[mask].mean())
    return float(s.mean())


def fair_similarity(a: np.ndarray, b: np.ndarray, mask: np.ndarray | None = None) -> float:
    """SSIM à basse résolution sur niveaux de gris égalisés : ignore grain, teinte et exposition,
    pour comparer la structure d'une reconstruction à une vraie archive."""
    def prep(x):
        g = cv2.cvtColor(x, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (max(g.shape[1] // 4, 8), max(g.shape[0] // 4, 8)), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(cv2.equalizeHist(g), cv2.COLOR_GRAY2BGR)
    m = None
    if mask is not None:
        m = cv2.resize(mask.astype(np.uint8), (max(a.shape[1] // 4, 8), max(a.shape[0] // 4, 8)),
                       interpolation=cv2.INTER_NEAREST).astype(bool)
    return ssim(prep(a), prep(b), m)


def structure_similarity(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """Ressemblance des contours (insensible aux couleurs et au vieillissement)."""
    ea = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 60, 160)
    eb = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), 60, 160)
    ea = cv2.dilate(ea, np.ones((5, 5), np.uint8)) > 0
    eb = cv2.dilate(eb, np.ones((5, 5), np.uint8)) > 0
    inter = (ea & eb & mask).sum()
    union = ((ea | eb) & mask).sum()
    return float(inter / union) if union else 0.0
