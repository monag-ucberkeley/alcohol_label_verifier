import re
from typing import List, Tuple
from rapidfuzz import fuzz
from .models import TextBox, ExtractedFields
from .utils import normalize_text

ABV_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*%(\s*abv)?", re.IGNORECASE)
NET_RE = re.compile(r"(\d+)\s*(ml|mL|ML|l|L|oz|fl\.?\s*oz|cl)", re.IGNORECASE)

def is_gov_warning(text: str) -> bool:
    # Fuzzy so minor OCR errors still match (requirement: robust + fast)
    if not text:
        return False
    t = normalize_text(text)
    if "government warning" in t:
        return True
    # handle common OCR errors: "governrnent warnlng"
    return fuzz.partial_ratio(t, "government warning") >= 85

def extract_fields(all_text: List[TextBox], image_w: int = 1000, image_h: int = 1000) -> ExtractedFields:
    abv, net, warn = [], [], []
    for tb in all_text:
        t = tb.text
        if ABV_RE.search(t):
            abv.append(tb)
        if NET_RE.search(t):
            net.append(tb)
        if is_gov_warning(t):
            warn.append(tb)

    # Brand candidates: top region + larger height + high conf
    brand_candidates = []
    for tb in all_text:
        x, y, w, h = tb.bbox
        if y <= 0.4 * image_h:
            score = (h * 0.7) + (tb.conf * 50.0)
            brand_candidates.append((score, tb))
    brand_candidates.sort(key=lambda p: p[0], reverse=True)
    brand = [tb for _, tb in brand_candidates[:15]]

    return ExtractedFields(
        abv_candidates=abv,
        net_contents_candidates=net,
        warning_candidates=warn,
        brand_candidates=brand,
        all_text=all_text,
    )

def best_brand_match(expected: str, candidates: List[TextBox]) -> Tuple[TextBox | None, float, str]:
    exp = normalize_text(expected)
    if not exp:
        return None, 0.0, "empty_expected"
    best = None
    best_score = 0.0
    best_reason = "no_candidates"

    for tb in candidates:
        found = normalize_text(tb.text)
        if not found:
            continue

        # Primary score: token-set similarity
        score = fuzz.token_set_ratio(exp, found) / 100.0
        reason = "token_set_ratio"

        # Bonus: substring/truncation tolerance (Dave's nuance: e.g., "STONE'S" vs "STONE'S THROW")
        if exp in found or found in exp:
            # only accept if meaningful overlap (avoid 1-2 char matches)
            min_len = min(len(exp), len(found))
            max_len = max(len(exp), len(found))
            if min_len >= 5 and (min_len / max_len) >= 0.60:
                score = max(score, 0.86)
                reason = "substring_overlap"

        if score > best_score:
            best_score = score
            best = tb
            best_reason = reason

    return best, best_score, best_reason
