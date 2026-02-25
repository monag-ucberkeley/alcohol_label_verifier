import io
import time
import zipfile
from statistics import mean
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from .models import ApplicationFields, VerificationResult, ImageQuality, BatchResult, BatchItemResult
from .ocr import ocr_boxes
from .extract import extract_fields
from .compare import compare

app = FastAPI(title="Alcohol Label Verifier", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"ok": True, "message": "Alcohol Label Verifier API. See /docs for interactive API docs."}

def _image_size_from_bytes(image_bytes: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(image_bytes))
    return img.size

def _assess_image_quality(boxes) -> ImageQuality:
    if not boxes:
        return ImageQuality(
            rating="POOR",
            avg_ocr_confidence=0.0,
            low_conf_ratio=1.0,
            total_text_chars=0,
            recommendation="No readable text detected. Request a clearer image."
        )
    confs = [float(tb.conf) for tb in boxes]
    avg = mean(confs) if confs else 0.0
    low = sum(1 for c in confs if c < 0.5) / max(1, len(confs))
    chars = sum(len(tb.text or "") for tb in boxes)

    if avg < 0.50 or chars < 80:
        rating = "POOR"
        rec = "Image likely unreadable (low OCR confidence). Request a clearer, well-lit photo without glare."
    elif avg < 0.65 or low > 0.35:
        rating = "FAIR"
        rec = "Image is borderline. Automated checks may miss details; review warning text and numeric fields."
    else:
        rating = "GOOD"
        rec = "Image quality is sufficient for automated checks."

    return ImageQuality(
        rating=rating,
        avg_ocr_confidence=round(avg, 3),
        low_conf_ratio=round(low, 3),
        total_text_chars=int(chars),
        recommendation=rec
    )

@app.post("/api/verify", response_model=VerificationResult)
async def verify(
    file: UploadFile = File(...),
    brand_name: str = Form(...),
    abv: str | None = Form(None),
    net_contents: str | None = Form(None),
    require_gov_warning: bool = Form(True),
    debug: bool = Form(False),
):
    t0 = time.time()
    image_bytes = await file.read()

    app_fields = ApplicationFields(
        brand_name=brand_name,
        abv=abv,
        net_contents=net_contents,
        require_gov_warning=require_gov_warning,
    )

    w, h = _image_size_from_bytes(image_bytes)

    boxes, t_ocr = ocr_boxes(image_bytes)
    t1 = time.time()

    quality = _assess_image_quality(boxes)

    ext = extract_fields(boxes, image_w=w, image_h=h)
    items = compare(app_fields, ext, image_quality_rating=quality.rating)

    # Overall: PASS only if every item PASS (and image quality not POOR)
    overall = "PASS" if all(i.status == "PASS" for i in items) and quality.rating != "POOR" else "NEEDS_REVIEW"

    timings = {
        **t_ocr,
        "extract_compare_ms": int((time.time() - t1) * 1000),
        "total_ms": int((time.time() - t0) * 1000),
    }

    return VerificationResult(
        overall_status=overall,
        items=items,
        image_quality=quality,
        timings_ms=timings,
        debug={"num_boxes": len(boxes)} if debug else None
    )

@app.post("/api/verify-batch", response_model=BatchResult)
async def verify_batch(
    zip_file: UploadFile = File(...),
    brand_name: str = Form(...),
    abv: str | None = Form(None),
    net_contents: str | None = Form(None),
    require_gov_warning: bool = Form(True),
):
    content = await zip_file.read()
    z = zipfile.ZipFile(io.BytesIO(content))
    results: list[BatchItemResult] = []

    for name in z.namelist():
        if name.lower().endswith((".png", ".jpg", ".jpeg")):
            image_bytes = z.read(name)
            app_fields = ApplicationFields(
                brand_name=brand_name,
                abv=abv,
                net_contents=net_contents,
                require_gov_warning=require_gov_warning,
            )
            w, h = _image_size_from_bytes(image_bytes)
            boxes, _ = ocr_boxes(image_bytes)
            quality = _assess_image_quality(boxes)
            ext = extract_fields(boxes, image_w=w, image_h=h)
            items = compare(app_fields, ext, image_quality_rating=quality.rating)
            overall = "PASS" if all(i.status == "PASS" for i in items) and quality.rating != "POOR" else "NEEDS_REVIEW"
            results.append(BatchItemResult(
                filename=name,
                overall_status=overall,
                items=items,
                image_quality=quality,
                timings_ms={},
                debug=None
            ))

    return BatchResult(count=len(results), results=results)
