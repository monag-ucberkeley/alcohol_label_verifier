"""Internal verification helper used for batch pair endpoint.

This mirrors the /api/verify endpoint logic (OCR -> extract -> compare) but
accepts raw image bytes and application values.
"""

from __future__ import annotations

import io
import time
from typing import Any, Dict, Optional, Tuple

from PIL import Image

from .models import ApplicationFields
from .ocr import ocr_boxes
from .extract import extract_fields
from .compare import compare


def _image_size_from_bytes(image_bytes: bytes) -> Tuple[int, int]:
    with Image.open(io.BytesIO(image_bytes)) as im:
        return im.size  # (w, h)


def verify_label_bytes(
    label_bytes: bytes,
    brand_name: str,
    abv: Optional[str],
    net_contents: Optional[str],
    require_gov_warning: bool = True,
) -> Dict[str, Any]:
    t0 = time.time()

    app_fields = ApplicationFields(
        brand_name=brand_name or "",
        abv=abv,
        net_contents=net_contents,
        require_gov_warning=require_gov_warning,
    )

    w, h = _image_size_from_bytes(label_bytes)

    boxes, t_ocr = ocr_boxes(label_bytes)
    t1 = time.time()

    ext = extract_fields(boxes, image_w=w, image_h=h)
    items = compare(app_fields, ext)

    overall = "PASS" if all(getattr(i, "status", None) == "PASS" for i in items) else "NEEDS_REVIEW"

    timings = {
        **(t_ocr or {}),
        "extract_compare_ms": int((time.time() - t1) * 1000),
        "total_ms": int((time.time() - t0) * 1000),
    }

    # Convert pydantic models to dict-friendly objects
    items_out = []
    for i in items:
        try:
            items_out.append(i.model_dump())
        except Exception:
            try:
                items_out.append(i.dict())
            except Exception:
                items_out.append({
                    "field": getattr(i, "field", None),
                    "status": getattr(i, "status", None),
                    "expected": getattr(i, "expected", None),
                    "found": getattr(i, "found", None),
                    "confidence": getattr(i, "confidence", None),
                    "notes": getattr(i, "notes", None),
                })

    return {
        "overall_status": overall,
        "items": items_out,
        "timings_ms": timings,
    }
