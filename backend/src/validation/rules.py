import math
import re
from datetime import datetime, date, timezone
from typing import Dict, Iterable, Tuple, Optional
from src.validation.reference_ranges import (
    UNIT_CONVERSIONS, RAW_COUNT_THRESHOLD, PLAUSIBLE_LIMITS, canonical_unit, get_reference_range,
)

COUNT_FIELDS = {"white_blood_cell_count", "platelet_count"}

def normalize_text(val: str) -> str:
    if not val:
        return ""
    # Trim and normalize whitespace
    return re.sub(r'\s+', ' ', val.strip())

_MDY_FORMATS = ("%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y")
# 14-Mar-1985, 14 Mar 1985, 14 March 1985, Mar 14, 1985, March 14 1985
_MONTH_NAME_FORMATS = ("%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%d-%B-%Y", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y")
_DMY_FORMATS = ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y")

def date_order() -> str:
    from src.core.config import settings
    return "DMY" if str(settings.DATE_ORDER).upper() == "DMY" else "MDY"

def parse_date(val: str, order: Optional[str] = None) -> Optional[date]:
    """
    ISO first; then numeric day/month dates in `order` (default: the configured DATE_ORDER),
    falling back to the other order only when the value cannot be read that way (e.g. a day
    above 12). Dotted dates (31.12.2024) are always day first.
    """
    val = normalize_text(val)
    numeric = _DMY_FORMATS if (order or date_order()) == "DMY" else _MDY_FORMATS
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", *numeric, "%d.%m.%Y", *_MONTH_NAME_FORMATS):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None

def is_ambiguous_date(val: str) -> bool:
    """True for numeric dates like 03/04/2025 that are valid both day-first and month-first."""
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-]\d{4}", normalize_text(val or ""))
    return bool(m) and m.group(1) != m.group(2) and int(m.group(1)) <= 12 and int(m.group(2)) <= 12

def document_date_order(values: Iterable[Optional[str]]) -> Optional[str]:
    """
    "DMY" or "MDY" when one of a document's numeric dates can only be read that way (a day above
    12, e.g. 25/03/1980), so its ambiguous dates are read the same way. None without such
    evidence, or when the dates disagree.
    """
    seen = set()
    for val in values:
        m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-]\d{4}", normalize_text(val or ""))
        if m:
            first, second = int(m.group(1)), int(m.group(2))
            if first > 12 >= second:
                seen.add("DMY")
            elif second > 12 >= first:
                seen.add("MDY")
    return seen.pop() if len(seen) == 1 else None

def normalize_date(val: str, order: Optional[str] = None) -> Optional[str]:
    parsed = parse_date(val, order)
    return parsed.strftime("%Y-%m-%d") if parsed else None

# Thousands separators ("250,000"), a decimal comma ("14,8") or a decimal point ("13.2")
_NUMERIC = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+,\d{1,2}(?![\d,])|\d+(?:\.\d+)?)")

def _to_float(text: str) -> float:
    if re.fullmatch(r"-?\d+,\d{1,2}", text):
        return float(text.replace(",", "."))  # decimal comma
    return float(text.replace(",", ""))

def normalize_numeric(val: str) -> Optional[float]:
    match = _NUMERIC.search(normalize_text(val))
    if not match:
        return None
    num = _to_float(match.group(0))
    return num if math.isfinite(num) else None

# A value typed by a reviewer: one number, optionally after < > <= >= (no other digits or letters)
_WHOLE_NUMBER = re.compile(rf"\s*(?:<=?|>=?|\u2264|\u2265)?\s*{_NUMERIC.pattern}\s*")

def is_whole_number(val: Optional[str]) -> bool:
    """True when the whole value is a number, so "14.2.5" or "92abc7" is not read as 14.2 or 92."""
    return bool(_WHOLE_NUMBER.fullmatch(val or ""))

