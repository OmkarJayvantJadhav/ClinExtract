import re
from typing import Dict, Any, List, Optional
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, ExtractedFieldData

# Field labels used as look-ahead terminators for free-text values such as the patient name.
_LABELS = (
    r"DOB|D\.O\.B\.?|Date\s*of\s*Birth|Birth\s*Date|Patient|MRN|Medical|Sex|Gender|Age|Glucose|"
    r"Hemoglobin|Haemoglobin|Hgb|Hematocrit|Haematocrit|Hct|White|WBC|Platelets?|PLT|Specimen|Sample|"
    r"Collect(?:ion|ed)|Received|Accession|Ordering|Physician|Doctor|Report"
)
_DATE = r"\d{4}-\d{1,2}-\d{1,2}|\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4}|\d{1,2}\.\d{1,2}\.\d{4}"
_COUNT_UNIT = r"(?:x\s*)?10\^?[39]\s*/\s*[uµμ]?L|K/[uµμ]L|thou/[uµμ]L|cells/[uµμ]L|/[uµμ]L|/mm3"
_NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"

class RuleBasedExtractor(BaseExtractor):
    def __init__(self):
        # A deterministic rule engine. Labels accept common synonyms/abbreviations so several
        # lab report layouts work. Each rule captures the value in group "value" and,
        # optionally, the unit in group "unit".
        self.rules = [
            {"field_name": "patient_name", "pattern": rf"(?i)(?:patient\s*name\s*:?|\b(?:patient|name)\s*:)\s*(?P<value>[A-Za-z][A-Za-z'\-\.,]*(?:\s+[A-Za-z][A-Za-z'\-\.,]*)*?),?(?=\s+(?:{_LABELS})\b|\s*$)"},
            {"field_name": "date_of_birth", "pattern": rf"(?i)(?:\bdob\b|d\.o\.b\.?|date\s*of\s*birth|birth\s*date):?\s*(?P<value>{_DATE})"},
            {"field_name": "patient_id", "pattern": r"(?i)(?:patient\s*id|\bmrn\b|medical\s*record\s*(?:number|no\.?|#)|\bpt\.?\s*id)\s*:?\s*#?\s*(?P<value>[a-zA-Z0-9][a-zA-Z0-9\-]*)"},
            {"field_name": "patient_sex", "pattern": r"(?i)\b(?:sex|gender)\s*:?\s*(?P<value>male|female|m|f)\b"},
            {"field_name": "specimen_type", "pattern": r"(?i)(?:specimen|sample)(?:\s*type)?\s*:?\s*(?P<value>whole\s+blood|blood|urine|saliva|serum|plasma)\b"},
            {"field_name": "collection_date", "pattern": rf"(?i)(?:collection\s*date|date\s*collected|collected(?:\s*on)?|draw\s*date)\s*:?\s*(?P<value>{_DATE})"},
            {"field_name": "received_date", "pattern": rf"(?i)(?:received\s*date|date\s*received|received(?:\s*on)?)\s*:?\s*(?P<value>{_DATE})"},
            {"field_name": "glucose", "pattern": rf"(?i)\bglucose(?:,?\s*(?:fasting|random|serum|plasma))?\s*:?\s*(?P<value>{_NUMBER})\s*(?P<unit>mg/dL|mmol/L)?"},
            {"field_name": "hemoglobin", "pattern": rf"(?i)\b(?:hemoglobin|haemoglobin|hgb|hb)\b\s*:?\s*(?P<value>{_NUMBER})\s*(?P<unit>g/dL|g/L|mmol/L)?"},
            {"field_name": "hematocrit", "pattern": rf"(?i)\b(?:hematocrit|haematocrit|hct)\b\s*:?\s*(?P<value>{_NUMBER})\s*(?P<unit>%|L/L)?"},
            {"field_name": "white_blood_cell_count", "pattern": rf"(?i)\b(?:white\s*blood\s*cell(?:s|\s*count)?|wbc(?:\s*count)?|leukocytes?)\b\s*:?\s*(?P<value>{_NUMBER})\s*(?P<unit>{_COUNT_UNIT})?"},
            {"field_name": "platelet_count", "pattern": rf"(?i)\b(?:platelets?(?:\s*count)?|plt)\b\s*:?\s*(?P<value>{_NUMBER})\s*(?P<unit>{_COUNT_UNIT})?"},
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

            # Construct text while keeping track of word offsets to map back to bboxes
            parts = []
            word_indices = []
            offset = 0
            for i, w in enumerate(words):
                w_text = w.get("text", "")
                parts.append(w_text)
                word_indices.append((offset, offset + len(w_text), i))
                offset += len(w_text) + 1  # +1 for the space delimiter
            full_text = " ".join(parts)

            for rule in self.rules:
                if rule["field_name"] in found:
                    continue
                match = re.search(rule["pattern"], full_text)
                if not match:
                    continue

                val = match.group("value").strip()
                if not val:
                    continue
                unit = match.groupdict().get("unit")

                # Highlight the value and its unit together
                m_start = match.start("value")
                m_end = match.end("unit") if unit else match.end("value")

                matched_words = [
                    words[word_idx]
                    for start_idx, end_idx, word_idx in word_indices
                    if start_idx < m_end and end_idx > m_start
                ]

                extracted_fields.append(ExtractedFieldData(
                    field_name=rule["field_name"],
                    value=val,
                    unit=unit.strip() if unit else None,
                    confidence=self._compute_avg_confidence(matched_words),
                    page_num=page_num,
                    bbox_normalized=self._compute_union_bbox(matched_words)
                ))
                found.add(rule["field_name"])

        return ExtractionResult(
            extractor_type="rule_based",
            model_version="rule-based-v1.2",
            provider="deterministic",
            prompt_version="1.0",
            fields=extracted_fields
        )

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
