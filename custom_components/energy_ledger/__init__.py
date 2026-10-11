"""Local bill recording and historical Energy statistics."""
import asyncio
from copy import deepcopy
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder import get_instance
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (DOMAIN, PLATFORMS, PROJECTION_VERSION, SIGNAL_UPDATED,
                    STORAGE_MINOR_VERSION, STORAGE_VERSION)
from .ledger import (KINDS, merge_records, migrate_storage_data, remove,
                     statistics, upsert, validate_record,
                     validate_stored_records)


class LedgerStore(Store):
    """Versioned, atomically written storage with explicit migrations."""

    async def _async_migrate_func(self, old_major_version, old_minor_version,
                                  old_data):
        return migrate_storage_data(old_major_version, old_minor_version,
                                    old_data)


class LedgerManager:
    """Serialize local commits; Recorder data is a rebuildable projection."""
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.records = []
        # Keep the storage key stable across releases. HA migrates 1.1 to 1.2
        # only after the complete old payload validates, then replaces it with
        # an atomic write. Integration updates therefore retain every bill.
        self.store = LedgerStore(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}",
            atomic_writes=True, minor_version=STORAGE_MINOR_VERSION)
        self.lock = asyncio.Lock()
        self.tz = ZoneInfo(entry.data["timezone"])
        self.currency = entry.data["currency"]
        self.projected = {}
        self.projection_ready = False

    async def load(self):
        data = await self.store.async_load() or {}
        self.records = validate_stored_records(data.get("records", []))
        self.projection_ready = data.get("projection_version") == PROJECTION_VERSION
        if self.projection_ready:
            await self.publish()
        return not self.projection_ready

    def storage_data(self):
        return {"records": self.records, "projection_version": PROJECTION_VERSION}

    async def clear_statistics(self):
        """Remove only this integration's six series before a format rebuild."""
        done = asyncio.Event()

        def finished():
            self.hass.loop.call_soon_threadsafe(done.set)

        statistic_ids = [f"{DOMAIN}:{kind}_{metric}"
                         for kind in KINDS for metric in ("consumption", "cost")]
        get_instance(self.hass).async_clear_statistics(statistic_ids, on_done=finished)
        async with asyncio.timeout(60):
            await done.wait()

    async def migrate_projection(self, _hass):
        """Rebuild after HA starts so Recorder can process its queued clear."""
        async with self.lock:
            if self.projection_ready:
                return
            await self.clear_statistics()
            self.projected.clear()
            await self.publish()
            await get_instance(self.hass).async_block_till_done()
            await self.store.async_save(self.storage_data())
            self.projection_ready = True

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
        stored = {"records": records}
        if self.projection_ready:
            stored["projection_version"] = PROJECTION_VERSION
        await self.store.async_save(stored)
        self.records = deepcopy(records)
        if self.projection_ready:
            await self.publish()
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)


async def async_setup_entry(hass, entry):
    manager = LedgerManager(hass, entry)
    migration_needed = await manager.load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if migration_needed:
        entry.async_on_unload(async_at_started(hass, manager.migrate_projection))
    async def refresh(_now):
        # Recorder accepts completed hours. Retry records entered during the
        # first hour of a month, and extend the latest sparse cumulative tail.
        async with manager.lock:
            if manager.projection_ready:
                await manager.publish()
    entry.async_on_unload(async_track_time_change(hass, refresh, minute=5, second=0))
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
