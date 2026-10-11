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
        previous = 0
        for i, expected in enumerate(quantities, 1):
            event = next(r for r in usage if
                         r["start"].astimezone(self.tz).strftime("%Y-%m-%d %H:%M") ==
                         f"2026-{i:02}-01 00:00")
            self.assertEqual(event["sum"] - previous, expected)
            previous = event["sum"]

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

    def test_sparse_points_keep_utc_alignment_across_dst(self):
        rows = [self.record("2026-03", "9", "180"),
                self.record("2026-04", "10", "200")]
        usage, _ = ledger.statistics(rows, "gas", ZoneInfo("Europe/Berlin"), self.now)
        self.assertEqual(usage, sorted(usage, key=lambda row: row["start"]))
        self.assertTrue(all(row["start"].minute == row["start"].second == 0
                            for row in usage))
        self.assertEqual(len(usage), 4)  # baseline, two bills and one current tail

    def test_sparse_history_scales_with_bills_and_does_not_expire(self):
        records = []
        serial = 2026 * 12 + 10 - 1
        for age in range(120):
            value = serial - age
            records.append({"kind": "gas", "month": f"{value // 12:04}-{value % 12 + 1:02}",
                            "consumption": "1", "cost": "2", "deleted": False})
        usage, costs = ledger.statistics(records, "gas", self.tz, self.now)
        self.assertLessEqual(len(usage), len(records) + 2)
        self.assertEqual((usage[-1]["sum"], costs[-1]["sum"]), (120, 240))
        old = [{"kind": "gas", "month": "2000-01", "consumption": "1",
                "cost": "2", "deleted": False}]
        self.assertEqual(ledger.statistics(old, "gas", self.tz, self.now)[0][-1]["sum"], 1)

    def test_current_incomplete_hour_defers_month_event(self):
        now = datetime(2026, 10, 1, 0, 30, tzinfo=self.tz)
        row = ledger.validate_record(dict(kind="gas", month="2026-10",
                                          consumption="5", cost="50"), now, self.tz)
        usage, _ = ledger.statistics([row], "gas", self.tz, now)
        self.assertEqual([point["sum"] for point in usage], [0])

    def test_stored_rows_are_validated_without_expiring_history(self):
        old = [{"kind": "gas", "month": "2000-01", "consumption": "1.5",
                "cost": "2", "deleted": False}]
        self.assertEqual(ledger.validate_stored_records(old)[0]["month"], "2000-01")
        tombstone = [{**old[0], "consumption": "999", "cost": "999", "deleted": True}]
        self.assertEqual(ledger.validate_stored_records(tombstone)[0]["consumption"], "0")
        long_lived = []
        for offset in range(361):
            serial = 1900 * 12 + offset
            long_lived.append({**old[0], "month": f"{serial // 12:04}-{serial % 12 + 1:02}"})
        self.assertEqual(len(ledger.validate_stored_records(long_lived)), 361)
        for invalid in [None, [{**old[0], "deleted": "yes"}], old + old,
                        [{**old[0], "kind": "other"}], old * (ledger.MAX_STORED_RECORDS + 1)]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                ledger.validate_stored_records(invalid)

    def test_storage_1_1_migration_preserves_all_records(self):
        legacy = {
            "records": [
                self.record("2026-01", "12", "240"),
                {**self.record("2026-02", "15", "300"),
                 "consumption": "0", "cost": "0", "deleted": True},
            ],
            "projection_version": 2,
        }
        snapshot = {"records": [dict(row) for row in legacy["records"]],
                    "projection_version": 2}
        migrated = ledger.migrate_storage_data(1, 1, legacy)
        self.assertEqual(migrated, snapshot)
        self.assertEqual(legacy, snapshot)
        with self.assertRaisesRegex(ValueError, "unsupported_storage_version"):
            ledger.migrate_storage_data(2, 0, legacy)
        with self.assertRaisesRegex(ValueError, "invalid_storage"):
            ledger.migrate_storage_data(1, 1, {"records": legacy["records"] * 2})

    def test_timezone_checks_full_entry_window(self):
        ledger.validate_timezone(self.now, self.tz)
        with self.assertRaisesRegex(ValueError, "unsupported_timezone"):
            ledger.validate_timezone(self.now, ZoneInfo("Australia/Lord_Howe"))


if __name__ == "__main__":
    unittest.main()
