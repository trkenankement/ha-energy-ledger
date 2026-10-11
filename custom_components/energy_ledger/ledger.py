"""Local monthly billing ledger; no Home Assistant or network dependency."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

KINDS = {"electricity": "kWh", "gas": "m³", "water": "m³"}
MAX_MONTHS = 120


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


def validate_record(data, now, tz):
    kind, month = data["kind"], data["month"]
    if kind not in KINDS or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("invalid_period")
    start = datetime.fromisoformat(month + "-01").replace(tzinfo=tz)
    local_now = now.astimezone(tz)
    age = (local_now.year - start.year) * 12 + local_now.month - start.month
    if age < 0 or age >= MAX_MONTHS:
        raise ValueError("invalid_period")
    # Hour-based Recorder timestamps require whole-hour UTC alignment.
    if start.utcoffset().total_seconds() % 3600:
        raise ValueError("unsupported_timezone")
    return {"kind": kind, "month": month,
            "consumption": str(amount(data["consumption"])),
            "cost": str(amount(data["cost"])), "deleted": False}


def upsert(records, record):
    """One record per resource/month; a correction replaces, never appends."""
    return sorted([r for r in records if (r["kind"], r["month"]) !=
                   (record["kind"], record["month"])] + [dict(record)],
                  key=lambda r: (r["kind"], r["month"]))


def remove(records, kind, month):
    """Keep the period as a tombstone so old statistics can be overwritten."""
    match = next((r for r in records if r["kind"] == kind and r["month"] == month), None)
    if match is None:
        raise ValueError("record_not_found")
    return upsert(records, {**match, "consumption": "0", "cost": "0", "deleted": True})


def statistics(records, kind, tz, now):
    """Build repeatable cumulative hourly data; allocate bill to month start.

    This is monthly bill accounting, NOT a daily measured consumption estimate.
    Flat intervening hours exist only to make HA cumulative differences correct.
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
    cursor = min(events) - timedelta(hours=1)
    end = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    if (end - cursor).days > 3660:
        raise ValueError("history_too_long")
    usage, costs = [], []
    total_usage = total_cost = Decimal(0)
    while cursor <= end:
        increment, price = events.get(cursor, (Decimal(0), Decimal(0)))
        total_usage += increment
        total_cost += price
        usage.append({"start": cursor, "state": float(total_usage), "sum": float(total_usage)})
        costs.append({"start": cursor, "state": float(total_cost), "sum": float(total_cost)})
        cursor += timedelta(hours=1)
    return usage, costs
