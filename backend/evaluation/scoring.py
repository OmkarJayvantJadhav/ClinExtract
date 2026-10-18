"""Runs labeled cases through the real pipeline and scores the result per field and per document."""
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.db.models.extracted_field import ExtractedField
from src.db.models.extraction import Extraction
from src.extraction.rule_based import RuleBasedExtractor
from src.processing.analyzer import DocumentAnalyzer
from src.validation.engine import ValidationEngine, NUMERIC_FIELDS

from evaluation.synthetic import Case

FIELDS = ["patient_name", "patient_id", "date_of_birth", "patient_sex", "specimen_type", "collection_date",
          "received_date", "glucose", "hemoglobin", "hematocrit", "white_blood_cell_count", "platelet_count"]


@dataclass
class CaseResult:
    case: Case
    decision: str
    outcomes: Dict[str, str]  # field -> correct | wrong | missing
    found: Dict[str, Optional[str]] = field(default_factory=dict)

    @property
    def fully_correct(self) -> bool:
        return all(o == "correct" for o in self.outcomes.values())


def _matches(field_name: str, found: Optional[str], expected: str) -> bool:
    if found is None:
        return False
    if field_name in NUMERIC_FIELDS:
        try:
            got, want = float(found), float(expected)
        except ValueError:
            return False
        return abs(got - want) <= max(0.01 * abs(want), 0.051)
    return found.strip().lower() == expected.strip().lower()


def run_case(case: Case, engine: Optional[ValidationEngine] = None, extractor=None) -> CaseResult:
    artifact = DocumentAnalyzer.process(case.data, case.mime, "eval", "eval")
    # The vision extractor reads the page images, the others the OCR/native text
    result = (extractor or RuleBasedExtractor()).extract(artifact, metadata={"image_bytes": case.data})
    extraction = Extraction(id=uuid.uuid4(), model_version="eval", provider="eval", prompt_version="eval")
    extraction.extracted_fields = [
        ExtractedField(field_name=f.field_name, value=f.value, unit=f.unit, confidence=f.confidence,
                       page_num=f.page_num, reference_range=f.reference_range, abnormal_flag=f.abnormal_flag)
        for f in result.fields
    ]
    (engine or ValidationEngine()).validate_extraction(extraction, artifact)
    by_name = {f.field_name: f for f in extraction.extracted_fields}

    outcomes, found = {}, {}
    for name in FIELDS:
        f = by_name.get(name)
        value = None
        if f is not None and f.value:
            # Compare what the system would store: the normalized value when validation produced one
            value = f.normalized_value if f.normalized_value not in (None, "") else f.value
        found[name] = value
        outcomes[name] = "missing" if value is None else "correct" if _matches(name, value, case.truth[name]) else "wrong"
    return CaseResult(case=case, decision=extraction.decision, outcomes=outcomes, found=found)


@dataclass
class Report:
    results: List[CaseResult]

    def field_accuracy(self) -> Dict[str, Counter]:
        table = defaultdict(Counter)
        for r in self.results:
            for name, outcome in r.outcomes.items():
                table[name][outcome] += 1
        return table

    @property
    def overall_field_accuracy(self) -> float:
        total = sum(len(r.outcomes) for r in self.results)
        return sum(o == "correct" for r in self.results for o in r.outcomes.values()) / max(total, 1)

    @property
    def auto_accepted(self) -> List[CaseResult]:
        return [r for r in self.results if r.decision == "AUTO_ACCEPTED"]

    @property
    def auto_accept_precision(self) -> Optional[float]:
        """Of the documents accepted without review, the share that was extracted fully correctly."""
        accepted = self.auto_accepted
        return sum(r.fully_correct for r in accepted) / len(accepted) if accepted else None

    def by_trait(self, trait: str) -> Dict[str, float]:
        groups = defaultdict(list)
        for r in self.results:
            groups[r.case.traits[trait]].append(r)
        return {
            k: sum(o == "correct" for r in rs for o in r.outcomes.values()) / sum(len(r.outcomes) for r in rs)
            for k, rs in sorted(groups.items())
        }

    def markdown(self) -> str:
        n = len(self.results)
        accepted = self.auto_accepted
        precision = self.auto_accept_precision
        lines = [
            f"Documents: {n}",
            f"Field accuracy: {self.overall_field_accuracy:.1%}",
            f"Documents fully correct: {sum(r.fully_correct for r in self.results) / n:.1%}",
            f"Auto-accepted: {len(accepted) / n:.1%} of documents"
            + (f", of which fully correct: {precision:.1%}" if precision is not None else ""),
            "",
            "| Field | Correct | Wrong | Missing |",
            "|---|---|---|---|",
        ]
        for name in FIELDS:
            c = self.field_accuracy()[name]
            lines.append(f"| {name} | {c['correct'] / n:.0%} | {c['wrong']} | {c['missing']} |")
        for trait in ("media", "layout", "dates"):
            lines.append("")
            lines.append(f"By {trait}: " + ", ".join(f"{k} {v:.1%}" for k, v in self.by_trait(trait).items()))
        return "\n".join(lines)


def evaluate(cases: List[Case], extractor=None) -> Report:
    return Report([run_case(c, extractor=extractor) for c in cases])
