# Persistent Feishu Delivery Routing Implementation Plan (v2.12)

1. Add failing security tests for direct config loading, override confirmation, closed evidence, create-only bootstrap, invalid/expired rebuild, and delivery-mode isolation.
2. Implement direct persistent-config loading and remove route-result inputs.
3. Migrate all fixtures to the persistent config schema.
4. Align SKILL, QUALITY_GATE, OUTPUT_TEMPLATE, README, CHANGELOG, and design documentation; remove stale route-file and per-run-preflight language.
5. Run unittest discovery, py_compile, quick_validate, diff check, and stale-term searches before committing.