def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    u = unit.strip().lower().replace(" ", "")
    u = u.replace("µ", "u").replace("μ", "u").replace("×", "x").replace("*", "^")
    u = u.replace("cumm", "mm3").replace("mm^3", "mm3")
    return u or None

def validate_date(val: str, today: Optional[date] = None, order: Optional[str] = None) -> Tuple[str, Optional[str]]:
    parsed = parse_date(val, order)
    if not parsed:
        return "INVALID_FORMAT", None
    today = today or datetime.now(timezone.utc).date()
    if parsed > today:
        return "IMPLAUSIBLE_VALUE", parsed.strftime("%Y-%m-%d")
    return "VALID", parsed.strftime("%Y-%m-%d")

def _format_number(num: float) -> str:
    num = round(num, 3)
    return str(int(num)) if float(num).is_integer() else str(num)

_RANGE_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_RANGE_PAIR = re.compile(rf"(-?{_RANGE_NUMBER})\s*(?:-|\u2013|to)\s*(-?{_RANGE_NUMBER})", re.IGNORECASE)
_RANGE_BOUND = re.compile(rf"(<=?|>=?|\u2264|\u2265)\s*({_RANGE_NUMBER})")

def parse_printed_range(text: Optional[str]) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """(lower, upper) from a printed range such as "70 - 100", "<200" or ">= 60"; None if unreadable."""
    if not text:
        return None
    pair = _RANGE_PAIR.search(text)
    if pair:
        lower, upper = (_to_float(n) for n in pair.groups())
        return (lower, upper) if lower <= upper else None
    bound = _RANGE_BOUND.search(text)
    if bound:
        op, number = bound.groups()
        limit = _to_float(number)
        return (None, limit) if op in ("<", "<=", "\u2264") else (limit, None)
    return None

# Analytes whose common units differ by a factor that still gives a plausible-looking number
# (glucose 5.5 mmol/L vs mg/dL; hemoglobin 8.9 mmol/L vs g/dL): without a unit the value
# cannot be read safely.
UNIT_REQUIRED = {"glucose", "hemoglobin"}

# Values beyond this multiple of the range's upper limit (or below its lower limit divided by
# it) are treated as a likely misread rather than a plain abnormal result.
FAR_OUTSIDE_FACTOR = 4.0
# Cell counts lose their decimal point easily ("3.2" read as "32"), and a low count read tenfold
# lands only a few times above the range, so they are held to a tighter factor.
FAR_OUTSIDE_FACTORS = {"white_blood_cell_count": 2.5, "platelet_count": 2.5}

def normalize_flag(flag: Optional[str]) -> Optional[str]:
    """"H"/"L" for a printed high/low flag (HH/LL/High/Low included), else None."""
    f = (flag or "").strip().upper()
    if f in ("H", "HH", "HIGH"):
        return "H"
    if f in ("L", "LL", "LOW"):
        return "L"
    return None

