import re
from typing import Dict, Any, List, Optional
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, ExtractedFieldData

# Horizontal whitespace. The page text keeps its line breaks, and a value must be on the same
# line as its label, so a blank field never takes the next line's label or value.
_S = r"[^\S\n]"
# Field labels used as look-ahead terminators for free-text values such as the patient name.
_LABELS = (
    r"DOB|D\.O\.B\.?|Date\s*of\s*Birth|Birth\s*Date|Patient|MRN|Medical|Sex|Gender|Age|Glucose|"
    r"Hemoglobin|Haemoglobin|Hgb|Hematocrit|Haematocrit|Hct|White|WBC|Platelets?|PLT|Specimen|Sample|"
    r"Collect(?:ion|ed)|Received|Accession|Ordering|Physician|Doctor|Report"
)
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
# ISO, numeric day/month, dotted, and month-name dates (14-Mar-1985, 14 March 1985, Mar 14, 1985)
_DATE = (
    rf"\d{{1,2}}(?:-|{_S}){_MONTH}(?:-|{_S})\d{{4}}|{_MONTH}{_S}+\d{{1,2}},?{_S}+\d{{4}}|"
    r"\d{4}-\d{1,2}-\d{1,2}|\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4}|\d{1,2}\.\d{1,2}\.\d{4}"
)
_COUNT_UNIT = rf"(?:x{_S}*)?10\^?[39]{_S}*/{_S}*[uµμ]?L|K/[uµμ]L|thou/[uµμ]L|cells/[uµμ]L|/[uµμ]L|/mm3"
# Thousands separators ("250,000") or a decimal point or comma ("14.8", "14,8")
_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?"
# Abnormal flag printed next to a result (H, L, HH, LL, High, Low). Not followed by a letter or
# "/", so the "L" of a unit such as "L/L" or the start of the next label is never taken as a flag.
_FLAG = r"(?:HH|LL|HIGH|LOW|H|L)(?![\w/])"
# The report's own reference range: "70 - 100", "13.5-17.5", "(4.5 to 11.0)", "<200", ">= 60"
_RANGE = rf"(?:{_NUMBER}){_S}*(?:-|–|to){_S}*(?:{_NUMBER})|(?:<=?|>=?|≤|≥){_S}*(?:{_NUMBER})"
# Any other unit printed with a glucose or hemoglobin result ("gm/dL", OCR's "mmol/1"). Captured
# so that an unknown unit is reported for review instead of the value being read in the
# canonical unit; their units differ by factors that still give plausible-looking numbers.
# (Counts and hematocrit are not: a wrong scale there is caught as an implausible value, and
# OCR often garbles their superscript units, e.g. "x10³/uL" read as "x1043/uL".)
_OTHER_UNIT = rf"[A-Za-zµμ][A-Za-z0-9µμ^.]*{_S}*/{_S}*[A-Za-z0-9µμ^.]+"

def _result(unit_pattern: str, other_units: bool = False) -> str:
    """Value, then optional flag, unit, flag, printed reference range and unit, in table-row order."""
    units = rf"(?:{unit_pattern})(?![\w/])" + (f"|{_OTHER_UNIT}" if other_units else "")
    return (
        rf"(?P<value>{_NUMBER})(?![\d.,]?\d)"
        # A number that starts a range ("13.5 - 17.5" with the result cell empty) is not the result
        rf"(?!{_S}*(?:-|–|to){_S}*\d)"
        rf"(?:{_S}*(?P<flag>{_FLAG}))?(?:{_S}*(?P<unit>{units}))?"
        rf"(?:{_S}*(?P<flag2>{_FLAG}))?(?:{_S}*\(?{_S}*(?P<ref>{_RANGE}){_S}*\)?)?"
        rf"(?:{_S}*(?P<unit2>{units}))?"
    )

# A "... Name:" that belongs to someone or something other than the patient
_NOT_PATIENT = {
    "physician", "doctor", "dr", "dr.", "provider", "ordering", "referring", "referred", "consultant",
    "attending", "lab", "laboratory", "facility", "hospital", "clinic", "test", "collector", "guardian",
    "father", "mother", "father's", "mother's", "parent", "insurance", "employer", "company", "contact",
    "kin", "technician", "tech", "verified", "reported", "approved", "signed", "user", "account",
    "practice", "client", "sample", "specimen", "site", "location", "department", "ward", "panel", "report",
}

