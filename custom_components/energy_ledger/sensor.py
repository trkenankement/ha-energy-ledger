"""Summary entities. Historical statistics are owned by the external source."""
from decimal import Decimal
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN, SIGNAL_UPDATED
from .ledger import KINDS


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BillSensor(manager, kind, metric)
                        for kind in KINDS for metric in ["consumption", "cost"]])


class BillSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, manager, kind, metric):
        self.manager, self.kind, self.metric = manager, kind, metric
        self._attr_unique_id = f"{DOMAIN}_{kind}_{metric}"
        self._attr_name = f"Energy Ledger {kind} {metric}"
        self._attr_native_unit_of_measurement = manager.currency if metric == "cost" else KINDS[kind]
        self._attr_device_class = (SensorDeviceClass.MONETARY if metric == "cost" else
                                  {"electricity": SensorDeviceClass.ENERGY,
                                   "gas": SensorDeviceClass.GAS,
                                   "water": SensorDeviceClass.WATER}[kind])
        # No state_class: do not create a second live statistics stream.

    @property
    def native_value(self):
        return sum((Decimal(r[self.metric]) for r in self.manager.records
                    if r["kind"] == self.kind and not r["deleted"]), Decimal(0))

    @property
    def extra_state_attributes(self):
        return {"statistic_id": f"{DOMAIN}:{self.kind}_{self.metric}",
                "accounting_method": "monthly_bill_at_month_start_not_daily_measurement",
                "bills": [dict(r) for r in self.manager.records if r["kind"] == self.kind and not r["deleted"]]}

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED,
                                                     self.async_write_ha_state))
