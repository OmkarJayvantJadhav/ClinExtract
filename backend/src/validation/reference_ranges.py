
# Adult reference ranges, expressed in each analyte's canonical unit.
# NOTE: these are not sex- or age-specific (no sex/age field is extracted yet), so
# OUTSIDE_REFERENCE_RANGE is a prompt for human review, never a reason to block approval.
REFERENCE_RANGES = {
    "glucose": {"min": 70.0, "max": 100.0, "unit": "mg/dL"},
    "hemoglobin": {"min": 12.0, "max": 17.5, "unit": "g/dL"},
    "hematocrit": {"min": 36.0, "max": 50.0, "unit": "%"},
    "white_blood_cell_count": {"min": 4.5, "max": 11.0, "unit": "x10^3/uL"},
    "platelet_count": {"min": 150.0, "max": 450.0, "unit": "x10^3/uL"}
}

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
