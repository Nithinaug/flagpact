from typing import Any


def segment_rules(limit: str, include_missing: bool = False) -> list[dict[str, Any]]:
    conditions = [{"operator": "LESS_THAN", "property": "app_version", "value": f"{limit}:semver"}]
    if include_missing:
        conditions.append({"operator": "IS_NOT_SET", "property": "app_version", "value": ""})
    return [{"type": "ALL", "rules": [{"type": "ANY", "rules": [], "conditions": conditions}], "conditions": []}]
