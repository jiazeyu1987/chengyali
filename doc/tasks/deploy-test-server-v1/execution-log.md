# Execution Log

BDD: Deploy current code to test server -> Given the local repository has a committed current `main` and a reference deployment project exists, When publishing to the test server is requested, Then the release uses an explicit test-server target and reproducible artifact path, verifies runtime state after deployment, and does not execute production, backup, restore, or rollback actions.

GREEN: `git status -sb; git log -1 --oneline` -> PASS, current branch is clean and at `7d47099 docs: record update to latest`.

GREEN: ci-cd-environment-delivery skill -> PASS, deployment must identify target environment, commands, artifact, secrets, rollback, and verification evidence before declaring success.

GREEN: reference-project-scan -> PASS, located `D:\ProjectPackage\Int\IntRuoyiMaintance\ops\deploy\publish-int-ruoyi.ps1`, reference task evidence for test deployment, and reference docs pointing to server access and release/backup/restore policies.

GREEN: experience-preflight -> PASS, test server target is `172.30.30.58`; deployment is limited to `/opt/loan-interest-accrual` and port `18082`; production, backup, restore, rollback, database sync, and object storage sync are forbidden for this task.

GREEN: ssh-test-server-readonly-preflight -> PASS, SSH to `root@172.30.30.58` works; Docker is installed; systemd is present; `/` has about 34G free and `/var/lib/docker` has about 1.4T free.

GREEN: remote-port-preflight -> PASS, port `8000` is owned by `/opt/intpp-backend`, ports `18080` and `18081` are used, and port `18082` is free.

RED: docker-base-image-preflight -> FAIL, expected reason: both local Docker and remote Docker could not pull `python:3.12-slim` from Docker Hub because the connection timed out or was reset.

RED: remote-pip-download-preflight -> FAIL, expected reason: remote `pip download` for this project's requirements exceeded 3 minutes and was stopped as a task-owned hanging process.

GREEN: local-linux-wheelhouse-preflight -> PASS, local pip downloaded Linux CPython 3.12 wheels for `requirements.txt` into `.artifacts\deploy-test-server-v1\wheelhouse-linux`.

GREEN: deploy-contract-tests -> PASS, `.\.venv\Scripts\python.exe -m pytest tests\deploy\test_test_server_deploy_contract.py tests\bootstrap -q` returned `9 passed`.

GREEN: deploy-script-syntax -> PASS, PowerShell parsed `scripts\deploy-test-server.ps1`.

GREEN: implementation-commit -> PASS, committed deployment script and contract tests as `d281589`.

RED: deploy-script-remote-encoding -> FAIL, expected reason: first deployment of `chenyali-d281589-r202607151430` installed dependencies and started the service, but the piped remote bash script contained a BOM so bash did not execute `set -euo pipefail`, and the final status output returned non-zero.

GREEN: deploy-script-remote-encoding-fix -> PASS, changed the script to write a UTF-8 no-BOM remote deployment script file, upload it with `scp`, and execute it via `bash`.

GREEN: deployment-script-fix-tests -> PASS, `.\.venv\Scripts\python.exe -m pytest tests\deploy\test_test_server_deploy_contract.py tests\bootstrap -q` returned `9 passed`.

GREEN: script-fix-commit -> PASS, committed deployment script fix as `a02c95a`.

GREEN: publish-test-server -> PASS, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy-test-server.ps1 -ReleaseTag chenyali-a02c95a-r202607151435` returned status `pass`.

GREEN: test-server-runtime-state -> PASS, `/opt/loan-interest-accrual/current-release.json` records release tag `chenyali-a02c95a-r202607151435` and commit `a02c95acea2d7eec78da5a85dcea729a36e6430f`; `systemctl is-active loan-interest-accrual-test.service` returned `active`; `ss` shows Python listening on `0.0.0.0:18082`; remote `curl http://127.0.0.1:18082/health` returned `{"status":"ok"}`.

GREEN: external-http-smoke -> PASS, local HTTP checks returned health `{"status":"ok"}`, homepage HTTP 200, and template download content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

GREEN: real-calculate-smoke -> PASS, a real `.xlsx` upload to `http://172.30.30.58:18082/calculate` returned HTTP 200, period `2025-06-01至2025-06-30`, one preview row, and accrued interest `3.00`.

GREEN: playwright-browser-entry -> PASS, Chromium opened `http://172.30.30.58:18082/`, response HTTP 200, title and `h1` were `贷款利息自动计提`, console errors `0`, failed requests `0`.

GREEN: cicd-evidence-validation -> PASS, `python C:\Users\BJB110\.codex\skills\ci-cd-environment-delivery\scripts\validate_cicd_environment.py --evidence docs\environments\ci-cd-evidence.md` returned valid.

GREEN: task-closeout-preview -> PASS, cleanup preview kept task records and CI/CD evidence, deleted only `.artifacts\deploy-test-server-v1`, and had no blocked paths.

GREEN: task-closeout-apply -> PASS, cleanup apply deleted `.artifacts\deploy-test-server-v1` and had no blocked paths.

GREEN: final-remote-health-recheck -> PASS, current release remains `chenyali-a02c95a-r202607151435`, service is active, and health returns `{"status":"ok"}`.
