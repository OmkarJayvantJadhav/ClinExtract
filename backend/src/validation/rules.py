import re
from datetime import datetime, date, timezone
from typing import Dict, Tuple, Optional
from src.validation.reference_ranges import (
    UNIT_CONVERSIONS, RAW_COUNT_THRESHOLD, PLAUSIBLE_LIMITS, canonical_unit, get_reference_range,
)

COUNT_FIELDS = {"white_blood_cell_count", "platelet_count"}

def normalize_text(val: str) -> str:
    if not val:
        return ""
    # Trim and normalize whitespace
    return re.sub(r'\s+', ' ', val.strip())

def parse_date(val: str) -> Optional[date]:
    val = normalize_text(val)
    # ISO first, then US MM/DD/YYYY, then DD/MM/YYYY (only reachable when the day is > 12,
    # i.e. the value cannot be a valid US date).
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None

def normalize_date(val: str) -> Optional[str]:
    parsed = parse_date(val)
    return parsed.strftime("%Y-%m-%d") if parsed else None

def normalize_numeric(val: str) -> Optional[float]:
    val = normalize_text(val)
    # Accept thousands separators ("250,000") as well as plain decimals ("13.2").
    match = re.search(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?', val)
    if match:
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None
    return None

def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    u = unit.strip().lower().replace(" ", "")
    u = u.replace("µ", "u").replace("μ", "u").replace("×", "x").replace("*", "^")
    u = u.replace("cumm", "mm3").replace("mm^3", "mm3")
    return u or None

def validate_date(val: str, today: Optional[date] = None) -> Tuple[str, Optional[str]]:
    parsed = parse_date(val)
    if not parsed:
        return "INVALID_FORMAT", None
    today = today or datetime.now(timezone.utc).date()
    if parsed > today:
        return "IMPLAUSIBLE_VALUE", parsed.strftime("%Y-%m-%d")
    return "VALID", parsed.strftime("%Y-%m-%d")

def _format_number(num: float) -> str:
    num = round(num, 3)
    return str(int(num)) if float(num).is_integer() else str(num)

_RANGE_PAIR = re.compile(r"(-?[\d,]*\.?\d+)\s*(?:-|\u2013|to)\s*(-?[\d,]*\.?\d+)", re.IGNORECASE)
_RANGE_BOUND = re.compile(r"(<=?|>=?|\u2264|\u2265)\s*([\d,]*\.?\d+)")

def parse_printed_range(text: Optional[str]) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """(lower, upper) from a printed range such as "70 - 100", "<200" or ">= 60"; None if unreadable."""
    if not text:
        return None
    pair = _RANGE_PAIR.search(text)
    if pair:
        lower, upper = (float(n.replace(",", "")) for n in pair.groups())
        return (lower, upper) if lower <= upper else None
    bound = _RANGE_BOUND.search(text)
    if bound:
        op, number = bound.groups()
        limit = float(number.replace(",", ""))
        return (None, limit) if op in ("<", "<=", "\u2264") else (limit, None)
    return None

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
        else:
            ref = get_reference_range(field_name, sex, age)
            if ref is None:
                meta["reason"] = f"no adult reference range applies (age {age})"
                return "NO_REFERENCE_RANGE", norm_str, meta
            lower, upper, basis = ref
        meta["range_basis"] = basis

        outside = (lower is not None and num < lower) or (upper is not None and num > upper)
        flag = normalize_flag(printed_flag)
        if flag:
            meta["printed_flag"] = flag
        if outside or flag:
            meta.update({"value": round(num, 3), "lower": lower, "upper": upper})
            return "OUTSIDE_REFERENCE_RANGE", norm_str, meta

    return "VALID", norm_str, (meta or None)

def normalize_sex(val: Optional[str]) -> Optional[str]:
    v = normalize_text(val or "").lower()
    if v in ("m", "male", "man"):
        return "M"
    if v in ("f", "female", "woman"):
        return "F"
    return None

def age_in_years(dob: Optional[str], on: Optional[str] = None) -> Optional[int]:
    """Age in whole years on the given ISO date (default: today); None if unknown."""
    birth = parse_date(dob) if dob else None
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

def validate_source_agreement(extracted: str, source_text: str) -> bool:
    """
    True when the extracted value appears in the source text, ignoring case, whitespace and
    punctuation (so "250,000" matches "250000" and "O'Brien" matches "OBrien"). Used to catch
    values an AI extractor produced that are not actually printed on the page.
    """
    value = _squash(extracted)
    if not value:
        return True
    return value in _squash(source_text)
