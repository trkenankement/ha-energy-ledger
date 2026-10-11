"""HA-native forms: configure, enter, correct and delete monthly bills."""
import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .ledger import KINDS, parse_import, validate_record, validate_timezone


class EnergyLedgerFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            timezone = dt_util.get_time_zone(self.hass.config.time_zone)
            try:
                if timezone is None:
                    raise ValueError("unsupported_timezone")
                validate_timezone(dt_util.utcnow(), timezone)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                return self.async_create_entry(title="Energy Ledger", data={
                    "currency": user_input["currency"],
                    "timezone": self.hass.config.time_zone,
                })
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("currency", default=self.hass.config.currency):
                vol.In(["TRY", "EUR", "USD", "GBP"]),
        }))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BillOptions()


class BillOptions(config_entries.OptionsFlow):
    @property
    def manager(self):
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["record", "import", "delete"])

    def summary(self, row):
        return f"{row['kind']} · {row['month']} · {row['consumption']} {KINDS[row['kind']]} · {row['cost']} {self.manager.currency}"

    async def async_step_import(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self.pending_batch = parse_import(user_input["bills"], dt_util.utcnow(), self.manager.tz)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                return await self.async_step_import_confirm()
        return self.async_show_form(step_id="import", errors=errors, data_schema=vol.Schema({
            vol.Required("bills", default=(user_input or {}).get("bills", "")):
                selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        }))

    async def async_step_import_confirm(self, user_input=None):
        if user_input is not None:
            try:
                await self.manager.save_records(self.pending_batch)
            except ValueError as err:
                return self.async_show_form(step_id="import_confirm", data_schema=vol.Schema({}),
                    errors={"base": str(err)}, description_placeholders=self.batch_preview())
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="import_confirm", data_schema=vol.Schema({}),
            description_placeholders=self.batch_preview())

    def batch_preview(self):
        existing = {(r["kind"], r["month"]) for r in self.manager.records if not r["deleted"]}
        replaced = sum((r["kind"], r["month"]) in existing for r in self.pending_batch)
        return {"count": str(len(self.pending_batch)), "replaced": str(replaced),
                "summary": "\n\n".join(self.summary(r) for r in self.pending_batch)}

    async def async_step_record(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                record = validate_record(user_input, dt_util.utcnow(), self.manager.tz)
            except ValueError as err:
                errors["base"] = str(err)
            else:
                self.pending = record
                return await self.async_step_confirm()
        defaults = user_input or {}
        return self.async_show_form(step_id="record", errors=errors, data_schema=vol.Schema({
            vol.Required("kind", default=defaults.get("kind", "gas")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(KINDS), translation_key="resource")),
            vol.Required("month", default=defaults.get("month", "")): str,
            vol.Required("consumption", default=str(defaults.get("consumption", ""))): str,
            vol.Required("cost", default=str(defaults.get("cost", ""))): str,
        }))

    async def async_step_confirm(self, user_input=None):
        if user_input is not None:
            try:
                await self.manager.save_record(self.pending)
            except ValueError as err:
                return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}),
                    errors={"base": str(err)}, description_placeholders={
                        "summary": self.summary(self.pending), "previous": "—"})
            return self.async_create_entry(title="", data={})
        row = self.pending
        previous = next((r for r in self.manager.records if r["kind"] == row["kind"]
                         and r["month"] == row["month"] and not r["deleted"]), None)
        return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}),
            description_placeholders={
                "summary": self.summary(row),
                "previous": self.summary(previous) if previous else "—",
            })

    async def async_step_delete(self, user_input=None):
        choices = {f"{r['kind']}:{r['month']}": f"{r['kind']} · {r['month']} · {r['consumption']} {KINDS[r['kind']]} · {r['cost']} {self.manager.currency}"
                   for r in self.manager.records if not r["deleted"]}
        if not choices:
            return self.async_abort(reason="no_records")
        if user_input is not None:
            self.delete_key = user_input.get("record")
            if self.delete_key not in choices:
                return self.async_show_form(step_id="delete", errors={"base": "record_not_found"},
                    data_schema=vol.Schema({vol.Required("record"): vol.In(choices)}))
            self.delete_label = choices[self.delete_key]
            return await self.async_step_delete_confirm()
        return self.async_show_form(step_id="delete", data_schema=vol.Schema({
            vol.Required("record"): vol.In(choices),
        }))

    async def async_step_delete_confirm(self, user_input=None):
        if user_input is not None:
            kind, month = self.delete_key.split(":")
            try:
                await self.manager.delete_record(kind, month)
            except ValueError as err:
                return self.async_show_form(step_id="delete_confirm", data_schema=vol.Schema({}),
                    errors={"base": str(err)},
                    description_placeholders={"summary": self.delete_label})
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="delete_confirm", data_schema=vol.Schema({}),
                                    description_placeholders={"summary": self.delete_label})
