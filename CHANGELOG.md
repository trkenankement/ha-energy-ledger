# Changelog

## 0.4.0

- Add an explicit Home Assistant Store `1.1 -> 1.2` migration that validates the complete legacy payload before saving and preserves every bill and deletion marker.
- Keep the existing `energy_ledger.<config-entry-id>` storage key stable and enable atomic Store writes so code updates do not replace the ledger with a partial file.
- Keep Recorder projection migration independent from ledger storage migration; only the six owned statistics can be rebuilt and bill rows remain the source of truth.
- Pin GitHub Actions dependencies to reviewed immutable commit SHAs and add a contract test that rejects mutable action tags.

Upgrading does not require re-entering bills. Take a full Home Assistant backup before deployment; a downgrade to an older integration should use that backup if the older code cannot interpret a future storage schema.

## 0.3.0

- Replace the dense hour-by-hour projection with sparse cumulative points at the baseline, bill months and latest completed hour. Projection work now scales with bill count instead of ledger age.
- Migrate 0.2.x projections by clearing and rebuilding only the six `energy_ledger:*` statistics; bill records remain in local storage and unrelated statistics are untouched.
- Remove the 3,660-day projection failure mode so retained historical records do not make integration setup fail as they age.
- Stop exposing full bill rows in summary entity attributes. Summary states now disclose only the total, bill count, latest month and owned statistic ID; Recorder history and old backups may still retain earlier attributes.
- Validate persisted ledger shape, duplicate keys and tombstones before projection.
- Separate the 360-row import limit from a 10,000-row retained-ledger safety limit so a rolling 120-month entry window does not expire older valid records.
- Reject unsupported non-hour-aligned timezones during setup instead of allowing an unusable installation.
- Handle stale delete confirmations and revalidation failures as form errors.
- Add sparse-history, incomplete-hour, timezone-window, storage-integrity and migration-contract scenarios.

This version is locally tested against Home Assistant 2026.10.1 but has not been installed on the user's live Home Assistant or released through HACS.

## 0.2.0

- Bulk bill entry through the native Home Assistant Configure menu, with a full review before confirmation.
- Explicit resource and unit validation, decimal comma support, input limits, and duplicate resource/month rejection within a batch.
- Existing bills for the same resource/month are replaced; omitted months and other resources are preserved.
- Readable single-bill and batch confirmation summaries.
- Local integration icons for light and dark themes, including high-resolution variants.
- Updated English and Turkish forms and guides.
- Expanded synthetic tests for bulk validation, replacement, repeat imports, and brand assets.

Existing features remain: monthly electricity, gas and water consumption/cost records; confirmed correction and deletion; local persistent storage; six summary entities; historical Energy statistics without cloud access or telemetry.

Monthly bills are accounting entries, not measured daily usage. HACS end-to-end installation has not yet been verified. No personal bills, Home Assistant backups or credentials are included in the repository.
