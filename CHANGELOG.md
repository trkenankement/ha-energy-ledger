# Changelog

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
