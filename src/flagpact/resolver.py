import copy
import json
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
