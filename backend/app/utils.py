import re

def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[’']", "", s)           # remove apostrophes
    s = re.sub(r"[^a-z0-9\s]", " ", s)  # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()
    return s

def normalize_abv(s: str) -> str:
    # Standardize many formats to e.g. "12.5%"
    if not s:
        return ""
    t = s.strip().lower()
    # common noise
    t = t.replace("abv", "").replace("alc/vol", "").replace("alc.", "").replace("vol.", "")
    t = re.sub(r"\s+", "", t)

    m = re.search(r"(\d{1,2}(?:\.\d{1,3})?)%", t)
    if not m:
        return ""
    val = float(m.group(1))
    out = f"{val:.1f}".rstrip("0").rstrip(".")
    return f"{out}%"

def normalize_net_contents(s: str) -> str:
    if not s:
        return ""
    t = s.strip().lower()
    t = re.sub(r"\s+", "", t)
    t = t.replace("milliliters", "ml").replace("milliliter", "ml")
    return t

def normalize_warning(s: str) -> str:
    """Normalize warning statement for comparison.

    - uppercases
    - removes punctuation
    - collapses whitespace
    """
    if not s:
        return ""
    t = s.upper()
    t = re.sub(r"[^A-Z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
