"""Record the fixtures for the static replay demo from the real flagpact engine.

It runs the real Service over the demo environment document in each state the
console can reach, and writes the answers to ui/src/static/fixtures.json.
It needs no Flagsmith. Run it with the project's Python:

    .venv/bin/python scripts/make_static_fixtures.py
"""
import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ["FLAGPACT_STATE_FILE"] = str(pathlib.Path(tempfile.mkdtemp()) / "state.json")

from flagpact.resolver import patch_default, with_fix  # noqa: E402
from flagpact.service import Service  # noqa: E402

CONFIG = json.loads((ROOT / "flagpact.json").read_text())
FLAG = CONFIG["flag"]
D0 = json.loads((ROOT / "demo" / "environment.json").read_text())
START = next(json.loads(s["feature_state_value"]) for s in D0["feature_states"] if s["feature"]["name"] == FLAG)
BREAK = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}
OUTSIDE = CONFIG["outside_edit"]
LIMIT = "3.0.0"
SEGMENT = f"flagpact/{FLAG}/{LIMIT}"


class Doc:
    def __init__(self, document):
        self.document = document
        self.dashboard_url = ""

    def document_(self):
        return self.document


class StubAdmin:
    dashboard_url = ""

    def __init__(self, document):
        self._document = document

    def document(self):
        return self._document


def service(document, last_safe=None):
    s = Service(StubAdmin(copy.deepcopy(document)), str(ROOT / "flagpact.json"))
    s._last_safe = last_safe
    return s


def documents(im):
    applied = patch_default(with_fix(D0, FLAG, SEGMENT, LIMIT, START, BREAK, im), FLAG, START)
    published = with_fix(D0, FLAG, SEGMENT, LIMIT, START, BREAK, im)
    return {"applied": applied, "published": published, "staged": published}


outside = patch_default(D0, FLAG, OUTSIDE)
protected = with_fix(outside, FLAG, SEGMENT, LIMIT, START, OUTSIDE, True)


def jsonable(x):
    return json.loads(json.dumps(x))


def key(phase, im):
    return f"{phase}|{'1' if im else '0'}"


fx = {"start_value": START, "break_value": BREAK, "outside_value": OUTSIDE, "limit": LIMIT, "segment": SEGMENT,
      "state": {}, "watch": {}, "check_live": {}, "check_break": {}, "plan_live": {}, "plan_break": {},
      "render_live": {}, "render_break": {}, "stages": {}, "apply_cells": {}, "steps": {}}

phases = [("start", D0, None), ("outside", outside, None), ("protected", protected, None)]
for im in (True, False):
    for name, doc in documents(im).items():
        phases.append((name, doc, im))

for phase, doc, im in phases:
    ims = (True, False) if im is None else (im,)
    for flag_im in ims:
        k = key(phase, flag_im)
        s = service(doc, last_safe=START)
        state = jsonable(s.state())
        state["applied"] = phase in ("applied", "published", "staged", "protected")
        state["published"] = phase in ("published", "staged", "protected")
        fx["state"][k] = state
        live = state["value"]
        fx["watch"][k] = jsonable(service(doc, last_safe=START).watch())
        fx["check_live"][k] = {"quick": jsonable(s.check(live, replay=False)), "full": jsonable(s.check(live, replay=True))}
        fx["check_break"][k] = {"quick": jsonable(s.check(BREAK, replay=False)), "full": jsonable(s.check(BREAK, replay=True))}
        fx["plan_live"][k] = jsonable(s.plan(live, include_missing=flag_im))
        fx["plan_break"][k] = jsonable(s.plan(BREAK, include_missing=flag_im))
        fx["render_live"][k] = {"before": jsonable(s.panes(None)["before"]), "after": None}
        fx["render_break"][k] = jsonable(s.panes(BREAK))
        try:
            fx["stages"][k] = jsonable(s.stages(BREAK, include_missing=flag_im))
        except Exception as error:  # a state the stage planner does not accept
            fx["stages"][k] = {"stages": [], "current": -1, "error": str(error)}
        print("recorded", k)

for im in (True, False):
    after = service(documents(im)["applied"], last_safe=START)
    fx["apply_cells"][key("x", im)] = jsonable(after.check(BREAK, replay=True)["cells"])

result = subprocess.run(
    [sys.executable, "-m", "flagpact", "import", "--json", "https://github.com/Nithinaug/flagpact-sample-app"],
    capture_output=True, text=True,
)
fx["import_sample"] = json.loads(result.stdout)

out = ROOT / "ui" / "src" / "static"
out.mkdir(parents=True, exist_ok=True)
(out / "fixtures.json").write_text(json.dumps(fx, indent=1) + "\n")
print("wrote", out / "fixtures.json", (out / "fixtures.json").stat().st_size, "bytes")
