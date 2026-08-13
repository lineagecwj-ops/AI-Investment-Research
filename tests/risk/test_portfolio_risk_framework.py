import sys
import unittest
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from risk import HoldingType
from risk import PortfolioPosition
from risk import PortfolioPositionError
from risk import RiskArtifactGenerator
from risk import RiskAssessment
from risk import RiskCategory
from risk import RiskChecksumGenerator
from risk import RiskContext
from risk import RiskDefinition
from risk import RiskRegistry
from risk import RiskRegistryError
from risk import RiskSeverity
from risk import RiskSignal
from risk import RiskSignalError
from risk import aggregate_risk_level


class PortfolioRiskFrameworkTestCase(unittest.TestCase):

    def created_at(self):
        return datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

    def analysis_date(self):
        return date(2026, 8, 13)

    def whole_position(self):
        return PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("10"),
            average_cost=Decimal("650.00"),
            holding_type="whole_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def fractional_position(self):
        return PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("15.5"),
            average_cost=Decimal("650.00"),
            holding_type="fractional_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

    def definition(self, risk_id="TECH_TREND_WEAKENING_V1", category=RiskCategory.TECHNICAL):
        return RiskDefinition(
            risk_id=risk_id,
            risk_name="Trend Weakening",
            category=category,
            version="v1",
            description="Synthetic technical risk definition for framework tests.",
            severity_rule="highest deterministic threshold bucket wins",
        )

    def context(self):
        return RiskContext(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            analysis_date=self.analysis_date(),
            feature_version="feature_set_v1",
            model_version="baseline_model_v1",
            calculation_id="risk_calc_phase7k_001",
        )

    def signal(self, risk_id="TECH_TREND_WEAKENING_V1", category=RiskCategory.TECHNICAL, severity=RiskSeverity.MEDIUM):
        return RiskSignal(
            risk_id=risk_id,
            symbol="2330.TW",
            category=category,
            severity=severity,
            trigger_reason="synthetic threshold breach for risk framework validation",
            created_at=self.created_at(),
        )

    def assessment(self):
        signals = (
            self.signal(severity=RiskSeverity.MEDIUM),
            self.signal("PORT_POSITION_CONCENTRATION_V1", RiskCategory.PORTFOLIO, RiskSeverity.HIGH),
        )
        return RiskAssessment.from_signals(
            portfolio_id="portfolio_synthetic_001",
            symbol="2330.TW",
            signals=signals,
            assessment_date=self.analysis_date(),
        )

    def artifact(self):
        return RiskArtifactGenerator().generate(
            artifact_id="risk_artifact_phase7k_001",
            position=self.whole_position(),
            context=self.context(),
            assessment=self.assessment(),
            created_at=self.created_at(),
        )

    def test_portfolio_position_creation(self):
        position = self.whole_position()

        self.assertEqual(position.symbol, "2330.TW")
        self.assertEqual(position.currency, "TWD")
        self.assertEqual(position.identity["symbol"], "2330.TW")

    def test_whole_share_support(self):
        position = self.whole_position()

        self.assertEqual(position.holding_type, HoldingType.WHOLE_SHARE)
        self.assertEqual(position.shares, Decimal("10"))

    def test_fractional_share_support(self):
        position = self.fractional_position()

        self.assertEqual(position.holding_type, HoldingType.FRACTIONAL_SHARE)
        self.assertEqual(position.shares, Decimal("15.5"))

    def test_decimal_precision_validation(self):
        position = PortfolioPosition(
            symbol="2330.TW",
            shares=Decimal("0.125"),
            average_cost=Decimal("650.125"),
            holding_type="fractional_share",
            acquisition_date=date(2026, 1, 5),
            currency="TWD",
        )

        self.assertEqual(position.shares, Decimal("0.125"))
        self.assertEqual(position.average_cost, Decimal("650.125"))
        self.assertEqual(position.identity["shares"], Decimal("0.125"))

    def test_risk_definition_creation(self):
        definition = self.definition()

        self.assertEqual(definition.risk_id, "TECH_TREND_WEAKENING_V1")
        self.assertEqual(definition.category, RiskCategory.TECHNICAL)
        self.assertEqual(definition.version, "v1")

    def test_risk_context_creation(self):
        context = self.context()

        self.assertEqual(context.portfolio_id, "portfolio_synthetic_001")
        self.assertEqual(context.feature_version, "feature_set_v1")
        self.assertEqual(context.calculation_id, "risk_calc_phase7k_001")

    def test_risk_registry_registration(self):
        registry = RiskRegistry()
        definition = self.definition()

        registry.register(definition)

        self.assertIs(registry.get_risk("TECH_TREND_WEAKENING_V1", "v1"), definition)
        self.assertEqual(registry.list_risks(), ("TECH_TREND_WEAKENING_V1:v1",))

    def test_duplicate_risk_rejection(self):
        registry = RiskRegistry()
        registry.register(self.definition())

        with self.assertRaisesRegex(RiskRegistryError, "already registered"):
            registry.register(self.definition())

    def test_risk_signal_creation(self):
        signal = self.signal()

        self.assertEqual(signal.category, RiskCategory.TECHNICAL)
        self.assertEqual(signal.severity, RiskSeverity.MEDIUM)
        self.assertEqual(signal.symbol, "2330.TW")

    def test_technical_fundamental_market_portfolio_risk_framework_categories(self):
        definitions = (
            self.definition("TECH_MA_BREAKDOWN_V1", RiskCategory.TECHNICAL),
            self.definition("FUND_EPS_DETERIORATION_V1", RiskCategory.FUNDAMENTAL),
            self.definition("MARKET_VOLATILITY_INCREASE_V1", RiskCategory.MARKET),
            self.definition("PORT_POSITION_CONCENTRATION_V1", RiskCategory.PORTFOLIO),
        )

        self.assertEqual(tuple(definition.category for definition in definitions), (
            RiskCategory.TECHNICAL,
            RiskCategory.FUNDAMENTAL,
            RiskCategory.MARKET,
            RiskCategory.PORTFOLIO,
        ))

    def test_risk_aggregation(self):
        signals = (
            self.signal(severity=RiskSeverity.LOW),
            self.signal("TECH_MOMENTUM_DETERIORATION_V1", RiskCategory.TECHNICAL, RiskSeverity.HIGH),
            self.signal("MARKET_SECTOR_WEAKNESS_V1", RiskCategory.MARKET, RiskSeverity.MEDIUM),
        )

        self.assertEqual(aggregate_risk_level(signals), RiskSeverity.HIGH)

    def test_risk_assessment_creation(self):
        assessment = self.assessment()

        self.assertEqual(assessment.portfolio_id, "portfolio_synthetic_001")
        self.assertEqual(assessment.symbol, "2330.TW")
        self.assertEqual(assessment.overall_risk_level, RiskSeverity.HIGH)
        self.assertEqual(len(assessment.signals), 2)

    def test_risk_artifact_generation(self):
        artifact = self.artifact()

        self.assertEqual(artifact.artifact_id, "risk_artifact_phase7k_001")
        self.assertEqual(artifact.position_identity["holding_type"], "whole_share")
        self.assertEqual(artifact.feature_lineage["feature_version"], "feature_set_v1")
        self.assertEqual(artifact.calculation_metadata["calculation_id"], "risk_calc_phase7k_001")

    def test_checksum_reproducibility(self):
        generator = RiskChecksumGenerator()
        artifact = self.artifact()
        context = self.context()

        self.assertEqual(generator.generate(artifact, context), generator.generate(artifact, context))

    def test_invalid_input_rejection(self):
        with self.assertRaisesRegex(PortfolioPositionError, "integer shares"):
            PortfolioPosition(
                symbol="2330.TW",
                shares=Decimal("10.5"),
                average_cost=Decimal("650.00"),
                holding_type="whole_share",
                acquisition_date=date(2026, 1, 5),
                currency="TWD",
            )

        with self.assertRaisesRegex(PortfolioPositionError, "must use Decimal"):
            PortfolioPosition(
                symbol="2330.TW",
                shares=10.5,
                average_cost=Decimal("650.00"),
                holding_type="fractional_share",
                acquisition_date=date(2026, 1, 5),
                currency="TWD",
            )

        with self.assertRaisesRegex(RiskSignalError, "created_at"):
            RiskSignal(
                risk_id="TECH_TREND_WEAKENING_V1",
                symbol="2330.TW",
                category=RiskCategory.TECHNICAL,
                severity=RiskSeverity.LOW,
                trigger_reason="synthetic invalid signal",
                created_at="2026-08-13",
            )

    def test_risk_modules_do_not_import_existing_runtime_boundaries(self):
        risk_source = "\n".join(
            path.read_text()
            for path in sorted((SRC_PATH / "risk").glob("*.py"))
        )

        forbidden_imports = (
            "live_data_store",
            "LiveDataStore",
            "swing_scanner_service",
            "swing_scanner_pdf_export_service",
            "ResearchDataStore",
            "sqlite3",
            "yfinance",
        )
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, risk_source)


if __name__ == "__main__":
    unittest.main()
