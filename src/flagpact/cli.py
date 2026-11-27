import argparse
import json
import os
import sys
from typing import Any

from .admin import AdminError, ReadOnlyClient
from .importer import ScanError, scan_source
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
        fix = {
            "keep_below": plan["limit"],
            "segment": plan["segment"],
            "rules": plan["rules"],
            "rule": plan["rules"][0],
            "keep_value": plan["keep_value"],
            "steps": plan["diff"],
        }
    exposure = plan.get("exposure")
    if exposure:
        for item in versions:
            info = exposure["versions"].get(item["version"])
            if info:
                item["share"] = info["share"]
                item["users"] = info["users"]
    return {
        "at_risk": {"share": exposure["at_risk_share"], "users": exposure["at_risk_users"]} if exposure else None,
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
    at_risk = report.get("at_risk")
    if at_risk and report["breaks"]:
        print(f"At risk: {at_risk['share']:g}% of sessions, about {at_risk['users']:,} users")
    for line in report.get("notices", []):
        print(f"Note: {line}")
    if report["fix"]:
        print(f"Suggested fix: keep versions below {report['fix']['keep_below']} on the live value, then publish.")
    elif report["error"]:
        print(f"No automatic fix: {report['error']}")


def print_import(result: dict[str, Any]) -> None:
    where = "GitHub repository" if result["kind"] == "github" else "folder"
    print(f"Scanned {result['files_scanned']} files in {where} {result['source']}")
    if not result["flags"]:
        print("No Flagsmith value reads found")
    for flag in result["flags"]:
        print(f"Flag {flag['flag']}: read at {len(flag['sites'])} place(s)")
        for read in flag["reads"]:
            parts = []
            if read["required_in"]:
                parts.append("required in " + ", ".join(read["required_in"]))
            if read["default_in"]:
                parts.append("default in " + ", ".join(read["default_in"]))
            print(f"  {read['path']:<20}{'; '.join(parts)}  ({read['places'][0]})")
    if result.get("tags"):
        print(f"Read {len(result['tags'])} release tags: {', '.join(result['tags'])}")
    for item in result["versions"]:
        mark = " (from a package file)" if item["guessed"] else ""
        print(f"App version {item['version']} in {item['directory']}{mark}")
    for line in result["needs_review"]:
        print(f"Review: {line}")
    for line in result["notes"]:
        print(f"Note: {line}")


def run_import(args: argparse.Namespace) -> int:
    try:
        result = scan_source(args.source, checkout=args.checkout)
        if args.out and result["draft"] is not None:
            if os.path.exists(args.out):
                raise ScanError(f"{args.out} already exists, choose another file")
            with open(args.out, "x") as handle:
                handle.write(json.dumps(result["draft"], indent=2) + "\n")
    except (ScanError, OSError) as error:
        print(f"flagpact: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_import(result)
        if result["draft"] is not None:
            print(f"Draft written to {args.out}" if args.out else "Draft flagpact.json:")
            if not args.out:
                print(json.dumps(result["draft"], indent=2))
    return 0 if result["draft"] is not None else 1


def main(argv: list[str] | None = None, admin: Any = None) -> int:
    parser = argparse.ArgumentParser(prog="flagpact")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a pending config value against every app version")
    check.add_argument("--value", required=True, help="JSON file, inline JSON, or - for stdin")
    check.add_argument("--config", default="flagpact.json")
    check.add_argument("--env-file", help="file with FLAGSMITH_API_URL and FLAGSMITH_ENV_SERVER_KEY")
    check.add_argument("--json", action="store_true", help="print a JSON report")
    imp = commands.add_parser("import", help="scan a local folder or a public GitHub repository and draft a flagpact.json")
    imp.add_argument("source", help="a local folder, or a public https://github.com/owner/repo URL")
    imp.add_argument("--out", help="write the draft flagpact.json to this new file")
    imp.add_argument("--checkout", help="write each release tag's files into this new folder, one subfolder per tag")
    imp.add_argument("--json", action="store_true", help="print the full scan as JSON")
    args = parser.parse_args(argv)
    if args.command == "import":
        return run_import(args)

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
