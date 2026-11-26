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
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
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


class LiveStub:
    dashboard_url = ""

    def __init__(self):
        self.doc = json.loads(json.dumps(DOCUMENT))

    def document(self):
        return self.doc

    def state(self):
        return next(s for s in self.doc["feature_states"] if s["feature"]["name"] == "home_banner")

    def feature_id(self, flag):
        return 1

    def default_state(self, feature_id):
        return {"id": 1}

    def set_default(self, state_id, value):
        self.state()["feature_state_value"] = value


def live_service(config=None):
    stub = LiveStub()
    return Service(stub, config or str(ROOT / "flagpact.json")), stub


def test_watch_is_quiet_while_the_live_value_is_safe():
    service, _ = live_service()
    result = service.watch()
    assert result["ok"] is True and result["broken"] == [] and result["restore"] is False


def test_watch_catches_an_outside_edit_and_offers_a_restore():
    service, stub = live_service()
    service.watch()
    result = service.simulate_outside_edit()
    assert result["value"] == NEW
    caught = service.watch()
    assert caught["ok"] is False and caught["broken"] == ["1.0.0", "2.0.0"]
    assert caught["restore"] is True and caught["at_risk"] == 61
    assert "title" in caught["previous"] and caught["previous"] != caught["value"]


def test_restore_puts_the_last_safe_value_back():
    service, stub = live_service()
    service.watch()
    service.simulate_outside_edit()
    service.watch()
    service.restore()
    again = service.watch()
    assert again["ok"] is True and again["restore"] is False
    assert "title" in json.loads(stub.state()["feature_state_value"])


def test_restore_without_an_earlier_safe_value_is_refused():
    from flagpact.admin import AdminError
    service, stub = live_service()
    stub.state()["feature_state_value"] = json.dumps(NEW)
    result = service.watch()
    assert result["ok"] is False and result["restore"] is False
    try:
        service.restore()
        raised = False
    except AdminError:
        raised = True
    assert raised


def test_watch_route_and_conflict_on_bad_restore(base):
    status, body = call(base, "GET", "/api/watch")
    assert status == 200 and body["ok"] is True
    assert call(base, "POST", "/api/restore", {})[0] == 409


def test_protect_keeps_older_versions_on_the_previous_value(monkeypatch):
    from flagpact import service as service_module
    from flagpact.fix import Applied
    seen = {}

    def fake_apply(admin, plan):
        seen["plan"] = plan
        return Applied("home_banner", "{}", 1, 2, 3, True, False, ["segment created"])

    monkeypatch.setattr(service_module, "apply_plan", fake_apply)
    service, stub = live_service()
    service.watch()
    service.simulate_outside_edit()
    result = service.protect()
    plan = seen["plan"]
    assert plan.limit == "3.0.0" and plan.include_missing is True
    assert "title" in plan.old_value and plan.new_value == NEW
    assert service.applied.published is True and result["limit"] == "3.0.0"


def test_protect_is_refused_when_the_live_value_is_safe():
    from flagpact.admin import AdminError
    service, _ = live_service()
    try:
        service.protect()
        raised = False
    except AdminError:
        raised = True
    assert raised


def test_protect_is_refused_without_an_earlier_safe_value():
    from flagpact.admin import AdminError
    service, stub = live_service()
    stub.state()["feature_state_value"] = json.dumps(NEW)
    try:
        service.protect()
        raised = False
    except AdminError:
        raised = True
    assert raised


class RecoverStub(LiveStub):
    project_id = "1"

    def __init__(self, published):
        super().__init__()
        self.published = published
        self.doc["project"]["segments"].append({
            "id": 7,
            "name": "flagpact/home_banner/3.0.0",
            "rules": [],
            "feature_states": [{
                "feature": {"id": 1, "name": "home_banner", "type": "STANDARD"},
                "feature_state_value": json.dumps({"title": "Sale on now"}),
            }],
        })

    def _ok(self, method, path, body=None, kind="master"):
        return {"results": [{"id": 7, "name": "flagpact/home_banner/3.0.0"}]}

    def _items(self, payload):
        return payload["results"]

    def environment_id(self):
        return 1

    def feature_segments(self, env_id, feature_id):
        return [{"id": 8, "segment": 7}]

    def default_state(self, feature_id):
        value = json.dumps(NEW if self.published else {"title": "Sale on now"})
        return {"id": 1, "feature_state_value": value}


def test_an_existing_flagpact_rule_is_taken_over_after_a_restart():
    service = Service(RecoverStub(published=True), str(ROOT / "flagpact.json"))
    state = service.state()
    assert state["applied"] is True and state["published"] is True
    assert service.applied.segment_id == 7 and service.applied.previous_default == json.dumps({"title": "Sale on now"})


def test_a_rule_without_a_published_change_is_recovered_as_unpublished():
    service = Service(RecoverStub(published=False), str(ROOT / "flagpact.json"))
    state = service.state()
    assert state["applied"] is True and state["published"] is False


def test_the_last_safe_value_survives_a_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("FLAGPACT_STATE_FILE")
    config = tmp_path / "flagpact.json"
    source = json.loads((ROOT / "flagpact.json").read_text())
    source["contracts"] = str(ROOT / "contracts")
    for entry in source["versions"]:
        entry["directory"] = str(ROOT / entry["directory"])
    config.write_text(json.dumps(source))
    first, stub = live_service(str(config))
    assert first.watch()["ok"] is True
    assert (tmp_path / ".flagpact-state.json").exists()
    stub.state()["feature_state_value"] = json.dumps(NEW)
    second = Service(stub, str(config))
    result = second.watch()
    assert result["ok"] is False and result["restore"] is True and "title" in result["previous"]
