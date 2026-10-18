"""
Labeled synthetic lab reports for measuring extraction accuracy.

Each generated case has the document bytes and the ground truth: what every field should
normalize to. Layouts, label wording, date formats, units and media (digital PDF, scan, typed
header with a pasted results table) vary, seeded so a run is reproducible. Every name and
number is made up.
"""
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

import cv2
import fitz
import numpy as np

FIRST = ["Aarav", "Meera", "Rohan", "Ananya", "Vikram", "Kavya", "Arjun", "Isha", "Kabir", "Diya",
         "Neil", "Sara", "Dev", "Tara", "Omar", "Lena", "Ravi", "Nina", "Aditya", "Zoya"]
LAST = ["Mehta", "Iyer", "Kulkarni", "Rao", "Joshi", "Nair", "Desai", "Shah", "Kapoor", "Menon",
        "Bose", "Khan", "Singh", "Pillai", "Gupta", "Verma", "Reddy", "Das", "Patel", "Chopra"]

# (canonical lower, upper) per sex used to draw values and print reference ranges
RANGES = {
    "glucose": {"M": (70, 100), "F": (70, 100)},
    "hemoglobin": {"M": (13.5, 17.5), "F": (12.0, 15.5)},
    "hematocrit": {"M": (41, 50), "F": (36, 44)},
    "white_blood_cell_count": {"M": (4.5, 11.0), "F": (4.5, 11.0)},
    "platelet_count": {"M": (150, 450), "F": (150, 450)},
}

# Printed label variants per field (layout "abbrev" uses the last one)
LABELS = {
    "glucose": ["Glucose", "Glucose, Fasting", "GLU"],
    "hemoglobin": ["Hemoglobin", "Haemoglobin", "HGB"],
    "hematocrit": ["Hematocrit", "Haematocrit", "HCT"],
    "white_blood_cell_count": ["White Blood Cell Count", "WBC Count", "WBC"],
    "platelet_count": ["Platelet Count", "Platelets", "PLT"],
}

# unit -> multiplier from the canonical unit to the printed unit, and decimals to print
UNITS = {
    "glucose": [("mg/dL", 1.0, 0), ("mmol/L", 1 / 18.016, 1)],
    "hemoglobin": [("g/dL", 1.0, 1), ("g/L", 10.0, 0)],
    "hematocrit": [("%", 1.0, 1)],
    "white_blood_cell_count": [("x10^3/uL", 1.0, 1), ("K/uL", 1.0, 1), ("10^9/L", 1.0, 1)],
    "platelet_count": [("x10^3/uL", 1.0, 0), ("K/uL", 1.0, 0), ("10^9/L", 1.0, 0)],
}

DATE_FORMATS = [("%Y-%m-%d", "iso"), ("%m/%d/%Y", "us"), ("%d-%b-%Y", "month name")]
SPECIMENS = ["Blood", "Whole Blood", "Serum", "Plasma"]
LAYOUTS = ["table", "colon", "abbrev"]
MEDIA = ["pdf", "pdf", "pdf", "scan", "scan", "mixed"]


@dataclass
class Case:
    name: str
    data: bytes
    mime: str
    truth: Dict[str, Optional[str]]  # field -> expected normalized value
    traits: Dict[str, str] = field(default_factory=dict)  # layout, media, date format, ...


def _fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def _draw(page: fitz.Page, header: List[str], rows: List[List[str]], layout: str, results_as_image: bool) -> None:
    page.insert_text((50, 60), "Riverside Clinical Laboratory (fictional)", fontsize=15)
    page.insert_text((50, 80), "Hematology and Chemistry Report", fontsize=11)
    y = 120
    for line in header:
        page.insert_text((50, y), line, fontsize=11)
        y += 18
    y += 20
    target, ty = page, y
    if results_as_image:
        pic = fitz.open()
        target = pic.new_page(width=510, height=180)
        ty = 25
    if layout == "colon":
        for test, value, flag, unit, ref in rows:
            line = f"{test}: {value} {unit}" + (f" {flag}" if flag else "") + f" ({ref})"
            target.insert_text((50 if target is page else 10, ty), line, fontsize=11)
            ty += 20
    else:
        columns = (0, 190, 250, 290, 385)
        x0 = 50 if target is page else 10
        for x, title in zip(columns, ("Test", "Result", "Flag", "Units", "Ref. Range")):
            target.insert_text((x0 + x, ty), title, fontsize=11)
        for row in rows:
            ty += 22
            for x, text in zip(columns, row):
                if text:
                    target.insert_text((x0 + x, ty), text, fontsize=11)
    if results_as_image:
        png = target.get_pixmap(dpi=200).tobytes("png")
        page.insert_image(fitz.Rect(50, y - 15, 560, y + 165), stream=png)
    page.insert_text((50, 780), "SYNTHETIC TEST DOCUMENT - not a real patient", fontsize=8)


