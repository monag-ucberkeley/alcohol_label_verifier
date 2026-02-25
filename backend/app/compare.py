from rapidfuzz import fuzz
from .models import ApplicationFields, ExtractedFields, CheckItem
from .utils import normalize_abv, normalize_net_contents

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

    # Government warning
    if app.require_gov_warning:
        if ext.warning_candidates:
            ids = [tb.id for tb in ext.warning_candidates[:3]]
            items.append(CheckItem(field="government_warning", status="PASS", expected="present", found=ext.warning_candidates[0].text, confidence=ext.warning_candidates[0].conf, bbox_ids=ids))
        else:
            items.append(CheckItem(field="government_warning", status="FAIL", expected="present", notes="Government warning not detected"))

    return items
