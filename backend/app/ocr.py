import os
import io
import time
from typing import List, Tuple, Dict, DefaultDict
from collections import defaultdict

from PIL import Image
import pytesseract
import cv2
import numpy as np

from .models import TextBox

def _preprocess(pil_img: Image.Image, max_pixels: int) -> Image.Image:
    # Resize huge images for speed
    w, h = pil_img.size
    if w * h > max_pixels:
        scale = (max_pixels / (w * h)) ** 0.5
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        pil_img = pil_img.resize((nw, nh))
    return pil_img

def _union_bbox(bboxes):
    xs = [b[0] for b in bboxes]
    ys = [b[1] for b in bboxes]
    xe = [b[0] + b[2] for b in bboxes]
    ye = [b[1] + b[3] for b in bboxes]
    x0, y0, x1, y1 = min(xs), min(ys), max(xe), max(ye)
    return [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]

def ocr_boxes(image_bytes: bytes) -> Tuple[List[TextBox], Dict[str, int]]:
    """Return LINE-level OCR boxes.

    Why line-level?
    - Tesseract often returns single words (e.g. brand becomes just 'THROW')
    - '750 mL' often appears as two tokens ('750' and 'mL')
    - 'GOVERNMENT WARNING' may come back as separate words

    Grouping into lines makes regex extraction and matching behave like a human reviewer.
    """
    t0 = time.time()
    max_pixels = int(os.getenv("MAX_IMAGE_PIXELS", "6000000"))
    lang = os.getenv("OCR_LANG", "eng")

    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil_img = _preprocess(pil_img, max_pixels)

    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    data = pytesseract.image_to_data(gray, lang=lang, output_type=pytesseract.Output.DICT)

    # Group words into lines using Tesseract's block/par/line indices.
    groups: DefaultDict[tuple, list] = defaultdict(list)
    n = len(data["text"])
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        conf_raw = data["conf"][i]
        conf = float(conf_raw) if conf_raw != "-1" else 0.0
        x, y, w, h = int(data["left"][i]), int(data["top"][i]), int(data["width"][i]), int(data["height"][i])
        key = (
            int(data.get("page_num", [1]*n)[i]),
            int(data.get("block_num", [0]*n)[i]),
            int(data.get("par_num", [0]*n)[i]),
            int(data.get("line_num", [0]*n)[i]),
        )
        groups[key].append((x, y, w, h, max(0.0, conf) / 100.0, txt))

    # Build line boxes sorted top-to-bottom, then left-to-right
    line_items = []
    for key, words in groups.items():
        words.sort(key=lambda t: t[0])  # by x
        text = " ".join(w[-1] for w in words)
        bboxes = [(w[0], w[1], w[2], w[3]) for w in words]
        bbox = _union_bbox(bboxes)
        conf = sum(w[4] for w in words) / max(1, len(words))
        # approximate y for sorting
        line_items.append((bbox[1], bbox[0], text, conf, bbox))

    line_items.sort(key=lambda t: (t[0], t[1]))

    boxes: List[TextBox] = []
    for idx, (_, __, text, conf, bbox) in enumerate(line_items, start=1):
        boxes.append(TextBox(id=f"l{idx}", text=text, conf=float(conf), bbox=bbox))

    timings = {"ocr_ms": int((time.time() - t0) * 1000)}
    return boxes, timings
