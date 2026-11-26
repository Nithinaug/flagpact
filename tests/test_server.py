import json
import pathlib
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from flagpact.server import make_handler
from flagpact.service import Service

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "demo" / "environment.json").read_text())
NEW = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}


class StubAdmin:
    def document(self):
        return DOCUMENT


@pytest.fixture
def base():
    service = Service(StubAdmin(), str(ROOT / "flagpact.json"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def call(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_state_lists_flag_and_versions(base):
    status, body = call(base, "GET", "/api/state")
    assert status == 200 and body["flag"] == "home_banner" and body["versions"] == ["1.0.0", "2.0.0", "3.0.0"]
    assert sorted(body["contracts"]) == ["1.0.0", "2.0.0", "3.0.0"]


def test_check_returns_matrix(base):
    status, body = call(base, "POST", "/api/check", {"value": NEW})
    assert status == 200
    assert [c["state"] for c in body["cells"]] == ["red", "red", "green", "amber"]


def test_check_without_replay_is_static(base):
    status, body = call(base, "POST", "/api/check", {"value": NEW, "replay": False})
    assert [c["state"] for c in body["cells"]] == ["red", "red", "amber", "amber"]


def test_plan_returns_diff(base):
    status, body = call(base, "POST", "/api/plan", {"value": NEW})
    assert status == 200 and body["limit"] == "3.0.0" and len(body["diff"]) == 4


def test_plan_reports_manual_fix(base):
    status, body = call(base, "POST", "/api/plan", {"value": {"title": "ok", "heading": "h", "cta": {"text": "t"}}})
    assert status == 200 and "error" in body


def test_rollback_without_apply_is_conflict(base):
    assert call(base, "POST", "/api/rollback", {})[0] == 409


def test_bad_value_is_rejected(base):
    assert call(base, "POST", "/api/check", {"value": "nope"})[0] == 400
    assert call(base, "POST", "/api/check", {})[0] == 400


def test_unknown_route_and_missing_ui(base):
    assert call(base, "GET", "/api/nope")[0] == 404


def test_plan_simulates_the_fix_before_writing(base):
    status, body = call(base, "POST", "/api/plan", {"value": NEW})
    assert [c["state"] for c in body["after"]] == ["green", "green", "green", "amber"]
    assert body["at_risk"] == 61 and body["protected"] == 96


def test_plan_can_protect_builds_without_the_trait(base):
    status, body = call(base, "POST", "/api/plan", {"value": NEW, "include_missing": True})
    assert [c["state"] for c in body["after"]] == ["green", "green", "green", "green"]
    assert body["protected"] == 100


def test_state_carries_shares_and_latest(base):
    status, body = call(base, "GET", "/api/state")
    assert body["latest"] == "3.0.0" and body["meta"]["1.0.0"]["share"] == 22 and body["missing"]["share"] == 4


def test_panes_show_before_and_after(base):
    status, body = call(base, "POST", "/api/render", {"value": NEW})
    assert status == 200
    assert all(p["ok"] for p in body["before"])
    assert [p["ok"] for p in body["after"]] == [False, False, True]
    assert "title" in body["after"][0]["output"]
    assert body["after"][2]["output"].startswith("[BANNER]")


def test_panes_without_a_value_are_live_only(base):
    status, body = call(base, "POST", "/api/render", {})
    assert body["after"] is None and all(p["ok"] for p in body["before"])


def test_publish_before_apply_is_conflict(base):
    assert call(base, "POST", "/api/publish", {"value": NEW})[0] == 409


class StubClone:
    def __init__(self, document, broken=False):
        self.document = document
        self.broken = broken
        self.cleaned = False
        self.fixed = None

    def apply(self, plan):
        from flagpact.resolver import with_fix
        old = json.loads(next(s for s in self.document["feature_states"] if s["feature"]["name"] == "home_banner")["feature_state_value"])
        self.fixed = with_fix(self.document, "home_banner", plan.segment_name, plan.limit, old, plan.new_value, plan.include_missing)

    def publish(self, value):
        return None

    def probe(self, flag, version):
        if self.broken:
            raise RuntimeError("probe failed")
        from flagpact.resolver import resolve
        return resolve(self.fixed, flag, version)

    def cleanup(self):
        self.cleaned = True


def make_service(clone):
    service = Service(StubAdmin(), str(ROOT / "flagpact.json"))
    service.clone_factory = lambda: clone
    return service


def test_rehearsal_confirms_every_version_on_a_clone():
    clone = StubClone(DOCUMENT)
    result = make_service(clone).rehearse(NEW, True)
    assert result["ok"] is True and clone.cleaned
    assert [(r["version"], r["expects"], r["ok"]) for r in result["rows"]] == [
        ("1.0.0", "old", True), ("2.0.0", "old", True), ("3.0.0", "new", True), ("none", "old", True),
    ]


def test_rehearsal_without_missing_protection_expects_the_new_value():
    result = make_service(StubClone(DOCUMENT)).rehearse(NEW, False)
    assert result["rows"][-1]["expects"] == "new" and result["ok"]


def test_rehearsal_cleans_up_when_a_probe_fails():
    clone = StubClone(DOCUMENT, broken=True)
    try:
        make_service(clone).rehearse(NEW, True)
    except RuntimeError:
        pass
    assert clone.cleaned


def test_rehearsal_is_refused_while_a_fix_is_applied():
    from flagpact.admin import AdminError
    service = make_service(StubClone(DOCUMENT))
    service.applied = object()
    try:
        service.rehearse(NEW, True)
        raised = False
    except AdminError:
        raised = True
    assert raised
