import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from flagpact.admin import AdminClient
from flagpact.fix import apply_plan, plan_fix, publish, rollback
from flagpact.matrix import AppVersion, build_matrix
from flagpact.resolver import resolve
from seed import FLAG, START, load_keys

NEW = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}
VERSIONS = [AppVersion(f"{n}.0.0", str(ROOT / "demo" / f"v{n}")) for n in (1, 2, 3)]
PROBES = ["0.9.0", "1.0.0", "1.9.9", "2.0.0", "2.5.0", "2.99.99", "3.0.0", "3.0.1", "3.1.0", "10.0.0", None]


def compare(label, admin):
    document = admin.document()
    rows = []
    for version in PROBES:
        local = resolve(document, FLAG, version)
        live = admin.probe(FLAG, version)
        rows.append((version or "no app_version", local == live, sorted(live)))
    matched = sum(1 for _, ok, _ in rows if ok)
    print(f"\n{label}: {matched}/{len(rows)} match")
    print("| app_version | flagpact == live Flagsmith | fields served |")
    print("| --- | --- | --- |")
    for version, ok, fields in rows:
        print(f"| {version} | {'yes' if ok else 'NO'} | {', '.join(fields)} |")
    return matched, len(rows)


def main():
    load_keys(sys.argv[1])
    admin = AdminClient.from_env()
    contracts = str(ROOT / "contracts")
    results = [compare("Starting value, no fix", admin)]

    cells = build_matrix(admin.document(), FLAG, NEW, VERSIONS, contracts)
    plan = plan_fix(FLAG, START, NEW, cells)
    applied = apply_plan(admin, plan)
    try:
        publish(admin, applied, NEW)
        results.append(compare(f"Breaking change with the fix (versions below {plan.limit} kept on the old value)", admin))
    finally:
        rollback(admin, applied)
    restored = resolve(admin.document(), FLAG, "3.0.0") == START
    print(f"\nrestored to the starting value: {restored}")

    matched = sum(m for m, _ in results)
    total = sum(t for _, t in results)
    print(f"\ntotal: {matched}/{total} app versions resolved the same in flagpact and in live Flagsmith")
    sys.exit(0 if matched == total and restored else 1)


main()
