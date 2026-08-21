import inspect
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import risk_oos.official_broad_industry_mapping as mapping_module
from risk_oos.official_broad_industry_mapping import TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCOPE_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCHEMA_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_URL_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_ID_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_PRE_2024_HISTORICAL_INDUSTRY_CLASSIFICATION_V1
from risk_oos.official_broad_industry_mapping import TECH_RISK_TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_V1
from risk_oos.official_broad_industry_mapping import TechnicalRiskBroadIndustryMappingStatus
from risk_oos.official_broad_industry_mapping import TechnicalRiskOfficialBroadIndustryMappingError
from risk_oos.official_broad_industry_mapping import build_official_broad_industry_mapping_artifact
from risk_oos.official_broad_industry_mapping import encode_official_broad_industry_mapping_artifact
from risk_oos.official_broad_industry_mapping import save_official_broad_industry_mapping_artifact


class TechnicalRiskOfficialBroadIndustryMappingTestCase(unittest.TestCase):
    def test_builds_complete_deterministic_mapping_for_218_symbols(self):
        artifact = _artifact()
        again = _artifact()

        self.assertEqual(artifact.artifact_schema_version, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCHEMA_V1)
        self.assertEqual(artifact.diagnostic_scope, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SCOPE_V1)
        self.assertEqual(artifact.universe_id, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_ID_V1)
        self.assertEqual(artifact.universe_size, TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_UNIVERSE_SIZE_V1)
        self.assertEqual(
            artifact.classification_temporal_semantics,
            TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1,
        )
        self.assertFalse(artifact.historical_industry_classification_claim_allowed)
        self.assertEqual(len(artifact.records), 218)
        self.assertEqual(artifact.artifact_id, again.artifact_id)
        self.assertEqual(artifact.artifact_checksum, again.artifact_checksum)

    def test_duplicate_or_incomplete_universe_fails_closed(self):
        with self.assertRaisesRegex(TechnicalRiskOfficialBroadIndustryMappingError, "218"):
            _artifact(universe_symbols=("2330.TW",))
        duplicate_symbols = _symbols()
        duplicate_symbols = duplicate_symbols[:-1] + (duplicate_symbols[0],)
        with self.assertRaisesRegex(TechnicalRiskOfficialBroadIndustryMappingError, "duplicate"):
            _artifact(universe_symbols=duplicate_symbols)

    def test_records_preserve_official_lineage_and_allowed_status(self):
        artifact = _artifact()
        by_symbol = {record.symbol: record for record in artifact.records}
        tsmc = by_symbol["2330.TW"]

        self.assertEqual(tsmc.company_name, "台積電")
        self.assertEqual(tsmc.broad_industry_code, "24")
        self.assertEqual(tsmc.broad_industry, "半導體業")
        self.assertEqual(tsmc.mapping_status, TechnicalRiskBroadIndustryMappingStatus.MAPPED)
        self.assertEqual(tsmc.industry_source, "TWSE")
        self.assertEqual(tsmc.industry_source_version, "TWSE_t187ap03_L_1150820")
        self.assertEqual(tsmc.classification_as_of_date, date(2026, 8, 20))
        self.assertTrue(tsmc.source_record_checksum)

    def test_current_official_classification_is_not_historical_pre_2024_classification(self):
        artifact = _artifact()
        encoded = encode_official_broad_industry_mapping_artifact(artifact)

        self.assertEqual(
            encoded["classification_temporal_semantics"],
            TECH_RISK_CURRENT_OFFICIAL_INDUSTRY_CLASSIFICATION_V1,
        )
        self.assertNotEqual(
            encoded["classification_temporal_semantics"],
            TECH_RISK_PRE_2024_HISTORICAL_INDUSTRY_CLASSIFICATION_V1,
        )
        self.assertFalse(encoded["historical_industry_classification_claim_allowed"])

    def test_unknown_and_review_required_statuses_are_explicit(self):
        rows = _official_rows()
        rows = [row for row in rows if row["公司代號"] not in {"2330", "2454"}]
        rows.append({"出表日期": "1150820", "公司代號": "2454", "公司簡稱": "聯發科", "產業別": "99"})
        artifact = _artifact(official_rows=rows)
        by_symbol = {record.symbol: record for record in artifact.records}

        self.assertEqual(by_symbol["2330.TW"].mapping_status, TechnicalRiskBroadIndustryMappingStatus.UNKNOWN)
        self.assertEqual(by_symbol["2454.TW"].mapping_status, TechnicalRiskBroadIndustryMappingStatus.REVIEW_REQUIRED)

    def test_distribution_and_technology_preview_are_descriptive_only(self):
        artifact = _artifact()
        distribution = artifact.industry_distribution()
        by_code = {row["broad_industry_code"]: row for row in distribution}

        self.assertEqual(by_code["24"]["symbol_count"], 2)
        self.assertTrue(by_code["24"]["technology_related_preview"])
        self.assertEqual(artifact.technology_related_candidate_count, 3)
        encoded = encode_official_broad_industry_mapping_artifact(artifact)
        self.assertEqual(
            encoded["technology_subset_semantics"],
            TECH_RISK_TECHNOLOGY_REVIEW_CANDIDATE_WORKLOAD_PREVIEW_V1,
        )
        self.assertFalse(encoded["ai_exposure_classification_claim_allowed"])
        self.assertEqual(encoded["technology_related_candidate_count"], 3)
        self.assertNotIn("AI_HIGH", str(encoded))
        self.assertNotIn("AI_ADJACENT", str(encoded))

    def test_save_writes_research_side_json_without_production_path(self):
        artifact = _artifact()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_official_broad_industry_mapping_artifact(artifact, tmpdir)
            self.assertTrue(path.exists())
            self.assertIn("technical_risk_official_broad_industry_mapping_218_twse_v1.json", path.name)
            self.assertNotIn("production", str(path))

    def test_no_risk_performance_network_or_production_dependency(self):
        source = inspect.getsource(mapping_module)
        forbidden = (
            "Candidate C",
            "HoldoutRegionEvaluator",
            "TechnicalRiskCandidateEvaluator",
            "mae20",
            "mae60",
            "stock return",
            "price performance",
            "yfinance",
            "requests",
            "data/production",
            "production_runtime",
            "AI_HIGH",
            "AI_ADJACENT",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


def _symbols():
    first = ("2330.TW", "2454.TW", "3008.TW")
    rest = tuple(f"{code:04d}.TW" for code in range(4000, 4000 + 215))
    return first + rest


def _official_rows():
    rows = [
        {"出表日期": "1150820", "公司代號": "2330", "公司簡稱": "台積電", "產業別": "24"},
        {"出表日期": "1150820", "公司代號": "2454", "公司簡稱": "聯發科", "產業別": "24"},
        {"出表日期": "1150820", "公司代號": "3008", "公司簡稱": "大立光", "產業別": "26"},
    ]
    for code in range(4000, 4000 + 215):
        rows.append({"出表日期": "1150820", "公司代號": str(code), "公司簡稱": f"公司{code}", "產業別": "20"})
    return rows


def _artifact(**overrides):
    values = {
        "universe_symbols": _symbols(),
        "official_rows": _official_rows(),
        "retrieved_at": "2026-08-21T00:00:00+00:00",
        "source_url": TECH_RISK_OFFICIAL_BROAD_INDUSTRY_MAPPING_SOURCE_URL_V1,
    }
    values.update(overrides)
    return build_official_broad_industry_mapping_artifact(**values)


if __name__ == "__main__":
    unittest.main()
