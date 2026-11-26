import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from flagpact.admin import AdminClient
from flagpact.fix import apply_plan, plan_fix, rollback
from flagpact.matrix import AppVersion, build_matrix
from flagpact.resolver import resolve
from seed import FLAG, START, load_keys

NEW = {"heading": "Sale on now", "cta": {"text": "Shop"}}
VERSIONS = [AppVersion(f"{n}.0.0", str(ROOT / "demo" / f"v{n}")) for n in (1, 2, 3)]


def show(label, cells):
    print(label, [(c.version, c.state) for c in cells])


def main():
    load_keys(sys.argv[1])
    admin = AdminClient.from_env()
    contracts = str(ROOT / "contracts")

    before = build_matrix(admin.document(), FLAG, NEW, VERSIONS, contracts)
    show("before write", before)
    plan = plan_fix(FLAG, START, NEW, before)
    print("\n".join("  " + line for line in plan.diff()))

    applied = apply_plan(admin, plan)
    print("applied:", applied.steps)
    document = admin.document()
    print("live resolve:", {v.version: sorted(resolve(document, FLAG, v.version)) for v in VERSIONS})
    show("after write", build_matrix(document, FLAG, NEW, VERSIONS, contracts))

    print("rollback:", rollback(admin, applied))
    restored = resolve(admin.document(), FLAG, "3.0.0")
    print("default restored:", restored == START)


main()
