---
name: flagpact-safe-rollout
description: Change a Flagsmith JSON config value without breaking older app versions. Checks every app version, builds a protective segment, applies and publishes it with the Flagsmith CLI after a person approves, and keeps rollback ready. Use when asked to change, roll out or fix a remote config value that old app versions still read.
---

# Change a Flagsmith config safely across app versions

Old app versions keep running for months. A config change that is fine for the newest app can crash an older one. This skill checks that first, and if a version would break, keeps it on the previous value with a segment on `app_version`.

Stop and ask a person at the two marked gates. Never write to Flagsmith before gate 1.

## Before you start
- `flagsmith config` shows the right environment. If it is production, say so at each gate.
- Self-hosted Flagsmith needs a host-scoped admin key. For `http://127.0.0.1:8010/api/v1` export `FLAGSMITH_API_KEY_127_0_0_1_8010` (dots and colons become `_`), plus `FLAGSMITH_API_URL`, `FLAGSMITH_ORGANISATION`, `FLAGSMITH_PROJECT` and `FLAGSMITH_ENVIRONMENT` (the environment's client-side SDK key), or run `flagsmith init` once. A plain `FLAGSMITH_API_KEY` is ignored for any host except api.flagsmith.com.
- `flagpact.json` exists in the project. If not, run `flagpact import <repo-or-folder> --out flagpact.json` and ask the person to review it.
- `FLAGSMITH_API_URL` and `FLAGSMITH_ENV_SERVER_KEY` are set for `flagpact` (read-only). Mind the difference: the Flagsmith CLI wants the host root (`http://127.0.0.1:8010`, it adds `/api/v1` itself), while `flagpact` wants the URL ending in `/api/v1`. Pass the CLI's with `--api-url` and keep the variable for `flagpact`.

## Steps
1. Read the live value. `flagsmith flag get FLAG --jq .` first to see the shape once. Keep it as `previous.json`, it is the rollback.
2. Write the proposed value to `new.json`.
3. Check every app version. `flagpact check --value new.json --config flagpact.json --json`
   - exit 0: nothing breaks, go to step 6
   - exit 1: read only `plan_id`, `breaks`, `at_risk` and `fix` from the report, ignore the rest. Keep the `plan_id`.
   - exit 2: the check could not run, report the `error` and stop
   - exit 3: only with `--expect-plan`, the plan is stale, see gate 2
4. **Gate 1.** Tell the person: which versions break, how many users (`at_risk.users`), and the fix (`fix.keep_below`). Wait for a yes.
5. Apply the fix. Write `fix.rule` (one rule object, not a list) to `rules.json`, then:
   - `flagsmith segment create "<fix.segment>" --rules @rules.json`
   - `flagsmith flag update FLAG --segment "<fix.segment>" --type string --value '<fix.keep_value as JSON>' --enable --priority 0`
6. **Gate 2.** First run `flagpact check --value new.json --config flagpact.json --expect-plan <plan_id> --json`. Exit 3 means Flagsmith or the value changed since the person approved, so stop, say so, and go back to step 3. If the environment is not the local demo, the person must type its name before you publish. Otherwise ask the person to confirm publishing. Then `flagsmith flag update FLAG --type string --value '<new.json as JSON>'`.
7. Verify. Run step 3 again, it must exit 0. For the oldest version, `flagsmith evaluate FLAG --trait app_version=<oldest> --json` must still return the previous value.

## Roll back
- `flagsmith flag update FLAG --type string --value '<previous.json as JSON>'`
- `flagsmith flag delete FLAG --segment "<fix.segment>"`
- `flagsmith segment delete "<fix.segment>"`

## Keep output small
- Use `--json` with `--jq` and read only the field you need.
- Never print the environment document or the full flag list.
- The `flagpact check --json` report is already compact. Read `status`, `breaks`, `at_risk` and `fix`.