class RuleBasedExtractor(BaseExtractor):
    def __init__(self):
        # A deterministic rule engine. Labels accept common synonyms/abbreviations so several
        # lab report layouts work. Each rule captures the value in group "value" and,
        # optionally, the unit in group "unit".
        self.rules = [
            {"field_name": "patient_name", "not_after": _NOT_PATIENT,
             "pattern": rf"(?im)(?:\bpatient{_S}*name{_S}*:?|\b(?:patient|name){_S}*:){_S}*(?P<value>[A-Za-z][A-Za-z'\-\.,]*(?:{_S}+[A-Za-z][A-Za-z'\-\.,]*)*?),?(?={_S}+(?:{_LABELS})\b|{_S}*$)"},
            {"field_name": "date_of_birth", "pattern": rf"(?i)(?:\bdob\b|d\.o\.b\.?|date{_S}*of{_S}*birth|birth{_S}*date):?{_S}*(?P<value>{_DATE})"},
            # An ID contains a digit, so a label word ("Patient ID Number") is never taken as the ID
            {"field_name": "patient_id", "pattern": rf"(?i)(?:\bpatient{_S}*id(?:entifier)?\b|\bmrn\b|\bmedical{_S}*record\b|\bpt\.?{_S}*id\b)(?:{_S}*(?:number|no\.?|#))?{_S}*:?{_S}*#?{_S}*(?P<value>(?=[A-Za-z\-]*\d)[A-Za-z0-9][A-Za-z0-9\-]*)"},
            {"field_name": "patient_sex", "pattern": rf"(?i)\b(?:sex|gender){_S}*:?{_S}*(?P<value>male|female|m|f)\b"},
            {"field_name": "specimen_type", "pattern": rf"(?i)(?:specimen|sample)(?:{_S}*type)?{_S}*:?{_S}*(?P<value>whole{_S}+blood|blood|urine|saliva|serum|plasma)\b"},
            {"field_name": "collection_date", "pattern": rf"(?i)(?:collection{_S}*date|date{_S}*collected|collected(?:{_S}*on)?|draw{_S}*date){_S}*:?{_S}*(?P<value>{_DATE})"},
            {"field_name": "received_date", "pattern": rf"(?i)(?:received{_S}*date|date{_S}*received|received(?:{_S}*on)?){_S}*:?{_S}*(?P<value>{_DATE})"},
            # Not "Estimated Average Glucose" (eAG)
            {"field_name": "glucose", "pattern": rf"(?i)(?<!average[^\S\n])\b(?:glucose|glu)(?:,?{_S}*(?:fasting|random|serum|plasma))?{_S}*:?{_S}*{_result(rf'mg{_S}*/{_S}*dL|mmol{_S}*/{_S}*L', other_units=True)}"},
            # Not MCH/MCHC ("Mean Cell/Corpuscular Hemoglobin") or HbA1c ("Glycated Hemoglobin", "Hemoglobin A1c")
            {"field_name": "hemoglobin", "pattern": rf"(?i)(?<!cell[^\S\n])(?<!corpuscular[^\S\n])(?<!glycated[^\S\n])(?<!glycosylated[^\S\n])\b(?:hemoglobin|haemoglobin|hgb|hb)\b(?!{_S}*a1c){_S}*:?{_S}*{_result(rf'g{_S}*/{_S}*dL|g{_S}*/{_S}*L|mmol{_S}*/{_S}*L', other_units=True)}"},
            {"field_name": "hematocrit", "pattern": rf"(?i)\b(?:hematocrit|haematocrit|hct)\b{_S}*:?{_S}*{_result(rf'%|L{_S}*/{_S}*L')}"},
            {"field_name": "white_blood_cell_count", "pattern": rf"(?i)\b(?:white{_S}*blood{_S}*cell(?:s|{_S}*count)?|wbc(?:{_S}*count)?|leukocytes?)\b{_S}*:?{_S}*{_result(_COUNT_UNIT)}"},
            {"field_name": "platelet_count", "pattern": rf"(?i)\b(?:platelets?(?:{_S}*count)?|plt)\b{_S}*:?{_S}*{_result(_COUNT_UNIT)}"},
        ]

    def extract(self, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> ExtractionResult:
        extracted_fields = []
        found = set()

        # Iterate over pages; the first page on which a field is found wins, so a
        # repeated header on later pages does not create duplicate fields.
        for page in document_data.get("pages", []):
            page_num = page.get("page_number")
            words = page.get("words", [])
            if not words:
                continue

            # Page text with its line breaks, keeping track of word offsets to map back to bboxes
            parts = []
            word_indices = []
            offset = 0
            for line in self._lines(words):
                for position, i in enumerate(line):
                    w_text = words[i].get("text", "")
                    parts.append(w_text + ("\n" if position == len(line) - 1 else " "))
                    word_indices.append((offset, offset + len(w_text), i))
                    offset += len(w_text) + 1  # +1 for the space or line break
            full_text = "".join(parts)

            for rule in self.rules:
                if rule["field_name"] in found:
                    continue
                match = next((m for m in re.finditer(rule["pattern"], full_text)
                              if not self._follows(full_text, m.start(), rule.get("not_after"))), None)
                if not match:
                    continue

                val = match.group("value").strip()
                if not val:
                    continue
                groups = match.groupdict()
                unit = groups.get("unit")
                flag = groups.get("flag") or groups.get("flag2")
                ref = groups.get("ref")

                # Highlight the value and its unit together
                m_start = match.start("value")
                m_end = match.end("unit") if unit else match.end("value")
                unit = unit or groups.get("unit2")

                matched_words = [
                    words[word_idx]
                    for start_idx, end_idx, word_idx in word_indices
                    if start_idx < m_end and end_idx > m_start
                ]

                extracted_fields.append(ExtractedFieldData(
                    field_name=rule["field_name"],
                    value=val,
                    unit=unit.strip() if unit else None,
                    reference_range=ref.strip() if ref else None,
                    abnormal_flag=flag.upper() if flag else None,
                    confidence=self._compute_avg_confidence(matched_words),
                    page_num=page_num,
                    bbox_normalized=self._compute_union_bbox(matched_words)
                ))
                found.add(rule["field_name"])

        return ExtractionResult(
            extractor_type="rule_based",
            model_version="rule-based-v1.3",
            provider="deterministic",
            prompt_version="1.0",
            fields=extracted_fields
        )

    @staticmethod
    def _lines(words: List[Dict[str, Any]]) -> List[List[int]]:
        """
        Groups a page's words into visual lines, top to bottom and left to right within a line,
        as indexes into `words`. OCR'd words carry their line number (their boxes may be on a
        skewed scan); other words are grouped by position. Without boxes they stay one line.
        """
        if all("line" in w for w in words):
            lines = {}
            for i, w in enumerate(words):
                lines.setdefault(w["line"], []).append(i)
            return [lines[n] for n in sorted(lines)]
        if not all(len(w.get("bbox") or []) == 4 for w in words):
            return [list(range(len(words)))]
        rows = []  # [center_y, height, indexes]
        for i in sorted(range(len(words)), key=lambda i: words[i]["bbox"][1] + words[i]["bbox"][3] / 2):
            _, y, _, h = words[i]["bbox"]
            center = y + h / 2
            if rows and abs(center - rows[-1][0]) <= max(rows[-1][1], h) * 0.5:
                rows[-1][2].append(i)
            else:
                rows.append([center, h, [i]])
        return [sorted(indexes, key=lambda i: words[i]["bbox"][0]) for _, _, indexes in rows]

    @staticmethod
    def _follows(text: str, position: int, words: Optional[set]) -> bool:
        """True when the word just before `position` on the same line is one of `words`."""
        if not words:
            return False
        before = text[:position].rsplit("\n", 1)[-1].split()
        return bool(before) and before[-1].lower().rstrip(":") in words

    def _compute_union_bbox(self, words: List[Dict[str, Any]]) -> Optional[List[float]]:
        boxes = [w["bbox"] for w in words if w.get("bbox") and len(w["bbox"]) == 4]
        if not boxes:
            return None

        min_x = min(b[0] for b in boxes)
        min_y = min(b[1] for b in boxes)
        max_x = max(b[0] + b[2] for b in boxes)
        max_y = max(b[1] + b[3] for b in boxes)

        return [min_x, min_y, min(max_x, 1.0) - min_x, min(max_y, 1.0) - min_y]

    def _compute_avg_confidence(self, words: List[Dict[str, Any]]) -> float:
        confs = [w.get("confidence") for w in words if w.get("confidence") is not None]
        if not confs:
            return 100.0
        return sum(confs) / len(confs)
