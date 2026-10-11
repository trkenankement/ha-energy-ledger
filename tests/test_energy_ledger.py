"""Independent monthly billing tests, without touching live HA."""
import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PATH = Path(__file__).resolve().parents[1] / "custom_components/energy_ledger/ledger.py"
spec = importlib.util.spec_from_file_location("ledger", PATH)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Istanbul")
        self.now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)

    def record(self, month="2026-01", consumption="12", cost="240"):
        return ledger.validate_record(dict(kind="gas", month=month,
                                          consumption=consumption, cost=cost), self.now, self.tz)

    def test_totals_match_synthetic_monthly_inputs(self):
        quantities = [12, 15, 9, 8, 5, 2, 1, 1, 3, 4]
        prices = [240, 300, 180, 160, 100, 40, 20, 20, 60, 80]
        records = [self.record(f"2026-{i:02}", str(q), str(p))
                   for i, (q, p) in enumerate(zip(quantities, prices), 1)]
        usage, cost = ledger.statistics(records, "gas", self.tz, self.now)
        self.assertEqual(usage[-1]["sum"], 60)
        self.assertEqual(cost[-1]["sum"], 1200)
        for i, expected in enumerate(quantities, 1):
            month_rows = [r for r in usage if r["start"].astimezone(self.tz).month == i]
            before = next(r["sum"] for r in usage if r["start"] == month_rows[0]["start"] - ledger.timedelta(hours=1))
            self.assertEqual(month_rows[-1]["sum"] - before, expected)

    def test_repeat_and_correction_are_idempotent(self):
        rows = ledger.upsert([], self.record())
        self.assertEqual(ledger.upsert(rows, self.record()), rows)
        rows = ledger.upsert(rows, self.record(consumption="100", cost="1800"))
        usage, cost = ledger.statistics(rows, "gas", self.tz, self.now)
        self.assertEqual((usage[-1]["sum"], cost[-1]["sum"]), (100, 1800))

    def test_delete_overwrites_history_without_shifting_start(self):
        rows = [self.record(), self.record("2026-02", "15", "300")]
        old, _ = ledger.statistics(rows, "gas", self.tz, self.now)
        deleted = ledger.remove(rows, "gas", "2026-01")
        new, _ = ledger.statistics(deleted, "gas", self.tz, self.now)
        self.assertEqual(old[0]["start"], new[0]["start"])
        self.assertEqual(new[-1]["sum"], 15)

    def test_invalid_numbers_dates_and_future(self):
        for value in ["NaN", "Infinity", "-1", "1.234,56", "oops", "1e-999999", "9" * 1000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.record(cost=value)
        for month in ["2026-13", "2026-11", "2010-01", "January"]:
            with self.subTest(month=month), self.assertRaises(ValueError):
                self.record(month)
        self.assertEqual(self.record(cost="0")["cost"], "0")
        self.assertEqual(self.record(cost="1,50")["cost"], "1.50")

    def test_streams_are_separate(self):
        self.assertEqual(ledger.statistics([self.record()], "water", self.tz, self.now), ([], []))

    def test_dst_boundaries_keep_hourly_utc_spacing(self):
        rows = [self.record("2026-03", "9", "180")]
        usage, _ = ledger.statistics(rows, "gas", ZoneInfo("Europe/Berlin"), self.now)
        self.assertTrue(all(b["start"] - a["start"] == ledger.timedelta(hours=1)
                            for a, b in zip(usage, usage[1:])))


if __name__ == "__main__":
    unittest.main()
