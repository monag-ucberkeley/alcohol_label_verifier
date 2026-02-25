from __future__ import annotations

from rapidfuzz import fuzz
from .models import ApplicationFields, ExtractedFields, CheckItem
from .utils import normalize_abv, normalize_net_contents, normalize_warning

def _status_from_score(score: float, pass_th: float, review_th: float) -> str:
    if score >= pass_th:
        return "PASS"
    if score >= review_th:
        return "REVIEW"
    return "FAIL"

# Canonical U.S. alcohol government warning (27 CFR 16.21 style).
# For this prototype we check for the required clauses after normalization.
REQUIRED_WARNING_PHRASES = [
    "GOVERNMENT WARNING",
    "ACCORDING TO THE SURGEON GENERAL WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING PREGNANCY",
    "CONSUMPTION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE A CAR OR OPERATE MACHINERY AND MAY CAUSE HEALTH PROBLEMS",
]

def _collect_all_text(ext: ExtractedFields) -> str:
    return " ".join(tb.text for tb in ext.all_text if tb.text)

def compare(app: ApplicationFields, ext: ExtractedFields, *, image_quality_rating: str | None = None) -> list[CheckItem]:
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
            notes=f"Brand match via {reason} (punctuation/case tolerant).",
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
            s = 1.0 if found == exp_abv else (fuzz.ratio(exp_abv, found) / 100.0)
            if s > best_score:
                best_score, best_tb = s, tb

        if not best_tb:
            items.append(CheckItem(field="abv", status="MISSING", expected=app.abv, notes="No ABV detected"))
        else:
            st = _status_from_score(best_score, pass_th=0.95, review_th=0.80)
            items.append(CheckItem(
                field="abv",
                status=st,
                expected=app.abv,
                found=best_tb.text,
                confidence=round(best_score, 3),
                notes=f"Normalized expected={exp_abv}.",
                bbox_ids=[best_tb.id]
            ))

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
            items.append(CheckItem(
                field="net_contents",
                status=st,
                expected=app.net_contents,
                found=best_tb.text,
                confidence=round(best_score, 3),
                notes=f"Normalized expected={exp}.",
                bbox_ids=[best_tb.id]
            ))

    # Government warning (Jenny: strictness matters)
    if app.require_gov_warning:
        all_text_raw = _collect_all_text(ext)
        all_norm = normalize_warning(all_text_raw)

        # 1) presence (fuzzy, to reduce false negatives from OCR)
        present = bool(ext.warning_candidates) or ("GOVERNMENT WARNING" in all_norm)
        if present:
            items.append(CheckItem(
                field="government_warning_present",
                status="PASS",
                expected="present",
                found="present",
                confidence=round(ext.warning_candidates[0].conf, 3) if ext.warning_candidates else None,
                notes="Detected a government warning block."
            ))
        else:
            items.append(CheckItem(
                field="government_warning_present",
                status="FAIL",
                expected="present",
                notes="Government warning not detected."
            ))
            # If not present, strict checks don't matter
            return items

        # 2) header capitalization/colon check
        header_ok = False
        header_tb = None
        for tb in ext.warning_candidates[:10]:
            if "GOVERNMENT WARNING" in tb.text and ":" in tb.text:
                header_ok = True
                header_tb = tb
                break
            # sometimes OCR returns without colon; allow REVIEW for missing colon
            if "GOVERNMENT WARNING" in tb.text:
                header_tb = tb
        if header_ok:
            items.append(CheckItem(
                field="government_warning_header",
                status="PASS",
                expected="GOVERNMENT WARNING:",
                found=header_tb.text if header_tb else None,
                notes="Header is uppercase with ':' as required."
            ))
        else:
            # If we saw header but not exact (e.g. title case), mark FAIL.
            # If we only saw it without colon, mark REVIEW.
            if header_tb and header_tb.text.upper().find("GOVERNMENT WARNING") >= 0:
                # check caps
                if "GOVERNMENT WARNING" in header_tb.text and ":" not in header_tb.text:
                    st = "REVIEW"
                    note = "Header found but ':' missing/unclear in OCR. Manual review recommended."
                else:
                    st = "FAIL"
                    note = "Header not in all-caps 'GOVERNMENT WARNING:' (case/format mismatch)."
                items.append(CheckItem(
                    field="government_warning_header",
                    status=st,
                    expected="GOVERNMENT WARNING:",
                    found=header_tb.text,
                    notes=note
                ))
            else:
                items.append(CheckItem(
                    field="government_warning_header",
                    status="FAIL",
                    expected="GOVERNMENT WARNING:",
                    found=None,
                    notes="Unable to locate warning header line."
                ))

        # 3) body phrase strictness (word-for-word after normalization)
        missing = []
        for phrase in REQUIRED_WARNING_PHRASES[1:]:
            if phrase not in all_norm:
                missing.append(phrase)

        if not missing:
            items.append(CheckItem(
                field="government_warning_text",
                status="PASS",
                expected="exact required clauses",
                found="all required clauses present",
                notes="Warning body contains the required clauses (normalized exact match)."
            ))
        else:
            # partial match -> REVIEW (OCR errors) vs FAIL (clearly wrong).
            # Use fuzzy match to decide.
            fuzzy_hits = 0
            for phrase in missing:
                if fuzz.partial_ratio(all_norm, phrase) >= 85:
                    fuzzy_hits += 1
            st = "REVIEW" if fuzzy_hits else "FAIL"
            items.append(CheckItem(
                field="government_warning_text",
                status=st,
                expected="exact required clauses",
                found=f"missing {len(missing)} clause(s)",
                notes="Missing required warning text clauses. " + ("Likely OCR degradation; request clearer image or manually verify." if st=="REVIEW" else "Appears non-compliant wording.")
            ))

    # Image quality (helps agents decide: reject vs proceed)
    if image_quality_rating:
        if image_quality_rating == "POOR":
            items.append(CheckItem(
                field="image_quality",
                status="REVIEW",
                expected="readable photo",
                found="poor",
                notes="OCR confidence indicates the image may be unreadable. Consider requesting a clearer photo."
            ))
        elif image_quality_rating == "FAIR":
            items.append(CheckItem(
                field="image_quality",
                status="REVIEW",
                expected="readable photo",
                found="fair",
                notes="Image is borderline; review borderline fields carefully."
            ))
        else:
            items.append(CheckItem(
                field="image_quality",
                status="PASS",
                expected="readable photo",
                found="good",
                notes="Image quality is sufficient for automated checks."
            ))

    return items
