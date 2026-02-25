import io
import zipfile
from PIL import Image

from app.models import TextBox, ApplicationFields
from app.extract import best_brand_match, is_gov_warning, extract_fields
from app.compare import compare
from app.utils import normalize_text, normalize_abv, normalize_net_contents

def tb(i, text, conf=0.95, bbox=(10,10,100,30)):
    return TextBox(id=f"t{i}", text=text, conf=conf, bbox=list(bbox))

def test_brand_punctuation_and_case_match():
    # Requirement: routine matching; tolerate punctuation/case differences
    expected = "Stone's Throw"
    candidates = [tb(1, "STONE’S THROW"), tb(2, "HANDCRAFTED WINE")]
    best, score, reason = best_brand_match(expected, candidates)
    assert best.text in ("STONE’S THROW",)
    assert score >= 0.85

def test_brand_truncation_substring_overlap():
    # Dave's nuance: label has longer brand, application shorter (or vice versa)
    expected = "Stone's"
    candidates = [tb(1, "STONE'S THROW"), tb(2, "RIVER VALLEY")]
    best, score, reason = best_brand_match(expected, candidates)
    assert best.id == "t1"
    assert score >= 0.70  # should be REVIEW or PASS depending on scoring
    assert reason in ("substring_overlap", "token_set_ratio")

def test_gov_warning_fuzzy_matches_ocr_errors():
    # Requirement: warning presence; OCR may introduce mistakes
    assert is_gov_warning("GOVERNMENT WARNING")
    assert is_gov_warning("GOVERNRMENT WARNlNG")  # rn / l confusion
    assert not is_gov_warning("WARNING: KEEP REFRIGERATED")

def test_abv_normalization_formats():
    assert normalize_abv("12.5% ABV") == "12.5%"
    assert normalize_abv("ALC./VOL. 12.50%") == "12.5%"
    assert normalize_abv(" alc/vol 7% ") == "7%"

def test_net_contents_normalization():
    assert normalize_net_contents("750 mL") == "750ml"
    assert normalize_net_contents(" 750ML ") == "750ml"
    assert normalize_net_contents("750 milliliters") == "750ml"

def test_compare_passes_when_all_present():
    # Requirement: simple applications should auto-pass quickly when all matches present
    app = ApplicationFields(brand_name="Stone's Throw", abv="12.5%", net_contents="750 mL", require_gov_warning=True)
    all_text = [
        tb(1, "STONE'S THROW", bbox=(10, 10, 300, 60)),
        tb(2, "12.5% ABV", bbox=(10, 120, 120, 25)),
        tb(3, "750 mL", bbox=(10, 150, 120, 25)),
        tb(4, "GOVERNMENT WARNING", bbox=(10, 300, 300, 25)),
    ]
    ext = extract_fields(all_text, image_w=1000, image_h=1500)
    items = compare(app, ext)
    assert all(i.status == "PASS" for i in items)

def test_compare_flags_missing_warning():
    app = ApplicationFields(brand_name="A Brand", abv=None, net_contents=None, require_gov_warning=True)
    all_text = [tb(1, "A BRAND", bbox=(10,10,300,60))]
    ext = extract_fields(all_text, image_w=1000, image_h=1500)
    items = compare(app, ext)
    warn = [i for i in items if i.field == "government_warning"][0]
    assert warn.status == "FAIL"

def test_batch_zip_payload_roundtrip_without_server():
    # Requirement: batch uploads of 200-300 labels should be supported via ZIP
    # Here we just validate we can create a ZIP of images, as backend expects.
    img = Image.new("RGB", (200, 100), color=(255,255,255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("label1.png", img_bytes)
        z.writestr("label2.png", img_bytes)

    # Ensure ZIP is readable and contains expected members
    zip_buf.seek(0)
    with zipfile.ZipFile(zip_buf, "r") as z:
        names = z.namelist()
        assert "label1.png" in names and "label2.png" in names
