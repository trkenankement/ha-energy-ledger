# Energy Ledger

[Türkçe kılavuz](README.tr.md)

Record monthly electricity, natural gas and water bills inside Home Assistant, then use their consumption and cost statistics in the Energy dashboard. No bank account, cloud account or meter hardware is required.

This is a **custom integration**, not an official Home Assistant integration or Supervisor app. Version 0.2.0 is a development release. Synthetic tests with real Home Assistant 2026.10.1, Recorder and persistent storage passed. Monthly and annual consumption and cost were verified in a live HA Energy dashboard. Installation through a HACS custom repository, followed by restart and record persistence checks, also passed.

## 1. What it records

| Resource | Consumption unit | Cost |
| --- | --- | --- |
| Electricity | kWh | Selected currency |
| Natural gas | m³ | Selected currency |
| Water | m³ | Selected currency |

One record per resource and accounting month. Entering that same pair again replaces the previous bill instead of adding it twice. Six summary entities show recorded totals; historical consumption and cost are published as separate Recorder statistics.

Only enter a quantity whose unit is confirmed on the bill. Gas billed in kWh is not automatically converted to m³. Missing bills do not establish zero consumption.

## 2. Install

Requirements: Home Assistant 2026.10 or newer, Recorder enabled, and a time zone with whole-hour UTC offsets. The currency and time zone are fixed at initial setup. Supported currencies: TRY, EUR, USD and GBP. No additional pip requirements are installed by this integration; it uses libraries already supplied by Home Assistant.

Take a full Home Assistant backup first.

### Manual installation

1. Download the source from [ha-energy-ledger](https://github.com/trkenankement/ha-energy-ledger).
2. Copy `custom_components/energy_ledger` into `/config/custom_components/`, preserving the folder structure.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Energy Ledger** and select the currency.

### HACS custom repository

The repository is public, but is not in the default HACS catalogue. Use **HACS → Custom repositories → repository URL → Integration → download → restart**. This installation path was verified with v0.2.0. Installation downloads code from GitHub, not your bills. Updates are not automatic `git pull` operations.

## 3. Add or correct a bill

1. Open the integration's **Configure** menu and select **Add / correct bill**.
2. Select the resource and enter its accounting month as `YYYY-MM`, for example `2026-01`.
3. Enter the month's consumption and total bill cost. A decimal point or comma is accepted; do not use thousands separators. Values must be between 0 and 1,000,000,000, with at most six decimal places.
4. Review the new and previous values, then confirm. Closing the form before confirmation does not save the bill.

Use the consumption period, not automatically the payment or due-date month. A bill spanning two months needs an explicit accounting choice; the integration does not infer or prorate it. The current month and previous 119 months can be entered.

To correct a bill, enter the same resource and month again. To remove one, choose **Delete bill**, select the record and confirm. Only Energy Ledger statistics are recalculated; other integrations' history is not changed. A zero-valued deletion marker remains in local storage so old statistics can be overwritten. This is not secure erasure from Recorder history or backups.

### Import several bills

Choose **Import bills** in Configure and paste semicolon-separated rows with the exact header `kind;month;unit;consumption;cost`. Use `electricity` with `kWh`, or `gas`/`water` with `m3` (also accepts `m³`). Costs use the currency selected at setup. Decimal commas are accepted.

Review every row before confirming. All rows are validated before saving; duplicate resource/month pairs within one import are rejected. An existing resource/month is replaced, while months omitted from the import are preserved. At most 360 rows and 65,536 characters are accepted. Recorder publishing follows the local save; this is not an atomic database transaction and interrupted publishing is rebuilt on startup.

## 4. Connect the Energy dashboard

After saving a bill, let Recorder process its queue. Open **Settings → Dashboards → Energy**, choose the relevant electricity/gas/water source, and select:

| Resource | Consumption statistic | Cost statistic |
| --- | --- | --- |
| Electricity | `energy_ledger:electricity_consumption` | `energy_ledger:electricity_cost` |
| Natural gas | `energy_ledger:gas_consumption` | `energy_ledger:gas_cost` |
| Water | `energy_ledger:water_consumption` | `energy_ledger:water_cost` |

Use the corresponding total-cost statistic when configuring cost tracking. These are external statistics, not the six summary sensor entities. If no bill has been saved for a resource, its statistics may not yet be offered.

**Choose monthly or yearly views.** A whole monthly bill is allocated to the selected month's first hour. Daily/hourly graphs therefore show an accounting spike, not measured daily usage. No invented daily breakdown is generated.

For electricity, treat the bill as the whole-home grid total and smart plugs as individual-device breakdowns. Do not add the same measured household total and its bill as two grid sources: that double-counts consumption.

## 5. Privacy and access

The integration contains no cloud client, telemetry or outbound network code. Bill data stays with Home Assistant in its `.storage` ledger, Recorder statistics and sensor attributes. Installation/update tooling and unrelated HA integrations can still use the internet; this integration is not a firewall. No live packet-capture claim is made.

Local does **not** mean admin-only or encrypted by this component. Active bill rows are included in sensor attributes and can be visible to users or clients allowed to read those states. HA backups may also contain the data. Native configuration forms rely on Home Assistant's administrator permissions. Protect HA access, host files and backups; never publish actual bills, `.storage`, credentials or backup archives to GitHub.

Unloading/removing the integration does not automatically purge its stored bills or Recorder history.

## 6. Limits and troubleshooting

- One household and one monthly record per resource; multiple meters, tariff calculations, currency conversion and PDF parsing are not supported.
- Currency/time zone changes do not revalue historical entries. Non-whole-hour time zones are rejected.
- The hourly projection is bounded to 3,660 days. Retained records do not automatically expire, so a ledger approaching that age needs migration; do not treat it as indefinite archival support.
- Empty summary totals describe an empty ledger, not proof of zero household usage.
- If statistics do not appear, verify a bill was confirmed and Recorder is running; check HA logs for `energy_ledger`. Do not replace unrelated working Energy sources while troubleshooting.

## 7. Verification and development

Run the synthetic unit and contract tests from the repository root:

```sh
python -m unittest discover -s tests -v
```

Tests cover corrections, repeated entry, deletion, independent monthly totals, malformed input, time boundaries, translation structure and import boundaries. Ten concurrent corrections and persistence in a second process passed in isolated real HA. Live monthly/annual graphs and HACS installation were checked separately. These checks are not a comprehensive stress test or hassfest certification. Source-level no-network tests are not packet capture. The implementation uses HA's `async_add_external_statistics` API, cumulative sums and hourly UTC timestamps.
