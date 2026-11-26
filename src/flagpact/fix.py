import json
from dataclasses import dataclass, field
from typing import Any

import semver

from .admin import AdminClient, AdminError
from .matrix import Cell
from .verdict import RED


class PlanError(Exception):
    pass


@dataclass
class Plan:
    flag: str
    limit: str
    segment_name: str
    old_value: dict[str, Any]
    new_value: dict[str, Any]
    broken: list[str]
    include_missing: bool = False

    def diff(self) -> list[str]:
        scope = f"app_version < {self.limit}" + (" or app_version is not set" if self.include_missing else "")
        return [
            f"create or update segment '{self.segment_name}': {scope}",
            f"override for that segment keeps the previous value {json.dumps(self.old_value)}",
            "give that override the highest priority",
            f"then change the environment default to {json.dumps(self.new_value)}",
        ]


@dataclass
class Applied:
    flag: str
    previous_default: str
    state_id: int
    feature_segment_id: int
    segment_id: int
    created_segment: bool
    published: bool = False
    steps: list[str] = field(default_factory=list)


def plan_fix(flag: str, old_value: dict[str, Any], new_value: dict[str, Any], cells: list[Cell],
             include_missing: bool = False) -> Plan:
    broken = sorted((c.version for c in cells if c.state == RED), key=semver.Version.parse)
    working = sorted((c.version for c in cells if c.state != RED), key=semver.Version.parse)
    if not broken:
        raise PlanError("nothing is broken, no fix needed")
    if not working:
        raise PlanError("no version can read the new value, so there is nothing to keep as the default")
    if semver.Version.parse(broken[-1]) > semver.Version.parse(working[0]):
        raise PlanError("broken versions are not all older than the working ones, so the fix is manual")
    limit = working[0]
    return Plan(flag, limit, f"flagpact/{flag}/{limit}", old_value, new_value, broken, include_missing)


def apply_plan(admin: AdminClient, plan: Plan) -> Applied:
    env_id = admin.environment_id()
    feature_id = admin.feature_id(plan.flag)
    default = admin.default_state(feature_id)
    steps = []

    segment = admin.find_segment(plan.segment_name)
    created = segment is None
    body = admin.segment_body(plan.segment_name, plan.limit, plan.include_missing)
    if created:
        segment = admin._ok("POST", f"/projects/{admin.project_id}/segments/", body)
        steps.append("segment created")
    else:
        segment = admin._ok("PUT", f"/projects/{admin.project_id}/segments/{segment['id']}/", body)
        steps.append("segment updated")

    existing = [f for f in admin.feature_segments(env_id, feature_id) if f["segment"] == segment["id"]]
    override_value = {"type": "unicode", "string_value": json.dumps(plan.old_value)}
    if existing:
        fseg = existing[0]
        state = admin._ok("GET", f"/features/featurestates/?feature_segment={fseg['id']}")
        state_id = admin._items(state)[0]["id"]
        admin._ok("PATCH", f"/features/featurestates/{state_id}/", {"feature_state_value": override_value})
        steps.append("override updated")
    else:
        fseg = admin._ok("POST", "/features/feature-segments/", {
            "feature": feature_id, "segment": segment["id"], "environment": env_id, "priority": 0,
        })
        admin._ok("POST", "/features/featurestates/", {
            "feature": feature_id, "feature_segment": fseg["id"], "environment": env_id,
            "enabled": True, "feature_state_value": override_value,
        })
        steps.append("override created")

    others = [f["id"] for f in admin.feature_segments(env_id, feature_id)]
    admin.prioritise(fseg["id"], others)
    steps.append("override moved to highest priority")
    return Applied(plan.flag, default["feature_state_value"], default["id"], fseg["id"], segment["id"], created, False, steps)


def publish(admin: AdminClient, applied: Applied, new_value: dict[str, Any]) -> list[str]:
    admin.set_default(applied.state_id, json.dumps(new_value))
    applied.published = True
    return ["default changed"]


def rollback(admin: AdminClient, applied: Applied) -> list[str]:
    steps = []
    if applied.published:
        admin.set_default(applied.state_id, applied.previous_default)
        steps.append("default restored")
    if applied.created_segment:
        admin._ok("DELETE", f"/features/feature-segments/{applied.feature_segment_id}/")
        admin._ok("DELETE", f"/projects/{admin.project_id}/segments/{applied.segment_id}/")
        steps.append("segment and override removed")
    return steps
