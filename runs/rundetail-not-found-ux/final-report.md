# RunDetail Not Found UX

## Summary

Fixed stale RunDetail behavior after a dev database reset.

## Change

- RunDetail now detects `404` / missing run responses.
- Polling stops after the run is confirmed missing.
- The UI shows a clear "Run not found" state with links to Runs, New Task, and Projects.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`

Both checks passed.
