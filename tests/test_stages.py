import json
import pathlib
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from flagpact import service as service_module
from flagpact.admin import AdminError
from flagpact.fix import Applied
from flagpact.server import make_handler
from flagpact.service import Service

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "demo" / "environment.json").read_text())
SAFE = {"title": "Winter sale", "heading": "Winter sale", "cta": {"text": "Shop", "label": "Shop"}}
BREAKING = {"heading": "Sale on now", "subheading": "Up to 40% off", "cta": {"label": "Shop the sale"}}


class StubAdmin:
    def document(self):
        return DOCUMENT


@pytest.fixture
def service():
    return Service(StubAdmin(), str(ROOT / "flagpact.json"))


@pytest.fixture
def base(service):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def call(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_safe_change_is_staged_newest_version_first(service):
    result = service.stages(SAFE, include_missing=False)
    assert [s["boundary"] for s in result["stages"]] == ["3.0.0", "2.0.0", "1.0.0"]
    assert result["current"] == -1 and all(s["ok"] for s in result["stages"])
    assert [s["gets_change"] for s in result["stages"]] == [["3.0.0"], ["2.0.0", "3.0.0"], ["1.0.0", "2.0.0", "3.0.0"]]
    assert [s["kept"] for s in result["stages"]] == [["1.0.0", "2.0.0"], ["1.0.0"], []]


def test_share_on_the_change_grows_each_stage(service):
    shares = [s["share_new"] for s in service.stages(SAFE, include_missing=True)["stages"]]
    assert shares == [35, 74, 96]
    assert [s["share_new"] for s in service.stages(SAFE, include_missing=False)["stages"]] == [39, 78, 100]


def test_breaking_change_only_stages_versions_that_can_read_it(service):
    result = service.stages(BREAKING)
    assert [s["boundary"] for s in result["stages"]] == ["3.0.0"]
    assert result["held"] == ["1.0.0", "2.0.0"]
    assert result["stages"][0]["ok"]


def test_change_no_version_can_read_has_no_stages(service):
    result = service.stages({})
    assert result["stages"] == [] and "error" in result


def test_every_stage_cell_set_has_no_break(service):
    for stage in service.stages(SAFE)["stages"]:
        assert stage["blocked"] == []
        assert "red" not in [c["state"] for c in stage["cells"]]


def patch_writes(monkeypatch, service):
    calls = []
    old = service._default(DOCUMENT)

    def fake_apply(admin, plan, limit=None):
        calls.append(("apply", limit))
        return Applied("home_banner", json.dumps(old), 1, 2, 3, True, False, ["segment created"], limit)

    def fake_publish(admin, applied, value):
        applied.published = True
        calls.append(("publish",))
        return ["default changed"]

    def fake_move(admin, applied, plan, boundary):
        applied.boundary = boundary
        calls.append(("move", boundary))
        return [f"moved to {boundary}"]

    def fake_rollback(admin, applied):
        calls.append(("rollback",))
        return ["default restored", "segment and override removed"]

    monkeypatch.setattr(service_module, "apply_plan", fake_apply)
    monkeypatch.setattr(service_module, "publish", fake_publish)
    monkeypatch.setattr(service_module, "move_boundary", fake_move)
    monkeypatch.setattr(service_module, "rollback", fake_rollback)
    return calls


def test_stages_apply_one_at_a_time_and_finish(monkeypatch, service):
    calls = patch_writes(monkeypatch, service)
    first = service.stage_next(SAFE)
    assert first == {"steps": ["segment created", "default changed"], "stage": 0, "done": False}
    assert calls == [("apply", "3.0.0"), ("publish",)]
    assert service.stages(SAFE)["current"] == 0
    assert service.stage_next(SAFE)["stage"] == 1 and calls[-1] == ("move", "2.0.0")
    last = service.stage_next(SAFE)
    assert last["stage"] == 2 and last["done"] and calls[-1] == ("move", "1.0.0")
    with pytest.raises(AdminError, match="every stage"):
        service.stage_next(SAFE)


def test_back_moves_one_stage_then_rolls_everything_back(monkeypatch, service):
    calls = patch_writes(monkeypatch, service)
    for _ in range(3):
        service.stage_next(SAFE)
    assert service.stage_back(SAFE)["stage"] == 1 and calls[-1] == ("move", "2.0.0")
    assert service.stage_back(SAFE)["stage"] == 0 and calls[-1] == ("move", "3.0.0")
    result = service.stage_back(SAFE)
    assert result["stage"] == -1 and calls[-1] == ("rollback",)
    assert service.applied is None


def test_back_without_a_stage_is_refused(service):
    with pytest.raises(AdminError, match="no stage"):
        service.stage_back(SAFE)


def test_unpublished_fix_blocks_staging(monkeypatch, service):
    patch_writes(monkeypatch, service)
    service.applied = Applied("home_banner", json.dumps(SAFE), 1, 2, 3, True, False, [], "3.0.0")
    with pytest.raises(AdminError, match="publish or undo"):
        service.stage_next(SAFE)


def test_boundary_is_read_back_from_the_environment_document():
    segment = {"rules": [{"type": "ALL", "rules": [{"type": "ANY", "rules": [], "conditions": [
        {"operator": "LESS_THAN", "value": "2.0.0:semver", "property_": "app_version"},
        {"operator": "IS_NOT_SET", "value": "", "property_": "app_version"},
    ]}], "conditions": []}]}
    assert Service._boundary(segment) == "2.0.0"
    assert Service._boundary({"rules": []}) == ""


def test_stage_routes(base):
    status, body = call(base, "/api/stages", {"value": SAFE})
    assert status == 200 and len(body["stages"]) == 3
    assert call(base, "/api/stages", {})[0] == 400
    assert call(base, "/api/stage-back", {"value": SAFE})[0] == 409
    assert call(base, "/api/stage-next", {"value": {}})[0] == 409


def test_last_stage_says_when_builds_without_a_version_are_held(service):
    held = service.stages(SAFE, include_missing=True)["stages"]
    free = service.stages(SAFE, include_missing=False)["stages"]
    assert held[-1]["holds_missing"] is True and free[-1]["holds_missing"] is False


def test_next_and_back_only_build_the_stage_they_need(monkeypatch, service):
    built = []
    original = service_module.build_matrix

    def counting(*args, **kwargs):
        built.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(service_module, "build_matrix", counting)
    patch_writes(monkeypatch, service)
    service.stage_next(SAFE)
    assert len(built) == 2


def test_write_routes_refuse_requests_without_json_content_type(base):
    request = urllib.request.Request(base + "/api/stage-next", data=json.dumps({"value": SAFE}).encode(), method="POST")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request)
    assert error.value.code == 403
