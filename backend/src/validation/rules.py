import re
from datetime import datetime, date, timezone
from typing import Dict, Tuple, Optional
from src.validation.reference_ranges import REFERENCE_RANGES, UNIT_CONVERSIONS, RAW_COUNT_THRESHOLD

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
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
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

def validate_numeric_and_range(field_name: str, val: str, unit: Optional[str] = None) -> Tuple[str, Optional[str], Optional[Dict]]:
    num = normalize_numeric(val)
    if num is None:
        return "INVALID_FORMAT", None, None

    ref = REFERENCE_RANGES.get(field_name)
    meta: Dict = {}
    conversions = UNIT_CONVERSIONS.get(field_name, {})
    norm_unit = normalize_unit(unit)

    if norm_unit:
        factor = conversions.get(norm_unit)
        if factor is None:
            # We cannot compare against the reference range without knowing the scale.
            meta = {"value": num, "unit": unit, "expected_unit": ref["unit"] if ref else None}
            return "UNRECOGNIZED_UNIT", _format_number(num), meta
        if factor != 1.0:
            meta["original_value"] = num
            meta["original_unit"] = unit
            num = num * factor
    elif field_name in COUNT_FIELDS and num >= RAW_COUNT_THRESHOLD:
        meta["original_value"] = num
        meta["assumed_unit"] = "cells/uL"
        num = num / 1000.0

    norm_str = _format_number(num)

    if ref:
        meta["canonical_unit"] = ref["unit"]
        if num < ref["min"] or num > ref["max"]:
            meta.update({"value": round(num, 3), "lower": ref["min"], "upper": ref["max"]})
            return "OUTSIDE_REFERENCE_RANGE", norm_str, meta

    return "VALID", norm_str, (meta or None)

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
    # Placeholder: source agreement is currently only exercised through the
    # `mock_mismatch` hook used by tests. A real implementation should compare the
    # extracted value with the OCR words under the field's bounding box.
    return True
