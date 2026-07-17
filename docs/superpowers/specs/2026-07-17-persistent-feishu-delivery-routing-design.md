# Persistent Feishu Delivery Routing Design (v2.12)

## Decision

The persistent delivery config is the only default-route authority. `run_manifest.py init --delivery-config` loads and validates it directly; no hand-authored route result or bootstrap result is accepted. A one-run override requires an explicit route plus non-empty user confirmation, is recorded in the manifest, and never changes the persistent default.

## Bootstrap evidence

Evidence is a closed, credential-free schema: evidence version, capability version, typed route capabilities, timezone-aware verification and expiry timestamps. Bootstrap is create-only while the existing config is current. Invalid, invalidated, expired, or structurally damaged configs may be atomically rebuilt under the config lock. File and parent directory are fsynced.

## Delivery isolation

`docx` and formal `interactive_card` evidence are mutually exclusive. Ordinary `preview_images` is not a formal route and cannot satisfy or masquerade as interactive-card delivery. Content-only runs still require evidence for their selected formal route.

## Recovery

Schema v3-v7 manifests may be rebuilt with `init --force`; a valid current v8 manifest is create-only, while an invalid v8 may be explicitly reinitialized with monotonic generation and revision.
