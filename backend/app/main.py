import io
import time
import zipfile
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from .models import ApplicationFields, VerificationResult
from .ocr import ocr_boxes
from .extract import extract_fields
from .compare import compare

app = FastAPI(title="Alcohol Label Verifier", version="0.2.0")

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

def _image_size_from_bytes(image_bytes: bytes) -> tuple[int, int]:
    img = Image.open(io.BytesIO(image_bytes))
    return img.size

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

    ext = extract_fields(boxes, image_w=w, image_h=h)
    items = compare(app_fields, ext)

    overall = "PASS" if all(i.status == "PASS" for i in items) else "NEEDS_REVIEW"

    timings = {
        **t_ocr,
        "extract_compare_ms": int((time.time() - t1) * 1000),
        "total_ms": int((time.time() - t0) * 1000),
    }

    return VerificationResult(
        overall_status=overall,
        items=items,
        timings_ms=timings,
        debug={"num_boxes": len(boxes)} if debug else None
    )

@app.post("/api/verify-batch")
async def verify_batch(
    zip_file: UploadFile = File(...),
    brand_name: str = Form(...),
    abv: str | None = Form(None),
    net_contents: str | None = Form(None),
    require_gov_warning: bool = Form(True),
):
    content = await zip_file.read()
    z = zipfile.ZipFile(io.BytesIO(content))
    results = []

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
            ext = extract_fields(boxes, image_w=w, image_h=h)
            items = compare(app_fields, ext)
            overall = "PASS" if all(i.status == "PASS" for i in items) else "NEEDS_REVIEW"
            results.append({"filename": name, "overall_status": overall, "items": [i.model_dump() for i in items]})

    return {"count": len(results), "results": results}
