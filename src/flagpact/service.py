import json
import os
import pathlib
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any

from .admin import AdminClient, AdminError
from .contracts import load_contracts
from .fix import Applied, Plan, PlanError, apply_plan, plan_fix, publish, rollback
from .matrix import AppVersion, Cell, build_matrix
from .replay import render
from .resolver import patch_default, resolve, with_fix
from .verdict import AMBER, GREEN, RED

MISSING = "none"


class Service:
    def __init__(self, admin: AdminClient, config_path: str) -> None:
        self.admin = admin
        root = pathlib.Path(config_path).resolve().parent
        config = json.loads(pathlib.Path(config_path).read_text())
        self.flag = config["flag"]
        self.contracts = str(root / config["contracts"])
        self.versions = [AppVersion(v["version"], str(root / v["directory"])) for v in config["versions"]]
        self.meta = {
            v["version"]: {"share": v.get("share"), "users": v.get("users"), "platforms": v.get("platforms", "")}
            for v in config["versions"]
        }
        self.missing = config.get("missing_trait")
        self.applied: Applied | None = None
        self._planned: dict[str, Plan] = {}

    def _default(self, document: dict[str, Any]) -> dict[str, Any]:
        for state in document["feature_states"]:
            if state["feature"]["name"] == self.flag:
                return json.loads(state["feature_state_value"])
        raise KeyError(self.flag)

    def _share(self, version: str) -> float:
        if version == MISSING:
            return float((self.missing or {}).get("share") or 0)
        return float((self.meta.get(version) or {}).get("share") or 0)

    def _missing_cell(self, document: dict[str, Any], protected: bool) -> Cell:
        value = resolve(document, self.flag, None)
        if protected:
            return Cell(MISSING, GREEN, "keeps the live value", value)
        return Cell(MISSING, AMBER, "no recorded behaviour for builds without app_version", value)

    def _with_missing(self, cells: list[Cell], document: dict[str, Any], protected: bool) -> list[dict[str, Any]]:
        rows = [asdict(c) for c in cells]
        if self.missing:
            rows.append(asdict(self._missing_cell(document, protected)))
        return rows

    def _risk(self, cells: list[Cell]) -> float:
        return sum(self._share(c.version) for c in cells if c.state == RED)

    def state(self) -> dict[str, Any]:
        document = self.admin.document()
        latest = max(self.meta, key=lambda v: tuple(int(p) for p in v.split(".")))
        return {
            "flag": self.flag,
            "value": self._default(document),
            "versions": [v.version for v in self.versions],
            "meta": self.meta,
            "missing": self.missing,
            "latest": latest,
            "applied": self.applied is not None,
            "published": self.applied is not None and self.applied.published,
            "dashboard": getattr(self.admin, "dashboard_url", ""),
            "contracts": {c["app_version"]: c["reads"] for c in load_contracts(self.contracts, self.flag)},
        }

    def check(self, value: dict[str, Any], replay: bool = True) -> dict[str, Any]:
        document = self.admin.document()
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts, replay)
        patched = patch_default(document, self.flag, value)
        return {"cells": self._with_missing(cells, patched, False)}

    def plan(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        document = self.admin.document()
        before = build_matrix(document, self.flag, value, self.versions, self.contracts)
        patched = patch_default(document, self.flag, value)
        result: dict[str, Any] = {
            "cells": self._with_missing(before, patched, False),
            "at_risk": self._risk(before),
        }
        current = self._default(document)
        try:
            plan = plan_fix(self.flag, current, value, before, include_missing)
        except PlanError as error:
            result["error"] = str(error)
            return result
        fixed = with_fix(document, self.flag, plan.segment_name, plan.limit, current, value, include_missing)
        after = build_matrix(fixed, self.flag, value, self.versions, self.contracts)
        protected = 100.0 - self._risk(after)
        if self.missing and not include_missing:
            protected -= self._share(MISSING)
        self._planned = {json.dumps([value, include_missing], sort_keys=True): plan}
        result.update({
            "limit": plan.limit,
            "diff": plan.diff(),
            "segment": plan.segment_name,
            "include_missing": include_missing,
            "after": self._with_missing(after, fixed, include_missing),
            "protected": protected,
        })
        return result

    def apply(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        key = json.dumps([value, include_missing], sort_keys=True)
        plan = self._planned.pop(key, None)
        if plan is None:
            document = self.admin.document()
            cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
            plan = plan_fix(self.flag, self._default(document), value, cells, include_missing)
        self.applied = apply_plan(self.admin, plan)
        document = self.admin.document()
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
        patched = patch_default(document, self.flag, value)
        return {"steps": self.applied.steps, "cells": self._with_missing(cells, patched, include_missing)}

    def publish(self, value: dict[str, Any]) -> dict[str, Any]:
        if self.applied is None:
            raise AdminError("apply the fix first")
        steps = publish(self.admin, self.applied, value)
        return {"steps": steps}

    def rollback(self) -> dict[str, Any]:
        if self.applied is None:
            raise AdminError("nothing to roll back")
        steps = rollback(self.admin, self.applied)
        self.applied = None
        return {"steps": steps}

    def _render_all(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "document.json")
            with open(path, "w") as handle:
                json.dump(document, handle)
            with ThreadPoolExecutor(max_workers=len(self.versions) or 1) as pool:
                outputs = list(pool.map(lambda app: render(app.directory, path, app.version), self.versions))
        return [
            {"version": app.version, "ok": output.passed, "output": output.output}
            for app, output in zip(self.versions, outputs)
        ]

    def panes(self, value: dict[str, Any] | None) -> dict[str, Any]:
        document = self.admin.document()
        before = self._render_all(document)
        after = self._render_all(patch_default(document, self.flag, value)) if value is not None else None
        return {"before": before, "after": after}
