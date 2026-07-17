# Persistent Feishu Delivery Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Feishu Listing delivery route derive from persistent, non-secret Skill configuration rather than per-task model choice.

**Architecture:** Add a focused delivery configuration CLI with locked atomic storage and deterministic route resolution. Upgrade the manifest to schema v8 so init consumes route-resolution evidence, while Skill documentation separates bootstrap from runtime and forbids silent fallback.

**Tech Stack:** Python 3 standard library, unittest, Markdown AgentSkill documentation, Git/GitHub.

## Global Constraints

- Scope excludes image-only ecommerce creative strategy.
- Default configured Feishu route is `docx`; `interactive_card` requires configuration or explicit per-run user override.
- No credentials or tokens may be persisted in the Skill delivery config.
- Runtime does not repeat bootstrap checks unless configuration or an actual call fails.
- `preview_images` is never a formal delivery route.
- Old manifests must be rebuilt with `init --force`.

---

### Task 1: Persistent delivery configuration CLI

**Files:**
- Create: `scripts/delivery_config.py`
- Create: `tests/test_delivery_config.py`

**Interfaces:**
- Produces CLI commands `bootstrap`, `status`, `resolve`, `record-success`, `invalidate`.
- Produces route JSON containing `delivery_route`, `delivery_route_source`, `delivery_config_schema_version`, and `delivery_override`.

- [ ] Write failing tests for missing/corrupt config, bootstrap, secret rejection, deterministic resolution, explicit override, invalidation, success timestamp, and concurrent bootstrap.
- [ ] Run `python3 -m unittest tests.test_delivery_config -v` and verify failures are caused by the absent CLI.
- [ ] Implement schema v1 validation, lock file, atomic save, and commands with no external dependencies.
- [ ] Run `python3 -m unittest tests.test_delivery_config -v` and verify all tests pass.
- [ ] Commit `feat: add persistent delivery route configuration`.

### Task 2: Manifest schema v8 consumes controlled route evidence

**Files:**
- Modify: `scripts/run_manifest.py`
- Modify: `tests/test_run_manifest.py`
- Modify: `tests/test_manifest_v28.py`
- Modify: `tests/test_final_review_security.py`
- Modify: `tests/test_delivery_directory_contract.py`
- Modify: `tests/test_no_post_qa.py`

**Interfaces:**
- Consumes route JSON from Task 1 via `init --delivery-route-file PATH`.
- Records route/source/config schema/override and dispatches `docx` versus `interactive_card` validation.

- [ ] Add failing tests proving `--delivery-mode` is rejected, route file is mandatory, only allowed route sources pass, explicit overrides require user evidence, and preview cannot satisfy formal delivery.
- [ ] Run targeted manifest tests and verify expected failures.
- [ ] Upgrade schema and init parser, replace all `delivery_mode` branches, and enforce route evidence.
- [ ] Migrate existing fixtures to controlled route files.
- [ ] Run all manifest/directory/security tests and verify green.
- [ ] Commit `feat: bind manifests to configured delivery routes`.

### Task 3: Skill behavior contract and release documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `QUALITY_GATE.md`
- Modify: `OUTPUT_TEMPLATE.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_skill_contract.py`

**Interfaces:**
- Documents bootstrap-only environment checks and direct runtime resolution.
- Uses exact route names `docx`, `interactive_card`, and non-formal `preview_images`.

- [ ] Add failing contract tests for persistent config, bootstrap triggers, no repeated preflight, explicit fallback confirmation, and route naming.
- [ ] Run `python3 -m unittest tests.test_skill_contract -v` and verify contract failures.
- [ ] Update the Skill and templates, remove contradictory per-task preflight/free-route language, bump metadata to `2.12.0`, and add migration/release notes.
- [ ] Run contract tests and verify green.
- [ ] Commit `docs: enforce persistent Feishu delivery routing`.

### Task 4: Full verification, review, merge, and installation sync

**Files:**
- Verify all changed files.
- Sync approved repository tree into both local Skill installations after merge.

**Interfaces:**
- Produces GitHub main commit and byte-equivalent local installations.

- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `python3 -m py_compile scripts/*.py`.
- [ ] Run Skill Creator `quick_validate.py .`.
- [ ] Run `git diff --check` and focused searches for stale `delivery_mode`/ambiguous `card` behavior.
- [ ] Review the full diff against the design and repair any correctness or scope gaps with tests first.
- [ ] Push the feature branch, create and merge the GitHub PR, then update repository main.
- [ ] Sync the merged tree to workspace and user-global Skill directories without copying `.git` or runtime secrets.
- [ ] Re-run quick validation and unittest from the installed workspace Skill.
- [ ] Compare normalized tree hashes and confirm version `2.12.0` in repository and both installations.
