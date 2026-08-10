from scanner_condition_coverage_outcome_research_service import DEFAULT_RESEARCH_DOC_PATH
from scanner_condition_coverage_outcome_research_service import DEFAULT_RESEARCH_OUTPUT_PATH
from scanner_condition_coverage_outcome_research_service import run_final_condition_coverage_outcome_study
from scanner_condition_coverage_outcome_research_service import write_condition_coverage_research_artifacts


def main() -> int:
    result = run_final_condition_coverage_outcome_study()
    json_path, doc_path = write_condition_coverage_research_artifacts(
        result,
        json_path=DEFAULT_RESEARCH_OUTPUT_PATH,
        doc_path=DEFAULT_RESEARCH_DOC_PATH,
    )
    print(f"JSON: {json_path}")
    print(f"Doc: {doc_path}")
    print(f"Checksum: {result.checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
