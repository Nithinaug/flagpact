import hashlib
import json
import os
import pathlib
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any

import semver

from .admin import AdminClient, AdminError
from .contracts import load_contracts
from .fix import Applied, Plan, PlanError, apply_plan, move_boundary, plan_fix, publish, rollback
from .matrix import AppVersion, Cell, build_matrix
from .rehearsal import Clone
from .replay import render
from .resolver import patch_default, resolve, with_fix, without_fixes
from .risks import notices as flag_notices
from .risks import partial
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
        self.outside_edit = config.get("outside_edit")
        self._state_file = pathlib.Path(os.environ.get("FLAGPACT_STATE_FILE") or root / ".flagpact-state.json")
        self._last_safe: dict[str, Any] | None = self._load_last_safe()
        self._watch_cache: tuple[str, dict[str, Any]] | None = None
        self._watch_lock = threading.Lock()
        self.applied: Applied | None = None
        self._planned: dict[str, Plan] = {}
        self.clone_factory = lambda: Clone.create(self.admin)

    def _load_last_safe(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self._state_file.read_text())
        except (OSError, ValueError):
            return None
        value = data.get(self.flag) if isinstance(data, dict) else None
        return value if isinstance(value, dict) else None

    def _remember_safe(self, value: dict[str, Any]) -> None:
        self._last_safe = value
        try:
            data = json.loads(self._state_file.read_text())
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        data[self.flag] = value
        try:
            self._state_file.write_text(json.dumps(data, indent=2) + "\n")
        except OSError:
            return

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
        if partial(document, self.flag):
            for row in rows:
                if row["state"] == GREEN:
                    row["state"] = AMBER
                    row["reason"] = "partly checked: this flag has a split or variations"
        if self.missing:
            rows.append(asdict(self._missing_cell(document, protected)))
        return rows

    def _risk(self, cells: list[Cell]) -> float:
        return sum(self._share(c.version) for c in cells if c.state == RED)

    def _recover(self) -> None:
        if self.applied is not None or not hasattr(self.admin, "feature_segments"):
            return
        try:
            prefix = f"flagpact/{self.flag}/"
            payload = self.admin._ok("GET", f"/projects/{self.admin.project_id}/segments/?q={prefix}")
            found = [s for s in self.admin._items(payload) if s["name"].startswith(prefix)]
            if not found:
                return
            segment = found[0]
            env_id = self.admin.environment_id()
            feature_id = self.admin.feature_id(self.flag)
            fsegs = [f for f in self.admin.feature_segments(env_id, feature_id) if f["segment"] == segment["id"]]
            if not fsegs:
                return
            default = self.admin.default_state(feature_id)
            document = self.admin.document()
            in_document = next(s for s in document["project"]["segments"] if s["name"] == segment["name"])
            override = next(f for f in in_document["feature_states"] if f["feature"]["name"] == self.flag)
            raw = override["feature_state_value"]
            old = raw if isinstance(raw, str) else json.dumps(raw)
            published = json.loads(default["feature_state_value"]) != json.loads(old)
            boundary = self._boundary(in_document)
            self.applied = Applied(self.flag, old, default["id"], fsegs[0]["id"], segment["id"], True, published, ["recovered"], boundary)
        except (AdminError, KeyError, IndexError, ValueError, StopIteration):
            return

    @staticmethod
    def _boundary(segment: dict[str, Any]) -> str:
        for rule in segment.get("rules", []):
            for inner in rule.get("rules", []):
                for condition in inner.get("conditions", []):
                    if condition.get("property_") == "app_version" and condition.get("operator") == "LESS_THAN":
                        return str(condition.get("value", "")).split(":")[0]
        return ""

    def state(self) -> dict[str, Any]:
        self._recover()
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
            "notices": flag_notices(document, self.flag),
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
            "notices": flag_notices(document, self.flag),
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
        self._recover()
        if self.applied is None:
            raise AdminError("nothing to roll back")
        steps = rollback(self.admin, self.applied)
        self.applied = None
        return {"steps": steps}

    def _stage_context(self, value: dict[str, Any], include_missing: bool, want: str = "all") -> tuple[Plan, dict[int, dict[str, Any]], int, int]:
        self._recover()
        stripped = without_fixes(self.admin.document(), self.flag)
        old = json.loads(self.applied.previous_default) if self.applied is not None else self._default(stripped)
        before = build_matrix(stripped, self.flag, value, self.versions, self.contracts)
        plan = plan_fix(self.flag, old, value, before, include_missing, staged=True)
        names = plan.boundaries()
        current = -1
        if self.applied is not None and self.applied.boundary in names:
            current = names.index(self.applied.boundary)
        wanted = {"all": set(range(len(names))), "next": {current + 1}, "back": {current - 1}}[want]
        stages: dict[int, dict[str, Any]] = {}
        for index, boundary in enumerate(names):
            if index not in wanted:
                continue
            fixed = with_fix(stripped, self.flag, plan.segment_name, boundary, old, value, include_missing)
            cells = build_matrix(fixed, self.flag, value, self.versions, self.contracts)
            on_new = [v.version for v in self.versions if semver.Version.parse(v.version) >= semver.Version.parse(boundary)]
            kept = [v.version for v in self.versions if v.version not in on_new]
            share = sum(self._share(v) for v in on_new) + (0 if include_missing else self._share(MISSING))
            blocked = [c.version for c in cells if c.state == RED]
            stages[index] = {
                "index": index,
                "boundary": boundary,
                "gets_change": on_new,
                "kept": kept,
                "share_new": share,
                "cells": self._with_missing(cells, fixed, include_missing),
                "ok": not blocked,
                "blocked": blocked,
                "holds_missing": bool(include_missing and self.missing),
            }
        return plan, stages, current, len(names)

    def stages(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        try:
            plan, stages, current, _ = self._stage_context(value, include_missing)
        except PlanError as error:
            return {"stages": [], "current": -1, "error": str(error)}
        return {
            "stages": [stages[i] for i in sorted(stages)],
            "current": current,
            "segment": plan.segment_name,
            "held": plan.broken,
            "published": self.applied is not None and self.applied.published,
        }

    def stage_next(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        self._recover()
        if self.applied is not None and not self.applied.published:
            raise AdminError("publish or undo the applied fix before staging a rollout")
        plan, stages, current, count = self._stage_context(value, include_missing, "next")
        if self.applied is not None and current == -1:
            raise AdminError("the applied fix does not match this rollout, undo it first")
        target = current + 1
        if target >= count:
            raise AdminError("every stage is already applied")
        stage = stages[target]
        if not stage["ok"]:
            raise AdminError(f"stage {target + 1} would break {', '.join(stage['blocked'])}, so it was not applied")
        if self.applied is None:
            applied = apply_plan(self.admin, plan, stage["boundary"])
            steps = list(applied.steps) + publish(self.admin, applied, value)
            self.applied = applied
        else:
            steps = move_boundary(self.admin, self.applied, plan, stage["boundary"])
        self._watch_cache = None
        return {"steps": steps, "stage": target, "done": target == count - 1}

    def stage_back(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        self._recover()
        if self.applied is None:
            raise AdminError("no stage is applied")
        plan, stages, current, _ = self._stage_context(value, include_missing, "back")
        if current <= 0:
            result = self.rollback()
            self._watch_cache = None
            return {**result, "stage": -1}
        steps = move_boundary(self.admin, self.applied, plan, stages[current - 1]["boundary"])
        self._watch_cache = None
        return {"steps": steps, "stage": current - 1}

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

    def rehearse(self, value: dict[str, Any], include_missing: bool = False) -> dict[str, Any]:
        if self.applied is not None:
            raise AdminError("undo the fix before rehearsing on a clone")
        key = json.dumps([value, include_missing], sort_keys=True)
        plan = self._planned.get(key)
        document = self.admin.document()
        if plan is None:
            cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
            plan = plan_fix(self.flag, self._default(document), value, cells, include_missing)
        started = time.time()
        clone = self.clone_factory()
        rows: list[dict[str, Any]] = []
        try:
            clone.apply(plan)
            clone.publish(value)
            targets: list[str | None] = [v.version for v in self.versions]
            if self.missing:
                targets.append(None)
            for version in targets:
                got = clone.probe(self.flag, version)
                if version is None:
                    held = include_missing
                else:
                    held = semver.Version.parse(version) < semver.Version.parse(plan.limit)
                expected = plan.old_value if held else value
                rows.append({
                    "version": version or MISSING,
                    "expects": "old" if held else "new",
                    "ok": got == expected,
                    "fields": sorted(got),
                })
        finally:
            clone.cleanup()
        return {"ok": all(r["ok"] for r in rows), "seconds": round(time.time() - started, 1), "rows": rows}

    def watch(self) -> dict[str, Any]:
        with self._watch_lock:
            return self._watch()

    def _watch(self) -> dict[str, Any]:
        document = self.admin.document()
        value = self._default(document)
        key = hashlib.sha1(json.dumps(document, sort_keys=True).encode()).hexdigest()
        if self._watch_cache is not None and self._watch_cache[0] == key:
            return {**self._watch_cache[1], "checked_at": time.time()}
        cells = build_matrix(document, self.flag, value, self.versions, self.contracts)
        broken = [c.version for c in cells if c.state == RED]
        ok = not broken
        if ok and value != self._last_safe:
            self._remember_safe(value)
        result = {
            "ok": ok,
            "value": value,
            "broken": broken,
            "cells": self._with_missing(cells, document, False),
            "at_risk": self._risk(cells),
            "restore": (not ok) and self._last_safe is not None and self._last_safe != value,
            "previous": None if ok else self._last_safe,
            "checked_at": time.time(),
        }
        self._watch_cache = (key, result)
        return result

    def _write_default(self, value: dict[str, Any]) -> None:
        feature_id = self.admin.feature_id(self.flag)
        state = self.admin.default_state(feature_id)
        self.admin.set_default(state["id"], json.dumps(value))
        self._watch_cache = None

    def restore(self) -> dict[str, Any]:
        document = self.admin.document()
        if self._last_safe is None or self._last_safe == self._default(document):
            raise AdminError("there is no earlier safe value to restore")
        self._write_default(self._last_safe)
        return {"value": self._last_safe}

    def simulate_outside_edit(self) -> dict[str, Any]:
        if not self.outside_edit:
            raise AdminError("no outside edit is configured")
        if self._last_safe is None:
            self.watch()
        self._write_default(self.outside_edit)
        return {"value": self.outside_edit}

    def protect(self, include_missing: bool = True) -> dict[str, Any]:
        if self.applied is not None:
            raise AdminError("a fix is already applied")
        result = self.watch()
        if result["ok"]:
            raise AdminError("the live value is safe, there is nothing to protect")
        previous = result["previous"]
        if previous is None:
            raise AdminError("there is no earlier safe value to keep older versions on")
        cells = [
            Cell(c["version"], c["state"], c["reason"], c["value"])
            for c in result["cells"]
            if c["version"] != MISSING
        ]
        plan = plan_fix(self.flag, previous, result["value"], cells, include_missing)
        applied = apply_plan(self.admin, plan)
        applied.previous_default = json.dumps(previous)
        applied.published = True
        self.applied = applied
        self._watch_cache = None
        return {"steps": applied.steps, "limit": plan.limit}