def validate_numeric_and_range(
    field_name: str, val: str, unit: Optional[str] = None, sex: Optional[str] = None, age: Optional[int] = None,
    printed_range: Optional[str] = None, printed_flag: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[Dict]]:
    """
    Normalizes the value to the analyte's canonical unit and checks it against a reference range:
    the report's own printed range when there is one (it already fits the patient and the lab's
    method), otherwise the built-in adult range. A printed H/L flag also marks the value abnormal.
    """
    num = normalize_numeric(val)
    if num is None:
        return "INVALID_FORMAT", None, None

    expected_unit = canonical_unit(field_name)
    meta: Dict = {}
    conversions = UNIT_CONVERSIONS.get(field_name, {})
    norm_unit = normalize_unit(unit)
    # Multiplier taking the printed value (and its printed range, same row) to the canonical unit
    scale = 1.0

    if norm_unit:
        factor = conversions.get(norm_unit)
        if factor is None:
            # We cannot compare against the reference range without knowing the scale.
            meta = {"value": num, "unit": unit, "expected_unit": expected_unit}
            return "UNRECOGNIZED_UNIT", _format_number(num), meta
        if factor != 1.0:
            meta["original_value"] = num
            meta["original_unit"] = unit
            num = num * factor
            scale = factor
    elif field_name in UNIT_REQUIRED:
        return "UNRECOGNIZED_UNIT", _format_number(num), {"value": num, "unit": None, "expected_unit": expected_unit}
    elif field_name in COUNT_FIELDS and num >= RAW_COUNT_THRESHOLD:
        meta["original_value"] = num
        meta["assumed_unit"] = "cells/uL"
        num = num / 1000.0
        scale = 0.001

    norm_str = _format_number(num)

    if expected_unit:
        meta["canonical_unit"] = expected_unit
        limits = PLAUSIBLE_LIMITS.get(field_name)
        if limits and not (limits[0] <= num <= limits[1]):
            meta.update({"value": round(num, 3), "plausible_lower": limits[0], "plausible_upper": limits[1]})
            return "EXTREME_VALUE", norm_str, meta
        printed = parse_printed_range(printed_range)
        if printed:
            lower, upper = (None if b is None else round(b * scale, 3) for b in printed)
            basis = "report"
            meta["printed_range"] = printed_range
            # Which side of the printed range the value falls on; checked against the report's
            # own H/L flags by the validation engine.
            meta["printed_direction"] = "H" if upper is not None and num > upper else "L" if lower is not None and num < lower else None
        else:
            ref = get_reference_range(field_name, sex, age)
            if ref is None:
                meta["reason"] = f"no adult reference range applies (age {age})"
                return "NO_REFERENCE_RANGE", norm_str, meta
            lower, upper, basis = ref
        meta["range_basis"] = basis
        # Which side of the range the value falls on; checked against a printed H/L flag
        meta["direction"] = "H" if upper is not None and num > upper else "L" if lower is not None and num < lower else None

        outside = (lower is not None and num < lower) or (upper is not None and num > upper)
        factor = FAR_OUTSIDE_FACTORS.get(field_name, FAR_OUTSIDE_FACTOR)
        if (upper and num > factor * upper) or (lower and num < lower / factor):
            # A misplaced decimal point moves a value tenfold; a human should look at this one.
            meta.update({"value": round(num, 3), "lower": lower, "upper": upper, "reason": "far_outside_range"})
            return "EXTREME_VALUE", norm_str, meta
        flag = normalize_flag(printed_flag)
        if flag:
            meta["printed_flag"] = flag
        if outside or flag:
            meta.update({"value": round(num, 3), "lower": lower, "upper": upper})
            return "OUTSIDE_REFERENCE_RANGE", norm_str, meta

    return "VALID", norm_str, (meta or None)

# Printed when the sex is not known; the field is optional, so these mean "not given"
UNKNOWN_SEX = {"u", "unknown", "unk", "other", "o", "x", "not specified", "not stated", "undisclosed", "n/a", "na"}

def normalize_sex(val: Optional[str]) -> Optional[str]:
    v = normalize_text(val or "").lower()
    if v in ("m", "male", "man"):
        return "M"
    if v in ("f", "female", "woman"):
        return "F"
    return None

def age_in_years(dob: Optional[str], on: Optional[str] = None, order: Optional[str] = None) -> Optional[int]:
    """Age in whole years on the given ISO date (default: today); None if unknown."""
    birth = parse_date(dob, order) if dob else None
    if not birth:
        return None
    ref = parse_date(on) if on else None
    ref = ref or datetime.now(timezone.utc).date()
    years = ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))
    return years if years >= 0 else None

_NON_ALNUM = re.compile(r"[^0-9a-z]+")

def _squash(text: str) -> str:
    return _NON_ALNUM.sub("", (text or "").lower())

