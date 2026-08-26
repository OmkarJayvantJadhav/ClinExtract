import re
from typing import Dict, Any, List, Optional
from src.extraction.base import BaseExtractor
from src.extraction.schemas import ExtractionResult, ExtractedFieldData

class RuleBasedExtractor(BaseExtractor):
    def __init__(self):
        # A simple deterministic rule engine using regex patterns.
        self.rules = [
            {"field_name": "patient_name", "pattern": r"(?i)patient\s*name:?\s*([A-Za-z\s]+?)(?=\s+(?:DOB|Patient|Glucose|Hemoglobin|Hematocrit|White|Platelet|Specimen|Collection|Received|$))"},
            {"field_name": "date_of_birth", "pattern": r"(?i)dob:?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "patient_id", "pattern": r"(?i)patient\s*id:?\s*([a-zA-Z0-9\-]+)"},
            {"field_name": "specimen_type", "pattern": r"(?i)specimen\s*type:?\s*(blood|urine|saliva|serum|plasma)"},
            {"field_name": "collection_date", "pattern": r"(?i)collection\s*date:?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "received_date", "pattern": r"(?i)received\s*date:?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"},
            {"field_name": "glucose", "pattern": r"(?i)glucose:?\s*(\d+\.?\d*)\s*(mg/dL|mmol/L)?"},
            {"field_name": "hemoglobin", "pattern": r"(?i)hemoglobin:?\s*(\d+\.?\d*)\s*(g/dL|g/L)?"},
            {"field_name": "hematocrit", "pattern": r"(?i)hematocrit:?\s*(\d+\.?\d*)\s*(%)?"},
            {"field_name": "white_blood_cell_count", "pattern": r"(?i)white\s*blood\s*cell\s*count:?\s*(\d+\.?\d*)"},
            {"field_name": "platelet_count", "pattern": r"(?i)platelet\s*count:?\s*(\d+\.?\d*)"},
        ]

    def extract(self, document_data: Dict[str, Any], metadata: Dict[str, Any] = None) -> ExtractionResult:
        extracted_fields = []

        # Iterate over pages
        for page in document_data.get("pages", []):
            page_num = page.get("page_number")
            words = page.get("words", [])
            if not words:
                continue

            # Construct text while keeping track of word indices to map back to bboxes
            text_buffer = []
            word_indices = []
            
            for i, w in enumerate(words):
                w_text = w.get("text", "")
                start_idx = len("".join(text_buffer))
                text_buffer.append(w_text)
                end_idx = start_idx + len(w_text)
                word_indices.append((start_idx, end_idx, i))
                text_buffer.append(" ") # Space delimiter
                
            full_text = "".join(text_buffer)
            
            for rule in self.rules:
                match = re.search(rule["pattern"], full_text)
                if match:
                    # Default to group 1 if it exists, otherwise full match
                    val_group = 1 if match.lastindex else 0
                    val = match.group(val_group).strip()
                    if not val:
                        continue
                        
                    m_start, m_end = match.span(val_group)
                    
                    # Intersect words with the matched span
                    matched_words = []
                    for start_idx, end_idx, word_idx in word_indices:
                        if start_idx < m_end and end_idx > m_start:
                            matched_words.append(words[word_idx])
                            
                    bbox = self._compute_union_bbox(matched_words)
                    conf = self._compute_avg_confidence(matched_words)
                    
                    extracted_fields.append(ExtractedFieldData(
                        field_name=rule["field_name"],
                        value=val,
                        confidence=conf,
                        page_num=page_num,
                        bbox_normalized=bbox
                    ))

        return ExtractionResult(
            extractor_type="rule_based",
            model_version="rule-based-v1.0",
            provider="deterministic",
            prompt_version="1.0",
            fields=extracted_fields
        )

    def _compute_union_bbox(self, words: List[Dict[str, Any]]) -> Optional[List[float]]:
        if not words:
            return None
            
        x0_vals = []
        y0_vals = []
        x1_vals = []
        y1_vals = []
        
        for w in words:
            bbox = w.get("bbox")
            if bbox and len(bbox) == 4:
                x, y, width, height = bbox
                x0_vals.append(x)
                y0_vals.append(y)
                x1_vals.append(x + width)
                y1_vals.append(y + height)
                
        if not x0_vals:
            return None
            
        min_x = min(x0_vals)
        min_y = min(y0_vals)
        max_x = max(x1_vals)
        max_y = max(y1_vals)
        
        return [min_x, min_y, max_x - min_x, max_y - min_y]
        
    def _compute_avg_confidence(self, words: List[Dict[str, Any]]) -> float:
        confs = [w.get("confidence") for w in words if w.get("confidence") is not None]
        if not confs:
            return 100.0
        return sum(confs) / len(confs)
