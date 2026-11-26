# flagpact

Check a Flagsmith config change against every app version before you publish it.

A Flagsmith remote-config value changes, and the apps that read it get the new value at once, with no redeploy. That is the point of remote config. It also means an old build still in people's hands, one that expects the old shape, can crash the moment you save. flagpact tells you which app versions would break before the change goes live, and fixes it by keeping those versions on the previous value.

Built for the Flagsmith "Toggle Wars" hackathon, Track 03: Build on Open Source Flagsmith. It works with self-hosted Flagsmith and has been tried on 2.294.0.

## What it does

- **Records what each app version reads.** Run an app version's own tests once. flagpact records which JSON fields they read, which are required and what types they expect. That is the version's contract.
- **Checks a pending value against every version.** Edit the new value in the console, or pass it to `flagpact check`. flagpact resolves which value each version would get through Flagsmith's segments, then replays each version's own tests against it.
- **Shows what each version would display.** The live app previews show the real banner for each version, or a crash.
- **Fixes the break.** It creates a Flagsmith segment on the `app_version` trait that keeps older versions on the previous value, then you publish the change for everyone else.
- **Rehearses on a clone.** Before anything touches your environment, it clones the environment through Flagsmith's API, applies and publishes the fix there, probes each version, and deletes the clone.
- **Watches for edits made outside flagpact.** If someone changes the value in the Flagsmith dashboard and it breaks a version, flagpact shows what changed and offers "Protect older versions" or "Restore previous value".
- **Runs in CI.** `flagpact check` and a GitHub Action fail the build when a pending value would break a version.

## Quick start

You need Docker, Python 3.10 or newer, and Node 22 (only to build the console).

```bash
bash scripts/demo.sh
```

This starts a self-hosted Flagsmith and its database in Docker, creates an organisation, project and environment, seeds the `home_banner` config, installs flagpact, builds the console and starts it.

- Console: http://127.0.0.1:8765
- Demo controls: http://127.0.0.1:8765/demo (adds a button that simulates an edit made in the Flagsmith dashboard)
- Flagsmith: http://127.0.0.1:8000

If those ports are taken, set `FLAGSMITH_PORT` before the first run and `FLAGPACT_PORT` when starting.

The Flagsmith stack listens on 127.0.0.1 only. Secrets are generated at random into `stack/.env` and `.flagpact-keys.env`, both git-ignored.

To reset the demo value at any time:

```bash
.venv/bin/python scripts/seed.py .flagpact-keys.env
```

## Using the console

1. Open the console. It shows three demo app versions, 1.0.0, 2.0.0 and 3.0.0, with what each one reads.
2. Click "Try a breaking change", or edit the new value. flagpact checks it and shows which versions break, what each would display, and the suggested fix.
3. Optional: "Rehearse on a clone" proves the fix on a real copy of the environment.
4. "Apply the fix" creates the protective rule. "Publish your change" then changes the default for everyone else.
5. Undo removes the rule and restores the default.

## Command line and GitHub Action

```bash
flagpact check --value new-value.json --env-file .flagpact-keys.env
```

`--value` takes a JSON file, inline JSON or `-` for stdin. Add `--json` for a report.

| Exit code | Meaning |
|---|---|
| 0 | No app version would break |
| 1 | At least one app version would break |
| 2 | Configuration or API error |

The check is read-only. It needs `FLAGSMITH_API_URL` and the environment's server-side key (`FLAGSMITH_ENV_SERVER_KEY`). It never needs a management key. The report never contains keys.

As a GitHub Action, in the repository that holds your app and its tests:

```yaml
- name: Check the pending config value
  uses: Nithinaug/flagpact@v0.1.0
  with:
    value: config/home_banner.json
    api-url: ${{ vars.FLAGSMITH_API_URL }}
    server-key: ${{ secrets.FLAGSMITH_ENV_SERVER_KEY }}
```

The job fails when a version would break and writes a table of results to the job summary. The runner must be able to reach your Flagsmith instance.

## How Flagsmith is used

- **Remote config:** `home_banner` is a feature whose value is JSON. Each app version reads it through the Flagsmith SDK.
- **Segments and the semver operator:** the fix is a segment with the rule `app_version < 3.0.0`, plus an optional "trait is not set" condition for builds that send no version.
- **Segment overrides and priority:** older versions get the previous value, everyone else gets the default.
- **Environment document and the flag engine:** checks run against a patched copy of the environment document, using Flagsmith's own engine, so results match the server.
- **SDK offline mode:** each version's tests replay against that document, with no network.
- **Transient identities:** probes send traits without storing anything in Flagsmith.
- **Environment clone and the admin API:** used for the rehearsal and for writing the rule and the default.

## Connect your own app

The app must read the config through flagpact's wrapper. It wraps the Flagsmith Python SDK and records what is read.

```python
from flagpact import FlagpactClient

client = FlagpactClient.from_env()
banner = client.config("home_banner")
title = banner["title"]
subtitle = banner.get("subtitle", "")
```

The wrapper reads `FLAGPACT_APP_VERSION` (the trait value this build sends) and either `FLAGSMITH_API_URL` with `FLAGSMITH_ENV_CLIENT_KEY`, or `FLAGPACT_DOCUMENT` for offline replay.

Record the contract by running the app's tests with the recorder:

```bash
FLAGPACT_APP_VERSION=1.0.0 FLAGPACT_RECORD_DIR=contracts FLAGPACT_SOURCES=app.py \
FLAGPACT_DOCUMENT=demo/environment.json python -m pytest -p flagpact.pytest_plugin
```

Then add the version to `flagpact.json`:

```json
{
  "flag": "home_banner",
  "trait": "app_version",
  "contracts": "contracts",
  "versions": [
    {"version": "1.0.0", "directory": "demo/v1", "share": 22, "users": 41200, "platforms": "iOS · Android"}
  ],
  "missing_trait": {"share": 4, "users": 7400}
}
```

`share`, `users` and `platforms` are optional. The numbers in this repository are sample values for the demo, not real traffic. In real use they come from your own analytics, and the console hides them when they are absent.

## Limits

- The wrapper and the test replay are Python only.
- A contract only holds what the tests actually read. A field no test reads is invisible to flagpact.
- It prevents breaks only for changes that go through the console or `flagpact check`. Open-source Flagsmith has no hook that runs before a dashboard edit is saved, and no change requests. Watch mode detects such an edit within a few seconds, after the fact.
- Builds that send no `app_version` trait cannot be checked. The fix can hold them on the previous value, but flagpact cannot tell what they read.
- Percentage rollouts, multivariate variations and identity overrides on the flag are detected and flagged with a notice. Versions affected by a split are shown as "Not checked", never "Safe". They are not fully evaluated.
- The enabled state of the feature is ignored. Only the value is checked.
- Writes go to a local Flagsmith only. flagpact refuses any other API URL.
- Replay runs each version's test command in its own folder. Tests are code, so point flagpact only at code you trust.

## Development

```bash
pip install -e . pytest
python -m pytest
cd ui && npm install && npm run build
```

The console is built into `ui/dist`, which is git-ignored. Run the build once after cloning.

## License

MIT. See [LICENSE](LICENSE).
