import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from catalyst_impact import CATALYST_IMPACT_HYPOTHESIS_VERSION
from catalyst_impact import CatalystImpactError
from catalyst_impact import HypothesisStatus
from catalyst_impact import ImpactChannel
from catalyst_impact import ImpactHypothesis


class CatalystImpactModelTestCase(unittest.TestCase):
    def hypothesis(self, **changes):
        values = {
            "hypothesis_id": "catalyst_impact_test",
            "event_id": "event_1216_revenue",
            "target_symbol": "1216.TW",
            "target_company_name": "統一",
            "impact_channel": ImpactChannel.REVENUE,
            "hypothesis_text": "近期月營收事件可能反映營運動能變化。",
            "why_it_matters_text": "營收變化可能影響後續可檢視的獲利基礎。",
            "hypothesis_status": HypothesisStatus.PLAUSIBLE,
            "supporting_evidence_refs": (),
            "contradictory_evidence_refs": (),
            "missing_evidence": ("missing:margin",),
            "contradiction_or_limit_text": "單一月份不足以確認持續性。",
            "uncertainty_text": "事業組合與利潤率資料仍缺。",
            "next_checks": ("比較後續營收與財務或法說資料。",),
        }
        values.update(changes)
        return ImpactHypothesis(**values)

    def test_contract_is_immutable_and_has_no_recommendation_fields(self):
        result = self.hypothesis()
        self.assertEqual(result.version, CATALYST_IMPACT_HYPOTHESIS_VERSION)
        with self.assertRaises(AttributeError):
            result.event_id = "changed"
        self.assertFalse(any(name in result.__dict__ for name in ("confidence", "probability", "price_target", "direction")))

    def test_supported_requires_independent_approved_support(self):
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(hypothesis_status=HypothesisStatus.SUPPORTED)
        self.assertEqual(
            self.hypothesis(hypothesis_status=HypothesisStatus.SUPPORTED, supporting_evidence_refs=("evidence:earnings",)).hypothesis_status,
            HypothesisStatus.SUPPORTED,
        )

    def test_contradicted_requires_explicit_contradiction(self):
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(hypothesis_status=HypothesisStatus.CONTRADICTED)
        self.assertEqual(
            self.hypothesis(hypothesis_status=HypothesisStatus.CONTRADICTED, contradictory_evidence_refs=("evidence:risk",)).hypothesis_status,
            HypothesisStatus.CONTRADICTED,
        )

    def test_refs_and_slots_are_bounded_and_deterministic(self):
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(supporting_evidence_refs=("b", "a"))
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(next_checks=("one", "two"))
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(uncertainty_text="x" * 421)
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(version="CATALYST_IMPACT_HYPOTHESIS_V2")
        with self.assertRaises(CatalystImpactError):
            self.hypothesis(supporting_evidence_refs=("evidence:support",), contradictory_evidence_refs=("evidence:support",))


if __name__ == "__main__":
    unittest.main()
