import io
import json
import time
import zipfile
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from .models import ApplicationFields, VerificationResult
from .ocr import ocr_boxes
from .extract import extract_fields
from .compare import compare
import base64
from zipfile import ZipFile
from collections import defaultdict


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


def _run_verification(image_bytes: bytes, app_fields: ApplicationFields, debug: bool = False) -> VerificationResult:
    t0 = time.time()
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

@app.post("/api/verify-with-application-json", response_model=VerificationResult)
async def verify_with_application_json(
    file: UploadFile = File(...),
    application_json: UploadFile = File(...),
    debug: bool = Form(False),
):
    """Verify a label image against a COLA application JSON file.

    Intended for:
    - Paired datasets (label.png + application.json)
    - Future export/integration where application fields are available in structured form
    """
    image_bytes = await file.read()
    app_bytes = await application_json.read()

    try:
        app_data = json.loads(app_bytes.decode("utf-8"))
    except Exception as e:
        # FastAPI will turn ValueError into 500; raise HTTPException for 400.
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid application JSON: {e}")

    app_fields = ApplicationFields(
        brand_name=str(app_data.get("brand_name", "")).strip(),
        abv=app_data.get("abv"),
        net_contents=app_data.get("net_contents"),
        require_gov_warning=bool(app_data.get("government_warning_required", True)),
    )

    return _run_verification(image_bytes=image_bytes, app_fields=app_fields, debug=debug)


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
            import base64
            from PIL import Image
            
            # thumbnail
            thumb_b64 = None
            try:
                im = Image.open(io.BytesIO(label_bytes)).convert('RGB')
                im.thumbnail((220,220))
                buf = io.BytesIO()
                im.save(buf, format='JPEG', quality=70)
                thumb_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            except Exception:
                thumb_b64 = None

            results.append({"filename": name, "overall_status": overall, "items": [i.model_dump() for i in items]})

    return {"count": len(results), "results": results}


from zipfile import ZipFile
import io
import json as _json
from collections import defaultdict

@app.post("/api/verify-batch-pairs")
async def verify_batch_pairs(
    zip_file: UploadFile = File(...),
):
    """Verify a ZIP containing (label image + application.json) pairs.

    Expected ZIP structure examples:
      - regular/sample_01/label.png + regular/sample_01/application.json
      - sample_01/label.png + sample_01/application.json

    Each folder must contain:
      - label.(png|jpg|jpeg) (or any image)
      - application.json
    """
    data = await zip_file.read()
    zf = ZipFile(io.BytesIO(data))

    # group files by folder
    groups = defaultdict(dict)
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        lower = name.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".json")):
            folder = name.rsplit("/", 1)[0] if "/" in name else ""
            groups[folder][name.rsplit("/", 1)[-1].lower()] = name

    results = []
    for folder, files in groups.items():
        # find application.json
        app_key = "application.json" if "application.json" in files else None
        if not app_key:
            continue

        # find label image (prefer label.*)
        label_key = None
        for k in files.keys():
            if k.endswith((".png", ".jpg", ".jpeg")) and ("label" in k or k.startswith("label")):
                label_key = k
                break
        if label_key is None:
            for k in files.keys():
                if k.endswith((".png", ".jpg", ".jpeg")):
                    label_key = k
                    break
        if not label_key:
            continue

        label_path = files[label_key]
        app_path = files[app_key]

        label_bytes = zf.read(label_path)
        app_bytes = zf.read(app_path)

        try:
            app_data = json.loads(app_bytes.decode("utf-8"))
        except Exception:
            app_data = {}

        # thumbnail (base64 JPEG)
        thumb_b64 = None
        try:
            im = Image.open(io.BytesIO(label_bytes)).convert("RGB")
            im.thumbnail((220, 220))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=70)
            thumb_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            thumb_b64 = None

        from app.verify import verify_label_bytes  # local import to avoid circulars

        res = verify_label_bytes(
            label_bytes=label_bytes,
            brand_name=app_data.get("brand_name", ""),
            abv=app_data.get("abv", ""),
            net_contents=app_data.get("net_contents", ""),
            require_gov_warning=bool(app_data.get("government_warning_required", True)),
        )

        results.append({
            "folder": folder or "(root)",
            "label_filename": label_key,
            "thumbnail_b64": thumb_b64,
            "application": {
                "brand_name": app_data.get("brand_name", ""),
                "abv": app_data.get("abv", ""),
                "net_contents": app_data.get("net_contents", ""),
                "government_warning_required": bool(app_data.get("government_warning_required", True)),
            },
            "result": res,
        })

    return {"count": len(results), "results": results}
