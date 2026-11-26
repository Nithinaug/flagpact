from __future__ import annotations

import json
import os
from typing import Any

_MISSING = object()
PROBE_IDENTITY = "flagpact-probe"


def _type_name(value: Any) -> str:
    if value is _MISSING:
        return "missing"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


class Recorder:
    def __init__(self) -> None:
        self._reads: dict[tuple[str, str], dict[str, Any]] = {}

    def record(self, flag: str, path: str, has_default: bool, value: Any) -> None:
        entry = self._reads.setdefault(
            (flag, path),
            {"path": path, "has_default": False, "types": [], "observed_values": []},
        )
        entry["has_default"] = entry["has_default"] or has_default
        t = _type_name(value)
        if t not in entry["types"]:
            entry["types"].append(t)
        if value is not _MISSING and value not in entry["observed_values"]:
            entry["observed_values"].append(value)

    def reads_for(self, flag: str) -> list[dict[str, Any]]:
        out = []
        for (f, _), e in sorted(self._reads.items()):
            if f == flag:
                out.append({
                    "path": e["path"],
                    "has_default": e["has_default"],
                    "type": e["types"][0] if len(e["types"]) == 1 else "|".join(e["types"]),
                    "observed_values": e["observed_values"],
                })
        return out

    def flags(self) -> list[str]:
        return sorted({f for f, _ in self._reads})


class RecordedConfig:
    def __init__(self, flag: str, data: Any, recorder: Recorder, prefix: str = "") -> None:
        self._flag = flag
        self._data = data
        self._rec = recorder
        self._prefix = prefix

    def _resolve(self, path: str) -> Any:
        node = self._data
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return _MISSING
        return node

    def _read(self, path: str, default: Any, has_default: bool) -> Any:
        full = f"{self._prefix}{path}"
        value = self._resolve(path)
        if value is not _MISSING and isinstance(value, dict):
            return RecordedConfig(self._flag, value, self._rec, prefix=f"{full}.")
        self._rec.record(self._flag, full, has_default, value)
        if value is _MISSING:
            return default if has_default else _MISSING
        return value

    def get(self, path: str, default: Any = _MISSING) -> Any:
        has_default = default is not _MISSING
        value = self._read(path, default, has_default)
        if value is _MISSING:
            return None
        return value

    def __getitem__(self, path: str) -> Any:
        value = self._read(path, _MISSING, False)
        if value is _MISSING:
            raise KeyError(f"{self._flag}: missing '{self._prefix}{path}'")
        return value


DEFAULT_RECORDER = Recorder()


class FlagpactClient:
    def __init__(self, sdk: Any, app_version: str, recorder: Recorder | None = None) -> None:
        self._sdk = sdk
        self.app_version = app_version
        self.recorder = recorder or Recorder()

    @classmethod
    def from_env(cls) -> "FlagpactClient":
        from flagsmith import Flagsmith

        version = os.environ["FLAGPACT_APP_VERSION"]
        document = os.environ.get("FLAGPACT_DOCUMENT")
        if document:
            from flagsmith.offline_handlers import LocalFileHandler

            sdk = Flagsmith(offline_mode=True, offline_handler=LocalFileHandler(document))
        else:
            sdk = Flagsmith(
                environment_key=os.environ["FLAGSMITH_ENV_CLIENT_KEY"],
                api_url=os.environ["FLAGSMITH_API_URL"],
            )
        return cls(sdk, version, DEFAULT_RECORDER)

    def raw_value(self, flag: str) -> Any:
        flags = self._sdk.get_identity_flags(
            PROBE_IDENTITY, traits={"app_version": self.app_version}
        )
        return flags.get_feature_value(flag)

    def config(self, flag: str) -> RecordedConfig:
        raw = self.raw_value(flag)
        data = json.loads(raw) if isinstance(raw, str) else raw
        return RecordedConfig(flag, data, self.recorder)

    def contract(self, flag: str, recorded_from: str) -> dict[str, Any]:
        return {
            "flag": flag,
            "app_version": self.app_version,
            "recorded_from": recorded_from,
            "reads": self.recorder.reads_for(flag),
        }
