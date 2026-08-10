from scanner_condition_coverage_phase2_robustness_service import PHASE2_DOC_PATH
from scanner_condition_coverage_phase2_robustness_service import PHASE2_OUTPUT_PATH
from scanner_condition_coverage_phase2_robustness_service import run_final_phase2_robustness_study
from scanner_condition_coverage_phase2_robustness_service import write_phase2_robustness_artifacts


def main() -> int:
    result = run_final_phase2_robustness_study()
    json_path, doc_path = write_phase2_robustness_artifacts(
        result,
        json_path=PHASE2_OUTPUT_PATH,
        doc_path=PHASE2_DOC_PATH,
    )
    print(f"JSON: {json_path}")
    print(f"Doc: {doc_path}")
    print(f"Checksum: {result.checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
