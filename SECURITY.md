# Security

flagpact is a local developer tool. This page says what it does and does not protect, so you can decide where to run it.

## What it protects

- **Local only.** The console listens on `127.0.0.1`. Every request that changes something must be JSON and must name `127.0.0.1` or `localhost` as the host, so a web page you visit cannot make it write.
- **Writes only to a local Flagsmith.** The admin client refuses any Flagsmith address that is not `127.0.0.1` or `localhost`. The GitHub Action and the `check` command use a read-only server key and never write.
- **Import never runs code.** `flagpact import` parses Python with the standard library `ast` module and reads other languages as text. A GitHub import makes a shallow clone with git hooks, submodules, credentials and symlinks turned off, a 60 second limit and a 200 MB limit. It reads at most 2,000 files, and skips files over 512 KB.
- **Small requests.** The console rejects request bodies over 64 KB.
- **Secrets stay out of git.** The keys file `.flagpact-keys.env`, the state file and `stack/.env` are in `.gitignore`.
- **The agent skill asks first.** `skills/flagpact-safe-rollout` stops for a person before it writes and again before it publishes, and a stale-plan check refuses a publish if Flagsmith changed after approval.

## What it does not protect

- **The console has no login.** Anyone who can reach the port on your machine can use it. Do not expose it to a network.
- **A check runs the tests of each app version.** To find out whether a version would break, flagpact replays that version's own tests, and that runs the code in those tests. Run it only on code you trust.
- **The demo keys are local.** The demo uses a Flagsmith admin key stored on your machine. Do not reuse that setup against a Flagsmith you care about.

## Reporting a problem

Please open a private security advisory on this repository (Security tab, "Report a vulnerability"). If that is not available, open an issue that says you have a security report, without the details, and I will contact you.
