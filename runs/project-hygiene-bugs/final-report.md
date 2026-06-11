# Project Hygiene Findings

## Confirmed Issues

`[BUG-001] Dev database polluted with stale pytest projects`

- Pages: New Task / Tools
- Problem: project lists showed entries such as `p`, `p2`, `p6`, `t`.
- Cause: `data/workbench.db` contained project rows pointing to deleted pytest temp paths under `/private/var/folders/.../pytest-of-hatss/...`.
- Severity: High for UX testing.

`[BUG-002] Tools page crashes with API 500 on missing project path`

- Page: Tools
- Problem: selected project pointed to a deleted pytest temp directory, so git status failed with a filesystem error.
- Expected: UI/backend should return a clear "Project path does not exist" message.
- Severity: Medium/High.

`[UX-001] Project dropdown is unreadable with many bad or duplicate names`

- Page: New Task
- Problem: dropdown shows project name only, making bad duplicate records hard to identify.
- Expected: show name, short path, and invalid/missing path badge.
- Severity: Medium.

## Cleanup Performed

- Backed up `data/workbench.db` to `backups/workbench_20260520_124340.db`.
- Removed polluted dev database files.
- Reinitialized a clean database.
- Created one clean sandbox project: `Test Calculator Project`.
