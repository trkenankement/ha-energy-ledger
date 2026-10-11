"""Local bill recording and historical Energy statistics."""
import asyncio
from copy import deepcopy
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS, SIGNAL_UPDATED
from .ledger import KINDS, merge_records, remove, statistics, upsert, validate_record


class LedgerManager:
    """Serialize local commits; Recorder data is a rebuildable projection."""
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.records = []
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.lock = asyncio.Lock()
        self.tz = ZoneInfo(entry.data["timezone"])
        self.currency = entry.data["currency"]
        self.projected = {}

    async def load(self):
        data = await self.store.async_load()
        if data:
            self.records = data["records"]
        await self.publish()

    async def publish(self):
        """Upsert all owned series; do not touch other integrations' data."""
        now = dt_util.utcnow()
        for kind, unit in KINDS.items():
            signature = tuple((r["month"], r["consumption"], r["cost"], r["deleted"])
                              for r in self.records if r["kind"] == kind)
            previous = self.projected.get(kind)
            usage, costs = await self.hass.async_add_executor_job(
                statistics, self.records, kind, self.tz, now)
            # Unchanged monthly data needs only a new tail, not thousands of
            # repeated database updates every hour. A correction rebuilds all.
            if previous and previous[0] == signature:
                usage = [row for row in usage if row["start"] > previous[1]]
                costs = [row for row in costs if row["start"] > previous[1]]
            for metric, values, measurement, unit_class in [
                ("consumption", usage, unit, "energy" if kind == "electricity" else "volume"),
                ("cost", costs, self.currency, None),
            ]:
                if values:
                    async_add_external_statistics(self.hass, {
                        "mean_type": StatisticMeanType.NONE, "has_sum": True,
                        "name": f"Energy Ledger {kind} {metric}",
                        "source": DOMAIN,
                        "statistic_id": f"{DOMAIN}:{kind}_{metric}",
                        "unit_class": unit_class,
                        "unit_of_measurement": measurement,
                    }, values)
            if usage:
                self.projected[kind] = (signature, usage[-1]["start"])

    async def save_record(self, data):
        async with self.lock:
            record = validate_record(data, dt_util.utcnow(), self.tz)
            await self._commit(upsert(self.records, record))

    async def delete_record(self, kind, month):
        async with self.lock:
            await self._commit(remove(self.records, kind, month))

    async def save_records(self, incoming):
        async with self.lock:
            now = dt_util.utcnow()
            records = merge_records(self.records, incoming, now, self.tz)
            # Reject projection bounds before committing any of the batch.
            for kind in KINDS:
                await self.hass.async_add_executor_job(statistics, records, kind, self.tz, now)
            await self._commit(records)

    async def _commit(self, records):
        # Durable ledger first. A restart retries projection if Recorder fails.
        await self.store.async_save({"records": records})
        self.records = deepcopy(records)
        await self.publish()
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)


async def async_setup_entry(hass, entry):
    manager = LedgerManager(hass, entry)
    await manager.load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async def refresh(_now):
        # Recorder accepts completed hours. Retry records entered during the
        # first hour of a month, and extend flat totals without network polling.
        async with manager.lock:
            await manager.publish()
    entry.async_on_unload(async_track_time_change(hass, refresh, minute=5, second=0))
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
