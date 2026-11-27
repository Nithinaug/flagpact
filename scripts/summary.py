import json
import sys

WORDS = {"breaks": "Breaks", "not_checked": "Not checked", "safe": "Safe"}


def render(report):
    if report.get("status") == "error":
        return "### flagpact check\n\nThe check could not run: %s\n" % report.get("error", "unknown error")
    versions = [v for v in report["versions"] if v["version"] != "none"]
    lines = ["### flagpact check: %s" % report["flag"], ""]
    if report["breaks"]:
        lines.append("%d of %d app versions would break." % (report["breaks"], len(versions)))
    else:
        lines.append("No app version would break.")
    at_risk = report.get("at_risk")
    if at_risk and report["breaks"]:
        lines.append("")
        lines.append("**At risk: %g%% of sessions, about {:,} users.**".format(at_risk["users"]) % at_risk["share"])
    lines += ["", "| App version | Result | Users | Reason |", "| --- | --- | --- | --- |"]
    for item in report["versions"]:
        name = "no app_version" if item["version"] == "none" else item["version"]
        users = "{:,}".format(item["users"]) if item.get("users") else ""
        lines.append("| %s | %s | %s | %s |" % (name, WORDS[item["result"]], users, item["reason"]))
    for note in report.get("notices", []):
        lines += ["", "Note: %s" % note]
    if report.get("fix"):
        lines += ["", "Suggested fix: keep versions below %s on the live value, then publish." % report["fix"]["keep_below"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    with open(sys.argv[1]) as handle:
        sys.stdout.write(render(json.load(handle)))
