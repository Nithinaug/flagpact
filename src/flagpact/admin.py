import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable

Request = Callable[[str, str, Any, str], tuple[int, Any]]


class AdminError(Exception):
    pass


def http_request(base: str, keys: dict[str, str]) -> Request:
    def call(method: str, path: str, body: Any = None, kind: str = "master") -> tuple[int, Any]:
        headers = {"Content-Type": "application/json"}
        if kind == "master":
            headers["Authorization"] = "Api-Key " + keys["master"]
        else:
            headers["X-Environment-Key"] = keys[kind]
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                text = response.read().decode()
                return response.status, (json.loads(text) if text else {})
        except urllib.error.HTTPError as error:
            text = error.read().decode()
            try:
                return error.code, json.loads(text)
            except ValueError:
                return error.code, {"raw": text[:200]}

    return call


class AdminClient:
    def __init__(self, request: Request, project_id: str, client_key: str, dashboard_url: str = "",
                 base: str = "", keys: dict[str, str] | None = None) -> None:
        self._call = request
        self._base = base
        self._keys = keys or {}
        self.dashboard_url = dashboard_url
        self.project_id = project_id
        self.client_key = client_key

    @classmethod
    def from_env(cls) -> "AdminClient":
        base = os.environ["FLAGSMITH_API_URL"].rstrip("/")
        if not base.startswith(("http://127.0.0.1", "http://localhost")):
            raise AdminError("flagpact writes only to a local Flagsmith")
        keys = {
            "master": os.environ["FLAGSMITH_MASTER_API_KEY"],
            "client": os.environ["FLAGSMITH_ENV_CLIENT_KEY"],
            "server": os.environ["FLAGSMITH_ENV_SERVER_KEY"],
        }
        dashboard = base.removesuffix("/api/v1") + f"/project/{os.environ['FLAGSMITH_PROJECT_ID']}/segments"
        return cls(http_request(base, keys), os.environ["FLAGSMITH_PROJECT_ID"], keys["client"], dashboard, base, keys)

    def _ok(self, method: str, path: str, body: Any = None, kind: str = "master", expect: tuple[int, ...] = (200, 201, 204)) -> Any:
        status, payload = self._call(method, path, body, kind)
        if status not in expect:
            raise AdminError(f"{method} {path} returned {status}")
        return payload

    @staticmethod
    def _items(payload: Any) -> list[dict[str, Any]]:
        return payload.get("results", payload) if isinstance(payload, dict) else payload

    def document(self) -> dict[str, Any]:
        return self._ok("GET", "/environment-document/", kind="server")

    def environment_id(self) -> int:
        payload = self._ok("GET", f"/environments/?project={self.project_id}")
        return next(e["id"] for e in self._items(payload) if e["api_key"] == self.client_key)

    def feature_id(self, flag: str) -> int:
        payload = self._ok("GET", f"/projects/{self.project_id}/features/?search={flag}")
        return next(f["id"] for f in self._items(payload) if f["name"] == flag)

    def default_state(self, feature_id: int) -> dict[str, Any]:
        payload = self._ok("GET", f"/environments/{self.client_key}/featurestates/?feature={feature_id}")
        return next(s for s in self._items(payload) if s.get("feature_segment") is None)

    def set_default(self, state_id: int, value: str) -> None:
        self._ok("PATCH", f"/environments/{self.client_key}/featurestates/{state_id}/", {"feature_state_value": value})

    def find_segment(self, name: str) -> dict[str, Any] | None:
        payload = self._ok("GET", f"/projects/{self.project_id}/segments/?q={name}")
        return next((s for s in self._items(payload) if s["name"] == name), None)

    def segment_body(self, name: str, limit: str, include_missing: bool = False) -> dict[str, Any]:
        conditions = [{"operator": "LESS_THAN", "property": "app_version", "value": f"{limit}:semver"}]
        if include_missing:
            conditions.append({"operator": "IS_NOT_SET", "property": "app_version", "value": ""})
        return {
            "name": name,
            "project": int(self.project_id),
            "rules": [{"type": "ALL", "rules": [{"type": "ANY", "rules": [], "conditions": conditions}], "conditions": []}],
        }

    def feature_segments(self, env_id: int, feature_id: int) -> list[dict[str, Any]]:
        return self._items(self._ok("GET", f"/features/feature-segments/?environment={env_id}&feature={feature_id}"))

    def prioritise(self, first_id: int, others: list[int]) -> None:
        order = [first_id] + [i for i in others if i != first_id]
        self._ok("POST", "/features/feature-segments/update-priorities/", [{"id": i, "priority": n} for n, i in enumerate(order)])

    def scoped(self, client_key: str, server_key: str) -> "AdminClient":
        if not self._base:
            raise AdminError("this client cannot be scoped to another environment")
        keys = {**self._keys, "client": client_key, "server": server_key}
        return AdminClient(http_request(self._base, keys), self.project_id, client_key, self.dashboard_url, self._base, keys)

    def clone_environment(self, name: str) -> str:
        payload = self._ok("POST", f"/environments/{self.client_key}/clone/", {"name": name})
        return payload["api_key"]

    def create_server_key(self, environment_key: str, name: str) -> str:
        return self._ok("POST", f"/environments/{environment_key}/api-keys/", {"name": name})["key"]

    def delete_environment(self, environment_key: str) -> None:
        self._ok("DELETE", f"/environments/{environment_key}/")

    def delete_segment(self, segment_id: int) -> None:
        self._ok("DELETE", f"/projects/{self.project_id}/segments/{segment_id}/")

    def probe(self, flag: str, version: str | None) -> dict[str, Any]:
        traits = [] if version is None else [{"trait_key": "app_version", "trait_value": version, "transient": True}]
        payload = self._ok("POST", "/identities/", {"identifier": "flagpact-probe", "transient": True, "traits": traits}, kind="client")
        state = next(f for f in payload["flags"] if f["feature"]["name"] == flag)
        return json.loads(state["feature_state_value"])


class ReadOnlyClient:
    dashboard_url = ""

    def __init__(self, base: str, server_key: str) -> None:
        if not base.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise AdminError("unsupported Flagsmith URL")
        self._call = http_request(base.rstrip("/"), {"server": server_key})

    @classmethod
    def from_env(cls) -> "ReadOnlyClient":
        try:
            return cls(os.environ["FLAGSMITH_API_URL"], os.environ["FLAGSMITH_ENV_SERVER_KEY"])
        except KeyError as error:
            raise AdminError(f"missing environment variable {error.args[0]}") from error

    def document(self) -> dict[str, Any]:
        status, payload = self._call("GET", "/environment-document/", None, "server")
        if status != 200:
            raise AdminError(f"Flagsmith returned {status} for the environment document")
        return payload
