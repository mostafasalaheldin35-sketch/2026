# Integration audit

This document is the change-impact checklist for the 2026 rebuild. No feature is considered complete until every dependent surface below is checked.

## Baseline
Reference: user-supplied Sokhna Port v4.8.16.9 FINAL EXE.
Known extracted UI SHA-256:
`61a7f549eecb803a7996c528302774ba5d1f89083e811da53cffe70be37f1705`

The later v4.8.16.11 base is not identical and must not be treated as the approved baseline.

## 1. Item validity
Single canonical function must drive:
- dashboard counters
- company item table
- all-items views
- company detail linked fields
- reports / Word exports
- CSV / Excel exports
- filters
- child item summaries
- inspection snapshots where validity is displayed

Rules:
- expiry present: automatic date-based status
- >60 days: valid
- 0..60 days: near expiry
- past: expired
- no expiry: manual valid / invalid
- untouched/unselected no-expiry item: incomplete
- manual state must never override an existing expiry date

## 2. Dates
Single display formatter: DD/MM/YYYY.
Check:
- every form input
- every table
- dashboard
- company fields
- items and child items
- inspections
- findings / NCR
- reports
- exports
- printed output
- snapshots
- old saved ISO values

Storage may remain ISO YYYY-MM-DD.

## 3. Child items
Check:
- create/edit/delete/reorder if supported
- independent issue/expiry/manual state
- independent attachments
- parent-child persistence
- parent summary counts
- company items render
- expand/collapse under parent row
- exports and reports
- company linked profile values if linked to a parent
- backup/restore/sync integrity

## 4. NCR source mapping
Source only from the current inspection's applicable inspection checklist.
Requirement and reference must remain synchronized to the same source row.
Persist:
- requirement name
- reference number only
Check edit of old findings and missing historical source rows.

## 5. Company profile editor
Compact row-based editor.
Per field placement:
- table
- below table
- hidden
Fields automatically grouped by placement and reorderable within each group.
Fields remain addable.
Preserve:
- type
- linked item
- linked property
- report placement
- legacy data
- inspection snapshots
- report behavior

## 6. Autosave / navigation
Application-wide dirty tracking.
Priority:
1. real save
2. on navigation, force pending real save
3. if validation prevents save, retain draft and still allow navigation with a clear warning
Never deadlock navigation.
Check all forms/dialogs and duplicate-submit protection.

## 7. SQLite and attachments
Keep one master SQLite database.
Selectable stable data root.
Physical attachments are authoritative; DB stores metadata/path/hash.
Organize human-readable folders for companies/items/inspections while maintaining stable IDs internally.
Moving data root must copy, verify, switch, and retain old root as safety copy.

## 8. Backup
Automatic:
- Daily
- Weekly
- Monthly
Retention: delete backup artifacts older than 90 days only.
Never delete live DB or live attachments.

Each scheduled backup includes:
- restorable SQLite + attachments backup
- per-company XLSX
Each company workbook includes:
- Items sheet matching company items view
- Inspections sheet with inspection rows and findings/NCR beneath each inspection
- hyperlinks to physical attachment folders/files

Missed scheduled backup should be caught up on next program start.

## Cross-cutting regression checks
- company deletion/archive
- item archive/N.A.
- master-list propagation
- inspection snapshots
- report generation
- Word export
- Excel export
- CSV export
- sync / restore
- attachments manager
- dashboard counters
- search/filter
- migration of existing v4.8.16.9 data
