import argparse
import json
import os
import sys
from typing import Any

from .admin import AdminError, ReadOnlyClient
from .service import MISSING, Service

RESULTS = {"red": "breaks", "amber": "not_checked", "green": "safe", "idle": "not_checked"}
WORDS = {"breaks": "BREAKS", "not_checked": "NOT CHECKED", "safe": "SAFE"}


def load_env(path: str) -> None:
    with open(path) as handle:
        for line in handle:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ.setdefault(key, value)


def read_value(source: str) -> dict[str, Any]:
    if source == "-":
        text = sys.stdin.read()
    elif source.lstrip().startswith("{"):
        text = source
    else:
        with open(source) as handle:
            text = handle.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("the new value must be a JSON object")
    return value


def build_report(flag: str, plan: dict[str, Any]) -> dict[str, Any]:
    versions = [
        {
            "version": cell["version"],
            "result": RESULTS[cell["state"]],
            "reason": cell["reason"],
            "gets": sorted(cell["value"]),
        }
        for cell in plan["cells"]
    ]
    counts = {name: sum(1 for v in versions if v["result"] == name) for name in WORDS}
    fix = None
    if plan.get("limit"):
        fix = {"keep_below": plan["limit"], "steps": plan["diff"]}
    return {
        "status": "fail" if counts["breaks"] else "pass",
        "flag": flag,
        **counts,
        "versions": versions,
        "fix": fix,
        "error": plan.get("error") if counts["breaks"] else None,
        "notices": plan.get("notices", []),
    }


def print_report(report: dict[str, Any]) -> None:
    total = len([v for v in report["versions"] if v["version"] != MISSING])
    if report["breaks"]:
        print(f"{report['flag']}: {report['breaks']} of {total} app versions would break")
    else:
        print(f"{report['flag']}: no app version would break")
    for item in report["versions"]:
        name = "no app_version" if item["version"] == MISSING else item["version"]
        print(f"  {name:<15}{WORDS[item['result']]:<13}{item['reason']}")
    for line in report.get("notices", []):
        print(f"Note: {line}")
    if report["fix"]:
        print(f"Suggested fix: keep versions below {report['fix']['keep_below']} on the live value, then publish.")
    elif report["error"]:
        print(f"No automatic fix: {report['error']}")


def main(argv: list[str] | None = None, admin: Any = None) -> int:
    parser = argparse.ArgumentParser(prog="flagpact")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a pending config value against every app version")
    check.add_argument("--value", required=True, help="JSON file, inline JSON, or - for stdin")
    check.add_argument("--config", default="flagpact.json")
    check.add_argument("--env-file", help="file with FLAGSMITH_API_URL and FLAGSMITH_ENV_SERVER_KEY")
    check.add_argument("--json", action="store_true", help="print a JSON report")
    args = parser.parse_args(argv)

    try:
        if args.env_file:
            load_env(args.env_file)
        value = read_value(args.value)
        client = admin or ReadOnlyClient.from_env()
        service = Service(client, args.config)
        plan = service.plan(value, include_missing=False)
    except (AdminError, OSError, ValueError, KeyError) as error:
        message = f"flagpact: {error}"
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}))
        else:
            print(message, file=sys.stderr)
        return 2

    report = build_report(service.flag, plan)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 1 if report["breaks"] else 0


if __name__ == "__main__":
    sys.exit(main())
