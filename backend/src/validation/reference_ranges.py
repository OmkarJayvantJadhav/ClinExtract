from typing import Optional, Tuple

# Adult reference ranges in each analyte's canonical unit, by sex ("M"/"F"), with an "any"
# fallback (the union of the sex-specific ranges) when sex is unknown.
# Pediatric ranges vary strongly with age, so for patients under ADULT_AGE no range is
# applied and the value is routed to human review instead.
ADULT_AGE = 18

REFERENCE_RANGES = {
    "glucose": {"unit": "mg/dL", "ranges": {"any": (70.0, 100.0)}},
    "hemoglobin": {"unit": "g/dL", "ranges": {"M": (13.5, 17.5), "F": (12.0, 15.5), "any": (12.0, 17.5)}},
    "hematocrit": {"unit": "%", "ranges": {"M": (41.0, 50.0), "F": (36.0, 44.0), "any": (36.0, 50.0)}},
    "white_blood_cell_count": {"unit": "x10^3/uL", "ranges": {"any": (4.5, 11.0)}},
    "platelet_count": {"unit": "x10^3/uL", "ranges": {"any": (150.0, 450.0)}},
}

def canonical_unit(field_name: str) -> Optional[str]:
    ref = REFERENCE_RANGES.get(field_name)
    return ref["unit"] if ref else None

def get_reference_range(field_name: str, sex: Optional[str] = None, age: Optional[int] = None) -> Optional[Tuple[float, float, str]]:
    """
    Returns (lower, upper, basis) for the patient, or None when no applicable range exists
    (unknown analyte, or a pediatric patient).
    """
    ref = REFERENCE_RANGES.get(field_name)
    if not ref:
        return None
    if age is not None and age < ADULT_AGE:
        return None
    ranges = ref["ranges"]
    if sex in ("M", "F") and sex in ranges:
        lower, upper = ranges[sex]
        return lower, upper, f"adult {'male' if sex == 'M' else 'female'}"
    lower, upper = ranges["any"]
    basis = "adult" if len(ranges) == 1 else "adult (sex unknown)"
    return lower, upper, basis

_COUNT_UNITS = {
    "x10^3/ul": 1.0, "10^3/ul": 1.0, "k/ul": 1.0, "thou/ul": 1.0,
    "x10^9/l": 1.0, "10^9/l": 1.0,
    "/ul": 0.001, "cells/ul": 0.001, "/mm3": 0.001, "cells/mm3": 0.001,
}

# Multipliers that convert a value in the given (normalized) unit into the canonical unit.
UNIT_CONVERSIONS = {
    "glucose": {"mg/dl": 1.0, "mmol/l": 18.016},
    "hemoglobin": {"g/dl": 1.0, "g/l": 0.1, "mmol/l": 1.611},
    "hematocrit": {"%": 1.0, "l/l": 100.0},
    "white_blood_cell_count": _COUNT_UNITS,
    "platelet_count": _COUNT_UNITS,
}

# Count analytes reported without a unit are usually x10^3/uL; values this large are
# almost certainly raw cells/uL and are scaled down.
RAW_COUNT_THRESHOLD = 1000.0
