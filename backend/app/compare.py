from rapidfuzz import fuzz
from .models import ApplicationFields, ExtractedFields, CheckItem
import re
import unicodedata

from .utils import normalize_abv, normalize_net_contents

# Canonical TTB warning text (commonly required). OCR is noisy, so we enforce
# a strict-but-OCR-aware match using header + required clauses with high similarity.
TTB_WARNING_EXPECTED = """GOVERNMENT WARNING:
(1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects.
(2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."""

def _normalize_warning_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.lower()
    # common OCR confusions
    s = s.replace("0", "o")
    # keep alphanumerics + spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_warning_block(ocr_text: str) -> str:
    # Find starting point near the warning header; then take a window after it.
    m = re.search(r"(government\s+warning[:\s])", ocr_text, flags=re.IGNORECASE)
    if not m:
        return ""
    start = m.start()
    return ocr_text[start:start + 900]

def _gov_warning_strict_status(ocr_text: str) -> tuple[str, float, str]:
    """Return (status, confidence, notes) for government warning strictness.

    Status: PASS | REVIEW | FAIL
    Confidence: 0..1
    """
    block = _extract_warning_block(ocr_text)
    if not block:
        return "FAIL", 0.0, "No GOVERNMENT WARNING block detected"

    # Header: must be all caps + colon. OCR can't verify bold reliably.
    header_ok = bool(re.search(r"\bGOVERNMENT\s+WARNING:\b", block))
    header_present = bool(re.search(r"\bGOVERNMENT\s+WARNING\b", block))

    block_n = _normalize_warning_text(block)
    expected_n = _normalize_warning_text(TTB_WARNING_EXPECTED)

    clause1_n = _normalize_warning_text(
        "According to the Surgeon General women should not drink alcoholic beverages during pregnancy because of the risk of birth defects"
    )
    clause2_n = _normalize_warning_text(
        "Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery and may cause health problems"
    )

    c1 = fuzz.partial_ratio(clause1_n, block_n) / 100.0 if clause1_n and block_n else 0.0
    c2 = fuzz.partial_ratio(clause2_n, block_n) / 100.0 if clause2_n and block_n else 0.0
    full_sim = fuzz.partial_ratio(expected_n, block_n) / 100.0 if expected_n and block_n else 0.0

    # PASS: strong evidence for header + both clauses + high similarity
    if header_ok and c1 >= 0.92 and c2 >= 0.92 and full_sim >= 0.88:
        conf = min(1.0, (c1 + c2 + full_sim) / 3.0)
        return "PASS", conf, f"Header OK; clause1={c1:.2f} clause2={c2:.2f} full={full_sim:.2f}"

    # REVIEW: warning present but OCR differs / partial clause coverage
    if header_present and (c1 >= 0.80 or c2 >= 0.80):
        conf = max(c1, c2, full_sim)
        return "REVIEW", conf, f"Warning detected but not exact; header_colon={header_ok}; clause1={c1:.2f} clause2={c2:.2f} full={full_sim:.2f}"

    return "FAIL", max(c1, c2, full_sim), f"Warning text insufficient; header_colon={header_ok}; clause1={c1:.2f} clause2={c2:.2f} full={full_sim:.2f}"


def _status_from_score(score: float, pass_th: float, review_th: float) -> str:
    if score >= pass_th:
        return "PASS"
    if score >= review_th:
        return "REVIEW"
    return "FAIL"

def compare(app: ApplicationFields, ext: ExtractedFields) -> list[CheckItem]:
    items: list[CheckItem] = []

    # Brand
    from .extract import best_brand_match
    best, score, reason = best_brand_match(app.brand_name, ext.brand_candidates)
    if best is None:
        items.append(CheckItem(field="brand_name", status="MISSING", expected=app.brand_name, notes="No brand candidates found"))
    else:
        st = _status_from_score(score, pass_th=0.85, review_th=0.70)
        items.append(CheckItem(
            field="brand_name",
            status=st,
            expected=app.brand_name,
            found=best.text,
            confidence=round(score, 3),
            notes=f"Brand match via {reason}",
            bbox_ids=[best.id]
        ))

    # ABV
    if app.abv:
        exp_abv = normalize_abv(app.abv)
        best_tb = None
        best_score = 0.0
        for tb in ext.abv_candidates:
            found = normalize_abv(tb.text)
            if not found or not exp_abv:
                continue
            # exact normalized match is best
            s = 1.0 if found == exp_abv else (fuzz.ratio(exp_abv, found) / 100.0)
            if s > best_score:
                best_score, best_tb = s, tb

        if not best_tb:
            items.append(CheckItem(field="abv", status="MISSING", expected=app.abv, notes="No ABV detected"))
        else:
            st = _status_from_score(best_score, pass_th=0.95, review_th=0.80)
            items.append(CheckItem(field="abv", status=st, expected=app.abv, found=best_tb.text, confidence=round(best_score, 3), bbox_ids=[best_tb.id]))

    # Net contents
    if app.net_contents:
        exp = normalize_net_contents(app.net_contents)
        best_tb = None
        best_score = 0.0
        for tb in ext.net_contents_candidates:
            found = normalize_net_contents(tb.text)
            s = (fuzz.ratio(exp, found) / 100.0) if exp and found else 0.0
            if s > best_score:
                best_score, best_tb = s, tb

        if not best_tb:
            items.append(CheckItem(field="net_contents", status="MISSING", expected=app.net_contents, notes="No net contents detected"))
        else:
            st = _status_from_score(best_score, pass_th=0.90, review_th=0.75)
            items.append(CheckItem(field="net_contents", status=st, expected=app.net_contents, found=best_tb.text, confidence=round(best_score, 3), bbox_ids=[best_tb.id]))

    # Government warning (strict-but-OCR-aware)
    if app.require_gov_warning:
        # Build a single OCR text string for matching.
        # (Using all_text is more reliable than only the header candidate.)
        ocr_text = "\n".join([tb.text for tb in ext.all_text]) if ext.all_text else ""
        st, conf, notes = _gov_warning_strict_status(ocr_text)
        if st == "PASS":
            ids = [tb.id for tb in ext.warning_candidates[:3]] if ext.warning_candidates else []
            found = ext.warning_candidates[0].text if ext.warning_candidates else "GOVERNMENT WARNING"
            items.append(CheckItem(field="government_warning", status="PASS", expected="TTB standard warning", found=found, confidence=round(conf, 3), notes=notes, bbox_ids=ids))
        elif st == "REVIEW":
            ids = [tb.id for tb in ext.warning_candidates[:3]] if ext.warning_candidates else []
            found = ext.warning_candidates[0].text if ext.warning_candidates else None
            items.append(CheckItem(field="government_warning", status="REVIEW", expected="TTB standard warning", found=found, confidence=round(conf, 3), notes=notes, bbox_ids=ids))
        else:
            items.append(CheckItem(field="government_warning", status="FAIL", expected="TTB standard warning", confidence=round(conf, 3), notes=notes))

    return items