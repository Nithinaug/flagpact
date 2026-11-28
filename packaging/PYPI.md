# flagpact

Check a Flagsmith config change against every app version before you publish it.

A Flagsmith remote-config value changes, and the apps that read it get the new value at once. An old build still in people's hands can crash the moment you save. flagpact replays each app version's own tests against the new value, shows which versions would break and how many users are on them, and keeps those versions on the previous value with a segment on `app_version`.

## Install

```bash
pip install flagpact
```

Python 3.10 or newer.

## Use

Check a pending value against every app version. It exits 1 if a version would break, and 0 if none would:

```bash
flagpact check --value new.json --config flagpact.json
```

Read a public GitHub repository (or a local folder) and draft a `flagpact.json`. Release tags such as `v1.0.0` and `v2.0.0` each become an app version:

```bash
flagpact import https://github.com/owner/repo --out flagpact.json
```

Open the local console, against a Flagsmith on your own machine:

```bash
flagpact-server .flagpact-keys.env flagpact.json
```

## More

The console, the one-command demo, the GitHub Action, the agent skill for the Flagsmith CLI, and the full documentation are in the repository: https://github.com/Nithinaug/flagpact

flagpact writes only to a Flagsmith on `127.0.0.1` or `localhost`. It is MIT licensed.
