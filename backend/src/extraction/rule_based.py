import re
from typing import Dict, Any, List, Optional
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, ExtractedFieldData

# Field labels used as look-ahead terminators for free-text values such as the patient name.
_LABELS = r"DOB|Date\s*of\s*Birth|Patient|Glucose|Hemoglobin|Hematocrit|White|Platelet|Specimen|Collection|Received"

class RuleBasedExtractor(BaseExtractor):
    def __init__(self):
        # A simple deterministic rule engine using regex patterns.
        # Each rule captures the value in group "value" and, optionally, the unit in group "unit".
        self.rules = [
            {"field_name": "patient_name", "pattern": rf"(?i)patient\s*name:?\s*(?P<value>[A-Za-z][A-Za-z'\-\.]*(?:\s+[A-Za-z][A-Za-z'\-\.]*)*?)(?=\s+(?:{_LABELS})\b|\s*$)"},
            {"field_name": "date_of_birth", "pattern": r"(?i)(?:dob|date\s*of\s*birth):?\s*(?P<value>\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "patient_id", "pattern": r"(?i)patient\s*id:?\s*(?P<value>[a-zA-Z0-9\-]+)"},
            {"field_name": "specimen_type", "pattern": r"(?i)specimen\s*type:?\s*(?P<value>blood|urine|saliva|serum|plasma)"},
            {"field_name": "collection_date", "pattern": r"(?i)collection\s*date:?\s*(?P<value>\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "received_date", "pattern": r"(?i)received\s*date:?\s*(?P<value>\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "glucose", "pattern": r"(?i)glucose:?\s*(?P<value>\d+\.?\d*)\s*(?P<unit>mg/dL|mmol/L)?"},
            {"field_name": "hemoglobin", "pattern": r"(?i)hemoglobin:?\s*(?P<value>\d+\.?\d*)\s*(?P<unit>g/dL|g/L)?"},
            {"field_name": "hematocrit", "pattern": r"(?i)hematocrit:?\s*(?P<value>\d+\.?\d*)\s*(?P<unit>%)?"},
            {"field_name": "white_blood_cell_count", "pattern": r"(?i)white\s*blood\s*cell\s*count:?\s*(?P<value>\d{1,3}(?:,\d{3})+|\d+\.?\d*)\s*(?P<unit>(?:x\s*)?10\^?[39]\s*/\s*[uµμ]?L|K/[uµμ]L|cells/[uµμ]L|/[uµμ]L)?"},
            {"field_name": "platelet_count", "pattern": r"(?i)platelet\s*count:?\s*(?P<value>\d{1,3}(?:,\d{3})+|\d+\.?\d*)\s*(?P<unit>(?:x\s*)?10\^?[39]\s*/\s*[uµμ]?L|K/[uµμ]L|cells/[uµμ]L|/[uµμ]L)?"},
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
            model_version="rule-based-v1.1",
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
