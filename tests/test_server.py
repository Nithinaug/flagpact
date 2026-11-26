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
NEW = {"heading": "Sale on now", "cta": {"text": "Shop"}}


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
    assert [c["state"] for c in body["cells"]] == ["red", "red", "green"]


def test_check_without_replay_is_static(base):
    status, body = call(base, "POST", "/api/check", {"value": NEW, "replay": False})
    assert [c["state"] for c in body["cells"]] == ["red", "red", "amber"]


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


def test_panes_preview_shows_old_versions_crashing(base):
    status, body = call(base, "POST", "/api/render", {"value": NEW})
    assert status == 200 and body["mode"] == "preview"
    assert [p["ok"] for p in body["panes"]] == [False, False, True]
    assert "title" in body["panes"][0]["output"]
    assert body["panes"][2]["output"].startswith("[BANNER]")


def test_panes_live_renders_every_version(base):
    status, body = call(base, "POST", "/api/render", {})
    assert body["mode"] == "live" and all(p["ok"] for p in body["panes"])
