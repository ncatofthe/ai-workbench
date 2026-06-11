# Requirements Spec Stage

## Summary

The orchestrator now includes an early product discovery stage. Each run produces a product spec and clarification questions before generating the execution plan.

## Changes

- `backend/src/orchestrator/engine.py`
  - Added `Analyze product requirements` run step.
  - Added `Save requirements artifacts` run step.
  - Generates `product-spec.md`.
  - Generates `clarification-questions.md`.
  - Planning prompt now includes product spec and clarification questions.
  - Final report now includes product spec, clarification questions, and the expanded artifact list.
  - Offline/failure fallback generates a conservative product spec and useful default questions.
- `backend/tests/test_run_steps.py`
  - Updated expected timeline to include requirements/spec steps.
  - Verifies `product-spec.md` and `clarification-questions.md` are written.
  - Verifies run artifacts include the new files.
- `backend/tests/test_cancellation.py`
  - Updated cancellation expectation to stop during the requirements stage.

## Verification

- `python3 -m py_compile backend/src/orchestrator/engine.py backend/tests/test_run_steps.py backend/tests/test_cancellation.py` passed.
- `.venv/bin/python -m pytest -q tests/test_run_steps.py tests/test_cancellation.py` passed: 3 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed: 16 backend tests.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- The system creates clarification questions, but there is not yet a UI loop for the user to answer them and resume the run.
- The spec stage is still orchestrator-only, not delegated to a product-manager agent.
- The run still stops after planning; autonomous implementation is not enabled yet.
