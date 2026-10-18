"""
Measure extraction accuracy on labeled synthetic lab reports.

    python scripts/evaluate_extraction.py [--count 60] [--seed 0] [--failures]
    GEMINI_API_KEY=... python scripts/evaluate_extraction.py --extractor llm --count 12

--extractor llm|vlm sends the generated (synthetic) reports to Gemini, the text or the
vision model, so you can compare it with the rule-based extractor on the same documents.

Prints per-field accuracy, accuracy by media/layout/date format, and the share of
auto-accepted documents that were fully correct (the number that matters most: those
documents are never seen by a reviewer).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.scoring import evaluate  # noqa: E402
from evaluation.synthetic import make_cases  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--failures", action="store_true", help="list every wrong or missing field")
    parser.add_argument("--extractor", choices=["rule_based", "llm", "vlm"], default="rule_based")
    args = parser.parse_args()

    extractor = None
    if args.extractor != "rule_based":
        from src.core.config import settings
        from src.extraction.factory import ExtractionFactory
        if not settings.GEMINI_API_KEY:
            parser.error("--extractor llm/vlm needs GEMINI_API_KEY (the mock provider would be measured instead)")
        settings.LLM_PROVIDER = settings.LLM_PROVIDER or "gemini"
        settings.VLM_PROVIDER = settings.VLM_PROVIDER or "gemini"
        # These documents are generated test data, not patient data
        settings.ALLOW_EXTERNAL_AI_PHI = True
        extractor = ExtractionFactory.get_extractor(args.extractor)

    report = evaluate(make_cases(args.count, args.seed), extractor)
    print(report.markdown())
    if args.failures:
        print("\nFailures:")
        for r in report.results:
            for name, outcome in r.outcomes.items():
                if outcome != "correct":
                    print(f"  {r.case.name} {r.case.traits}: {name} {outcome}: "
                          f"found {r.found[name]!r}, expected {r.case.truth[name]!r}")


if __name__ == "__main__":
    main()
