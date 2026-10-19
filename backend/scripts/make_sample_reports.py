"""
Generate synthetic lab reports for demos and manual testing.

    python scripts/make_sample_reports.py [output_dir]   # default: ../frontend/public/samples

Every name, ID and value is made up. Each sample shows one behaviour of the pipeline; the
expected outcome is in SAMPLES and is checked by tests/test_sample_reports.py.
"""
import os
import sys

import cv2
import pymupdf
import numpy as np

LAB_NAME = "Northfield Diagnostics (fictional)"
FOOTER = "SYNTHETIC SAMPLE - not a real patient. Generated for ClinExtract demos."

NORMAL = {
    "name": "Rohan Kulkarni", "patient_id": "MRN-204817", "dob": "1985-03-14", "sex": "Male",
    "specimen": "Blood", "collected": "2026-09-29", "received": "2026-09-30",
    "results": [
        ("Glucose, Fasting", "92", "mg/dL", "70 - 100"),
        ("Hemoglobin", "14.8", "g/dL", "13.5 - 17.5"),
        ("Hematocrit", "44.1", "%", "41 - 50"),
        ("White Blood Cell Count", "7.2", "x10^3/uL", "4.5 - 11.0"),
        ("Platelet Count", "265", "x10^3/uL", "150 - 450"),
    ],
}

# Labs print sex-specific ranges for these tests
FEMALE_RANGES = {"Hemoglobin": "12.0 - 15.5", "Hematocrit": "36 - 44"}

def _with(base: dict, **changes) -> dict:
    report = {**base, **{k: v for k, v in changes.items() if k != "results"}}
    overrides = changes.get("results", {})
    female = report["sex"] == "Female"
    report["results"] = [
        (t, overrides.get(t, v), u, FEMALE_RANGES.get(t, r) if female else r) for t, v, u, r in base["results"]
    ]
    return report

def _flag(value: str, ref: str) -> str:
    """H or L, as a lab prints it, when the value lies outside the printed range."""
    try:
        lower, upper = (float(x) for x in ref.split(" - "))
        number = float(value)
    except ValueError:
        return ""
    return "H" if number > upper else "L" if number < lower else ""

def _draw_report(page: pymupdf.Page, report: dict, results_as_image: bool = False) -> None:
    y = 60
    page.insert_text((50, y), LAB_NAME, fontsize=16)
    page.insert_text((50, y + 20), "Laboratory Report - Complete Blood Count and Glucose", fontsize=11)
    page.draw_line((50, y + 32), (560, y + 32))

    y = 125
    lines = [
        f"Patient Name: {report['name']}",
        f"Patient ID: {report['patient_id']}" if report.get("patient_id") else None,
        f"DOB: {report['dob']}    Sex: {report['sex']}",
        f"Specimen Type: {report['specimen']}",
        f"Collection Date: {report['collected']}    Received Date: {report['received']}",
    ]
    for line in filter(None, lines):
        page.insert_text((50, y), line, fontsize=11)
        y += 18

    y += 20
    if results_as_image:
        # Results pasted in as a picture (no text layer), as when a scanned table is attached
        # under a typed header.
        picture = pymupdf.open()
        table_page = picture.new_page(width=510, height=150)
        _draw_results(table_page, report["results"], 25)
        picture_bytes = table_page.get_pixmap(dpi=200).tobytes("png")
        page.insert_image(pymupdf.Rect(50, y - 10, 560, y + 140), stream=picture_bytes)
    else:
        _draw_results(page, report["results"], y)

    page.insert_text((50, 780), FOOTER, fontsize=8)

def _draw_results(page: pymupdf.Page, results, y: float) -> None:
    columns = (0, 200, 255, 295, 385)
    for x, title in zip(columns, ("Test", "Result", "Flag", "Unit", "Reference Range")):
        page.insert_text((50 + x, y), title, fontsize=11)
    page.draw_line((50, y + 6), (560, y + 6))
    for test, value, unit, ref in results:
        y += 22
        for x, text in zip(columns, (test, value, _flag(value, ref), unit, ref)):
            if text:
                page.insert_text((50 + x, y), text, fontsize=11)

def _pdf(report: dict, results_as_image: bool = False) -> bytes:
    doc = pymupdf.open()
    _draw_report(doc.new_page(), report, results_as_image)
    return doc.write(deflate=True, garbage=3)

def _scanned_jpeg(report: dict) -> bytes:
    """Rendered page, slightly rotated and noisy, as a phone or flatbed scan would be."""
    doc = pymupdf.open(stream=_pdf(report), filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    rotation = cv2.getRotationMatrix2D((w / 2, h / 2), 1.2, 1.0)
    img = cv2.warpAffine(img, rotation, (w, h), borderValue=(245, 245, 240))
    noise = np.random.default_rng(7).normal(0, 4, img.shape)
    img = np.clip(img.astype(np.float64) * 0.96 + 8 + noise, 0, 255).astype(np.uint8)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()

# filename -> (builder, expected decision, what it demonstrates)
SAMPLES = {
    "01_normal_report.pdf": (
        lambda: _pdf(NORMAL), "AUTO_ACCEPTED",
        "Clean digital report: every field extracted and valid, accepted without review."),
    "02_abnormal_results.pdf": (
        lambda: _pdf(_with(NORMAL, name="Meera Iyer", patient_id="MRN-311902", dob="1972-11-02", sex="Female",
                           results={"Glucose, Fasting": "182", "Hemoglobin": "10.9", "Hematocrit": "33.0"})),
        "AUTO_ACCEPTED",
        "Abnormal results: flagged on the record but, by default, not held for review."),
    "03_scanned_report.jpg": (
        lambda: _scanned_jpeg(_with(NORMAL, name="Arjun Desai", patient_id="MRN-118734", dob="1990-07-21",
                                    results={"White Blood Cell Count": "6.8"})),
        None,  # depends on OCR confidence
        "Scanned image: deskewed and read with OCR."),
    "04_needs_correction.pdf": (
        lambda: _pdf(_with(NORMAL, name="Kavya Nair", patient_id=None, dob="1988-14-03", sex="Female",
                           results={"Hemoglobin": "13.2", "Hematocrit": "40.2"})),
        "REVIEW_REQUIRED",
        "Missing patient ID and an impossible birth date: a reviewer must correct both before approval."),
    "05_decimal_misread.pdf": (
        lambda: _pdf(_with(NORMAL, name="Vikram Joshi", patient_id="MRN-509266", results={"Hemoglobin": "1.48"})),
        "REVIEW_REQUIRED",
        "Hemoglobin 1.48 g/dL: far outside any plausible result (likely a misplaced decimal), so it goes to review."),
    "06_mixed_page.pdf": (
        lambda: _pdf(_with(NORMAL, name="Ananya Rao", patient_id="MRN-772051", dob="1979-05-30", sex="Female",
                           results={"Hemoglobin": "13.1", "Hematocrit": "39.5"}), results_as_image=True),
        None,  # results come from OCR, so confidence decides
        "Typed header with the results pasted in as an image: both parts are read."),
}

def main() -> None:
    default = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public", "samples")
    out_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else default)
    os.makedirs(out_dir, exist_ok=True)
    for filename, (build, _, description) in SAMPLES.items():
        with open(os.path.join(out_dir, filename), "wb") as f:
            f.write(build())
        print(f"{filename}: {description}")

if __name__ == "__main__":
    main()
