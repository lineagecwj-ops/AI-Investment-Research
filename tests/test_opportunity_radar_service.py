import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opportunity_radar_service import (
    MonthlyRevenueRecord,
    find_latest_monthly_revenue_record,
    normalize_monthly_revenue_records,
)


class OpportunityRadarServiceTest(unittest.TestCase):
    def test_normalizes_official_fields_and_filters_frozen_universe(self):
        records = normalize_monthly_revenue_records([
            {"公司代號": "2330", "公司名稱": "台積電", "資料年": "2026", "月份": "08", "當月營收": "120", "上月營收": "100", "去年當月營收": "80", "去年同月增減(%)": "50"},
            {"公司代號": "9999", "當月營收": "1"},
        ], {"2330.TW"})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].symbol, "2330.TW")
        self.assertEqual(records[0].revenue_yoy, 0.5)
        self.assertAlmostEqual(records[0].revenue_mom, 0.2)

    def test_zero_denominator_is_unavailable_not_zero(self):
        record = normalize_monthly_revenue_records([{"公司代號": "2330", "當月營收": "120", "上月營收": "0", "去年當月營收": "0"}], {"2330.TW"})[0]
        self.assertIsNone(record.revenue_yoy)
        self.assertIsNone(record.revenue_mom)

    def test_combined_roc_year_month_maps_to_gregorian_revenue_period(self):
        record = normalize_monthly_revenue_records([
            {"公司代號": "2330", "資料年月": "11508", "當月營收": "120"}
        ], {"2330.TW"})[0]

        self.assertEqual(record.reported_year_month, "2026-08")

    def test_finds_one_symbol_from_the_existing_canonical_snapshot(self):
        record = MonthlyRevenueRecord("2027.TW", "大成鋼", "N/A", 120, 100, 80, 0.5, 0.2)

        resolved = find_latest_monthly_revenue_record(
            "2027.TW",
            snapshot_loader=lambda: ({"retrieved_at": "2026-08-30T00:00:00+08:00"}, (record,)),
        )

        self.assertEqual(resolved[1], record)
        self.assertIsNone(find_latest_monthly_revenue_record(
            "2330.TW",
            snapshot_loader=lambda: ({}, (record,)),
        ))


if __name__ == "__main__": unittest.main()