def check_date_consistency(dates: Dict[str, Optional[str]]) -> Dict[str, str]:
    """
    Cross-field plausibility: date_of_birth <= collection_date <= received_date.
    Takes normalized ISO dates keyed by field name; returns {field_name: message} for offenders.
    """
    problems: Dict[str, str] = {}
    dob = dates.get("date_of_birth")
    collected = dates.get("collection_date")
    received = dates.get("received_date")
    if dob and collected and collected < dob:
        problems["collection_date"] = "Collection date is before date of birth"
    if dob and received and received < dob:
        problems["received_date"] = "Received date is before date of birth"
    if collected and received and received < collected:
        problems["received_date"] = "Received date is before collection date"
    return problems

def name_looks_misread(name: Optional[str]) -> bool:
    """
    OCR tells: a digit in a name ("J0hn"), or a word starting lowercase in an otherwise
    capitalized name ("Neil lyer" for "Neil Iyer", the classic I/l confusion).
    """
    words = [w for w in re.split(r"[\s,]+", name or "") if w]
    if any(ch.isdigit() for w in words for ch in w):
        return True
    starts = [w[0] for w in words if w[0].isalpha()]
    return any(c.islower() for c in starts) and any(c.isupper() for c in starts)

# Words that label each lab result on a report (compared without case or punctuation)
RESULT_LABELS = {
    "glucose": {"glucose", "glu"},
    "hemoglobin": {"hemoglobin", "haemoglobin", "hgb", "hb"},
    "hematocrit": {"hematocrit", "haematocrit", "hct"},
    "white_blood_cell_count": {"white", "wbc", "leukocyte", "leukocytes", "leucocytes"},
    "platelet_count": {"platelet", "platelets", "plt"},
}
# A result must be within this many words after its label
LABEL_WINDOW = 12

def validate_source_agreement(extracted: str, source_text: str, field_name: Optional[str] = None) -> bool:
    """
    True when the extracted value is printed on the page: as whole words (so "90" does not match
    inside "1990"), ignoring case and punctuation ("250,000" matches "250000", "O'Brien" matches
    "OBRIEN"). Lab results must also follow their own label (e.g. "Hgb") within a few words, so a
    number that merely appears somewhere else on the page does not count. Used to catch values
    an AI extractor produced that are not actually on the page.
    """
    value = _squash(extracted)
    if not value:
        return True
    labels = RESULT_LABELS.get(field_name or "")
    if labels:
        return _number_follows_label(extracted, (source_text or "").split(), labels)
    tokens = [_squash(t) for t in (source_text or "").split()]
    tokens = [t for t in tokens if t]

    for start in range(len(tokens)):
        joined = ""
        for end in range(start, len(tokens)):
            joined += tokens[end]
            glued_unit = value.isdigit() and end == start and joined.startswith(value) and _unit_suffix(joined[len(value):])
            if joined == value or glued_unit:
                return True
            if not value.startswith(joined):
                break
    return False

def _number_follows_label(extracted: str, words: list, labels: set) -> bool:
    """
    A lab result is on the page when the same number (not merely the same digits: "99" is not
    "9.9") is printed within a few words after its label, alone or glued to its unit or flag.
    """
    wanted = normalize_numeric(extracted)
    if wanted is None:
        return False
    for i, word in enumerate(words):
        match = _NUMERIC.match(word.lstrip("(["))
        if not match or match.group(0).startswith("-"):
            continue
        rest = word.lstrip("([")[match.end():]
        if rest and (rest[0].isdigit() or rest[:1] in ".," and rest[1:2].isdigit()):
            continue  # part of a longer number or a date
        if _to_float(match.group(0)) == wanted and any(_squash(w) in labels for w in words[max(0, i - LABEL_WINDOW):i]):
            return True
    return False

def _unit_suffix(rest: str) -> bool:
    """A value printed glued to its unit or flag, e.g. "92mg/dL" or "182H"."""
    return bool(re.fullmatch(r"[a-z%]+[a-z0-9]*", rest))
