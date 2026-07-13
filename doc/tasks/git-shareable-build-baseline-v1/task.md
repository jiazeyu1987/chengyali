# Git shareable build baseline

## Task Goal
Commit the current runnable source tree to git so the project can be cloned on another Windows computer, dependencies can be installed, and the application can be packaged from source.

## Milestones
- [x] M1: Inspect repository status, project scripts, and local-only artifacts.
- [x] M2: Exclude local transient artifacts from version control.
- [x] M3: Verify setup, tests, and Windows EXE packaging from the tracked source tree.
- [x] M4: Commit task-owned source, documentation, and verification records to git.

## Expected Verification
- `scripts/setup.ps1` completes with the pinned Python 3.12 environment.
- `pytest` passes for the committed test suite.
- `scripts/build-exe.ps1` produces a single-file Windows executable under `dist/`.
- `git status --short` shows no unintended untracked source files after commit.

## Current Status
completed

## Closeout Evidence
- Task cleanup preview completed with no blocked paths.
- Task cleanup apply completed with no deleted paths and no blocked paths.
- Commit readiness verified after setup, full pytest, and EXE packaging passed.

## Cleanup Candidates
- .artifacts/git-shareable-build-baseline-v1/

## Cleanup Keep
- doc/tasks/git-shareable-build-baseline-v1/task.md
- doc/tasks/git-shareable-build-baseline-v1/execution-log.md
- doc/tasks/git-shareable-build-baseline-v1/verification-report.md
