import copy
import json
import uuid
from typing import Any

from flag_engine.engine import get_evaluation_result
from flagsmith.mappers import map_context_and_identity_data_to_context, map_environment_document_to_context

TRAIT = "app_version"


def patch_default(document: dict[str, Any], flag: str, value: dict[str, Any]) -> dict[str, Any]:
    patched = copy.deepcopy(document)
    for state in patched["feature_states"]:
        if state["feature"]["name"] == flag:
            state["feature_state_value"] = json.dumps(value)
            return patched
    raise KeyError(flag)


def resolve(document: dict[str, Any], flag: str, version: str | None) -> dict[str, Any]:
    context = map_environment_document_to_context(document)
    traits = None if version is None else {TRAIT: version}
    context = map_context_and_identity_data_to_context(context, "flagpact-probe", traits)
    raw = get_evaluation_result(context)["flags"][flag]["value"]
    return json.loads(raw) if isinstance(raw, str) else raw


def without_fixes(document: dict[str, Any], flag: str) -> dict[str, Any]:
    stripped = copy.deepcopy(document)
    prefix = f"flagpact/{flag}/"
    segments = stripped["project"]["segments"]
    segments[:] = [s for s in segments if not s["name"].startswith(prefix)]
    return stripped


def with_fix(document: dict[str, Any], flag: str, name: str, limit: str, old_value: dict[str, Any],
             new_value: dict[str, Any], include_missing: bool) -> dict[str, Any]:
    patched = patch_default(document, flag, new_value)
    feature = next(s["feature"] for s in patched["feature_states"] if s["feature"]["name"] == flag)
    conditions = [{"operator": "LESS_THAN", "value": f"{limit}:semver", "property_": TRAIT}]
    if include_missing:
        conditions.append({"operator": "IS_NOT_SET", "value": "", "property_": TRAIT})
    segments = patched["project"]["segments"]
    segments.append({
        "id": max([s["id"] for s in segments], default=0) + 1000,
        "name": name,
        "rules": [{"type": "ALL", "rules": [{"type": "ANY", "rules": [], "conditions": conditions}], "conditions": []}],
        "feature_states": [{
            "feature": feature,
            "enabled": True,
            "django_id": 999001,
            "feature_segment": {"priority": 0},
            "featurestate_uuid": str(uuid.uuid4()),
            "feature_state_value": json.dumps(old_value),
            "multivariate_feature_state_values": [],
        }],
    })
    return patched
