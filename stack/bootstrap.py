import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KEYS_FILE = os.path.join(ROOT, ".flagpact-keys.env")
NAME = "flagpact"
FLAG = "home_banner"


def read_env(path):
    out = {}
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key] = value
    return out


ENV = read_env(os.path.join(HERE, ".env"))
PORT = os.environ.get("FLAGSMITH_PORT") or ENV.get("FLAGSMITH_PORT", "8000")
BASE = "http://127.0.0.1:%s" % PORT
API = BASE + "/api/v1"


def call(method, path, body=None, token=None, master=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Token " + token)
    if master:
        request.add_header("Authorization", "Api-Key " + master)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode()
    return status, (json.loads(text) if text else {})


def items(payload):
    return payload.get("results", []) if isinstance(payload, dict) else payload


def wait_healthy():
    for _ in range(90):
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=3):
                return
        except Exception:
            time.sleep(2)
    sys.exit("Flagsmith did not become healthy in 3 minutes.")


def starting_value():
    path = os.path.join(ROOT, "demo", "environment.json")
    with open(path) as handle:
        document = json.load(handle)
    for state in document["feature_states"]:
        if state["feature"]["name"] == FLAG:
            return state["feature_state_value"]
    sys.exit("demo/environment.json has no %s" % FLAG)


def main():
    email, password = ENV["FLAGPACT_ADMIN_EMAIL"], ENV["FLAGPACT_ADMIN_PASSWORD"]
    wait_healthy()

    status, payload = call("POST", "/auth/users/", {
        "email": email, "first_name": "Flagpact", "last_name": "Admin",
        "password": password, "re_password": password,
    })
    if status == 201:
        token = payload["key"]
        print("admin: created")
    else:
        status, payload = call("POST", "/auth/login/", {"email": email, "password": password})
        if status != 200:
            sys.exit("admin: signup and login both failed (HTTP %s)" % status)
        token = payload["key"]
        print("admin: logged in")

    _, payload = call("GET", "/organisations/", token=token)
    org = next((o for o in items(payload) if o["name"] == NAME), None)
    if org is None:
        status, org = call("POST", "/organisations/", {"name": NAME}, token=token)
        assert status == 201, "organisation create failed: %s" % status
    print("organisation: ok")

    _, payload = call("GET", "/projects/?organisation=%s" % org["id"], token=token)
    project = next((p for p in items(payload) if p["name"] == NAME), None)
    if project is None:
        status, project = call("POST", "/projects/", {"name": NAME, "organisation": org["id"]}, token=token)
        assert status == 201, "project create failed: %s" % status
    print("project: ok")

    _, payload = call("GET", "/environments/?project=%s" % project["id"], token=token)
    environment = next((e for e in items(payload) if e["name"] == "demo"), None)
    if environment is None:
        status, environment = call("POST", "/environments/", {"name": "demo", "project": project["id"]}, token=token)
        assert status == 201, "environment create failed: %s" % status
    print("environment: ok")

    existing = read_env(KEYS_FILE) if os.path.exists(KEYS_FILE) else {}
    master = existing.get("FLAGSMITH_MASTER_API_KEY")
    if not master:
        status, created = call("POST", "/organisations/%s/master-api-keys/" % org["id"], {"name": NAME}, token=token)
        assert status == 201, "master key create failed: %s" % status
        master = created["key"]
        print("master key: created")
    server = existing.get("FLAGSMITH_ENV_SERVER_KEY")
    if not server:
        status, created = call("POST", "/environments/%s/api-keys/" % environment["api_key"], {"name": NAME}, master=master)
        assert status == 201, "server key create failed: %s" % status
        server = created["key"]
        print("server key: created")

    _, payload = call("GET", "/projects/%s/features/?search=%s" % (project["id"], FLAG), master=master)
    if not any(f["name"] == FLAG for f in items(payload)):
        status, _ = call("POST", "/projects/%s/features/" % project["id"], {
            "name": FLAG, "type": "STANDARD", "default_enabled": True, "initial_value": starting_value(),
        }, master=master)
        assert status == 201, "feature create failed: %s" % status
        print("feature %s: created" % FLAG)
    else:
        print("feature %s: already there" % FLAG)

    lines = [
        "FLAGSMITH_API_URL=%s" % API,
        "FLAGSMITH_ORG_ID=%s" % org["id"],
        "FLAGSMITH_PROJECT_ID=%s" % project["id"],
        "FLAGSMITH_ENV_CLIENT_KEY=%s" % environment["api_key"],
        "FLAGSMITH_MASTER_API_KEY=%s" % master,
        "FLAGSMITH_ENV_SERVER_KEY=%s" % server,
    ]
    descriptor = os.open(KEYS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    os.chmod(KEYS_FILE, 0o600)
    print("wrote .flagpact-keys.env (mode 600). Do not commit it.")


if __name__ == "__main__":
    main()
