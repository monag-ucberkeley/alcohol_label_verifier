from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ApplicationFields(BaseModel):
    brand_name: str = Field(..., description="Expected brand name from application")
    abv: Optional[str] = Field(None, description="Expected ABV (e.g., '12.5%')")
    net_contents: Optional[str] = Field(None, description="Expected net contents (e.g., '750 mL')")
    require_gov_warning: bool = Field(True, description="Whether govt warning is required for this label")

class TextBox(BaseModel):
    id: str
    text: str
    conf: float
    bbox: List[int]  # [x, y, w, h]

class ExtractedFields(BaseModel):
    abv_candidates: List[TextBox] = []
    net_contents_candidates: List[TextBox] = []
    warning_candidates: List[TextBox] = []
    brand_candidates: List[TextBox] = []
    all_text: List[TextBox] = []

class CheckItem(BaseModel):
    field: str
    status: str  # PASS | FAIL | REVIEW | MISSING
    expected: Optional[str] = None
    found: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    bbox_ids: List[str] = []

class ImageQuality(BaseModel):
    rating: str  # GOOD | FAIR | POOR
    avg_ocr_confidence: float
    low_conf_ratio: float
    total_text_chars: int
    recommendation: str

class VerificationResult(BaseModel):
    overall_status: str  # PASS | NEEDS_REVIEW
    items: List[CheckItem]
    image_quality: Optional[ImageQuality] = None
    timings_ms: Dict[str, int] = {}
    debug: Optional[Dict[str, Any]] = None

class BatchItemResult(VerificationResult):
    filename: str

class BatchResult(BaseModel):
    count: int
    results: List[BatchItemResult]
