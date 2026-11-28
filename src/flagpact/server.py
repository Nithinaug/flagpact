import json
import mimetypes
import os
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .admin import AdminClient, AdminError
from .fix import PlanError
from .importer import ScanError, scan_source
from .service import Service

PACKAGED_UI = pathlib.Path(__file__).resolve().parent / "webui"
DIST = PACKAGED_UI if PACKAGED_UI.is_dir() else pathlib.Path(__file__).resolve().parents[2] / "ui" / "dist"
MAX_BODY = 64 * 1024


def source_of(body):
    source = body["source"]
    if not isinstance(source, str):
        raise ValueError("source must be a string")
    return source


def make_handler(service: Service):
    routes = {
        ("POST", "/api/check"): lambda body: service.check(body["value"], body.get("replay", True)),
        ("POST", "/api/plan"): lambda body: service.plan(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/apply"): lambda body: service.apply(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/stages"): lambda body: service.stages(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/stage-next"): lambda body: service.stage_next(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/stage-back"): lambda body: service.stage_back(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/import"): lambda body: scan_source(source_of(body), github_only=True),
        ("POST", "/api/render"): lambda body: service.panes(body.get("value")),
        ("POST", "/api/rehearse"): lambda body: service.rehearse(body["value"], bool(body.get("include_missing"))),
        ("POST", "/api/publish"): lambda body: service.publish(body["value"]),
        ("POST", "/api/protect"): lambda body: service.protect(),
        ("POST", "/api/restore"): lambda body: service.restore(),
        ("POST", "/api/outside-edit"): lambda body: service.simulate_outside_edit(),
        ("POST", "/api/rollback"): lambda body: service.rollback(),
        ("GET", "/api/watch"): lambda body: service.watch(),
        ("GET", "/api/state"): lambda body: service.state(),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def send_json(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def local_json_request(self):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            kind = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return host in ("127.0.0.1", "localhost") and kind == "application/json"

        def handle_api(self, method):
            route = routes.get((method, self.path))
            if route is None:
                return self.send_json(404, {"error": "not found"})
            if method == "POST" and not self.local_json_request():
                return self.send_json(403, {"error": "requests must be JSON sent from this machine"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self.send_json(413, {"error": "body too large"})
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                if "value" in body and not isinstance(body["value"], dict):
                    return self.send_json(400, {"error": "value must be a JSON object"})
                return self.send_json(200, route(body))
            except (KeyError, ValueError):
                return self.send_json(400, {"error": "bad request"})
            except (AdminError, PlanError, ScanError) as error:
                return self.send_json(409, {"error": str(error)})

        def do_POST(self):
            self.handle_api("POST")

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self.handle_api("GET")
            target = (DIST / self.path.lstrip("/")).resolve()
            if not target.is_file() or DIST.resolve() not in target.parents:
                target = DIST / "index.html"
            if not target.is_file():
                return self.send_json(404, {"error": "interface not built"})
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    for line in open(sys.argv[1]):
        if "=" in line:
            key, value = line.strip().split("=", 1)
            os.environ.setdefault(key, value)
    service = Service(AdminClient.from_env(), sys.argv[2] if len(sys.argv) > 2 else "flagpact.json")
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("FLAGPACT_PORT", "8765"))), make_handler(service))
    print("flagpact server started")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("flagpact stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
