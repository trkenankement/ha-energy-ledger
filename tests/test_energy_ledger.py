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

    def test_batch_import_explicit_units_and_decimal_comma(self):
        text = "kind;month;unit;consumption;cost\ngas;2026-01;m3;12,5;240\nwater;2026-01;m³;4;80"
        rows = ledger.parse_import(text, self.now, self.tz)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["consumption"], "12.5")
        merged = ledger.merge_records([self.record()], rows, self.now, self.tz)
        self.assertEqual(len(merged), 2)
        self.assertEqual(ledger.merge_records(merged, rows, self.now, self.tz), merged)

    def test_invalid_batch_does_not_change_original(self):
        header = "kind;month;unit;consumption;cost\n"
        for text in ["", header, "wrong;header\n",
                     header + "gas;2026-01;kWh;12;240",
                     header + "gas;2026-01;m3;12;240\ngas;2026-01;m3;13;260",
                     header + "gas;2026-01;m3;12;240\nwater;2026-11;m3;2;30",
                     "x" * 65537, header + 'gas;"2026-01;m3;12;240']:
            with self.subTest(text=text[:80]), self.assertRaises(ValueError):
                ledger.parse_import(text, self.now, self.tz)
        original = [self.record()]
        snapshot = [dict(row) for row in original]
        with self.assertRaises(ValueError):
            ledger.merge_records(original, [self.record(), self.record("2026-02",cost="10") | {"cost":"NaN"}],
                                 self.now, self.tz)
        self.assertEqual(original, snapshot)
        with self.assertRaisesRegex(ValueError, "duplicate_record"):
            ledger.merge_records(original, [self.record(), self.record()], self.now, self.tz)

    def test_amount_bounds_and_adversarial_text(self):
        self.assertEqual(ledger.amount("1000000000"), ledger.Decimal("1000000000"))
        self.assertEqual(ledger.amount("0.000001"), ledger.Decimal("0.000001"))
        for value in ["1000000000.000001", "0.0000001", "1; DROP TABLE bills",
                      "../../secrets", "<script>alert(1)</script>", "1e9", "+1",
                      "1_000", "1 000", "9" * 33]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ledger.amount(value)

    def test_month_window_timezone_and_resource_boundaries(self):
        self.assertEqual(self.record("2016-11")["month"], "2016-11")
        for month in ["2016-10", "2026-11", "2026-00", "2026-1", "../2026-01"]:
            with self.subTest(month=month), self.assertRaises(ValueError):
                self.record(month)
        with self.assertRaisesRegex(ValueError, "unsupported_timezone"):
            ledger.validate_record(dict(kind="gas", month="2026-01",
                                        consumption="1", cost="1"),
                                   self.now, ZoneInfo("Asia/Kolkata"))
        with self.assertRaises(ValueError):
            ledger.validate_record(dict(kind="../../other", month="2026-01",
                                        consumption="1", cost="1"), self.now, self.tz)

    def test_record_mutations_preserve_caller_and_other_resources(self):
        original = [self.record(), {**self.record(), "kind": "water"}]
        snapshot = [dict(row) for row in original]
        changed = ledger.upsert(original, self.record(consumption="42"))
        deleted = ledger.remove(changed, "gas", "2026-01")
        self.assertEqual(original, snapshot)
        self.assertEqual([r for r in deleted if r["kind"] == "water"],
                         [r for r in snapshot if r["kind"] == "water"])
        self.assertEqual(ledger.remove(deleted, "gas", "2026-01"), deleted)
        with self.assertRaisesRegex(ValueError, "record_not_found"):
            ledger.remove(original, "gas", "2026-02")

    def test_dst_boundaries_keep_hourly_utc_spacing(self):
        rows = [self.record("2026-03", "9", "180")]
        usage, _ = ledger.statistics(rows, "gas", ZoneInfo("Europe/Berlin"), self.now)
        self.assertTrue(all(b["start"] - a["start"] == ledger.timedelta(hours=1)
                            for a, b in zip(usage, usage[1:])))


if __name__ == "__main__":
    unittest.main()
