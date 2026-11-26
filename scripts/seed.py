import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flagpact.admin import AdminClient, AdminError

START = {"title": "Sale on now", "heading": "Sale on now", "cta": {"text": "Shop"}}
FLAG = "home_banner"


def load_keys(path: str) -> None:
    for line in open(path):
        if "=" in line:
            key, value = line.strip().split("=", 1)
            os.environ.setdefault(key, value)


def main() -> None:
    load_keys(sys.argv[1])
    admin = AdminClient.from_env()
    existing = admin._items(admin._ok("GET", f"/projects/{admin.project_id}/features/?search={FLAG}"))
    if any(f["name"] == FLAG for f in existing):
        feature_id = admin.feature_id(FLAG)
        state = admin.default_state(feature_id)
        admin.set_default(state["id"], json.dumps(START))
        print(f"{FLAG} reset to the starting value")
        return
    admin._ok("POST", f"/projects/{admin.project_id}/features/", {
        "name": FLAG, "type": "STANDARD", "default_enabled": True, "initial_value": json.dumps(START),
    })
    print(f"{FLAG} created with the starting value")


if __name__ == "__main__":
    try:
        main()
    except AdminError as error:
        sys.exit(str(error))
