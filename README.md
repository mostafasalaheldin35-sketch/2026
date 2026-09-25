# Sokhna Port 2026

Clean rebuild workspace for the approved Sokhna Port desktop baseline.

## Baseline policy
- The user-supplied **Sokhna Port v4.8.16.9 FINAL** EXE is the behavioral/UI reference.
- Do **not** use v4.8.16.11 as a base.
- Preserve the original global font.
- Apply changes as integrated source changes, not as a late runtime monkey-patch.

## Approved change set
1. Unified item validity logic, including incomplete default and manual status only when no expiry date exists.
2. All user-facing dates are DD/MM/YYYY with calendar selection.
3. Child/sub-items with independent dates, attachments, status, parent summary, and inline expand/collapse.
4. NCR requirement/reference sourced from the current inspection checklist.
5. Compact company profile editor with field placement: table / below table / hidden, reorderable, and addable fields.
6. Safe application-wide autosave and navigation.
7. SQLite + physical attachments storage with selectable data root.
8. Automatic Daily / Weekly / Monthly backups, 90-day retention, plus per-company Excel recovery workbooks.

See `docs/INTEGRATION_AUDIT.md` before changing code.