def _scan(pdf_bytes: bytes, rng: random.Random) -> bytes:
    pix = fitz.open(stream=pdf_bytes, filetype="pdf")[0].get_pixmap(dpi=rng.choice([200, 300]))
    img = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    img = cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-2, 2), 1.0), (w, h),
                         borderValue=(245, 245, 240))
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.choice([2, 4, 6]), img.shape)
    img = np.clip(img.astype(np.float64) * 0.96 + 8 + noise, 0, 255).astype(np.uint8)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.choice([75, 90])])[1].tobytes()


def make_case(index: int, seed: int = 0) -> Case:
    rng = random.Random(seed * 100003 + index)
    sex = rng.choice("MF")
    layout = LAYOUTS[index % len(LAYOUTS)]
    media = MEDIA[index % len(MEDIA)]
    date_fmt, date_kind = DATE_FORMATS[(index // 3) % len(DATE_FORMATS)]

    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    patient_id = f"MRN-{rng.randrange(100000, 999999)}"
    dob = date(1950, 1, 1) + timedelta(days=rng.randrange(0, 365 * 50))
    collected = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 270))
    received = collected + timedelta(days=rng.choice([0, 0, 1]))
    specimen = rng.choice(SPECIMENS)

    truth = {
        "patient_name": name, "patient_id": patient_id, "date_of_birth": dob.isoformat(),
        "collection_date": collected.isoformat(), "received_date": received.isoformat(),
        "specimen_type": specimen, "patient_sex": sex,
    }
    label_choice = 2 if layout == "abbrev" else rng.choice([0, 1])
    rows = []
    for fname, by_sex in RANGES.items():
        lower, upper = by_sex[sex]
        abnormal = rng.random() < 0.25
        span = upper - lower
        canonical = rng.uniform(upper + 0.05 * span, upper + 0.4 * span) if abnormal and rng.random() < 0.5 \
            else rng.uniform(lower - 0.3 * span, lower - 0.05 * span) if abnormal \
            else rng.uniform(lower + 0.05 * span, upper - 0.05 * span)
        unit, factor, decimals = rng.choice(UNITS[fname])
        printed = _fmt(canonical * factor, decimals)
        ref = f"{_fmt(lower * factor, decimals if decimals else 0)} - {_fmt(upper * factor, decimals if decimals else 0)}"
        flag = "H" if canonical > upper else "L" if canonical < lower else ""
        truth[fname] = str(round(float(printed) / factor, 3))
        rows.append([LABELS[fname][label_choice], printed, flag, unit, ref])

    dob_label, id_label, coll_label = rng.choice([
        ("DOB", "Patient ID", "Collection Date"), ("Date of Birth", "MRN", "Collected"),
    ])
    sex_text = {"M": rng.choice(["Male", "M"]), "F": rng.choice(["Female", "F"])}[sex]
    header = [
        f"Patient Name: {name}",
        f"{id_label}: {patient_id}",
        f"{dob_label}: {dob.strftime(date_fmt)}    Sex: {sex_text}",
        f"Specimen Type: {specimen}",
        f"{coll_label}: {collected.strftime(date_fmt)}    Received Date: {received.strftime(date_fmt)}",
    ]

    doc = fitz.open()
    _draw(doc.new_page(), header, rows, layout, results_as_image=(media == "mixed"))
    pdf = doc.write(deflate=True, garbage=3)
    data, mime = (_scan(pdf, rng), "image/jpeg") if media == "scan" else (pdf, "application/pdf")
    return Case(
        name=f"case_{index:03d}", data=data, mime=mime, truth=truth,
        traits={"layout": layout, "media": media, "dates": date_kind, "sex": sex},
    )


def make_cases(count: int, seed: int = 0) -> List[Case]:
    return [make_case(i, seed) for i in range(count)]
