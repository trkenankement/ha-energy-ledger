"""Local monthly billing ledger; no Home Assistant or network dependency."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import csv
from io import StringIO
import re

KINDS = {"electricity": "kWh", "gas": "m³", "water": "m³"}
MAX_MONTHS = 120
MAX_IMPORT_RECORDS = MAX_MONTHS * len(KINDS)
MAX_STORED_RECORDS = 10_000


def parse_import(text, now, tz):
    """Parse bounded, explicitly unit-labelled semicolon-separated input."""
    if not isinstance(text, str) or not text.strip() or len(text) > 65536:
        raise ValueError("invalid_import")
    try:
        reader = csv.reader(StringIO(text), delimiter=";", strict=True)
        if next(reader, None) != ["kind", "month", "unit", "consumption", "cost"]:
            raise ValueError("invalid_import")
        rows = []
        seen = set()
        for fields in reader:
            if not fields or all(not field.strip() for field in fields):
                continue
            if len(fields) != 5 or len(rows) >= MAX_IMPORT_RECORDS:
                raise ValueError("invalid_import")
            kind, month, unit, consumption, cost = (f.strip() for f in fields)
            if kind not in KINDS or unit.replace("m3", "m³") != KINDS[kind]:
                raise ValueError("invalid_unit")
            row = validate_record(dict(kind=kind, month=month,
                                       consumption=consumption, cost=cost), now, tz)
            key = (kind, month)
            if key in seen:
                raise ValueError("duplicate_record")
            seen.add(key)
            rows.append(row)
    except csv.Error as err:
        raise ValueError("invalid_import") from err
    if not rows:
        raise ValueError("invalid_import")
    return rows


def merge_records(existing, incoming, now, tz):
    """Validate the entire batch before producing a replacement ledger."""
    if not incoming or len(incoming) > MAX_IMPORT_RECORDS:
        raise ValueError("invalid_import")
    validated = [validate_record(row, now, tz) for row in incoming]
    keys = [(row["kind"], row["month"]) for row in validated]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate_record")
    merged = {(r["kind"], r["month"]): dict(r) for r in existing}
    merged.update(zip(keys, validated))
    if len(merged) > MAX_STORED_RECORDS:
        raise ValueError("ledger_full")
    return sorted(merged.values(), key=lambda row: (row["kind"], row["month"]))


def amount(value):
    """Accept decimal input, but never interpret ambiguous thousands separators."""
    raw = str(value).strip()
    if len(raw) > 32 or not re.fullmatch(r"\d+(?:[.,]\d{1,6})?", raw):
        raise ValueError("invalid_amount")
    try:
        result = Decimal(raw.replace(",", "."))
    except InvalidOperation as err:
        raise ValueError("invalid_amount") from err
    if not result.is_finite() or result < 0 or result > Decimal("1000000000"):
        raise ValueError("invalid_amount")
    return result


def _record(data):
    """Normalize one untrusted record without applying the entry-date window."""
    if not isinstance(data, dict):
        raise ValueError("invalid_record")
    kind, month = data.get("kind"), data.get("month")
    if (not isinstance(kind, str) or kind not in KINDS or
            not isinstance(month, str) or
            not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month)):
        raise ValueError("invalid_period")
    return {"kind": kind, "month": month,
            "consumption": str(amount(data.get("consumption"))),
            "cost": str(amount(data.get("cost"))), "deleted": False}


def validate_record(data, now, tz):
    row = _record(data)
    month = row["month"]
    start = datetime.fromisoformat(month + "-01").replace(tzinfo=tz)
    local_now = now.astimezone(tz)
    age = (local_now.year - start.year) * 12 + local_now.month - start.month
    if age < 0 or age >= MAX_MONTHS:
        raise ValueError("invalid_period")
    # Hour-based Recorder timestamps require whole-hour UTC alignment.
    offset = start.utcoffset()
    if offset is None or offset.total_seconds() % 3600:
        raise ValueError("unsupported_timezone")
    return row


def validate_timezone(now, tz):
    """Require hourly alignment for every accounting month users can enter."""
    local_now = now.astimezone(tz)
    serial = local_now.year * 12 + local_now.month - 1
    for age in range(MAX_MONTHS):
        value = serial - age
        start = datetime(value // 12, value % 12 + 1, 1, tzinfo=tz)
        offset = start.utcoffset()
        if offset is None or offset.total_seconds() % 3600:
            raise ValueError("unsupported_timezone")


def validate_stored_records(records):
    """Validate persisted rows without expiring legitimate historical bills."""
    if not isinstance(records, list) or len(records) > MAX_STORED_RECORDS:
        raise ValueError("invalid_storage")
    result = []
    seen = set()
    for data in records:
        row = _record(data)
        key = (row["kind"], row["month"])
        if key in seen:
            raise ValueError("invalid_storage")
        seen.add(key)
        deleted = data.get("deleted", False)
        if not isinstance(deleted, bool):
            raise ValueError("invalid_storage")
        if deleted:
            row.update(consumption="0", cost="0", deleted=True)
        result.append(row)
    return sorted(result, key=lambda item: (item["kind"], item["month"]))


def migrate_storage_data(old_major_version, old_minor_version, data):
    """Validate and migrate an older HA Store payload without losing bills.

    The Store wrapper owns the version envelope. Keep migrations explicit so a
    future release cannot silently reinterpret or discard persisted records.
    """
    if (old_major_version, old_minor_version) != (1, 1):
        raise ValueError("unsupported_storage_version")
    if not isinstance(data, dict):
        raise ValueError("invalid_storage")
    migrated = {"records": validate_stored_records(data.get("records", []))}
    projection_version = data.get("projection_version")
    if isinstance(projection_version, int) and not isinstance(projection_version, bool):
        migrated["projection_version"] = projection_version
    return migrated


def upsert(records, record):
    """One record per resource/month; a correction replaces, never appends."""
    result = [r for r in records if (r["kind"], r["month"]) !=
              (record["kind"], record["month"])] + [dict(record)]
    if len(result) > MAX_STORED_RECORDS:
        raise ValueError("ledger_full")
    return sorted(result, key=lambda r: (r["kind"], r["month"]))


def remove(records, kind, month):
    """Keep the period as a tombstone so old statistics can be overwritten."""
    match = next((r for r in records if r["kind"] == kind and r["month"] == month), None)
    if match is None:
        raise ValueError("record_not_found")
    return upsert(records, {**match, "consumption": "0", "cost": "0", "deleted": True})


def statistics(records, kind, tz, now):
    """Build sparse cumulative hourly data; allocate bill to month start.

    This is monthly bill accounting, NOT a daily measured consumption estimate.
    Missing bills remain missing in the ledger; they do not prove zero usage.
    """
    selected = [r for r in records if r["kind"] == kind]
    if not selected:
        return [], []
    events = {}
    for row in selected:
        at = datetime.fromisoformat(row["month"] + "-01").replace(tzinfo=tz)
        at = at.astimezone(timezone.utc)
        events[at] = (amount(row["consumption"]), amount(row["cost"]))
    first = min(events) - timedelta(hours=1)
    end = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    points = [first, *(at for at in sorted(events) if at <= end)]
    if end > points[-1]:
        points.append(end)
    usage, costs = [], []
    total_usage = total_cost = Decimal(0)
    for cursor in points:
        increment, price = events.get(cursor, (Decimal(0), Decimal(0)))
        total_usage += increment
        total_cost += price
        usage.append({"start": cursor, "state": float(total_usage), "sum": float(total_usage)})
        costs.append({"start": cursor, "state": float(total_cost), "sum": float(total_cost)})
    return usage, costs
