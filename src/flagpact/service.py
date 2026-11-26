import json
import pathlib
from dataclasses import asdict
from typing import Any

from .admin import AdminClient, AdminError
from .contracts import load_contracts
from .fix import Applied, PlanError, apply_plan, plan_fix, rollback
from .matrix import AppVersion, build_matrix
from .resolver import resolve


class Service:
    def __init__(self, admin: AdminClient, config_path: str) -> None:
        self.admin = admin
        root = pathlib.Path(config_path).resolve().parent
        config = json.loads(pathlib.Path(config_path).read_text())
        self.flag = config["flag"]
        self.contracts = str(root / config["contracts"])
        self.versions = [AppVersion(v["version"], str(root / v["directory"])) for v in config["versions"]]
        self.applied: Applied | None = None

    def _current(self, document: dict[str, Any]) -> dict[str, Any]:
        return resolve(document, self.flag, None)

    def state(self) -> dict[str, Any]:
        document = self.admin.document()
        return {
            "flag": self.flag,
            "value": self._current(document),
            "versions": [v.version for v in self.versions],
            "applied": self.applied is not None,
            "contracts": {c["app_version"]: c["reads"] for c in load_contracts(self.contracts, self.flag)},
        }

    def check(self, value: dict[str, Any], replay: bool = True) -> dict[str, Any]:
        document = self.admin.document()
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts, replay)
        return {"cells": [asdict(c) for c in cells]}

    def plan(self, value: dict[str, Any]) -> dict[str, Any]:
        document = self.admin.document()
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
        try:
            plan = plan_fix(self.flag, self._current(document), value, cells)
        except PlanError as error:
            return {"cells": [asdict(c) for c in cells], "error": str(error)}
        return {"cells": [asdict(c) for c in cells], "limit": plan.limit, "diff": plan.diff(), "segment": plan.segment_name}

    def apply(self, value: dict[str, Any]) -> dict[str, Any]:
        document = self.admin.document()
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
        plan = plan_fix(self.flag, self._current(document), value, cells)
        self.applied = apply_plan(self.admin, plan)
        after = build_matrix(self.admin.document(), self.flag, value, self.versions, self.contracts)
        return {"steps": self.applied.steps, "cells": [asdict(c) for c in after]}

    def rollback(self) -> dict[str, Any]:
        if self.applied is None:
            raise AdminError("nothing to roll back")
        steps = rollback(self.admin, self.applied)
        self.applied = None
        return {"steps": steps}
